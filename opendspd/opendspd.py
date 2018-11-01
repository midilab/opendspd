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
REALTIME_PRIO = 48

class OpenDspCtrl:

    # self instance for singleton control
    __singleton__ = None
  
    # Subprocess dependencies objects
    __jack = None
    __jack_client = None
    __ttymidi = None  

	# Loaded app if any
    __app = None
    __app_name = None
    __app_midi_processor = None
    
    __midi_processor_thread = None
    
    __config = None
        
    # Default data path
    __data_path = USER_DATA
    
    def __init__(self):
        # before we go singleton, lets make our daemon realtime priorized
        self.setRealtime(os.getpid())
        # singleton him
        if OpenDspCtrl.__singleton__:
            raise OpenDspCtrl.__singleton__
        OpenDspCtrl.__singleton__ = self
        self.__config = configparser.ConfigParser()

    def setRealtime(self, pid, inc=0):
        subprocess.call(['/sbin/sudo', '/sbin/chrt', '-f', '-p', str(REALTIME_PRIO+inc), str(pid)], shell=False)

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
                # app midi processing
                self.__app_midi_processor,
                # opendsp midi controlled via cc messages on channel 16 
                ChannelFilter(16) >> Filter(CTRL) >> Call(thread=self.midi_processor_queue)            
            ]
        )

    def osc_processor(self):
        pass

    def keyboard_processor(self):
        pass

    def run_manager(self):
        
        # connect midi ports
        subprocess.call(['/usr/bin/jack_connect', 'ttymidi:MIDI_in', 'OpenDSP:in_1'], shell=False)

        while True:
            # check for new usb midi devices
            #self.__jack_client.get_ports(is_midi=True, is_output=True)
            #[jack.MidiPort('alsa_midi:Midi Through Port-0 (out)'), jack.MidiPort('ttymidi:MIDI_in'), jack.MidiPort('OpenDSP:out_1'), jack.MidiPort('OpenDSP:out_2'), jack.MidiPort('OpenDSP:out_3'), jack.MidiPort('OpenDSP:out_4'), jack.MidiPort('OpenDSP:out_5'), jack.MidiPort('OpenDSP:out_6'), jack.MidiPort('OpenDSP:out_7'), jack.MidiPort('OpenDSP:out_8'), jack.MidiPort('OpenDSP:out_9'), jack.MidiPort('OpenDSP:out_10'), jack.MidiPort('OpenDSP:out_11'), jack.MidiPort('OpenDSP:out_12'), jack.MidiPort('OpenDSP:out_13'), jack.MidiPort('OpenDSP:out_14'), jack.MidiPort('OpenDSP:out_15'), jack.MidiPort('OpenDSP:out_16'), jack.MidiPort('alsa_midi:ecasound (out)'), jack.MidiPort('ingen:notify')]
            #self.__jack_client.connect('novation:output_1', 'OpenDSP:in_1')
            time.sleep(500)

    def start_audio(self):
        self.__jack = subprocess.Popen(['/usr/bin/jackd', '-P50', '-t3000', '-dalsa', '-dhw:' + self.__config['audio']['hardware'], '-r' + self.__config['audio']['rate'], '-p' + self.__config['audio']['buffer'], '-n' + self.__config['audio']['period'], '-Xseq'], shell=False)
        time.sleep(1)
        self.setRealtime(self.__jack.pid, 2)
        # start our manager client
        self.__jack_client = jack.Client('odsp_manager')
 
    def start_midi(self):
        # start mididings and a thread for midi input listening
        config(backend='jack-rt', client_name='OpenDSP', out_ports = 16)
        self.__midi_processor_thread = threading.Thread(target=self.midi_processor, args=())
        self.__midi_processor_thread.daemon = True

        # start ttymidi? (only if your hardware has onboard serial uart)
        if self.__config['midi'].getboolean('onboard-uart') == True:
            self.__ttymidi = subprocess.Popen(['/usr/bin/ttymidi', '-s', self.__config['midi']['device'], '-b', '38400'], shell=False)
            time.sleep(1)
            self.setRealtime(self.__ttymidi.pid)

    def start_app(self, app_name=None):
        self.__app_name = self.__config['app']['name']
        module = importlib.import_module('opendspd.app.' + self.__app_name)
        app_class = getattr(module, self.__app_name)
        self.__app = app_class(self.__singleton__)
        self.__app_midi_processor = self.__app.get_midi_processor()
        # we wait the app midi processor metaprogramming data before start this thread
        self.__midi_processor_thread.start()
        time.sleep(1)
 
        self.__app.start()
        
    def getDataPath(self):
        return self.__data_path
