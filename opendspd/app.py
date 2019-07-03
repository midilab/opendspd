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
#...

# for reference of opendsp.Core() singleton object
from opendspd import opendspd

class App:

    def __init__(self, config, app):
        # OpenDSP Core singleton instance
        self.opendsp = self.opendsp = opendspd.Core()
        # config are all the user setup inside [appX] 
        self.config = config
        # app are the main data structure config of the running app
        self.app = app
        # running state memory
        self.data = {}

    def __del__(self):
        self.data['proc'].kill()

    def start(self):
        cmd = self.app['bin'].replace("\"", "")
        argments = None

        if 'project' in self.config:
            argments = "{0}{1}".format(self.app['path'], self.config['project'].replace("\"", ""))
                
        if 'display' in self.config:        
            # start the app with or without display
            if 'native' in self.config['display']:
                self.data['proc'] = self.opendsp.display(cmd, argments)
            elif 'virtual' in self.config['display']:
                self.data['proc'] = self.opendsp.display_virtual(cmd, argments)
        else:
            self.data['proc'] = self.opendsp.background(cmd, argments)

        # generate a list from, parsed by ','
        if 'audio_input' in self.app:
            self.data['audio_input'] = [ audio_input for audio_input in self.app['audio_input'].split(",") ]
        if 'audio_output' in self.app:
            self.data['audio_output'] = [ audio_output for audio_output in self.app['audio_output'].split(",") ]
        if 'midi_input' in self.app:
            self.data['midi_input'] = [ midi_input for midi_input in self.app['midi_input'].split(",") ]
        if 'midi_output' in self.app:
            self.data['midi_output'] = [ midi_output for midi_output in self.app['midi_output'].split(",") ]

        if 'realtime' in self.app:
            self.opendsp.set_realtime(self.data['proc'].pid, int(self.app['realtime']))  

