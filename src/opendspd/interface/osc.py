# -*- coding: utf-8 -*-

# OpenDSP OSC Interface
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
import logging

# OSC Support
from liblo import *

class OscInterface(ServerThread):

    def __init__(self, opendsp):
        self.opendsp = opendsp
        self.config = opendsp.config['system']['osc']
        ServerThread.__init__(self, self.config['port'])

    @make_method('/opendsp/system/restart', '')
    def system_restart(self, path, args):
        """/opendsp/system/restart"""
        # restart opendspd
        self.opendsp.restart()

    @make_method('/opendsp/display/force_screen', 's')
    def display_force_screen(self, path, args):
        """/opendsp/display/force_screen ['native' | 'virtual' | 'off']"""
        screen = args[0]
        # force display
        logging.info("force screen!")
        if screen == 'off' and 'force_display' in self.opendsp.config['system']['system']:
            del self.opendsp.config['system']['system']['force_display']
        else:
            self.opendsp.config['system']['system']['force_display'] = screen
        self.opendsp.save_system()
        self.opendsp.restart()

    @make_method('/opendsp/display/force_on', 's')
    def display_force_on(self, path, args):
        """/opendsp/display/force_on ['native' | 'virtual' | 'native, virtual' | 'off']"""
        logging.debug("forcing dsiplay on: %s" % args[0])

    @make_method('/opendsp/mod/load', 'ii')
    def mod_load(self, path, args):
        """/opendsp/mod/load [module_id] [module_bank]"""
        logging.debug("Loading module > '%s'" % path)
        mod_id, mod_bank = args
        if self.opendsp.mod is not None:
            mod = self.opendsp.mod.get_mod_by_idx(mod_id)
            if mod is not None:
                self.opendsp.load_mod(mod)

    @make_method('/opendsp/project/load', 'ii')
    def prj_call(self, path, args):
        """/opendsp/project/load [project_id] [project_bank]"""
        logging.debug("Loading project > '%s'" % path)
        project_id, project_bank = args
        if self.opendsp.mod is not None:
            project = self.opendsp.mod.get_project_by_idx(project_id)
            if project is not None:
                self.opendsp.mod.load_project(project)

    @make_method('/opendsp/osc2midi', 'siii')
    def midi_call(self, path, args):
        logging.debug("OSC-to-MIDI > '%s'" % path)
        cmd, channel, data1, data2 = args
        if cmd in self.opendsp.midi.midi_cmd:
            self.opendsp.midi.send_message(cmd, data1, data2, channel)

    @make_method(None, None)
    def fallback(self, path, args):
        logging.debug("received unknown message '%s'" % path)
