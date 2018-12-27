# -*- coding: utf-8 -*-

# OpenDSP Plugmod Application
# Copyright (C) 2015-2018 Romulo Silva <contact@midilab.co>
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

import time, subprocess, os, socket, glob

# import abstract App class interface
from . import App

class djing(App):

    __mixxx = None
    __ingen_socket = None
    __ecasound = None

    __app_path = 'djing'
    __project_bundle = None

    # addons
    # internal mixer mode use ecasound as main virtual mixing console
    # external mixer mode directs each module output to his mirroed number on system output
    __mixer = None # external, no internal mixer is the default 'internal' # 'external'
    __visualizer = None
    __is_visual_on = False
    
    __opendsp_midi_connected = False
    
    __project = None
    __bank = None
    
    def get_midi_processor(self):
        # realtime midi processing routing rules - based on mididings environment
        self.__midi_processor = str(1) + ": Channel(1) >> Port(1)"
        return self.__midi_processor 

    def start(self):

        if "visualizer" in self.params:   
            self.__visualizer = self.params["visualizer"]   

        # we need the --developer option to enable midi through alsa interface
        self.__mixxx = self.odsp.start_virtual_display_app('/usr/bin/mixxx -f --developer')
        #time.sleep(10)
        #self.odsp.setRealtime(self.__mixxx.pid)
        
    def run(self):
     
        if self.__opendsp_midi_connected == False:
            self.jack.connect('OpenDSP_RT:out_1', 'alsa_midi:Midi Through Port-0 (in)')
            self.__opendsp_midi_connected = True
                    
        # do we want to start visualizer?
        if self.__visualizer != None and self.__is_visual_on == False:
            # for now only "projectm", so no check...
            projectm = self.odsp.start_display_app('/usr/bin/projectM-jack')
            self.odsp.setRealtime(self.projectm.pid, -50)
            # wait projectm to comes up and them set it full screen
            time.sleep(20)
            subprocess.call(['/usr/bin/xdotool', 'key', 'f'], shell=True)
            # jump to next
            subprocess.call(['/usr/bin/xdotool', 'key', 'n'], shell=True)
            # lock preset
            subprocess.call(['/usr/bin/xdotool', 'key', 'l'], shell=True)
            self.__is_visual_on = True
               
        while True:
            time.sleep(5)

    def stop(self):
        #client.close()
        pass

    def load_project(self, project):
        pass
        
    def save_project(self, project):
        pass

    def load_project_request(self, event):
        self.load_project(event.data2)

    def save_project_request(self, event):
        self.save_project(event.data2)

    def program_change(self, event): #program, bank):
        pass
        #print("opendsp event incomming: " + str(event.data1) + ":" + str(event.data2) + ":" + str(event.channel) + ":" + str(event.type))
