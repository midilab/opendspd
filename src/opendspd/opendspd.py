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
import time
import datetime
import subprocess
import glob
import signal
import psutil
import configparser
import logging

# Mod handler
from . import mod
# Interfaces pack(jackd, osc, midi, display)
from .interface.jackd import JackdInterface
from .interface.osc import OscInterface
from .interface.midi import MidiInterface
from .interface.display import DisplayInterface

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
        # interfaces instance references
        self.jackd = None
        self.osc = None
        self.midi = None
        # running Mod instance reference
        self.mod = None
        # running state
        self.running = False
        # display management running state
        self.display = {}
        self.display['native'] = False
        self.display['virtual'] = False
        # configparser objects, system, ecosystem and mod
        self.config = {}
        self.config['system'] = configparser.ConfigParser()
        self.config['ecosystem'] = configparser.ConfigParser()
        self.config['mod'] = None
        # state attributes
        self.path_data = path_data
        self.updates_counter = 0

        # setup signal handling
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
            self.mod.stop()
            # stoping interfaces
            self.midi.stop()
            self.osc.stop()
            self.jackd.stop()
            # auto save config?
            #...
            # delete our data tmp file
            os.remove('/var/tmp/opendsp-run-data')
        except Exception as e:
            logging.error("error stoping opendsp: {message}"
                          .format(message=e))

    def init(self):
        """Init
        reads config files and initing all interfaces
        """
        logging.info('Initing Core')

        # config
        logging.info('Loading config files')
        self.load_config()

        # interfaces
        logging.info('Initing Jackd Interface')
        self.jackd = JackdInterface(self)
        self.jackd.start()
                
        logging.info('Initing OSC Interface')
        self.osc = OscInterface(self)
        self.osc.start()

        logging.info('Initing MIDI Interface')
        self.midi = MidiInterface(self)
        self.midi.start()

        logging.info('OpenDSP init completed!')

    def run(self):
        # script call for machine specific setup/tunning
        self.machine_setup()

        # load mod
        self.load_mod(self.config['system']['mod']['name'])

        # start running state
        self.running = True

        logging.info('OpenDSP up and running!')

        while self.running:
            # interface handlers
            self.midi.handle()
            # handling port connection state
            #self.jackd.handle()
            # health check for audio, midi and video subsystem
            self.health_check()
            # check for update packages
            self.check_updates()
            # rest for a while....
            time.sleep(5)

        # no running any more? call stop to handle all running process
        self.stop()

    def load_mod(self, name):
        """Load a Mod
        get data from mod cfg
        delete and stop a running mod
        checks and handle display needs
        instantiate and start the mod
        """
        try:
            # stop and destroy mod instance in case
            if self.mod != None:
                self.mod.stop()
                del self.mod

            # read our cfg file into memory
            del self.config['mod']
            self.config['mod'] = configparser.ConfigParser()
            self.config['mod'].read("{path_data}/mod/{name_mod}/mod.cfg"
                                    .format(path_data=self.path_data,
                                            name_mod=name))

            # inteligent display managment to save our beloved resources
            self.manage_display(self.config['mod'])

            # instantiate Mod object
            self.mod = mod.Mod(name, self.config['mod'], self.config['ecosystem'], self)

            # get mod application ecosystem up and running
            self.mod.start()

            # update our running data file
            self.update_run_data()
        except Exception as e:
            logging.exception("error loading mod {name}: {message}"
                              .format(name=name, message=str(e)))

    def health_check(self):
        pass

    def save_config(self, config):
        pass

    def load_config(self):
        try:
            # read apps definitions
            self.config['ecosystem'].read("{path_data}/mod/ecosystem.cfg"
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
                self.config['system']['system']['cpu'] = '0'
                self.config['system']['system']['realtime'] = '40'
            if 'mod' not in self.config['system']:
                self.config['system']['mod'] = {}
                self.config['system']['mod']['name'] = "blank"
            if 'osc' not in self.config['system']:
                self.config['system']['osc'] = {}
                self.config['system']['osc']['port'] = '8000'
        except Exception as e:
            logging.error("error trying to load opendsp config file: {message}"
                          .format(message=e))

    def manage_display(self, config):
        """Manage Display
        start and stop displays to match the config requested only
        it help us save resources in case we dont need then
        """
        # find what display resources we need from config
        display_mod = set()

        # parse [appX] config nodes
        apps = {app: config[app]
                for app in config
                if 'app' in app}
        for app in apps:
            if 'display' in apps[app]:
                display_mod.add(apps[app]['display'].strip())

        # parse [mod] config node
        if 'mod' in config:
            # display requests without app
            if 'display' in config['mod']:
                for display in config['mod']['display'].split(","):
                    display_mod.add(display.strip())

        # some one to stop?
        display_run = set([display
                           for display in self.display
                           if self.display[display] == True])
        display_stop = display_run - display_mod
        for display in self.display:
            if display in display_stop:
                self.stop_display(display)
            elif display in display_mod and display not in display_run:
                self.start_display(display)

    def stop_display(self, display='native'):
        if display == 'native':
            # stop native display service
            subprocess.run(['/sbin/sudo',
                            '/sbin/systemctl', 'stop', 'display'])
            self.display['native'] = False

        if display == 'virtual':
            # stop virtual display service
            subprocess.run(['/sbin/sudo',
                            '/sbin/systemctl', 'stop', 'vdisplay'])
            self.display['virtual'] = False

    def start_display(self, display='native'):
        # native display init
        if display == 'native':
            subprocess.run(['/sbin/sudo',
                            '/sbin/systemctl', 'start', 'display'])
            # wait display to get up...
            while "Xorg" not in (p.name() for p in psutil.process_iter()):
                time.sleep(1)
            try:
                # avoid screen auto shutoff
                subprocess.run(['/usr/bin/xset', 's', 'off'])
                subprocess.run(['/usr/bin/xset', '-dpms'])
                subprocess.run(['/usr/bin/xset', 's', 'noblank'])
            except:
                pass
            self.display['native'] = True

        # virtual display init
        if display == 'virtual':
            subprocess.run(['/sbin/sudo',
                            '/sbin/systemctl', 'start', 'vdisplay'])
            # wait virtual display to get up...
            while "Xvfb" not in (p.name() for p in psutil.process_iter()):
                time.sleep(1)
            self.display['virtual'] = True

    def start_proc(self, call, env=None):
        # yes we need environment vars!
        environment = os.environ.copy()

        if env is not None:
            # setup common SDL environment
            environment["SDL_AUDIODRIVER"] = "jack"
            environment["SDL_VIDEODRIVER"] = "x11"

        # native display run env request?
        if env == 'native':
            environment["DISPLAY"] = ":0"
            # start display service?
            if self.display['native'] == False:
                self.start_display('native')

        # virtual display run env request?
        if env == 'virtual':
            environment["DISPLAY"] = ":1"
            # start virtual display service?
            if self.display['virtual'] == False:
                self.start_display('virtual')

        # starting proc
        logging.info("starting proccess on env: {env} via cmd: {call}".format(env=env,
                                                                              call=" ".join(call)))
        return subprocess.Popen(call, env=environment, preexec_fn=os.setsid)

    def stop_proc(self, proc):
        os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        proc.terminate()

    def call(self, call, env=False):
        environment = os.environ.copy() if env == True else None
        subprocess.run(call, env=environment, shell=True, check=True)

    def set_limits(self, pid, limits):
        subprocess.call(['/sbin/sudo',
                         '/sbin/prlimit', '--pid', str(pid), limits])

    def set_cpu(self, pid, cpu):
        # set process cpu afinity
        #subprocess.call(['/sbin/sudo', '/sbin/taskset', '-p', '-c', str(cpu), str(pid)], shell=False)
        pass

    def set_realtime(self, pid, inc=0):
        subprocess.call(['/sbin/sudo',
                         '/sbin/chrt', '-a', '-f',
                         '-p', str(int(self.config['system']['system']['realtime'])+inc),
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
                            .format(project_path=self.mod.path_project))
                data.append("{project}\n"
                            .format(project=self.config['mod']['app1'].get('project', '')))
                if name_mod in self.config['ecosystem']:
                    data.append("{project_extension}\n"
                                .format(project_extension=self.config['ecosystem'][name_mod].get('extension', '')))
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
