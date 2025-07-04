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
import subprocess
import glob
import logging

# main App class
from . import app

class Mod:

    def __init__(self, name_mod, config_mod, ecosystem, opendsp):
        # OpenDSP Core instance
        self.opendsp = opendsp
        self.name = name_mod
        # config_mod is a modular collection configuration of ecosystem
        self.config = config_mod
        # ecosystem are all the applications avaliable to load into mod
        self.ecosystem = ecosystem
        # automations for app init
        self.init_map = {}
        # loaded apps midi_map dict
        self.midi_map = {}
        # App objects map
        self.app = {}
        # the main app
        self.main_app = None
        # used to setup config['project'] requests that deals with subdirs
        self.path = "/".join([self.opendsp.path_data, 'mod', name_mod])
        self.path_project = ""
        self.ext_project = ""
        # running state
        self.running = False
        # running thread
        self.thread = None

    def stop(self):
        self.running = False
        # delete all Apps objects
        for app_id in self.app:
            self.app[app_id].stop()

    def start(self):
        # construct a dict of apps config objects to be used as mod apps ecosystem
        apps = {app: self.config[app]
                for app in self.config if 'app' in app}

        # one app per config entry
        for app_id in apps:
            config = apps[app_id]
            name_app = config.get('name')
            if name_app in self.ecosystem:
                # parse config app
                config_app = self.parse_config_app(app_id, self.ecosystem[name_app])
                # app1 is used as main_app reference for project change requests
                if app_id == 'app1':
                    # this is the one used to handle projects on requests
                    self.main_app = app_id
                    if 'path' in config:
                        # project path is relative to mod directory
                        self.path_project = "/".join([self.path, config['path']])
                    if 'extension' in self.ecosystem[name_app]:
                        self.ext_project = self.ecosystem[name_app]['extension']
                # generate our list of pair ports connection representation between apps
                connections = self.gen_conn(app_id, config, config_app)
                # instantiate App object and keep track of it on app map
                self.app[app_id] = app.App(config, config_app, connections, self.path, self.opendsp)
                self.app[app_id].start()

        # creates midi_map
        self.create_midi_map()

        # any init command to automate?
        self.create_init_map()

        # thread the run method until we're dead
        self.thread = threading.Thread(target=self.run,
                                       daemon=True,
                                       args=())
        self.thread.start()

        # Run init commands for all apps after loading the project
        # wait a bit since not all apps should be fully initialized
        # TODO: implement a watch solution instead for init and close
        time.sleep(10)
        for app_id in self.init_map:
            for cmd in self.init_map[app_id]:
                self.run_map_action(cmd, app_id=app_id)

    def run(self):
        self.running = True
        while self.running:
            # handler audio and midi connections from config
            self.connection_handler()
            self.check_health()
            time.sleep(5)

    def run_map_action(self, action, app_id=None):
        """
        Runs a single mapped action command
        Based on xdotool - Read the manual
        """
        if app_id is None or not hasattr(self, 'opendsp') or self.opendsp.mod is None:
            logging.warning("No app_id provided or mod not loaded")
            return
        #
        env_display = 0
        if 'display' in self.app[app_id].config:
            if self.app[app_id].config['display'] == 'virtual':
                env_display = 1
        environment = { "DISPLAY": f":{env_display}" }

        # Normalize input to list format
        if isinstance(action, str):
            cmd = ["xdotool"] + action.strip().split()
        elif isinstance(action, list):
            cmd = ["xdotool"] + action
        else:
            logging.error(f"Invalid action type: {type(action)}")
            return

        # Run command with proper environment
        try:
            logging.debug(f"Running xdotool command: {' '.join(cmd)} [DISPLAY={env_display}]")
            subprocess.call(cmd, shell=False, env=environment)
        except Exception as e:
            logging.error(f"Failed to run command for app {app_id}: {cmd}, error: {e}")

    def load_project(self, project):
        # only load projects if we have a main app setup
        if self.main_app in self.app:
            # reset connections to force new ones before load new project
            self.connection_reset()
            self.app[self.main_app].load_project(project)
            # save mod state
            self.opendsp.save_mod()
        else:
            logging.info("No app1 setup for main app reference on projects")

    def get_projects(self):
        # only read project directory if we have a main app setup
        if self.main_app in self.app:
            dir_list = glob.glob("{path_project}/*{extension}"
                                 .format(path_project=self.path_project,
                                         extension=self.ext_project))
            return [os.path.basename(path_project)
                    for path_project in sorted(dir_list)]
        else:
            return []

    def get_project_by_idx(self, idx):
        # only read project directory if we have a main app setup
        if self.main_app in self.app:
            projects = self.get_projects()
            size = len(projects)
            if size > 0:
                return projects[idx % size]
        else:
            return None

    def get_mods(self):
        # sorted list of installed mods inside mod path
        return sorted(next(os.walk("{path_data}/mod/"
                                   .format(path_data=self.opendsp.path_data)))[1])

    def get_mod_by_idx(self, idx):
        mods = self.get_mods()
        size = len(mods)
        if size > 0:
            return mods[idx%size]
        return None

    def check_health(self):
        for app in self.app:
            self.app[app].check_health()

    def connection_handler(self):
        for app in self.app:
            self.app[app].connection_handler()

    def connection_reset(self):
        for app in self.app:
            self.app[app].connection_reset()

    def parse_config_app(self, app_id, config):
        # parse id requests only for now...
        return {option: config[option].replace('<id>', app_id)
                for option in config}

    def create_midi_map(self):
        """
        Pre-process all midi_map entries from apps into a single flat dict:
            {'cc34': [{'app_id': 'app1', 'cmd': 'key f'}, ...], ...}
        """
        self.midi_map = {}

        for app_id in self.app:
            app = self.app[app_id]
            if hasattr(app, 'config') and 'midi_map' in app.config:
                lines = [line.strip() for line in app.config['midi_map'].split(',') if line.strip()]
                for line in lines:
                    if ':' in line:
                        cc_part, cmd = line.split(':', 1)
                        cc_key = cc_part.strip().lower()
                        # Split multiple cmds per CC
                        cmds = [c.strip() for c in cmd.split(',') if c.strip()]
                        for c in cmds:
                            entry = {'app_id': app_id, 'cmd': c}
                            if cc_key not in self.midi_map:
                                self.midi_map[cc_key] = []
                            self.midi_map[cc_key].append(entry)

    def create_init_map(self):
        """
        Creates a map of initialization commands grouped by app_id.

        Example:
            {
                'app1': ['key g', 'key ctrl+c'],
                'app2': ['key f']
            }
        """
        self.init_map = {}

        # Iterate over all apps in the mod
        for app_id in self.app:
            app = self.app[app_id]
            if hasattr(app, 'config') and 'init' in app.config:
                # Split init line by commas and strip whitespace
                lines = [line.strip() for line in app.config['init'].split(',') if line.strip()]
                if lines:
                    self.init_map[app_id] = lines

    def parse_conn(self, conn_string):
        connections = conn_string.replace('"', '')
        return [conn.strip()
                for conn in connections.split(",")]

    def gen_conn(self, id_app, config_app, app):
        """Genarates Connection Pairs
        generates a list of jack based connections pairs
        to be used for auto connection support
        """
        conn_list = []
        # construct a dict of all *_input and *_output ports
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
                    conn['origin'] = self.parse_conn(self.ecosystem[name_app][port_type])[index]
                    conn['dest'] = self.parse_conn(self.ecosystem[name_dest][port_type_dest])[index_dest]
                except Exception as e:
                    logging.error("error, not enough data to generate port pairs: {message}"
                                  .format(message=str(e)))
                    continue

                conn_list.append(conn)

        return conn_list
