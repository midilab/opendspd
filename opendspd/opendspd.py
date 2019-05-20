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
  
    # subprocess dependencies objects
    jack_server = None
    jack = None
    mididings = None
    
    midi_port_in = []    
    midi_onboard_proc = None
    midi_devices_proc = [] 
    midi_devices = []  

    # app data
    app = None
    app_name = None
    app_midi_processor = None
    app_program_id = {
        0: "plugmod",
        1: "djing"
    } 
    
    # display management support
    display_on = False
    virtual_display_on = False
    visualizer = None
    visualizer_proc = None

    thread_check_midi = None
    thread_midi_processor = None
    thread_visualizer = None
    
    config = None
    
    running = False
    
    # Default data path
    data_path = USER_DATA
    
    def __init__(self):        
        # singleton him
        if Core._singleton:
            raise Core._singleton
        Core._singleton = self
        self.config = configparser.ConfigParser()
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
    
    def init(self):
        # check first run script created per platform
        if os.path.isfile('/home/opendsp/opendsp_1st_run.sh'):
            self.mount_fs('write')
            subprocess.check_call(['/sbin/sudo', '/home/opendsp/opendsp_1st_run.sh'])
            subprocess.check_call(['/bin/rm', '/home/opendsp/opendsp_1st_run.sh'])
            self.mount_fs('read')
            #subprocess.check_call(['/sbin/sudo', '/sbin/systemctl', 'reboot'])
            #sys.exit()
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
        self.set_realtime(os.getpid(), -4)

        # start initial App
        self.start_app()

        # midi handling 
        self.start_midi_processing()
        
        # do we want to start visualizer?
        if self.visualizer:
            self.thread_visualizer = threading.Thread(target=self.start_visualizer, args=())
            self.thread_visualizer.start()                 
        
        self.running = True
        
        check_updates_counter = 5
        
        # set main PCM to max gain volume
        subprocess.check_call(['/bin/amixer', 'sset', 'PCM,0', '100%'])
        
        while self.running:
            # check for update packages each 5th run cycle
            if check_updates_counter == 60:
                self.check_updates()
                check_updates_counter = 0
                
            if self.app:
                self.app.run()
            
            check_updates_counter += 1
            time.sleep(1)

    def __del__(self):
        # check for display on
        if self.display_on:
            # stop display service
            subprocess.call(['/sbin/sudo', '/sbin/systemctl', 'stop', 'display'], shell=True)
        # check for virtual display
        if self.virtual_display_on:
            # stop virtual display service
            subprocess.call(['/sbin/sudo', '/sbin/systemctl', 'stop', 'vdisplay'], shell=True)    
        # stop app
        self.stop_app()
        # kill sub process
        self.stop_midi_processing()
        self.jack.kill()
        if self.visualizer_proc != None:   
            self.visualizer_proc.kill()

    # catch SIGINT and SIGTERM and stop application
    def signal_handler(self, sig, frame):
        if self.app != None:
            del self.app  
        self.running = False

    def mount_fs(self, action):
        if 'write'in action: 
            subprocess.check_call(['/sbin/sudo', '/bin/mount' , '-o', 'remount,rw', '/'])
        elif 'read' in action:
            subprocess.check_call(['/sbin/sudo', '/bin/mount' , '-o', 'remount,ro', '/'])
            
    def start_visualizer(self):
        # for now only "projectm", so no check...
        self.visualizer_proc = self.display('/usr/bin/projectM-jack')
        self.set_realtime(self.visualizer_proc.pid, -15)
        # wait projectm to comes up and them set it full screen
        time.sleep(20)
        subprocess.check_call(['/usr/bin/xdotool', 'search', '--name', 'projectM', 'windowfocus', 'key', 'f'])
        time.sleep(1)
        # jump to next
        subprocess.check_call(['/usr/bin/xdotool', 'search', '--name', 'projectM', 'windowfocus', 'key', 'n'])
        time.sleep(1)
        # lock preset
        #subprocess.check_call(['/usr/bin/xdotool', 'search', '--name', 'projectM', 'windowfocus', 'key', 'l'])

    def stop_midi_processing(self):
        self.mididings.kill()
        # all jamrouter proc
        # TODO: eternal loop bug
        #for device in self.midi_devices_procs:
        #    device.kill()
        self.midi_devices_procs = []
        self.midi_devices = []
        self.thread_check_midi = None
        if 'midi' in self.config:
            self.midi_onboard_proc.kill()
            
    def start_midi_processing(self):
        # start on-board midi? (only if your hardware has onboard serial uart)
        if 'midi' in self.config:
            self.midi_onboard_proc = subprocess.Popen(['/usr/bin/ttymidi', '-s', self.config['midi']['device'], '-b', self.config['midi']['baudrate']])
            self.set_realtime(self.midi_onboard_proc.pid, 4)
            connected = False
            while connected == False:
                try:
                    self.jack.connect('ttymidi:MIDI_in', 'midi:in_1')
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
        
        # connect realtime output 16 to our internal mididings object processor(for midi host controlling)
        self.jack.connect('midi:out_16', 'OpenDSP:in_1')
        self.jack.connect('midi:out_15', 'OpenDSP:in_2')        

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

    def check_new_midi_input(self):
        # to use integrated jackd a2jmidid please add -Xseq to jackd init param
        jack_midi_lsp = map(lambda data: data.name, self.jack.get_ports(is_midi=True, is_output=True))
        for midi_port in jack_midi_lsp:
            if midi_port in self.midi_port_in or 'OpenDSP' in midi_port or 'midi' in midi_port or 'ingen' in midi_port or 'ttymidi' in midi_port or 'alsa_midi:ecasound' in midi_port or 'alsa_midi:Midi Through' in midi_port:
                continue
            self.jack.connect(midi_port, 'midi:in_1')
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
        num_proc = int(subprocess.check_output(['/bin/nproc', '--all']))
        usable_procs = ""
        for i in range(num_proc):
            if ((i+1)/num_proc) > 0.25:
                usable_procs = usable_procs + "," + str(i)
        usable_procs = usable_procs[1:]        
        # the first cpu's are the one allocated for main OS tasks, lets set afinity for other cpu's
        subprocess.call(['/sbin/sudo', '/sbin/taskset', '-p', '-c', usable_procs, str(pid)], shell=False)
        subprocess.call(['/sbin/sudo', '/sbin/chrt', '-a', '-f', '-p', str(REALTIME_PRIO+inc), str(pid)], shell=False)
        
    def load_config(self):
        self.config.read(USER_DATA + '/system.cfg')

        # audio setup
        # video setup
        # midi setup
        # app defaults

        # if system config file does not exist, load default values
        if len(self.config) == 0:
            # audio defaults
            self.config['audio']['rate'] = '48000'
            self.config['audio']['period'] = '8'
            self.config['audio']['buffer'] = '256'
            self.config['audio']['hardware'] = 'hw:0,0'
            # video defaults
            self.config['visualizer']['name'] = 'projectm'
            self.visualizer = self.config['visualizer']
            # midi setup
            # app defaults
            self.config['user']['app'] = self.get_app_name_by_id(0)
            self.app_name = self.config['user']['app']
            self.config[self.app_name]['project'] = '1'
            #self.config[self.app_name]['mixer'] = 'mixer422'
            self.config[self.app_name]['virtual_desktop'] = True
            #self.config[self.app_name]['sequencer'] = 'sequencer64'
            return
        
        if "visualizer" in self.config:   
            self.visualizer = self.config["visualizer"]   
                    
    def get_app_name_by_id(self, id):
        return self.app_program_id.get(id, 0)
        
    def save_config(self):
        self.config.write(USER_DATA + '/system.cfg')

    def load_app(self, app_name):
        self.config['user']['app'] = app_name
        self.app_name = self.config['user']['app']
        if 'project' not in self.config[self.app_name]:
            self.config[self.app_name]['project'] = '1'
        self.stop_app()
        self.stop_midi_processing()
        self.start_app()
        self.start_midi_processing()

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
        # previous visualizer preset    
        if event.ctrl == 20:       
            self.set_visualizer_preset('prev')
            return
        # next visualizer preset    
        if event.ctrl == 21:
            self.set_visualizer_preset('next')
            return
        # get a fresh and random visualizer preset   
        if event.ctrl == 22:
            self.set_visualizer_preset('random')
            return
        # lock/unlock visualizer preset    
        if event.ctrl == 23:
            self.set_visualizer_preset('lock')
            return
            
    def midi_processor_queue_app(self, event):
        self.app.midi_processor_queue(event)
            
    def midi_processor(self):
        run(
            [
                # opendsp midi controlled via cc messages on channel 16 
                PortFilter(1) >> Filter(CTRL) >> Call(thread=self.midi_processor_queue),
                PortFilter(2) >> Filter(CTRL) >> Call(thread=self.midi_processor_queue_app)            
            ]
        )

    # interface definitions
    # one generic interface and a device-to-interface translate table for keyboard, mouse, midi and osc
    def osc_processor(self):
        pass

    def keyboard_processor(self):
        pass

    def start_audio(self):
        # start jack server
        self.jack_server = subprocess.Popen(['/usr/bin/jackd', '-r', '-t10000', '-dalsa', '-d' + self.config['audio']['hardware'], '-r' + self.config['audio']['rate'], '-p' + self.config['audio']['buffer'], '-n' + self.config['audio']['period'], '-Xseq']) #, '-z' + self.config['audio']['dither']])
        self.set_realtime(self.jack_server.pid, 4)
        
        # start jack client
        self.jack = jack.Client('odsp_manager')
        self.jack.activate()
 
    def start_midi(self):
        # start mididings and a thread for midi input user control and feedback listening
        config(backend='jack', client_name='OpenDSP', in_ports=2)
        self.thread_midi_processor = threading.Thread(target=self.midi_processor, args=(), daemon=True)
        self.thread_midi_processor.start()

    def start_app(self):
        self.app_name = self.config['user']['app']
        module = importlib.import_module("opendspd.app.{app_name}".format(app_name=self.app_name))
        app_class = getattr(module, self.app_name)
        self.app = app_class(self._singleton)
        self.app_midi_processor = self.app.get_midi_processor()

        # call mididings and set it realtime alog with jack - named midi
        # from realtime standalone mididings processor get a port(16) and redirect to mididings python based
        # add one more rule for our internal opendsp management
        # ChannelFilter(16) >> Port(16)
        rules = "ChannelSplit({{ {app_rules}, 15: Port(15), 16: Port(16) }})".format(app_rules=self.app_midi_processor)
        self.mididings = subprocess.Popen(['/usr/bin/mididings', '-R', '-c', 'midi', '-o', '16', rules])
        self.set_realtime(self.mididings.pid, 4)

        self.app.start()

    def stop_app(self):
        if self.app != None:
            del self.app
            self.app = None

    def display(self, cmd):
        # check for display on
        if self.display_on == False:
            # start display service
            subprocess.check_call(['/sbin/sudo', '/sbin/systemctl', 'start', 'display'])
            time.sleep(10)
            # avoid screen auto shutoff
            subprocess.check_call(['/usr/bin/xset', 's', 'off'])
            subprocess.check_call(['/usr/bin/xset', '-dpms'])
            subprocess.check_call(['/usr/bin/xset', 's', 'noblank'])
            # TODO: check if display is running before setup as...
            self.display_on = True

        # start app
        # SDL_VIDEODRIVER=
        return subprocess.Popen(cmd.split(" "), env=os.environ.copy())

    def virtual_display(self, cmd):
        # check for display on
        if self.virtual_display_on == False:
            # start display service
            subprocess.check_call(['/sbin/sudo', '/sbin/systemctl', 'start', 'vdisplay'])
            # check if display is running before setup as...
            time.sleep(10)
            self.virtual_display_on = True
        
        # get opendsp user env and change the DISPLAY to our virtual one    
        environment = os.environ.copy()
        environment["DISPLAY"] = ":1"

        # start virtual display app
        return subprocess.Popen(cmd.split(" "), env=environment)

    def set_visualizer_preset(self, preset):
        if preset == 'prev':
            subprocess.call(['/usr/bin/xdotool', 'search', '--name', 'projectM', 'windowfocus', 'key', 'p'])
        elif preset == 'next':
            subprocess.call(['/usr/bin/xdotool', 'search', '--name', 'projectM', 'windowfocus', 'key', 'n'])
        elif preset == 'random':
            subprocess.call(['/usr/bin/xdotool', 'search', '--name', 'projectM', 'windowfocus', 'key', 'r'])
        elif preset == 'lock':
            subprocess.call(['/usr/bin/xdotool', 'search', '--name', 'projectM', 'windowfocus', 'key', 'l'])
