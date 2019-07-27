# -*- coding: utf-8 -*-

# OpenDSP Core Daemon
# Copyright (C) 2015-2019 Romulo Silva <contact@midilab.co>
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation; either version 2 of
# the License, or any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# For a full copy of the GNU General Public License see the doc/GPL.txt file.
# Common system tools
import os
import sys
import time
import datetime
import subprocess
import threading
import importlib
import glob
import signal
import psutil
import configparser
import logging

# Mod handler
from . import mod

# MIDI Support
from mididings import *

# Jack support
import jack

class Core():
    """OpenDSP main core

    Usage::

        >>> from opendspd import opendspd
        >>> opendsp = opendspd.Core('/home/opendsp/data')
        >>> opendsp.init()
        >>> opendsp.run()
        >>> opendsp.stop()
    """

    def __init__(self, path_data):
        # running Mod instance reference
        self.current_mod = None
        # running state
        self.running = False
        # default data path
        self.path_data = path_data
        self.updates_counter = 0
        # all mods and projects avaliable to load
        self.mods = []
        self.projects = []
        # manage the internal state of user midi input auto connections
        self.hid_devices = []
        self.opendsp_devices = []
        # connections state to handle
        self.connections = []
        self.connections_pending = []
        # all procs and threads references managed by opendsp
        self.proc = {}
        self.thread = {}
        # display management running state
        self.display = {}
        self.display['native'] = False
        self.display['virtual'] = False
        # configparser objects, system, ecosystem and mod
        self.config = {}
        self.config['system'] = configparser.ConfigParser()
        self.config['app'] = configparser.ConfigParser()
        self.config['mod'] = None

        # setup signal handling
        # by default, a SIGTERM is sent, followed by 90 seconds of waiting followed by a SIGKILL.
        signal.signal(signal.SIGTERM, self.signal_handler)
        # setup log environment
        logging.basicConfig(level=logging.DEBUG)
        logging.info('OpenDSP engine ready!')

    # catch SIGTERM and stop application
    def signal_handler(self, sig, frame):
        self.running = False

    def stop(self):
        try:
            # stop mod instance
            self.current_mod.stop()
            # all our threads are in daemon mode
            #... not need to stop then
            self.disconnect_port(self.connections)
            # stop all process
            for proc in self.proc:
                self.proc[proc].terminate()
            # delete our data tmp file
            os.remove('/var/tmp/opendsp-run-data')
        except Exception as e:
            logging.error("error stoping opendsp: {message}"
                          .format(message=e))

    def init(self):
        logging.info('OpenDSP initing...')
        # load user config files
        self.load_config()
        # start Audio engine
        self.start_audio()
        # start MIDI engine
        self.start_midi()
        logging.info('OpenDSP init completed!')

    def run(self):
        # script call for machine specific setup/tunning
        self.machine_setup()

        # read all avaliable mods names into memory
        self.mods = self.get_mods()

        # load mod
        self.load_mod(self.config['system']['mod']['name'])

        # start running state
        self.running = True
        while self.running:
            # user new input connections
            self.hid_lookup()
            # handling port connection state
            self.connection_handle()
            # health check for audio, midi and video subsystem
            self.health_check()
            # check for update packages
            self.check_updates()
            # rest for a while....
            time.sleep(5)

        # no running any more? call stop to handle all running process
        self.stop()

    def manage_display(self, config_mod):
        """Manage Display
        start and stop displays to match the config_mod requested only
        it help us save resources in case we dont need then
        """
        # find what display resources we need from config_mod
        display_mod = set()
        apps = {app: config_mod[app]
                for app in config_mod
                if 'app' in app}

        for app in apps:
            if 'display' in app:
                display_mod.add(app['display'].strip())

        # any mod display definition to handle from mod?
        if 'mod' in config_mod:
            # need to start display not used for other apps?
            if 'display' in config_mod['mod']:
                for display in self.config['mod']['display'].split(","):
                    display_mod.add(display.strip())

        # some one to stop?
        display_run = set([display
                           for display in self.display
                           if self.display[display] == True])
        stop_display = display_run - display_mod

        for display in self.display:
            if display in stop_display:
                self.stop_display(display)
            elif display in display_mod and display not in display_run:
                self.run_display(display)

    def load_mod(self, name):
        """Load a Mod
        get data from mod cfg
        delete and stop a running mod
        checks and handle display needs
        instantiate and start the mod
        """
        try:
            # read our cfg file into memory
            del self.config['mod']
            self.config['mod'] = configparser.ConfigParser()
            self.config['mod'].read("{path_data}/mod/{name_mod}.cfg"
                                    .format(path_data=self.path_data,
                                            name_mod=name))

            # stop and destroy mod instance in case
            if self.current_mod != None:
                self.current_mod.stop()
                del self.current_mod

            # inteligent display managment to save our beloved resources
            self.manage_display(self.config['mod'])

            # instantiate Mod object
            self.current_mod = mod.Mod(self.config['mod'],
                                       self.config['app'],
                                       self)

            # get mod application ecosystem up and running
            self.current_mod.start()

            # update our running data file
            self.update_run_data()
        except Exception as e:
            logging.error("error loading mod {name}: {message}"
                          .format(name=name, message=str(e)))

    def get_mods(self):
        return [os.path.basename(path_mod)[:-4]
                for path_mod in sorted(glob.glob("{path_data}/mod/*.cfg"
                                                 .format(path_data=self.path_data)))
                if os.path.basename(path_mod)[:-4] != 'app']

    def hid_lookup(self):
        """Hid Lookup
        take cares of user on the fly
        hid devices connections
        """
        jack_midi_lsp = [data.name
                         for data in self.jack.get_ports(is_midi=True, is_output=True)
                         if all(port.replace("\\", "") not in data.name
                                for port in self.opendsp_devices)]
        for midi_port in jack_midi_lsp:
            if midi_port in self.hid_devices:
                continue
            try:
                logging.info("opendsp hid device auto connect: {name_port} -> midiRT:in_1"
                             .format(name_port=midi_port))
                self.jack.connect(midi_port, 'midiRT:in_1')
                self.hid_devices.append(midi_port)
            except:
                pass

    def health_check(self):
        pass

    def connection_handle(self):
        """Connection Handle
        generic call to connect port pairs
        returns the non connected ports - still pending...
        """
        self.connections_pending = self.connect_port(self.connections_pending)

    def connect_port_add(self, origin, dest):
        """Connection Port Add
        create a new connection state to handle
        """
        connection = {'origin': origin, 'dest': dest}
        self.connections.append(connection)
        self.connections_pending.append(connection)

    def connect_port(self, connections_pending):
        connections_made = []
        for ports in connections_pending:
            # allow user to regex port expression on jack clients that randon their port names
            origin = [data.name for data in self.jack.get_ports(ports['origin'])]
            dest = [data.name for data in self.jack.get_ports(ports['dest'])]

            if len(origin) > 0 and len(dest) > 0:
                # port pair already connected? append it to connections_made
                jack_ports = [port.name
                              for port in self.jack.get_all_connections(dest[0])
                              if port.name == origin[0]]
                if len(jack_ports) > 0:
                    connections_made.append(ports)
                    continue

                try:
                    self.call("/usr/bin/jack_connect \"{port_origin}\" \"{port_dest}\""
                             .format(port_origin=origin[0], port_dest=dest[0]))
                    connections_made.append(ports)
                    logging.info("connect handler found: {port_origin} {port_dest}"
                                 .format(port_origin=origin[0], port_dest=dest[0]))
                except Exception as e:
                    logging.error("error on auto connection: {message}"
                                  .format(message=e))
            else:
                logging.info("connect handler looking for origin({port_origin}) and dest({port_dest})"
                             .format(port_origin=ports['origin'], port_dest=ports['dest']))
        # return connections made successfully
        return [ports for ports in connections_pending if ports not in connections_made]

    def disconnect_port(self, connections):
        for ports in connections:
            try:
                # allow user to regex port expression on jack clients that randon their port names
                origin = [data.name for data in self.jack.get_ports(ports['origin'])]
                dest = [data.name for data in self.jack.get_ports(ports['dest'])]
                if len(origin) > 0 and len(dest) > 0:
                    self.call("/usr/bin/jack_disconnect \"{port_origin}\" \"{port_dest}\""
                             .format(port_origin=origin[0], port_dest=dest[0]))
            except Exception as e:
                logging.error("error on reset disconnection: {message}"
                              .format(message=e))

    def save_config(self, config):
        pass

    def load_config(self):
        try:
            # read apps definitions
            self.config['app'].read("{path_data}/mod/app/ecosystem.cfg"
                                    .format(path_data=self.path_data))

            # loading general system config
            self.config['system'].read("{path_data}/system.cfg"
                                       .format(path_data=self.path_data))

            # audio setup
            # if system config file does not exist, load default values
            if 'audio' not in self.config['system']:
                # audio defaults
                self.config['system']['audio'] = {}
                self.config['system']['audio']['rate'] = '48000'
                self.config['system']['audio']['period'] = '8'
                self.config['system']['audio']['buffer'] = '256'
                self.config['system']['audio']['hardware'] = 'hw:0,0'
            if 'system' not in self.config['system']:
                self.config['system']['system'] = {}
                self.config['system']['system']['usage'] = '75'
                self.config['system']['system']['realtime'] = '95'
            if 'mod' not in self.config['system']:
                self.config['system']['mod'] = {}
                self.config['system']['mod']['name'] = "blank"
        except Exception as e:
            logging.error("error trying to load opendsp config file: {message}"
                          .format(message=e))

    def start_audio(self):
        # start jack server
        self.proc['jackd'] = subprocess.Popen(['/usr/bin/jackd',
                                               '-R', '-t10000', '-dalsa',
                                               '-d' + self.config['system']['audio']['hardware'],
                                               '-r' + self.config['system']['audio']['rate'],
                                               '-p' + self.config['system']['audio']['buffer'],
                                               '-n' + self.config['system']['audio']['period'],
                                               '-Xseq'])
        self.set_realtime(self.proc['jackd'].pid, 4)

        # start jack client
        self.jack = jack.Client('odsp_manager')
        self.jack.activate()

    def midi_queue(self, event):
        # PROGRAM messages
        if hasattr(event, 'program'):
            # load project, only for app1 if it is defined
            self.projects = self.current_mod.get_projects()
            if len(self.projects) > 0:
                index = (event.program-1) % len(self.projects)
                self.current_mod.load_project(self.projects[index])
            return
        # CTRL messages
        if hasattr(event, 'ctrl'):
            if event.ctrl == 120:
                self.mods = self.get_mods()
                if len(self.mods) > 0:
                    index = event.value % len(self.mods)
                    self.load_mod(self.mods[index])
                    return
            #if event.ctrl == 114:
            #    # restart opendspd
            #    subprocess.call('/sbin/sudo /usr/bin/systemctl restart opendsp', shell=True)
            #    return

    def midi_processor(self):
        # opendsp midi controlled via program changes and cc messages on channel 16
        run([PortFilter(1) >> Filter(PROGRAM|CTRL) >> Call(thread=self.midi_queue)])

    def start_midi(self):
        # start mididings and a thread for midi input user control and feedback listening
        config(backend='jack', client_name='OpenDSP', in_ports=1)
        self.thread['midi_processor'] = threading.Thread(target=self.midi_processor,
                                                         daemon=True,
                                                         args=())
        self.thread['midi_processor'].start()

        # call mididings and set it realtime alog with jack - named midi
        # from realtime standalone mididings processor get a port(16) and redirect to mididings python based
        rules = "ChannelSplit({ 1: Channel(1) >> Port(1), 2: Channel(1) >> Port(2), 3: Channel(1) >> Port(3), 4: Channel(1) >> Port(4), 5: Channel(1) >> Port(5), 6: Channel(1) >> Port(6), 7: Channel(1) >> Port(7), 8: Channel(1) >> Port(8), 9: Channel(1) >> Port(9), 10: Channel(1) >> Port(10), 11: Channel(1) >> Port(11), 12: Channel(1) >> Port(12), 13: Channel(1) >> Port(13), 14: Channel(1) >> Port(14), 15: Channel(1) >> Port(15), 16: Channel(1) >> Port(16) })"
        self.proc['mididings'] = subprocess.Popen(['/usr/bin/mididings',
                                                   '-R', '-c', 'midiRT', '-o', '16', rules])
        self.set_realtime(self.proc['mididings'].pid, 4)

        # channel 16 are mean to control opendsp interface
        self.connect_port_add('midiRT:out_16', 'OpenDSP:in_1')

        # start on-board midi? (only if your hardware has onboard serial uart)
        if 'midi' in self.config['system']:
            self.proc['board_midi'] = subprocess.Popen(['/usr/bin/ttymidi',
                                                        '-s', self.config['system']['midi']['device'],
                                                        '-b', self.config['system']['midi']['baudrate']])
            self.set_realtime(self.proc['board_midi'].pid, 4)
            # add to state
            self.connect_port_add('ttymidi:MIDI_in', 'midiRT:in_1')

        # local midi ports to avoid auto connect
        for app_name in self.config['app']:
            if 'midi_output' in self.config['app'][app_name]:
                connections = self.config['app'][app_name]['midi_output'].replace('"', '')
                self.opendsp_devices.extend([conn.strip() for conn in connections.split(",")])
        self.opendsp_devices.extend(['OpenDSP', 'alsa_midi:Midi Through Port-0', 'ttymidi'])

    def stop_display(self, display):
        if display == 'native':
            # stop native display service
            subprocess.run(['/sbin/sudo', '/sbin/systemctl', 'stop', 'display'])
            self.display['native'] = False

        if display == 'virtual':
            # stop virtual display service
            subprocess.run(['/sbin/sudo', '/sbin/systemctl', 'stop', 'vdisplay'])
            self.display['virtual'] = False

    def run_display(self, display='native', call=None):
        environment = os.environ.copy()
        # setup common SDL environment
        environment["SDL_AUDIODRIVER"] = "jack"
        environment["SDL_VIDEODRIVER"] = "x11"

        # virtual display init
        if self.display['virtual'] == False and display == 'virtual':
            environment["DISPLAY"] = ":1"
            # start virtual display service
            subprocess.run(['/sbin/sudo',
                            '/sbin/systemctl', 'start', 'vdisplay'], env=environment)
            # check if display is running before setup as...
            while "Xvfb" not in (p.name() for p in psutil.process_iter()):
                time.sleep(1)
            self.display['virtual'] = True

        # native display init
        if self.display['native'] == False and display == 'native':
            environment["DISPLAY"] = ":0"
            # start display service
            subprocess.run(['/sbin/sudo',
                            '/sbin/systemctl', 'start', 'display'], env=environment)
            while "Xorg" not in (p.name() for p in psutil.process_iter()):
                time.sleep(1)
            try:
                # avoid screen auto shutoff
                subprocess.run(['/usr/bin/xset', 's', 'off'], env=environment)
                subprocess.run(['/usr/bin/xset', '-dpms'], env=environment)
                subprocess.run(['/usr/bin/xset', 's', 'noblank'], env=environment)
            except:
                pass
            self.display['native'] = True

        if call == None:
            return None
        # start virtual display app
        return subprocess.Popen(call, env=environment)

    def run_background(self, call):
        environment = os.environ.copy()
        return subprocess.Popen(call, env=environment)

    def call(self, call, env=False):
        environment = os.environ.copy() if env == True else None
        subprocess.run(call, env=environment, shell=True, check=True)

    def set_limits(self, pid, limits):
        subprocess.call(['/sbin/sudo',
                         '/sbin/prlimit', '--pid', str(pid), limits])

    def set_realtime(self, pid, inc=0):
        # the idea is: use 25% of cpu for OS tasks and the rest for opendsp
        # nproc --all
        # self.config['system']['usage'])
        #num_proc = int(subprocess.check_output(['/bin/nproc', '--all']))
        #usable_procs = ""
        #for i in range(num_proc):
        #    if ((i+1)/num_proc) > 0.25:
        #        usable_procs = usable_procs + "," + str(i)
        #usable_procs = usable_procs[1:]
        # the first cpu's are the one allocated for main OS tasks, lets set afinity for other cpu's
        #subprocess.call(['/sbin/sudo', '/sbin/taskset', '-p', '-c', usable_procs, str(pid)], shell=False)
        subprocess.call(['/sbin/sudo',
                         '/sbin/chrt', '-a', '-f', '-p',
                         str(int(self.config['system']['system']['realtime'])+inc),
                         str(pid)])

    def machine_setup(self):
        # force rtirq to restart
        #subprocess.run(['/sbin/sudo', '/usr/bin/rtirq', 'restart'])
        # set main PCM to max gain volume
        subprocess.run(['/bin/amixer', 'sset', 'PCM,0', '100%'])

    def update_run_data(self):
        """updates /var/tmp/opendsp-run-data:
        opendsp_user_data_path
        mod_name
        mod_project_path
        mod_project
        mod_project_extension
        """
        #, path_data, name_mod, path_project, name_project):
        data = []
        data.append("{path_data}\n"
                    .format(path_data=self.path_data))
        if self.config['mod'] != None:
            if 'app1' in self.config['mod']:
                name_mod = self.config['mod']['app1'].get('name', '')
                data.append("{name}\n"
                            .format(name=name_mod))
                data.append("{project_path}\n"
                            .format(project_path=self.config['mod']['app1'].get('path', '')))
                data.append("{project}\n"
                            .format(project=self.config['mod']['app1'].get('project', '')))
                if name_mod in self.config['app']:
                    data.append("{project_extension}\n"
                                .format(project_extension=self.config['app'][name_mod].get('extension', '')))
        try:
            with open("/var/tmp/opendsp-run-data", "w+") as run_data:
                run_data.writelines(data)
        except Exception as e:
            logging.error("error trying to update run data: {message}"
                          .format(message=e))

    def mount_fs(self, fs, action):
        if 'write'in action:
            subprocess.run(['/sbin/sudo', '/bin/mount', '-o', 'remount,rw', fs])
        elif 'read' in action:
            subprocess.run(['/sbin/sudo', '/bin/mount', '-o', 'remount,ro', fs])

    def check_updates(self):
        """We check updates in 10 subcycles
        call to avoid disk reads overhead
        """
        if self.updates_counter == 10:
            self.updates_counter = 0
            update_pkgs = glob.glob("{path_data}/updates/*.pkg.tar.xz"
                                    .format(path_data=self.path_data))
            # any update package?
            for path_package in update_pkgs:
                # mount filesystem in rw mode
                self.mount_fs("/", "write")
                # install package
                subprocess.call(['/sbin/sudo',
                                 '/sbin/pacman',
                                 '--noconfirm',
                                 '-U',
                                 path_package])
                # any systemd changes?
                subprocess.call(['/sbin/sudo',
                                 '/sbin/systemctl',
                                 'daemon-reload',
                                 path_package])
                # mount filesystem in ro mode back again
                self.mount_fs("/", "read")
                # remove the package from /updates dir and leave user a note about the update
                subprocess.call(['/bin/rm', path_package])
                with open(self.path_data + '/updates/log.txt','a') as log_file:
                    log_file.write("{date}: package {package} updated successfully"
                                   .format(date=str(datetime.datetime.now()),
                                           package=path_package))
                if 'opendspd' in path_package:
                    # restart our self
                    subprocess.call(['/sbin/sudo',
                                     '/sbin/systemctl',
                                     'restart',
                                     'opendsp'])
        else:
            self.updates_counter += 1
