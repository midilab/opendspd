# OpenDSP Daemon
# Copyright (C) 2015-2016 Romulo Silva <contact@midilab.co>
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
import os, sys, time, subprocess, threading, importlib, glob, signal, psutil

import configparser

# MIDI Support
from mididings import *

# Jack support
import jack

# Main definitions
# Data bank paths
USER_DATA = "/home/opendsp/data"
EXTERNAL_DATA = "/home/opendsp/external"

# Realtime Priority
REALTIME_PRIO = 95

class Manager:

    # self instance for singleton control
    __singleton__ = None
  
    # Subprocess dependencies objects
    __jack = None
    __jack_client = None
    __mididings = None
    __onboard_midi = None
    __midi_devices_proc = [] 
    __midi_devices = []  

	# Loaded app if any
    __app = None
    __app_name = None
    __app_midi_processor = None
    __check_midi_thread = None
    
    __midi_processor_thread = None
    __midi_port_in = []
    
    # display manage support
    __display_on = False
    __virtual_display_on = False
    __visualizer = None
    __visualizer_proc = None
    
    __config = None
    
    __run = False
        
    # Default data path
    __data_path = USER_DATA
    
    def __init__(self):        
        # singleton him
        if Manager.__singleton__:
            raise Manager.__singleton__
        Manager.__singleton__ = self
        self.__config = configparser.ConfigParser()
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
    
    def __del__(self):
        # check for display on
        if self.__display_on == True:
            # stop display service
            subprocess.call(['/sbin/sudo', '/sbin/systemctl', 'stop', 'display'], shell=True)
        # check for virtual display
        if self.__virtual_display_on == True:
            # stop virtual display service
            subprocess.call(['/sbin/sudo', '/sbin/systemctl', 'stop', 'vdisplay'], shell=True)    
        # stop app
        self.stop_app()
        # kill sub process
        self.stop_midi_processing()
        self.__jack.kill()
        if self.__visualizer_proc != None:   
            self.__visualizer_proc.kill()

    # catch SIGINT and SIGTERM and stop application
    def signal_handler(self, sig, frame):
        if self.__app != None:
            del self.__app  
        self.__run = False

    def init(self):
        # load user config files
        self.load_config()
        # start Audio engine
        self.start_audio()
        # start MIDI engine
        self.start_midi()
        # force rtirq to restart
        #subprocess.call(['/sbin/sudo', '/usr/bin/rtirq', 'restart'], shell=True)

    def start_visualizer(self):
        # for now only "projectm", so no check...
        self.__visualizer_proc = self.start_display_app('/usr/bin/projectM-jack')
        self.setRealtime(self.__visualizer_proc.pid, -50)
        # wait projectm to comes up and them set it full screen
        time.sleep(60)
        subprocess.call(['/usr/bin/xdotool', 'search', '--name', 'projectM', 'windowfocus', 'key', 'f'])
        time.sleep(1)
        # jump to next
        subprocess.call(['/usr/bin/xdotool', 'search', '--name', 'projectM', 'windowfocus', 'key', 'n'])
        time.sleep(1)
        # lock preset
        subprocess.call(['/usr/bin/xdotool', 'search', '--name', 'projectM', 'windowfocus', 'key', 'l'])
        main_app_out = self.__app.get_main_outs()
        for output in main_app_out:
            try:
                self.__jack_client.connect(output, 'projectM-jack:input')
            except:
                pass

    def stop_midi_processing(self):
        self.__mididings.kill()
        # all jamrouter proc
        # TODO: eternal loop bug
        #for device in self.__midi_devices_procs:
        #    device.kill()
        self.__midi_devices_procs = []
        self.__midi_devices = []
        self.__check_midi_thread = None
        if self.__config['midi'].getboolean('onboard-uart') == True:
            self.__onboard_midi.kill()
            
    def start_midi_processing(self):
        # start on-board midi? (only if your hardware has onboard serial uart)
        if self.__config['midi'].getboolean('onboard-uart') == True:
            self.__onboard_midi = subprocess.Popen(['/usr/bin/ttymidi', '-s', self.__config['midi']['device'], '-b', self.__config['midi']['baudrate']], shell=False)
            self.setRealtime(self.__onboard_midi.pid, 4)
            connected = False
            while connected == False:
                try:
                    self.__jack_client.connect('ttymidi:MIDI_in', 'OpenDSP_RT:in_1')
                    connected = True
                except:
                    # max times to try
                    print('cant found ttymidi jack port... try again')
                    time.sleep(1)
            # set our serial to 38400 to trick raspbery goes into 31200
            #subprocess.call(['/sbin/sudo', '/usr/bin/stty', '-F', str(self.__config['midi']['device']), '38400'], shell=True)            
            # problem: cant get jamrouter to work without start ttymidi first, setup else where beisde the baudrate?
            #self.__onboard_midi = subprocess.Popen(['/usr/bin/jamrouter', '-M', 'generic', '-D', str(self.__config['midi']['device']), '-o', 'OpenDSP_RT:in_1', '-y', str(REALTIME_PRIO+4), '-Y', str(REALTIME_PRIO+4)], shell=False)
            #self.setRealtime(self.__onboard_midi.pid, 4)        
        
        # start checkNewMidi Thread
        self.__check_midi_thread = threading.Thread(target=self.checkNewMidiInput, args=())
        self.__check_midi_thread.start()     
        
        # connect realtime output 16 to our internal mididings object processor(for midi host controlling)
        self.__jack_client.connect('OpenDSP_RT:out_16', 'OpenDSP:in_1')
        self.__jack_client.connect('OpenDSP_RT:out_15', 'OpenDSP:in_2')        

    def run_manager(self):
        
        # lets make our daemon realtime priorized, 4 pts above other realtime process
        self.setRealtime(os.getpid(), -4)
        
        # start initial App
        self.start_app()

        # midi handling 
        self.start_midi_processing()
        
        # do we want to start visualizer?
        if self.__visualizer != None:
            self.__visualizer_thread = threading.Thread(target=self.start_visualizer, args=())
            self.__visualizer_thread.start()                 
        
        self.__run = True
        
        while self.__run:
            if self.__app != None:
                self.__app.run()
            time.sleep(5)

    def checkNewMidiInput(self):
        while self.__app != None:
            # new devices on raw midi layer?
            for midi_device in glob.glob("/dev/midi*"):
                if midi_device in self.__midi_devices:
                    continue
                midi_device_proc = subprocess.Popen(['/usr/bin/jamrouter', '-M', 'generic', '-D', str(midi_device), '-o', 'OpenDSP_RT:in_1', '-y', str(REALTIME_PRIO+4), '-Y', str(REALTIME_PRIO+4)], shell=True)
                self.setRealtime(self.midi_device_proc.pid, 4)  
                self.__midi_devices.append(midi_device)
                self.__midi_devices_procs.append(midi_device_proc)
            time.sleep(5)
        
    def setRealtime(self, pid, inc=0):
        # the idea is: use 25% of cpu for OS tasks and the rest for opendsp
        # nproc --all
        # the first cpu's are the one allocated for main OS tasks, lets set afinity for other cpu's
        #subprocess.call(['/sbin/sudo', '/sbin/taskset', '-p', '-c', '1,2,3', str(pid)], shell=False)
        #subprocess.call(['/sbin/sudo', '/sbin/chrt', '-a', '-f', '-p', str(REALTIME_PRIO+inc), str(pid)], shell=False)
        #parent = psutil.Process(pid)
        #children = parent.children(recursive=True)
        #for process in children:
        #    subprocess.call(['/sbin/sudo', '/sbin/chrt', '-a', '-f', '-p', str(REALTIME_PRIO+inc), str(process.pid)], shell=False)
        pass

    def load_config(self):
        self.__config.read(USER_DATA + '/system.cfg')
        # audio setup
        # video setup
        # midi setup
        # app defaults

        if "visualizer" in self.__config:   
            self.__visualizer = self.__config["visualizer"]   
            
        # if system config file does not exist, load default values
        if len(self.__config) == 0:
            # audio defaults
            self.__config['audio']['rate'] = '48000'
            self.__config['audio']['period'] = '8'
            self.__config['audio']['buffer'] = '256'
            self.__config['audio']['hardware'] = '0,0'
            # video defaults
            #self.__config['visualizer']
            # midi setup
            # app defaults
            self.__config['app']['name'] = 'plugmod'
            self.__config['app']['project'] = '1'
            
    def midi_processor_queue(self, event):
        #event.value
        if event.ctrl == 20:
            #LOAD_APP
            self.__config['app']['name'] = 'djing'
            self.__config['app']['project'] = '1'
            self.stop_app()
            self.stop_midi_processing()
            self.start_app()
            self.start_midi_processing()
            return
        if event.ctrl == 118:
            #LOAD_APP_PROJECT
            self.__config['app']['project'] = '1'
            self.stop_app()
            self.start_app()
            return
        if event.ctrl == 117:
            #LOAD_APP_NEXT_PROJECT
            return
        if event.ctrl == 116:
            #LOAD_APP_PREV_PROJECT
            return
        if event.ctrl == 115:
            #LOAD_APP_SAVE_AS
            return
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
        self.__app.midi_processor_queue(event)
            
    def midi_processor(self):
        run(
            [
                # opendsp midi controlled via cc messages on channel 16 
                PortFilter(1) >> Filter(CTRL) >> Call(thread=self.midi_processor_queue),
                PortFilter(2) >> Filter(CTRL) >> Call(thread=self.midi_processor_queue_app)            
            ]
        )

    def osc_processor(self):
        pass

    def keyboard_processor(self):
        pass

    def start_audio(self):
        self.__jack = subprocess.Popen(['/usr/bin/jackd', '-P' + str(REALTIME_PRIO+4), '-t3000', '-dalsa', '-d' + self.__config['audio']['hardware'], '-r' + self.__config['audio']['rate'], '-p' + self.__config['audio']['buffer'], '-n' + self.__config['audio']['period'], '-Xseq'], shell=False)
        self.setRealtime(self.__jack.pid, 4)
        # start our manager client
        self.__jack_client = jack.Client('odsp_manager')
        self.__jack_client.activate()
 
    def start_midi(self):
        # start mididings and a thread for midi input user control and feedback listening
        config(backend='jack', client_name='OpenDSP', in_ports=2)
        self.__midi_processor_thread = threading.Thread(target=self.midi_processor, args=())
        #self.__midi_processor_thread.daemon = True
        self.__midi_processor_thread.start()

    def start_app(self):
        self.__app_name = self.__config['app']['name']
        module = importlib.import_module('opendspd.app.' + self.__app_name)
        app_class = getattr(module, self.__app_name)
        self.__app = app_class(self.__singleton__)
        self.__app_midi_processor = self.__app.get_midi_processor()

        # call mididings and set it realtime alog with jack - named OpenDSP_RT
        # from realtime standalone mididings processor get a port(16) and redirect to mididings python based
        # add one more rule for our internal opendsp management
        # ChannelFilter(16) >> Port(16)
        rule = "ChannelSplit({ " + self.__app.get_midi_processor() + ", 15: Port(15), 16: Port(16) })"
        self.__mididings = subprocess.Popen(['/usr/bin/mididings', '-R', '-c', 'OpenDSP_RT', '-o', '16', rule], shell=False)
        self.setRealtime(self.__mididings.pid, 4)
 
        self.__app.start()

    def stop_app(self):
        if self.__app != None:
            del self.__app
            self.__app = None

    def start_display_app(self, cmd):
        # check for display on
        if self.__display_on == False:
            # start display service
            subprocess.call(['/sbin/sudo', '/sbin/systemctl', 'start', 'display'], shell=False)
            time.sleep(2)
            # avoid screen auto shutoff
            subprocess.call(['/usr/bin/xset', 's', 'off'], shell=False)
            subprocess.call(['/usr/bin/xset', '-dpms'], shell=False)
            subprocess.call(['/usr/bin/xset', 's', 'noblank'], shell=False)
            # check if display is running before setup as...
            self.__display_on = True
            
        # start app
        return subprocess.Popen([cmd], env=os.environ.copy(), shell=True)

    def start_virtual_display_app(self, cmd):
        # check for display on
        if self.__virtual_display_on == False:
            # start display service
            subprocess.call(['/sbin/sudo', '/sbin/systemctl', 'start', 'vdisplay'], shell=False)
            # check if display is running before setup as...
            self.__virtual_display_on = True
        
        # get opendsp user env and change the DISPLAY to our virtual one    
        environment = os.environ.copy()
        environment["DISPLAY"] = ":1"
    
        # start virtual display app
        return subprocess.Popen([cmd], env=environment, stdout=subprocess.PIPE, shell=True)
             
    def getDataPath(self):
        return self.__data_path

    def getAppParams(self):
        return self.__config['app']
        
    def getJackClient(self):
        return self.__jack_client

    def set_visualizer_preset(self, preset):
        if preset == 'prev':
            subprocess.call(['/usr/bin/xdotool', 'search', '--name', 'projectM', 'windowfocus', 'key', 'p'])
        elif preset == 'next':
            subprocess.call(['/usr/bin/xdotool', 'search', '--name', 'projectM', 'windowfocus', 'key', 'n'])
        elif preset == 'random':
            subprocess.call(['/usr/bin/xdotool', 'search', '--name', 'projectM', 'windowfocus', 'key', 'r'])
        elif preset == 'lock':
            subprocess.call(['/usr/bin/xdotool', 'search', '--name', 'projectM', 'windowfocus', 'key', 'l'])
            
