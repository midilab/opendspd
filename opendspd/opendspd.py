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
    
    __config = None
    
    __run = True
        
    # Default data path
    __data_path = USER_DATA
    
    def __init__(self):        
        # singleton him
        if Manager.__singleton__:
            raise Manager.__singleton__
        Manager.__singleton__ = self
        self.__config = configparser.ConfigParser()
        # lets make our daemon realtime priorized, 4 pts above other realtime process
        self.setRealtime(os.getpid(), -4)
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        
    def __del__(self):
        # not called... please check:
        # https://stackoverflow.com/questions/73663/terminating-a-python-script
        # check for display on
        if self.__display_on == True:
            # stop display service
            subprocess.call(['/sbin/sudo', '/sbin/systemctl', 'stop', 'display'], shell=True)
        # any other service to be stoped?   
        # vdisplay? 

    # catch SIGINT and SIGTERM and stop application
    def signal_handler(self, sig, frame):
        self.__run = False

    def init(self):
        # load user config files
        self.load_config()
        # start Audio engine
        self.start_audio()
        # start MIDI engine
        self.start_midi()
        # force rtirq to restart
        subprocess.call(['/sbin/sudo', '/usr/bin/rtirq', 'restart'], shell=True)

    def run_manager(self):
        
        # start initial App
        self.start_app()

        # start on-board midi? (only if your hardware has onboard serial uart)
        if self.__config['midi'].getboolean('onboard-uart') == True:
            # a trick here is to call ttymidi on our serial interface to setup it for jamrouter usage.
            ttymidi = subprocess.Popen(['/usr/bin/ttymidi', '-s', str(self.__config['midi']['device']), '-b', '38400'], shell=False)
            os.kill(ttymidi.pid, signal.SIGTERM)
            os.kill(ttymidi.pid, signal.SIGKILL)
            ttymidi.kill()
            self.__onboard_midi = subprocess.Popen(['/usr/bin/jamrouter', '-M', 'generic', '-D', str(self.__config['midi']['device']), '-o', 'OpenDSP_RT:in_1', '-y', str(REALTIME_PRIO+4), '-Y', str(REALTIME_PRIO+4)], shell=False)
            self.setRealtime(self.__onboard_midi.pid, 4)        
        
        # start checkNewMidi Thread
        self.__check_midi_thread = threading.Thread(target=self.checkNewMidiInput, args=())
        self.__check_midi_thread.daemon = True
        self.__check_midi_thread.start()     
        
        # connect realtime output 16 to our internal mididings object processor(for midi host controlling)
        self.__jack_client.connect('OpenDSP_RT:out_16', 'OpenDSP:in_1')
        
        while self.__run:
            self.__app.run()
            time.sleep(10)

    def checkNewMidiInput(self):
        # new devices on raw midi layer?
        for midi_device in glob.glob("/dev/midi*"):
            if midi_device in self.__midi_devices:
                continue
            midi_device_proc = subprocess.Popen(['/usr/bin/jamrouter', '-M', 'generic', '-D', str(midi_device), '-o', 'OpenDSP_RT:in_1', '-y', str(REALTIME_PRIO+4), '-Y', str(REALTIME_PRIO+4)], shell=True)
            self.setRealtime(self.__onboard_midi.pid, 4)  
            self.__midi_devices.append(midi_device)
            # todo: we need to keep midi_device_proc for later managemant purpose
        time.sleep(5)
            
    def setRealtime(self, pid, inc=0):
        subprocess.call(['/sbin/sudo', '/sbin/taskset', '-p', '-c', '1,2,3', str(pid)], shell=False)
        subprocess.call(['/sbin/sudo', '/sbin/chrt', '-a', '-f', '-p', str(REALTIME_PRIO+inc), str(pid)], shell=False)
        parent = psutil.Process(pid)
        children = parent.children(recursive=True)
        for process in children:
            subprocess.call(['/sbin/sudo', '/sbin/chrt', '-a', '-f', '-p', str(REALTIME_PRIO+inc), str(process.id)], shell=False)

    def load_config(self):
        self.__config.read(USER_DATA + '/system.cfg')
        # audio setup
        # video setup
        # midi setup
        # app defaults

        # if system config file does not exist, load default values
        if len(self.__config) == 0:
            # audio defaults
            self.__config['audio']['rate'] = '48000'
            self.__config['audio']['period'] = '8'
            self.__config['audio']['buffer'] = '256'
            self.__config['audio']['hardware'] = '0,0'
            # video defaults
            # midi setup
            self.__config['midi']['onboard-uart'] = 'true'
            self.__config['midi']['device'] = '/dev/ttyAMA0'
            # app defaults
            self.__config['app']['name'] = 'plugmod'
            self.__config['app']['project'] = '1'
                    
    def midi_processor_queue(self, event):
        #event.value
        for case in switch(event.ctrl):
            if case(119):
                #LOAD_APP
                break
            if case(118):
                #LOAD_APP_PROJECT
                break
            if case(117):
                #LOAD_APP_NEXT_PROJECT
                break
            if case(116):
                #LOAD_APP_PREV_PROJECT
                break
            if case(115):
                #LOAD_APP_SAVE_AS
                break
        
    def midi_processor(self):
        run(
            [
                # opendsp midi controlled via cc messages on channel 16 
                ChannelFilter(16) >> Filter(CTRL) >> Call(thread=self.midi_processor_queue)            
            ]
        )

    def osc_processor(self):
        pass

    def keyboard_processor(self):
        pass

    def start_audio(self):
        self.__jack = subprocess.Popen(['/usr/bin/jackd', '-P' + str(REALTIME_PRIO+4), '-t3000', '-dalsa', '-d' + self.__config['audio']['hardware'], '-r' + self.__config['audio']['rate'], '-p' + self.__config['audio']['buffer'], '-n' + self.__config['audio']['period']], shell=False)
        self.setRealtime(self.__jack.pid, 4)
        # start our manager client
        self.__jack_client = jack.Client('odsp_manager')
        self.__jack_client.activate()
 
    def start_midi(self):
        # start mididings and a thread for midi input user control and feedback listening
        config(backend='jack', client_name='OpenDSP')
        self.__midi_processor_thread = threading.Thread(target=self.midi_processor, args=())
        self.__midi_processor_thread.daemon = True
        self.__midi_processor_thread.start()

    def start_app(self, app_name=None):
        self.__app_name = self.__config['app']['name']
        module = importlib.import_module('opendspd.app.' + self.__app_name)
        app_class = getattr(module, self.__app_name)
        self.__app = app_class(self.__singleton__)
        self.__app_midi_processor = self.__app.get_midi_processor()
        
        # call mididings and set it realtime alog with jack - named OpenDSP_RT
        # from realtime standalone mididings processor get a port(16) and redirect to mididings python based
        # add one more rule for our internal opendsp management
        # ChannelFilter(16) >> Port(16)
        rule = "[ " + self.__app.get_midi_processor() + ", ChannelFilter(16) >> Port(16) ]"
        self.__mididings = subprocess.Popen(['/usr/bin/mididings', '-R', '-c', 'OpenDSP_RT', '-o', '16', rule], shell=False)
        self.setRealtime(self.__mididings.pid, 4)
 
        self.__app.start()     
        
    def start_display_app(self, cmd):
        # check for display on
        if self.__display_on == False:
            # start display service
            subprocess.call(['/sbin/sudo', '/sbin/systemctl', 'start', 'display'], shell=False)
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
        return subprocess.Popen([cmd], env=environment, shell=True)
             
    def getDataPath(self):
        return self.__data_path

    def getAppParams(self):
        return self.__config['app']
        
    def getJackClient(self):
        return self.__jack_client
