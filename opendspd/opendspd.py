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

# MIDI Support
from mididings import *

# Jack support
import jack

# Data bank paths
USER_DATA = "/home/opendsp/data"

# Realtime Priority
#REALTIME_PRIO = 45
REALTIME_PRIO = 95

class Core:
    """OpenDSP main core

    Usage::

        >>> from opendspd import opendspd
        >>> opendsp = opendspd.Core()
        >>> opendsp.init()
        >>> opendsp.run()
    """

    # self instance for singleton control
    _singleton = None
      
    # to control new midi devices  
    midi_port_in = []    
    
    # display management support
    display_on = False
    virtual_display_on = False

    thread_check_midi = None
    thread_midi_processor = None
    thread_visualizer = None
    
    # all proc reference managed by opendsp
    proc_map = {}
    # configparser objects
    config = None
    app_list = None
    # running state
    running = False
    # Default data path
    data_path = USER_DATA
    
    def __init__(self):        
        # singleton him
        if Core._singleton:
            raise Core._singleton
        Core._singleton = self
        # setup our 2 main config files, the system user and app config
        self.config = configparser.ConfigParser()
        self.app_list = configparser.ConfigParser()
        # setup signal handling 
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)

    def __del__(self):        
        # iterate over all app stack and kill each one of those
        for proc in self.proc_map:
            proc.kill()
        # check for display on
        if self.display_on:
            # stop display service
            subprocess.call(['/sbin/sudo', '/sbin/systemctl', 'stop', 'display'], shell=True)
        # check for virtual display
        if self.virtual_display_on:
            # stop virtual display service
            subprocess.call(['/sbin/sudo', '/sbin/systemctl', 'stop', 'vdisplay'], shell=True) 
        pass

    # catch SIGINT and SIGTERM and stop application
    def signal_handler(self, sig, frame):
        self.running = False

    def init(self):
        # check first run script created per platform
        self.first_time()
        # load user config files
        self.load_config()
        # start Audio engine
        self.start_audio()
        # start MIDI engine
        self.start_midi()
        # force rtirq to restart
        #subprocess.call(['/sbin/sudo', '/usr/bin/rtirq', 'restart'], shell=True)
    
    def run(self):
        # lets make our daemon realtime priorized, 4 pts above other realtime process
        #self.set_realtime(os.getpid(), -4)

        apps = [ app for app in self.config if 'app' in app ]
        for app in apps:
            name = self.config[app]['name']
            if name in self.app_list:
                self.start_app(app, name, self.app_list[name], self.config[app]['project'], self.config[app]['display'])
            else:
                print("app {app_name} not defined!".format(app_name=name))                 
        
        # set main PCM to max gain volume
        subprocess.check_call(['/bin/amixer', 'sset', 'PCM,0', '100%'])

        self.running = True
        
        check_updates_counter = 0
        while self.running:
            # health check for audio, midi and video subsystem
            #...    
            # health check for all running apps    
            #...
            # check for update packages 
            if check_updates_counter == 10:
                self.check_updates()
                check_updates_counter = 0
            check_updates_counter += 1
            # rest for a while....
            time.sleep(6)

    def check_new_midi_input(self):
        # to use integrated jackd a2jmidid please add -Xseq to jackd init param
        jack_midi_lsp = map(lambda data: data.name, self.jack.get_ports(is_midi=True, is_output=True))
        #[ data.name for data in self.jack.get_ports(is_midi=True, is_output=True) ]
        for midi_port in jack_midi_lsp:
            if midi_port in self.midi_port_in or 'OpenDSP' in midi_port or 'midiRT' in midi_port or 'ingen' in midi_port or 'ttymidi' in midi_port or 'alsa_midi:ecasound' in midi_port or 'alsa_midi:Midi Through' in midi_port:
                continue
            self.jack.connect(midi_port, 'midiRT:in_1')
            self.midi_port_in.append(midi_port)
        
        # new devices on raw midi layer?
        #for midi_device in glob.glob("/dev/midi*"):
        #    if midi_device in self.midi_devices:
        #        continue
        #    midi_device_proc = subprocess.Popen(['/usr/bin/jamrouter', '-M', 'generic', '-D', midi_device, '-o', 'midi:in_1'], shell=False) #, '-y', str(REALTIME_PRIO+4), '-Y', str(REALTIME_PRIO+4)], shell=True)
        #    self.set_realtime(midi_device_proc.pid, 4)  
        #    self.midi_devices.append(midi_device)
        #    self.midi_devices_procs.append(midi_device_proc)
        time.sleep(5)
    
    def set_realtime(self, pid, inc=0):
        # the idea is: use 25% of cpu for OS tasks and the rest for opendsp
        # nproc --all
        #num_proc = int(subprocess.check_output(['/bin/nproc', '--all']))
        #usable_procs = ""
        #for i in range(num_proc):
        #    if ((i+1)/num_proc) > 0.25:
        #        usable_procs = usable_procs + "," + str(i)
        #usable_procs = usable_procs[1:]        
        # the first cpu's are the one allocated for main OS tasks, lets set afinity for other cpu's
        #subprocess.call(['/sbin/sudo', '/sbin/taskset', '-p', '-c', usable_procs, str(pid)], shell=False)
        subprocess.call(['/sbin/sudo', '/sbin/chrt', '-a', '-f', '-p', str(REALTIME_PRIO+inc), str(pid)], shell=False)
        
    def load_config(self):

        # read apps definitions
        self.app_list.read(USER_DATA + '/app.cfg')

        # loading general system config
        self.config.read(USER_DATA + '/system.cfg')

        # audio setup
        # if system config file does not exist, load default values
        if 'audio' not in self.config:
            # audio defaults
            self.config['audio']['rate'] = '48000'
            self.config['audio']['period'] = '8'
            self.config['audio']['buffer'] = '256'
            self.config['audio']['hardware'] = 'hw:0,0'
                                
    def start_audio(self):
        # start jack server
        self.proc_map['jackd'] = subprocess.Popen(['/usr/bin/jackd', '-R', '-t10000', '-dalsa', '-d' + self.config['audio']['hardware'], '-r' + self.config['audio']['rate'], '-p' + self.config['audio']['buffer'], '-n' + self.config['audio']['period'], '-Xseq']) #, '-z' + self.config['audio']['dither']])
        self.set_realtime(self.proc_map['jackd'].pid, 4)
        
        # start jack client
        self.jack = jack.Client('odsp_manager')
        self.jack.activate()
 
    def midi_processor_queue(self, event):
        #event.value
        if event.ctrl == 119:
            #LOAD_APP
            self.load_app(self.get_app_name_by_id(event.value))
            return
        if event.ctrl == 118:
            #...
            return
        if event.ctrl == 117:
            #...
            return
        if event.ctrl == 116:
            #...
            return
        if event.ctrl == 115:
            #...
            return
        #if event.ctrl == 114:
        #    # restart opendspd
        #    subprocess.call(['/sbin/sudo', '/usr/bin/systemctl', 'restart', 'opendsp'])
        #    return


    def midi_processor_queue_app(self, event):
        #event.value
        if event.ctrl == 119:
            #...
            return   

    def midi_processor(self):
        run(
            [
                # opendsp midi controlled via cc messages on channel 16 
                PortFilter(1) >> Filter(CTRL) >> Call(thread=self.midi_processor_queue),
                PortFilter(2) >> Filter(CTRL) >> Call(thread=self.midi_processor_queue_app)            
            ]
        )

    def start_midi(self):
        # start mididings and a thread for midi input user control and feedback listening
        config(backend='jack', client_name='OpenDSP', in_ports=2)
        self.thread_midi_processor = threading.Thread(target=self.midi_processor, args=(), daemon=True)
        self.thread_midi_processor.start()

        # call mididings and set it realtime alog with jack - named midi
        # from realtime standalone mididings processor get a port(16) and redirect to mididings python based
        # add one more rule for our internal opendsp management
        # ChannelFilter(16) >> Port(16)
        rules = "ChannelSplit({ 1: Port(1), 2: Port(2), 3: Port(3), 4: Port(4), 5: Port(5), 6: Port(6), 7: Port(7), 8: Port(8), 9: Port(9), 10: Port(10), 11: Port(11), 12: Port(12), 13: Port(13), 14: Port(14), 15: Port(15), 16: Port(16) })"
        self.proc_map['mididings'] = subprocess.Popen(['/usr/bin/mididings', '-R', '-c', 'midiRT', '-o', '16', rules])
        self.set_realtime(self.proc_map['mididings'].pid, 4)

        # connect realtime output 16 to our internal mididings object processor(for midi host controlling)
        #self.jack.connect('midiRT:out_16', 'OpenDSP:in_1')
        #self.jack.connect('midiRT:out_15', 'OpenDSP:in_2')         

        # calls input2midi
        #self.input2midi = subprocess.Popen('/usr/bin/input2midi')
        self.proc_map['input2midi'] = subprocess.Popen('/home/opendsp/input2midi/run')
        self.set_realtime(self.proc_map['input2midi'].pid)       

        # start on-board midi? (only if your hardware has onboard serial uart)
        if 'midi' in self.config:
            self.proc_map['on_board_midi'] = subprocess.Popen(['/usr/bin/ttymidi', '-s', self.config['midi']['device'], '-b', self.config['midi']['baudrate']])
            self.set_realtime(self.proc_map['on_board_midi'].pid, 4)
            connected = False
            while connected == False:
                try:
                    self.jack.connect('ttymidi:MIDI_in', 'midiRT:in_1')
                    connected = True
                except:
                    # max times to try
                    print('cant found ttymidi jack port... try again')
                    time.sleep(1)
            # set our serial to 38400 to trick raspbery goes into 31200
            #subprocess.call(['/sbin/sudo', '/usr/bin/stty', '-F', str(self.config['midi']['device']), '38400'], shell=True)            
            # problem: cant get jamrouter to work without start ttymidi first, setup else where beside the baudrate?
            #self.midi_onboard_proc = subprocess.Popen(['/usr/bin/jamrouter', '-M', 'generic', '-D', str(self.config['midi']['device']), '-o', 'midi:in_1', '-y', str(REALTIME_PRIO+4), '-Y', str(REALTIME_PRIO+4)], shell=False)
            #self.set_realtime(self.midi_onboard_proc.pid, 4)        
        
        # start checkNewMidi Thread
        self.thread_check_midi = threading.Thread(target=self.check_new_midi_input, args=(), daemon=True)
        self.thread_check_midi.start() 

    def start_app(self, app_id, name, app_obj, project, display):
        # from where to load projects
        #app_obj['path']
        #app_path = "{0} {1}{2}".format(app_obj.bin, app_obj.path, project
        app_path = app_obj['bin']
        # the binary app
        if 'native' in display:
            self.display(app_path)
        elif 'virtual' in display:
            self.virtual_display(app_path)
        else:
            self.proc_map[name] = subprocess.Popen(app_path)

        # generate a list from, parsed by ','
        #app_obj.input
        #app_obj.output
        #app_obj.midi_input
        #app_obj.midi_output
        # create a list for all projects inside path

    def stop_app(self, app_id):
        pass

    def display(self, cmd):
        # check for display on
        if self.display_on == False:
            # start display service
            subprocess.check_call(['/sbin/sudo', '/sbin/systemctl', 'start', 'display'])
            while "xinit" not in (p.name() for p in psutil.process_iter()):
                time.sleep(1)
            # avoid screen auto shutoff
            subprocess.check_call(['/usr/bin/xset', 's', 'off'])
            subprocess.check_call(['/usr/bin/xset', '-dpms'])
            subprocess.check_call(['/usr/bin/xset', 's', 'noblank'])
            self.display_on = True

        # start app
        # SDL_VIDEODRIVER=
        # SDL_AUDIODRIVER=
        environment = os.environ.copy()
        environment["DISPLAY"] = ":0"
        environment["SDL_AUDIODRIVER"] = "jack"
        return subprocess.Popen(cmd.split(" "), env=environment)

    def virtual_display(self, cmd):
        # check for display on
        if self.virtual_display_on == False:
            # start display service
            subprocess.check_call(['/sbin/sudo', '/sbin/systemctl', 'start', 'vdisplay'])
            # check if display is running before setup as...
            while "Xvfb" not in (p.name() for p in psutil.process_iter()):
                time.sleep(1)
            self.virtual_display_on = True
        
        # get opendsp user env and change the DISPLAY to our virtual one    
        environment = os.environ.copy()
        environment["DISPLAY"] = ":1"
        environment["SDL_AUDIODRIVER"] = "jack"
        # start virtual display app
        return subprocess.Popen(cmd.split(" "), env=environment)

    def mount_fs(self, action):
        if 'write'in action: 
            subprocess.check_call(['/sbin/sudo', '/bin/mount' , '-o', 'remount,rw', '/'])
        elif 'read' in action:
            subprocess.check_call(['/sbin/sudo', '/bin/mount' , '-o', 'remount,ro', '/'])

    def first_time(self):
        # check first run script created per platform
        if os.path.isfile('/home/opendsp/opendsp_1st_run.sh'):
            self.mount_fs('write')
            subprocess.check_call(['/sbin/sudo', '/home/opendsp/opendsp_1st_run.sh'])
            subprocess.check_call(['/bin/rm', '/home/opendsp/opendsp_1st_run.sh'])
            self.mount_fs('read')
            #subprocess.check_call(['/sbin/sudo', '/sbin/systemctl', 'reboot'])
            #sys.exit()

    def check_updates(self):
        update_pkgs = glob.glob(self.data_path + '/updates/*.pkg.tar.xz')
        # any update package?
        for package_path in update_pkgs:
            # install package
            subprocess.call(['/sbin/sudo', '/sbin/pacman', '--noconfirm', '-U', package_path], shell=False)
            # any systemd changes?
            subprocess.call(['/sbin/sudo', '/sbin/systemctl', 'daemon-reload', package_path], shell=False)
            # remove the package from /updates dir and leave user a note about the update
            subprocess.call(['/bin/rm', package_path], shell=False)
            log_file = open(self.data_path + '/updates/log.txt','a')
            log_file.write(str(datetime.datetime.now()) + ': package ' + package_path + ' updated successfully')
            log_file.close()
            if 'opendspd' in package_path:
                # restart our self
                subprocess.call(['/sbin/sudo', '/sbin/systemctl', 'restart', 'opendsp'], shell=False)