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
import time
import threading

# for reference of opendsp.Core() singleton object
from opendspd import opendspd

# main App class
from . import app

class Mod:

    def __init__(self, config_mod, config_app):
        # OpenDSP Core singleton instance
        self.opendsp = self.opendsp = opendspd.Core()
        # config_mod is a modular collection configuration of config_app
        self.config_mod = config_mod
        # config_app are all the applications avaliable to load into mod
        self.config_app = config_app
        # App objects map
        self.app = {}
        # running state
        self.running = False
        # running thread
        self.thread = None

    def __del__(self):
        self.running = False
        # delete all Apps objects
        for app in self.app:
            del app

    def start(self):
        # construct a list of apps config objects to be used as mod apps ecosystem
        apps = [ self.config_mod[app] for app in self.config_mod if 'app' in app ]
        # one app per config entry
        for config in apps:
            name_app = config.get('name')
            if name_app in self.config_app:
                # instantiate App object and keep track of it on app map
                self.app[name_app] = app.App(config, self.config_app[name_app])
                self.app[name_app].start()

        # thread the run method until we're dead
        self.thread = threading.Thread(target=self.run, args=(), daemon=True)
        self.thread.start()

    def run(self):
        self.running = True
        while self.running:
            time.sleep(5)
            # manage connections
            #self.opendsp.jack()...
