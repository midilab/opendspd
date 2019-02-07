# -*- coding: utf-8 -*-

# OpenDSP Djing Application
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
import time
import subprocess
import os
import socket
import glob

# import abstract App class interface
from . import App

class djing(App):

    mixxx = None

    app_path = 'djing'
    midi_channel = 14
    
    project_bundle = None

    opendsp_midi_connected = False
    
    project = None
    bank = None

    def start(self):
        # we need the --developer option to enable midi through alsa interface
        if 'midi' in self.opendsp.config:
            self.mixxx = self.opendsp.virtual_display('/usr/bin/mixxx --developer')
        else:
            self.mixxx = self.opendsp.virtual_display('/usr/bin/mixxx')
        time.sleep(10)
        self.opendsp.set_realtime(self.mixxx.pid)
        
    def run(self):
        if self.opendsp.visualizer_proc != None and self.visualizer_on == False:
            try:
                self.opendsp.jack.connect('Mixxx:out_0', 'projectM-jack:input')
                self.opendsp.jack.connect('Mixxx:out_1', 'projectM-jack:input')
                self.visualizer_on = True
            except:
                pass
        if self.opendsp_midi_connected == False:
            try:
                self.opendsp.jack.connect('OpenDSP_RT:out_1', 'alsa_midi:Midi Through Port-0 (in)')
                self.opendsp_midi_connected = True
            except:
                pass

    def stop(self):
        pass

    def __del__(self):
        self.mixxx.kill()
            
    def get_midi_processor(self):
        # realtime midi processing routing rules - based on mididings environment
        return "{channel}: Channel(1) >> Port(1)".format(channel=self.midi_channel)

    # CTRL events on channel MIDI_CHANNEL
    def midi_processor_queue(self, event):
        #event.value
        #event.data1
        #event.data2
        #event.channel
        #event.type
        if event.ctrl == 119:
            return

    def load_project(self, project):
        pass
        
    def save_project(self, project):
        pass

    def program_change(self, program, bank):
        pass
