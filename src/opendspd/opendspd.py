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

# Data bank paths
USER_DATA = "/home/opendsp/data"

class Core():
    """OpenDSP main core

    Usage::

        >>> from opendspd import opendspd
        >>> opendsp = opendspd.Core()
        >>> opendsp.init()
        >>> opendsp.run()
        >>> opendsp.stop()
    """

    def __init__(self):
        # running Mod instance reference
        self.mod = None
        # all procs and threads references managed by opendsp
        self.proc = {}
        self.thread = {}
        # running state
        self.running = False
        # manage the internal state of user midi input auto connections
        self.midi_devices = []
        self.midi_port_in = []
        self.local_midi_out_ports = []
        # display management running state
        self.display_native_on = False
        self.display_virtual_on = False
        # default data path
        self.path_data = USER_DATA
        # all mods and projects avaliable to load
        self.avaliable_mods = []
        self.avaliable_projects = []
        # connections state to handle
        self.connections = []
        self.connections_pending = []
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
        logging.info('OpenDSP init completed!')

    # catch SIGTERM and stop application
    def signal_handler(self, sig, frame):
        self.running = False

    def stop(self):
        try:
            # stop mod instance
            self.mod.stop()
            # all our threads are in daemon mode
            #... not need to stop then
            self.disconnect_port(self.connections)
            # stop all process
            for proc in self.proc:
                self.proc[proc].terminate()
            # check for display
            #if self.display_native_on:
                # stop display service
            #    subprocess.run('/sbin/sudo /sbin/systemctl stop display', shell=True)
            # check for virtual display
            #if self.display_virtual_on:
                # stop virtual display service
            #    subprocess.run('/sbin/sudo /sbin/systemctl stop vdisplay', shell=True)
            # delete our data tmp file
            os.remove('/var/tmp/opendsp-run-data')
        except Exception as e:
            logging.error("error while trying to stop opendsp: {message}"
                          .format(message=e))

    def init(self):
        # load user config files
        self.load_config()
        # start Audio engine
        self.start_audio()
        # start MIDI engine
        self.start_midi()

    def run(self):
        # machine actions before running
        #.. call a user generated script inside user's home folder
        # force rtirq to restart
        #subprocess.run('/sbin/sudo /usr/bin/rtirq restart', shell=True)
        # set main PCM to max gain volume
        subprocess.run('/bin/amixer sset PCM,0 100%', shell=True)

        # read all avaliable mods names into memory
        # we sort glob here to make use of user numbered mods
        # usefull for MIDI requests
        self.avaliable_mods = self.get_mods()

        # load mod
        self.load_mod(self.config['system']['mod']['name'])
        # turn display and virtual display on for user interaction
        self.display()
        self.display_virtual()

        check_updates_counter = 0
        self.running = True
        while self.running:
            # user new input connections
            self.process_midi()
            # generic call to connect port pairs, returns the non connected ports - still pending...
            self.connections_pending = self.connect_port(self.connections_pending)
            # health check for audio, midi and video subsystem
            #...
            # check for update packages
            if check_updates_counter == 10:
                self.check_updates()
                check_updates_counter = 0
            check_updates_counter += 1
            # rest for a while....
            time.sleep(6)

        # no running any more? call stop to handle all running process
        self.stop()

    def load_mod(self, name):
        # load initial mod config
        try:
            # read our cfg file into memory
            del self.config['mod']
            self.config['mod'] = configparser.ConfigParser()
            self.config['mod'].read("{path_data}/mod/{name_mod}.cfg"
                                    .format(path_data=self.path_data, name_mod=name))
            # stop and destroy mod instance in case
            if self.mod != None:
                self.mod.stop()
                del self.mod
            # instantiate Mod object
            self.mod = mod.Mod(self.config['mod'], self.config['app'], self)
            # get mod application ecosystem up and running
            self.mod.start()
            # load all avaliable projets names into memory
            self.avaliable_projects = self.mod.get_projects()
            # update our running data file
            self.update_run_data()
        except Exception as e:
            logging.error("error trying to load mod {name_mod}: {message_error}"
                          .format(name_mod=name, message_error=str(e)))

    def get_mods(self):
        return [os.path.basename(path_mod)[:-4]
                for path_mod in sorted(glob.glob("{path_data}/mod/*.cfg"
                                                 .format(path_data=self.path_data)))
                if os.path.basename(path_mod)[:-4] != 'app']

    def process_midi(self):
        # take cares of user on the fly hid devices connections
        jack_midi_lsp = [data.name
                         for data in self.jack.get_ports(is_midi=True, is_output=True)
                         if all(port.replace("\\", "") not in data.name
                                for port in self.local_midi_out_ports)]
        for midi_port in jack_midi_lsp:
            if midi_port in self.midi_port_in:
                continue
            try:
                logging.info("opendsp hid device auto connect: {name_port} -> midiRT:in_1"
                             .format(name_port=midi_port))
                self.jack.connect(midi_port, 'midiRT:in_1')
                self.midi_port_in.append(midi_port)
            except:
                pass

    def connect_port_add(self, origin, dest):
        # create a new connection state to handle
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
                jack_ports = [port.name
                              for port in self.jack.get_all_connections(dest[0])
                              if port.name == origin[0]]

                if len(jack_ports) > 0:
                    connections_made.append(ports)
                    continue

                try:
                    self.cmd("/usr/bin/jack_connect \"{port_origin}\" \"{port_dest}\""
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
                    self.cmd("/usr/bin/jack_disconnect \"{port_origin}\" \"{port_dest}\""
                             .format(port_origin=origin[0], port_dest=dest[0]))
            except Exception as e:
                logging.error("error on reset disconnection: {message}"
                              .format(message=e))

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
                                               '-R',
                                               '-t10000',
                                               '-dalsa',
                                               '-d' + self.config['system']['audio']['hardware'],
                                               '-r' + self.config['system']['audio']['rate'],
                                               '-p' + self.config['system']['audio']['buffer'],
                                               '-n' + self.config['system']['audio']['period'],
                                               '-Xseq']) #, bufsize=1) #, '-z' + self.config['system']['audio']['dither']])
        self.set_realtime(self.proc['jackd'].pid, 4)

        # start jack client
        self.jack = jack.Client('odsp_manager')
        self.jack.activate()

    def midi_processor_queue(self, event):
        # PROGRAM messages
        if hasattr(event, 'program'):
            # load project, only for app1 if it is defined
            self.avaliable_projects = self.mod.get_projects()
            if len(self.avaliable_projects) > 0:
                index = (event.program-1) % len(self.avaliable_projects)
                self.mod.load_project(self.avaliable_projects[index])
            return
        # CTRL messages
        if hasattr(event, 'ctrl'):
            if event.ctrl == 120:
                self.avaliable_mods = self.get_mods()
                if len(self.avaliable_mods) > 0:
                    index = event.value % len(self.avaliable_mods)
                    self.load_mod(self.avaliable_mods[index])
                    return
            #if event.ctrl == 114:
            #    # restart opendspd
            #    subprocess.call('/sbin/sudo /usr/bin/systemctl restart opendsp', shell=True)
            #    return

    def midi_processor(self):
        # opendsp midi controlled via program changes and cc messages on channel 16
        run( [ PortFilter(1) >> Filter(PROGRAM|CTRL) >> Call(thread=self.midi_processor_queue) ] )

    def start_midi(self):
        # start mididings and a thread for midi input user control and feedback listening
        config(backend='jack', client_name='OpenDSP', in_ports=1)
        self.thread['midi_processor'] = threading.Thread(target=self.midi_processor, args=(), daemon=True)
        self.thread['midi_processor'].start()

        # call mididings and set it realtime alog with jack - named midi
        # from realtime standalone mididings processor get a port(16) and redirect to mididings python based
        rules = "ChannelSplit({ 1: Channel(1) >> Port(1), 2: Channel(1) >> Port(2), 3: Channel(1) >> Port(3), 4: Channel(1) >> Port(4), 5: Channel(1) >> Port(5), 6: Channel(1) >> Port(6), 7: Channel(1) >> Port(7), 8: Channel(1) >> Port(8), 9: Channel(1) >> Port(9), 10: Channel(1) >> Port(10), 11: Channel(1) >> Port(11), 12: Channel(1) >> Port(12), 13: Channel(1) >> Port(13), 14: Channel(1) >> Port(14), 15: Channel(1) >> Port(15), 16: Channel(1) >> Port(16) })"
        self.proc['mididings'] = subprocess.Popen(['/usr/bin/mididings',
                                                   '-R',
                                                   '-c',
                                                   'midiRT',
                                                   '-o',
                                                   '16',
                                                   rules])
        self.set_realtime(self.proc['mididings'].pid, 4)

        # channel 16 are mean to control opendsp interface
        self.connect_port_add('midiRT:out_16', 'OpenDSP:in_1')

        # start on-board midi? (only if your hardware has onboard serial uart)
        if 'midi' in self.config['system']:
            self.proc['on_board_midi'] = subprocess.Popen(['/usr/bin/ttymidi',
                                                           '-s', self.config['system']['midi']['device'],
                                                           '-b', self.config['system']['midi']['baudrate']])
            self.set_realtime(self.proc['on_board_midi'].pid, 4)
            # add to state
            self.connect_port_add('ttymidi:MIDI_in', 'midiRT:in_1')

        # local midi ports to avoid auto connect
        for app_name in self.config['app']:
            if 'midi_output' in self.config['app'][app_name]:
                connections = self.config['app'][app_name]['midi_output'].replace('"', '')
                self.local_midi_out_ports.extend([conn.strip() for conn in connections.split(",")])
        self.local_midi_out_ports.extend(['OpenDSP', 'alsa_midi:Midi Through Port-0', 'ttymidi'])

    def display(self, call=None):
        environment = os.environ.copy()
        environment["DISPLAY"] = ":0"
        environment["SDL_AUDIODRIVER"] = "jack"
        environment["SDL_VIDEODRIVER"] = "x11"
        # check for display on
        if self.display_native_on == False:
            # start display service
            subprocess.run('/sbin/sudo /sbin/systemctl start display', env=environment, shell=True)
            while "Xorg" not in (p.name() for p in psutil.process_iter()):
                time.sleep(1)
            try:
                # avoid screen auto shutoff
                subprocess.run('/usr/bin/xset s off', env=environment, shell=True)
                subprocess.run('/usr/bin/xset -dpms', env=environment, shell=True)
                subprocess.run('/usr/bin/xset s noblank', env=environment, shell=True)
            except:
                pass
            self.display_native_on = True

        if call == None:
            return None
        # start main display app
        return subprocess.Popen(call, env=environment) #, bufsize=1)

    def display_virtual(self, call=None):
        environment = os.environ.copy()
        environment["DISPLAY"] = ":1"
        environment["SDL_AUDIODRIVER"] = "jack"
        environment["SDL_VIDEODRIVER"] = "x11"
        # check for display on
        if self.display_virtual_on == False:
            # start virtual display service
            subprocess.run('/sbin/sudo /sbin/systemctl start vdisplay', env=environment, shell=True)
            # check if display is running before setup as...
            while "Xvfb" not in (p.name() for p in psutil.process_iter()):
                time.sleep(1)
            self.display_virtual_on = True

        if call == None:
            return None
        # start virtual display app
        return subprocess.Popen(call, env=environment) #, bufsize=1)

    def background(self, call):
        environment = os.environ.copy()
        return subprocess.Popen(call, env=environment) #, bufsize=1)

    def cmd(self, call, env=False):
        environment = os.environ.copy() if env == True else None
        subprocess.run(call, env=environment, shell=True, check=True)

    def set_limits(self, pid, limits):
        subprocess.call(['/sbin/sudo',
                         '/sbin/prlimit',
                         '--pid', str(pid),
                         limits])

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
                         '/sbin/chrt',
                         '-a',
                         '-f',
                         '-p',
                         str(int(self.config['system']['system']['realtime'])+inc),
                         str(pid)], shell=False)

    def update_run_data(self):
        """
        /var/tmp/opendsp-run-data
        opendsp_user_data_path
        mod_name
        mod_project_path
        mod_project
        mod_project_extension
        """
        #, path_data, name_mod, path_project, name_project):
        data = []
        data.append("{}\n"
                    .format(self.path_data))
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
            subprocess.run("/sbin/sudo /bin/mount -o remount,rw {file_system}"
                           .format(file_system=fs), shell=True)
        elif 'read' in action:
            subprocess.run("/sbin/sudo /bin/mount -o remount,ro {file_system}"
                           .format(file_system=fs), shell=True)

    def check_updates(self):
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
                             path_package], shell=False)
            # any systemd changes?
            subprocess.call(['/sbin/sudo',
                             '/sbin/systemctl',
                             'daemon-reload',
                             path_package], shell=False)
            # mount filesystem in ro mode back again
            self.mount_fs("/", "read")
            # remove the package from /updates dir and leave user a note about the update
            subprocess.call(['/bin/rm', path_package], shell=False)
            with open(self.path_data + '/updates/log.txt','a') as log_file:
                log_file.write(str(datetime.datetime.now()) + ': package ' + path_package + ' updated successfully')
            if 'opendspd' in path_package:
                # restart our self
                subprocess.call(['/sbin/sudo',
                                 '/sbin/systemctl',
                                 'restart',
                                 'opendsp'], shell=False)
