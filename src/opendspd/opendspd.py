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

# Mod handler
from . import mod

# MIDI Support
from mididings import *

# Jack support
import jack

# Data bank paths
USER_DATA = "/home/opendsp/data"

class Singleton(type):
    _instances = {}
    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]

class Core(metaclass=Singleton):
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
        # configparser objects
        self.config = {}
        # running state
        self.running = False
        # manage the internal state of user midi input auto connections 
        self.midi_port_in = []    
        self.app_midi_out_ports = []
        # display management running state
        self.display_native_on = False
        self.display_virtual_on = False
        # default data path
        self.path_data = USER_DATA
        # all mods and projects avaliable to load
        self.avaliable_mods = []
        self.avaliable_projects = []
        # setup our 2 main config files, the system user, mod and app list config
        self.config['system'] = configparser.ConfigParser()
        self.config['app'] = configparser.ConfigParser()
        self.config['mod'] = None 
        # setup signal handling
        # by default, a SIGTERM is sent, followed by 90 seconds of waiting followed by a SIGKILL.
        signal.signal(signal.SIGTERM, self.signal_handler)

    # catch SIGTERM and stop application
    def signal_handler(self, sig, frame):
        self.running = False

    def stop(self):    
        try:
            # stop mod instance   
            self.mod.stop()
            # all our threads are in daemon mode
            #... not need to stop then
            # stop all process
            for proc in self.proc:
                self.proc[proc].terminate()
            # check for display
            if self.display_native_on:
                # stop display service
                subprocess.run('/sbin/sudo /sbin/systemctl stop display', shell=True)
            # check for virtual display
            if self.display_virtual_on:
                # stop virtual display service
                subprocess.run('/sbin/sudo /sbin/systemctl stop vdisplay', shell=True) 
            # delete our data tmp file
            os.remove('/var/tmp/opendsp-run-data')  
        except Exception as e:
            print("error while trying to stop opendsp: {message}".format(e))

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

        # read all avaliable mods names into memory, we sort glob here to make use of user numbered mods - usefull for MIDI requests
        self.avaliable_mods = [ os.path.basename(path_mod)[:-4] for path_mod in sorted(glob.glob("{path_data}/mod/*.cfg".format(path_data=self.path_data))) if os.path.basename(path_mod)[:-4] != 'app' ]

        # load mod
        if 'mod' in self.config['system']:
            self.load_mod(self.config['system']['mod']['name'])
        else:
            # no mod setup? we turn display and virtual display on for user interaction
            self.display()
            self.display_virtual()
            # update our running data file
            self.update_run_data()

        # connect realtime output 16 to our internal mididings object processor(for midi host controlling)
        # TODO: handle all midi connections inside midi_process in a more inteligent way
        self.jack.connect('midiRT:out_16', 'OpenDSP:in_1')

        check_updates_counter = 0
        self.running = True
        while self.running:
            self.process_midi()
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
            self.config['mod'].read("{path_data}/mod/{name_mod}.cfg".format(path_data=self.path_data, name_mod=name))
            # stop and destroy mod instance in case
            if self.mod != None:
                self.mod.stop()
                del self.mod
            # instantiate Mod object
            self.mod = mod.Mod(self.config['mod'], self.config['app'])
            #self.app_midi_out_ports = self.mod.get_midi_out_ports()
            # get mod application ecosystem up and running
            self.mod.start()
            # load all avaliable projets names into memory
            self.avaliable_projects = self.mod.get_projects()
            # update our running data file
            self.update_run_data()
        except Exception as e:
            print("error trying to load mod {name_mod}: {message_error}".format(name_mod=name, message_error=str(e)))

    def process_midi(self):
        # to use integrated jackd a2jmidid please add -Xseq to jackd init param
        # getting jack ports and remove all the local ones
        # take cares of user on the fly devices connections
        jack_midi_lsp = [ data.name for data in self.jack.get_ports(is_midi=True, is_output=True) if all(port not in data.name for port in self.local_midi_out_ports) ]
        for midi_port in jack_midi_lsp:
            if midi_port in self.midi_port_in:           
                continue
            try:    
                print("opendsp hid device auto connect: {name_port} -> midiRT:in_1".format(name_port=midi_port))
                self.jack.connect(midi_port, 'midiRT:in_1')
                self.midi_port_in.append(midi_port)
            except:
                pass
        # new devices on raw midi layer?
        #for midi_device in glob.glob("/dev/midi*"):
        #    if midi_device in self.midi_devices:
        #        continue
        #    midi_device_proc = subprocess.Popen(['/usr/bin/jamrouter', '-M', 'generic', '-D', midi_device, '-o', 'midi:in_1'], shell=False) #, '-y', str(self.config['system']['system']['realtime']+4), '-Y', str(self.config['system']['system']['realtime']+4)], shell=True)
        #    self.set_realtime(midi_device_proc.pid, 4)  
        #    self.midi_devices.append(midi_device)
        #    self.midi_devices_procs.append(midi_device_proc)
        #time.sleep(5)

    def load_config(self):
        try:
            # read apps definitions
            self.config['app'].read("{path_data}/mod/app/ecosystem.cfg".format(path_data=self.path_data))

            # loading general system config
            self.config['system'].read("{path_data}/system.cfg".format(path_data=self.path_data))

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
            #if 'mod' not in self.config['system']:
            #    self.config['system']['mod'] = {}
            #    self.config['system']['mod']['name'] = "opendsp-factory"
        except Exception as e:
            print("error trying to load opendsp config file: {message}".format(e))

    def start_audio(self):
        # start jack server
        self.proc['jackd'] = subprocess.Popen(['/usr/bin/jackd', '-R', '-t10000', '-dalsa', '-d' + self.config['system']['audio']['hardware'], '-r' + self.config['system']['audio']['rate'], '-p' + self.config['system']['audio']['buffer'], '-n' + self.config['system']['audio']['period'], '-Xseq']) #, '-z' + self.config['system']['audio']['dither']])
        self.set_realtime(self.proc['jackd'].pid, 4)
        
        # start jack client
        self.jack = jack.Client('odsp_manager')
        self.jack.activate()
 
    def midi_processor_queue(self, event):
        # PROGRAM messages
        if hasattr(event, 'program'):
            # load project, only for app1 if it is defined
            if len(self.avaliable_projects) > 0:
                index = event.program % len(self.avaliable_projects)
                self.mod.load_project(self.avaliable_projects[index])
            return
        # CTRL messages
        if hasattr(event, 'ctrl'):
            if event.ctrl == 120:
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
        # add one more rule for our internal opendsp management
        # ChannelFilter(16) >> Port(16)
        rules = "ChannelSplit({ 1: Port(1), 2: Port(2), 3: Port(3), 4: Port(4), 5: Port(5), 6: Port(6), 7: Port(7), 8: Port(8), 9: Port(9), 10: Port(10), 11: Port(11), 12: Port(12), 13: Port(13), 14: Port(14), 15: Port(15), 16: Port(16) })"
        self.proc['mididings'] = subprocess.Popen(['/usr/bin/mididings', '-R', '-c', 'midiRT', '-o', '16', rules])
        self.set_realtime(self.proc['mididings'].pid, 4)

        # start on-board midi? (only if your hardware has onboard serial uart)
        if 'midi' in self.config['system']:
            self.proc['on_board_midi'] = subprocess.Popen(['/usr/bin/ttymidi', '-s', self.config['system']['midi']['device'], '-b', self.config['system']['midi']['baudrate']])
            self.set_realtime(self.proc['on_board_midi'].pid, 4)
            connected = False
            while connected == False:
                try:
                    self.jack.connect('ttymidi:MIDI_in', 'midiRT:in_1')
                    connected = True
                    print('ttymidi connected!')
                except:
                    # max times to try
                    print('waiting ttymidi to show up...')
                    time.sleep(1)
            # set our serial to 38400 to trick raspbery goes into 31200
            #subprocess.call(['/sbin/sudo', '/usr/bin/stty', '-F', str(self.config['system']['midi']['device']), '38400'], shell=True)            
            # problem: cant get jamrouter to work without start ttymidi first, setup else where beside the baudrate?
            #self.midi_onboard_proc = subprocess.Popen(['/usr/bin/jamrouter', '-M', 'generic', '-D', str(self.config['system']['midi']['device']), '-o', 'midi:in_1', '-y', str(REALTIME_PRIO+4), '-Y', str(REALTIME_PRIO+4)], shell=False)
            #self.set_realtime(self.midi_onboard_proc.pid, 4)        
        
        # start checkNewMidi Thread
        self.local_midi_out_ports = [ self.config['app'][app_name]['midi_output'] for app_name in self.config['app'] if 'midi_output' in self.config['app'][app_name] ]
        local_midi_ports = [ 'OpenDSP', 'midiRT', 'ttymidi', 'alsa_midi:Midi Through' ]
        self.local_midi_out_ports.extend(local_midi_ports)
        #self.thread['check_midi'] = threading.Thread(target=self.check_new_midi_input, args=(), daemon=True)
        #self.thread['check_midi'].start() 

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
        # start app
        # SDL_VIDEODRIVER=
        # SDL_AUDIODRIVER=
        return subprocess.Popen(call, env=environment)

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
        return subprocess.Popen(call, env=environment)

    def background(self, call):
        return subprocess.Popen(call)

    def cmd(self, call, env=False):
        environment = os.environ.copy() if env == True else None
        subprocess.run(call, env=environment, shell=True)

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
        subprocess.call(['/sbin/sudo', '/sbin/chrt', '-a', '-f', '-p', str(int(self.config['system']['system']['realtime'])+inc), str(pid)], shell=False)

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
        data.append("{}\n".format(self.path_data))
        if self.config['mod'] != None:
            if 'app1' in self.config['mod']:
                name_mod = self.config['mod']['app1'].get('name', '')
                data.append("{}\n".format(name_mod))
                data.append("{}\n".format(self.config['mod']['app1'].get('path', '')))
                data.append("{}\n".format(self.config['mod']['app1'].get('project', '')))
                if name_mod in self.config['app']:
                    data.append("{}\n".format(self.config['app'][name_mod].get('extension', '')))
        try:
            with open("/var/tmp/opendsp-run-data", "w+") as run_data:
                run_data.writelines(data)
        except Exception as e:
            print("error trying to update run data: {message}".format(e))

    def mount_fs(self, fs, action):
        if 'write'in action: 
            subprocess.run("/sbin/sudo /bin/mount -o remount,rw {0}".format(fs), shell=True)
        elif 'read' in action:
            subprocess.run("/sbin/sudo /bin/mount -o remount,ro {0}".format(fs), shell=True)

    def check_updates(self):
        update_pkgs = glob.glob(self.path_data + '/updates/*.pkg.tar.xz')
        # any update package?
        for path_package in update_pkgs:
            # install package
            subprocess.call(['/sbin/sudo', '/sbin/pacman', '--noconfirm', '-U', path_package], shell=False)
            # any systemd changes?
            subprocess.call(['/sbin/sudo', '/sbin/systemctl', 'daemon-reload', path_package], shell=False)
            # remove the package from /updates dir and leave user a note about the update
            subprocess.call(['/bin/rm', path_package], shell=False)
            log_file = open(self.path_data + '/updates/log.txt','a')
            log_file.write(str(datetime.datetime.now()) + ': package ' + path_package + ' updated successfully')
            log_file.close()
            if 'opendspd' in path_package:
                # restart our self
                subprocess.call(['/sbin/sudo', '/sbin/systemctl', 'restart', 'opendsp'], shell=False)