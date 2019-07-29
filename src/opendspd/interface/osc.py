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

    @make_method('/sys', 's')
    def sys_call(self, path, args):
        call = args[0]
        #self.opendsp.sys_call(call)
        logging.debug("sys call received '%s'" % path)

    @make_method('/mod', 'i')
    def mod_call(self, path, args):
        logging.debug("received message '%s'" % path)
        mod_id = args[0]
        if self.opendsp.mod is not None:
            mod = self.opendsp.mod.get_mod_by_idx(mod_id)
            if mod is not None:
                self.opendsp.load_mod(mod)

    @make_method('/prj', 'i')
    def prj_call(self, path, args):
        logging.debug("received message '%s'" % path)
        project_id = args[0]
        if self.opendsp.mod is not None:
            project = self.opendsp.mod.get_project_by_idx(project_id)
            if project is not None:
                self.opendsp.mod.load_project(project)

    @make_method('/midi', 'siii')
    def midi_call(self, path, args):
        logging.debug("OscInterface '%s'" % path)
        cmd, channel, data1, data2 = args
        if cmd in self.opendsp.midi.midi_cmd:
            self.opendsp.midi.send_message(cmd, data1, data2, channel)

    @make_method(None, None)
    def fallback(self, path, args):
        logging.debug("received unknown message '%s'" % path)
