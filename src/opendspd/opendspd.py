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
        self.config['mod'] = {}
        # state attributes
        self.path_data = path_data
        self.updates_counter = 0
        # rt process 
        self.rt_proc = {}

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
        audio_config = self.config['system']['audio']
        # app requests different audio setup? merge setup
        if 'audio' in self.config['mod']:
            audio_config.update(self.config['mod']['audio'])
        self.jackd = JackdInterface(self, audio_config)
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

        # do we need to unload rcu and organize irq threads for full tickless kernel support?
        if 'cpu' in self.config['system']['system']:
            self.set_tickless(self.config['system']['system']['cpu'])

        # setup running state
        self.running = True

        # load mod
        self.load_mod(self.config['system']['mod']['name'])

        logging.info('OpenDSP up and running!')

        while self.running:
            # realtime and tickless support check
            self.rt_handle()
            # interface handlers
            self.midi.handle()
            # health check for audio, midi and video subsystem
            self.health_check()
            # check for update packages
            self.check_updates()
            # rest for a while....
            time.sleep(5)

        # not running any more? call stop to handle all running process
        self.stop()

    def load_config_mod(self, name):
        # load our module cfg file into memory
        del self.config['mod']
        self.config['mod'] = {}
        try:
            self.config['mod'] = configparser.ConfigParser()
            self.config['mod'].read("{path_data}/mod/{name_mod}/mod.cfg"
                                    .format(path_data=self.path_data,
                                            name_mod=name))
            return True
        except Exception as e:
            logging.exception("error loading mod {name} config: {message}".format(name=name, message=str(e)))
        return False

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

            # load module config
            if self.load_config_mod(name) is not True:
                return

            # any audio config changes?
            reload_subsystem = False
            current_audio_config = self.jackd.get_config()
            check_audio_config = self.config['system']['audio']
            # check against requested mod instead of main system default?
            if 'audio' in self.config['mod']:
                check_audio_config = self.config['mod']['audio']
            # find the intersection of current and check config
            change = current_audio_config.keys() & check_audio_config.keys()
            # any value requested that differs from current one?
            for c in change:
                if current_audio_config[c] != check_audio_config[c]:
                    reload_subsystem = True
            # update sysconfig mod name reference and save it back to config file
            self.config['system']['mod']['name'] = name
            # save system config updates
            self.save_system()
            if reload_subsystem:
                # force a restart opendsp system
                self.restart()
                return

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

    def save_system(self):
        system_file = "{}/system.cfg".format(self.path_data)
        with open(system_file, 'w') as sys_config:
            self.config["system"].write(sys_config)        

    def save_mod(self):
        mod_file = "{}/mod/{}/mod.cfg".format(self.path_data, self.config['system']['mod']['name'])
        with open(mod_file, 'w') as mod_config:
            self.config["mod"].write(mod_config)

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

            # fallback default configuration in case user miss something
            default = {
                'audio': { 'rate': '48000', 'period': '6', 'buffer': '256', 'hardware': 'hw:0,0' },
                'system': { 'cpu': '1', 'realtime': '91', 'display': 'native, virtual' },
                'mod': { 'name': 'blank' },
                'midi': { 'onboard-uart': 'no', 'device': '/dev/ttyAMA0', 'baudrate': '38400' },
                'osc': { 'port': '8000' }
            }
            # merge and update
            for c in self.config['system']:
                if c in default:
                    default[c].update(self.config['system'][c])
            for c in default:
                self.config['system'][c] = default[c]

            # load module config into self.config['mod']
            if self.load_config_mod(self.config['system']['mod']['name']) is not True:
                return

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
            # display without app request
            if 'display' in config['mod']:
                for display in config['mod']['display'].split(","):
                    display_mod.add(display.strip())

        # parse [system] global config 
        # display without app request
        if 'display' in self.config['system']['system']:
            for display in self.config['system']['system']['display'].split(","):
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

        # force all proc request into a specific display
        # overwrite the display option on mod.cfg
        if 'force_display' in self.config['system']['system']:
            if self.config['system']['system']['force_display'] is not None:
                env = self.config['system']['system']['force_display']

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

    def set_cpu(self, rt_process, cpu):
        """
        For tickless kernel suport:
        https://www.kernel.org/doc/Documentation/timers/NO_HZ.txt
        """
        rt_process = rt_process.replace('"', '')
        if rt_process not in self.rt_proc:
            self.rt_proc[rt_process] = {}
            self.rt_proc[rt_process]['list'] = [] 
        self.rt_proc[rt_process]['cpu'] = cpu

    def set_realtime(self, rt_process, inc=0):
        """
        For RT kernel suport:
        https://rt.wiki.kernel.org/index.php/Main_Page
        """
        rt_process = rt_process.replace('"', '')
        if rt_process not in self.rt_proc:
            self.rt_proc[rt_process] = {}
            self.rt_proc[rt_process]['list'] = [] 
        self.rt_proc[rt_process]['priority'] = int(self.config['system']['system']['realtime'])+inc

    def rt_handle(self):
        try:
            # read pgrep process and compare those ones already setup from the new ones...
            for proc in self.rt_proc:
                # pgrep to find all process and childs to setup realtime
                pid_list = subprocess.check_output(['pgrep', proc]).decode()
                for pid in pid_list.split('\n'):
                    if len(pid) > 0:
                        if pid not in self.rt_proc[proc]['list']:
                            if 'cpu' in self.rt_proc[proc]:
                                # set process cpu afinity
                                subprocess.call(['/sbin/sudo', '/sbin/taskset', '-a', '-p', '-c', str(self.rt_proc[proc]['cpu']), str(pid)], shell=False)
                            if 'priority' in self.rt_proc[proc]:
                                # priority
                                subprocess.call(['/sbin/sudo',
                                                '/sbin/chrt', '-a', '-f',
                                                '-p', str(self.rt_proc[proc]['priority']),
                                                str(pid)])
                            # add to list of handled pids
                            self.rt_proc[proc]['list'].append(pid)
        except Exception as e:
            logging.error("error handling rt schema: {message}"
                          .format(message=e))

    def restart(self):
        self.running = False
        subprocess.run(['/sbin/sudo', '/sbin/systemctl', 'restart', 'opendsp'])

    def set_tickless(self, cpus):
        # unload rcu from isolated cpus
        subprocess.run(['/usr/bin/bash', '-c', "for i in `pgrep rcu` ; do sudo taskset -apc 0 $i ; done"])
        # move irq threads to opendsp system cpu
        subprocess.run(['/usr/bin/bash', '-c', "for i in `pgrep irq` ; do sudo taskset -apc {} $i ; done".format(cpus)])

    def machine_setup(self):
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
        #, path_data, name_mod, app_name, path_project, name_project):
        data = []
        data.append("{path_data}\n"
                    .format(path_data=self.path_data))
        data.append("{}\n"
                    .format(self.config['system']['mod'].get('name', '')))
        if self.config['mod'] != None:
            if 'app1' in self.config['mod']:
                app_name = self.config['mod']['app1'].get('name', '')
                data.append("{name}\n"
                            .format(name=app_name))
                data.append("{project_path}\n"
                            .format(project_path=self.mod.path_project))
                data.append("{project}\n"
                            .format(project=self.config['mod']['app1'].get('project', '')))
                if app_name in self.config['ecosystem']:
                    data.append("{project_extension}\n"
                                .format(project_extension=self.config['ecosystem'][app_name].get('extension', '')))
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
                    self.restart()
        else:
            self.updates_counter += 1
