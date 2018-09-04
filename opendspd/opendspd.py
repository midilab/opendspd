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
import os, sys, time, subprocess, threading, importlib

# MIDI Support
from mididings import *

# Main definitions
#USER_HOME = "/home/opendsp/user_data"
#USER_DATA = "/home/opendsp/session_data"
#FACTORY_DATA = "/home/opendsp/factory_data"

# Realtime Priority
REALTIME_PRIO = 48
#REALTIME_PRIO = 80
#REALTIME_PRIO = 63

class OpenDspCtrl:

    # self instance for singleton control
    __singleton__ = None
  
    # Subprocess dependencies objects
    __jack = None
    __ttymidi = None  

	# Loaded app if any
    __app = None
    __app_name = None
    
    def __init__(self):
        # before we go singleton, lets make our daemon realtime 
        self.setRealtime(os.getpid())
        # singleton him
        if OpenDspCtrl.__singleton__:
            raise OpenDspCtrl.__singleton__
        OpenDspCtrl.__singleton__ = self

    def setRealtime(self, pid, inc=0):
        subprocess.call(['/sbin/sudo', '/sbin/chrt', '-f', '-p', str(REALTIME_PRIO+inc), str(pid)], shell=False)

    def app_load_project_request(self, event):
        if ( self.__app_name == None ):
            return None
        return self.__app.load_project_request(event)

    def app_save_project_request(self, event):
        if ( self.__app_name == None ):
            return None
        return self.__app.save_project_request(event)

    def app_load_next_project_request(self, event):
        pass

    def app_load_previous_project_request(self, event):
        pass

    def app_program_change(self, event):
        if ( self.__app_name == None ):
            return None
        return self.__app.program_change(event)

    def midi_listener(self):
        run(
            [ 
                ChannelFilter(16) >> Filter(CTRL) >> CtrlSplit({
                    # CC 119 Channel 16: load a app
                    119: Process(self.load_app),
                    # CC 118 Channel 16: load a app project
                    118: Process(self.app_load_project_request),
                    # CC 117 Channel 16, load next app project
                    117: Process(self.app_load_next_project_request),
                    # CC 116 Channel 16, load previous app project
                    116: Process(self.app_load_previous_project_request),
                    # CC 115 Channel 16, save current app project as...
                    115: Process(self.app_save_project_request)
                }),
                #Filter(PROGRAM) >> Process(self.app_program_change)
                ChannelFilter(1) >> Filter(NOTE, PROGRAM, CTRL) >> Port(1),
                ChannelFilter(2) >> Filter(NOTE, PROGRAM, CTRL) >> Port(2),
                ChannelFilter(3) >> Filter(NOTE, PROGRAM, CTRL) >> Port(3),
                ChannelFilter(4) >> Filter(NOTE, PROGRAM, CTRL) >> Port(4),
            ]
        )

    def run_manager(self):
        while True:
            time.sleep(500)

    def start_audio(self):
        # /usr/bin/jackd -P50 -r -p32 -t2000 -dalsa -dhw:0,0 -r48000 -p256 -n8 -S -Xseq (Raspberry PI2 onboard soundcard)
        # /usr/bin/jackd -R -P50 -p128 -t2000 -dalsa -dhw:CODEC -r48000 -p128 -n8 -Xseq (Behringer UCA202)
        #self.__jack = subprocess.Popen(['/usr/bin/jackd', '-P50', 't3000', '-dalsa', '-dhw:CODEC', '-r48000', '-p256', '-n8', '-Xseq'], shell=False)
        self.__jack = subprocess.Popen(['/usr/bin/jackd', '-P50', '-t3000', '-dalsa', '-dhw:0,0', '-r48000', '-p2048', '-n3', '-Xseq'], shell=False)
        #self.__jack = subprocess.Popen(['/usr/bin/jackd', '-P48', '-r', '-p256', '-t3000', '-dalsa', '-dplughw:0,0', '-r48000', '-p256', '-n3', '-S', '-s', '-Xseq'], shell=False)
        #self.__jack = subprocess.Popen(['/usr/bin/jackd', '-P63', '-r', '-p256', '-t3000', '-dalsa', '-dplughw:0,0', '-r48000', '-p128', '-n8', '-S', '-s', '-Xraw'], shell=False)
        time.sleep(1)
        self.setRealtime(self.__jack.pid, 2)
        time.sleep(2)
 
    def start_midi(self):
        # start mididings and a thread for midi input listening
        config(backend='jack-rt', client_name='OpenDSP', out_ports = 16)
        thread = threading.Thread(target=self.midi_listener, args=())
        thread.daemon = True
        thread.start()

        # start ttymidi   
        self.__ttymidi = subprocess.Popen(['/usr/bin/ttymidi', '-s', '/dev/ttyAMA0', '-b', '38400'], shell=False)
        self.setRealtime(self.__ttymidi.pid)
        time.sleep(2)
        
        # connect midi cables
        subprocess.call(['/usr/bin/jack_connect', 'OpenDSP:in_1', 'ttymidi:MIDI_in'], shell=False)
        #subprocess.call(['/usr/bin/jack_connect', 'OpenDSP:out_1', 'ttymidi:MIDI_out'], shell=False)
		
    def load_app(self, event):
        pass

    def start_app(self, app_name):
        self.__app_name = app_name
        module = importlib.import_module('opendspd.app.' + app_name)
        app_class = getattr(module, app_name)
        self.__app = app_class(self.__singleton__)
        self.__app.start()
