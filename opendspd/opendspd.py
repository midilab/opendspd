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

# interface idea
# 8 generic buttons
# 1 select page button (hold while use general buttons to select the page and release it)
# 1 do it button(enter)
# increment and decrement buttons

# save and load button(for app project)
# use numerical usb keypad as case for interface

# use cases on opendsp:
#1) load app
#2) ...

# use cases on app(generic)
#0) select data bank (factory, user, external0, external1)
#1) load project
#2) save project
#3) new project
#/data/plugmod/projects/1_technera
#/data/plugmod/projects/2

#4) plugmod load module on track channel(its limited by the amount of channels registred on mixer)
#/data/plugmod/modules/1_moog
#/data/plugmod/modules/2_808
#/data/plugmod/modules/2_dx7

# what modules needs?
# sequential and numbered presets to be accessed via program change... it goes as long it can holds... bank+prog
# default controller interface based on generics of opendsp

# Common system tools
import os, sys, time, subprocess, threading, importlib

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
    
    __midi_processor_thread = None
    __midi_port_in = []
    
    __config = None
        
    # Default data path
    __data_path = USER_DATA
    
    def __init__(self):
        # before we go singleton, lets make our daemon realtime priorized
        self.setRealtime(os.getpid(), -4)
        # singleton him
        if Manager.__singleton__:
            raise Manager.__singleton__
        Manager.__singleton__ = self
        self.__config = configparser.ConfigParser()

    def init(self):
        # load user config files
        self.load_config()
        # start Audio engine
        self.start_audio()
        # start MIDI engine
        self.start_midi()

    def run_manager(self):
        # start initial App
        self.start_app()

        # start on-board midi? (only if your hardware has onboard serial uart)
        if self.__config['midi'].getboolean('onboard-uart') == True:
            self.__onboard_midi = subprocess.Popen(['/usr/bin/jamrouter', '-M', 'generic', '-D', self.__config['midi']['device'], '-o', 'OpenDSP_RT:in_1', '-y', str(REALTIME_PRIO+4), '-Y', str(REALTIME_PRIO+4)], shell=False)
            time.sleep(1)
            self.setRealtime(self.__onboard_midi.pid, 4)        
        
        while True:
            # check for new usb midi devices to auto connect into OpenDSP_RT midi processor port
            self.checkNewMidiInput()
            time.sleep(5)
            
    def setRealtime(self, pid, inc=0):
        #subprocess.call(['/sbin/sudo', '/sbin/taskset', '-p', '-c', '1,2,3', str(pid)], shell=False)
        subprocess.call(['/sbin/sudo', '/sbin/chrt', '-a', '-f', '-p', str(REALTIME_PRIO+inc), str(pid)], shell=False)

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

    def checkNewMidiInput(self):
        jack_midi_lsp = self.__jack_client.get_ports(is_midi=True, is_output=True)
        for midi_port in jack_midi_lsp:
            if midi_port.name in self.__midi_port_in or 'OpenDSP' in midi_port.name or 'ingen' in midi_port.name or 'alsa_midi:ecasound' in midi_port.name or 'alsa_midi:Midi Through' in midi_port.name:
                continue
            #self.__jack_client.connect(midi_port.name, 'OpenDSP:in_1')
            #self.__midi_port_in.append(midi_port.name)

            self.__midi_devices.append()
'''
        # start on-board midi? (only if your hardware has onboard serial uart)
        if self.__config['midi'].getboolean('onboard-uart') == True:
            self.__onboard_midi = subprocess.Popen(['/usr/bin/jamrouter', '-M', 'generic', '-D', self.__config['midi']['device'], '-o', 'OpenDSP_RT:in_1', '-y', str(REALTIME_PRIO+4), '-Y', str(REALTIME_PRIO+4)], shell=False)
            time.sleep(1)
            self.setRealtime(self.__onboard_midi.pid, 4)        
'''        

    def start_audio(self):
        self.__jack = subprocess.Popen(['/usr/bin/jackd', '-P' + str(REALTIME_PRIO+4), '-t3000', '-dalsa', '-d' + self.__config['audio']['hardware'], '-r' + self.__config['audio']['rate'], '-p' + self.__config['audio']['buffer'], '-n' + self.__config['audio']['period']], shell=False)
        time.sleep(1)
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
        time.sleep(1)
        
        # call mididings and set it realtime alog with jack - named OpenDSP_RT
        # from realtime standalone mididings processor get a port(16) and redirect to mididings python based
        # add one more rule for our internal opendsp management
        #ChannelFilter(16) >> Port(16), # for internal opendsp mangment
        #mididings -R -c OpenDSP_RT -o 16 "Filter(NOTE, PROGRAM, CTRL) >> Port(1) >> Channel(1)"
        rule = "[ " + self.__app.get_midi_processor() + ", ChannelFilter(16) >> Port(16) ]"
        self.__mididings = subprocess.Popen(['/usr/bin/mididings', '-R', '-c', 'OpenDSP_RT', '-o', '16', rule], shell=False)
        time.sleep(1)
        self.setRealtime(self.__mididings.pid, 4)
        time.sleep(1)
        
        # connect realtime output 16 to our internal mididings object processor(for midi host controlling)
        self.__jack_client.connect('OpenDSP_RT:out_16', 'OpenDSP:in_1')
 
        self.__app.start()
        
    def getDataPath(self):
        return self.__data_path

    def getAppParams(self):
        return self.__config['app']
        
