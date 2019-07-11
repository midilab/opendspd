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
import glob

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
        # the main app
        self.main_app = None
        # used to setup config['project'] requests that deals with subdirs
        self.path_project = ""
        # running state
        self.running = False
        # running thread
        self.thread = None

    def start(self):
        # construct a list of apps config objects to be used as mod apps ecosystem
        apps = { app: self.config_mod[app] for app in self.config_mod if 'app' in app }
        print(apps)
        # one app per config entry
        for app_id in apps:
            config = apps[app_id]
            name_app = config.get('name')
            if name_app in self.config_app:
                # app1 is used as main_app reference for project change requests
                if app_id == 'app1':
                    # this is the one used to handle projects on requests
                    self.main_app = name_app
                    if 'path' in config:
                        # get the project path for subdir support on user side
                        self.path_project = config['path']
                # generate our list of pair ports connection representation between apps
                connections = self.gen_conn(config, self.config_app[name_app])
                # instantiate App object and keep track of it on app map
                self.app[name_app] = app.App(config, self.config_app[name_app], connections)
                self.app[name_app].start()

        # thread the run method until we're dead
        self.thread = threading.Thread(target=self.run, args=(), daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
        # delete all Apps objects
        for app in self.app:
            self.app[app].stop()

    def run(self):
        self.running = True
        while self.running:
            # handler audio and midi connections from config_mod
            self.app_connection_handler()
            self.app_check_health()
            time.sleep(5)

    def get_projects(self):
        # only read project directory if we have a main app setup
        if self.main_app in self.app:
            dir_list = glob.glob("{path_data}/{path_project}/*".format(path_data=self.opendsp.path_data, path_project=self.path_project))
            return [ path_project.split("/")[-1] for path_project in sorted(dir_list) ]
        else:
            return []

    def load_project(self, project):
        # only load projects if we have a main app setup
        if self.main_app in self.app:
            self.app[self.main_app].load_project(project)
        else:
            print("No app1 setup for main app reference on projects")

    def app_check_health(self):
        for app in self.app:
            self.app[app].check_health()

    def app_connection_handler(self):
        for app in self.app:
            self.app[app].connection_handler()

    def gen_conn(self, config_app, app):
        conn_list = []
        # construct a list of all *_input and *_output ports
        ports_list = { port_type: config_app[port_type] for port_type in config_app if 'input' in port_type or 'output' in port_type }
        # iterate over each port and generate the concrete name of ports to connect
        for port_type in ports_list:
            # parse all ports by ',' and interate over then
            dest_port_list = ports_list[port_type].replace("\"", "").split(",")
            for index, dest_port in enumerate(dest_port_list):
                conn = { 'origin': '', 'dest': '' }
                port_type_dest = ""
                
                dest_data = dest_port.split(":")
                if len(dest_data) != 2:
                    continue

                # accessors
                name_app = config_app['name'].strip()
                name_dest = dest_data[0].strip()
                index_dest = int(dest_data[1])-1

                if 'audio_input' in port_type:
                    port_type_dest = 'audio_output'
                elif 'audio_output' in port_type:
                    port_type_dest = 'audio_input'
                elif 'midi_input' in port_type:
                    port_type_dest = 'midi_output'
                elif 'midi_output' in port_type:
                    port_type_dest = 'midi_input'
                else:
                    continue

                try:
                    conn['dest'] = self.config_app[name_app][port_type].replace("\"", "").split(",")[index].strip()
                    conn['origin'] = self.config_app[name_dest][port_type_dest].replace("\"", "").split(",")[index_dest].strip()
                except:
                    print("error, not enough data to generate port pairs")
                    continue
                
                conn_list.append(conn)

        return conn_list
