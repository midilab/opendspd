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
import os
import time
import threading
import glob
import logging

# main App class
from . import app

class Mod:

    def __init__(self, config_mod, config_app, opendsp):
        # OpenDSP Core singleton instance
        self.opendsp = opendsp
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

    def parse_config_app(self, id, config):
        # parse id requests only for now...
        return {option: config[option].replace('<id>', id)
                for option in config}

    def start(self):
        # construct a dict of apps config objects to be used as mod apps ecosystem
        apps = {app: self.config_mod[app]
                for app in self.config_mod if 'app' in app}

        # one app per config entry
        for app_id in apps:
            config = apps[app_id]
            name_app = config.get('name')
            if name_app in self.config_app:
                # parse config app
                config_app = self.parse_config_app(app_id, self.config_app[name_app])
                # app1 is used as main_app reference for project change requests
                if app_id == 'app1':
                    # this is the one used to handle projects on requests
                    self.main_app = app_id
                    if 'path' in config:
                        # get the project path for subdir support on user side
                        self.path_project = config['path']
                # generate our list of pair ports connection representation between apps
                connections = self.gen_conn(app_id, config, config_app)
                # instantiate App object and keep track of it on app map
                self.app[app_id] = app.App(config, config_app, connections, self.opendsp)
                self.app[app_id].start()

        # thread the run method until we're dead
        self.thread = threading.Thread(target=self.run, args=(), daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
        # delete all Apps objects
        for app_id in self.app:
            self.app[app_id].stop()

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
            dir_list = glob.glob("{path_data}/{path_project}/*"
                                 .format(path_data=self.opendsp.path_data,
                                         path_project=self.path_project))
            return [os.path.basename(path_project)
                    for path_project in sorted(dir_list)]
        else:
            return []

    def load_project(self, project):
        # only load projects if we have a main app setup
        if self.main_app in self.app:
            # reset connections to force new ones before load new project
            self.app_connection_reset()
            self.app[self.main_app].load_project(project)
        else:
            logging.info("No app1 setup for main app reference on projects")

    def app_check_health(self):
        for app in self.app:
            self.app[app].check_health()

    def app_connection_handler(self):
        for app in self.app:
            self.app[app].connection_handler()

    def app_connection_reset(self):
        for app in self.app:
            self.app[app].connection_reset()

    def parse_conn(self, conn_string):
        connections = conn_string.replace("\"", "")
        return [conn.strip() for conn in connections.split(",")]

    def gen_conn(self, id_app, config_app, app):
        conn_list = []
        # construct a list of all *_input and *_output ports
        ports_list = {port_type: config_app[port_type]
                      for port_type in config_app
                      if 'input' in port_type or 'output' in port_type}
        # iterate over each port and generate the concrete name of ports to connect
        for port_type in ports_list:
            dest_port_list = self.parse_conn(ports_list[port_type])
            for index, dest_port in enumerate(dest_port_list):
                conn = {}
                port_type_dest = ""

                dest_data = dest_port.split(":")
                if len(dest_data) != 2:
                    continue

                # key accessors
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
                    conn['origin'] = self.parse_conn(self.config_app[name_app][port_type])[index]
                    conn['dest'] = self.parse_conn(self.config_app[name_dest][port_type_dest])[index_dest]
                except Exception as e:
                    logging.error("error, not enough data to generate port pairs: {message}"
                                  .format(message=str(e)))
                    continue

                conn_list.append(conn)

        return conn_list
