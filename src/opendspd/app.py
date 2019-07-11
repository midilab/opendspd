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

# for reference of opendsp.Core() singleton object
from opendspd import opendspd

class App:

    def __init__(self, config, app, connections):
        # OpenDSP Core singleton instance
        self.opendsp = self.opendsp = opendspd.Core()
        # config are all the user setup inside [appX] 
        self.config = config
        # app are the main data structure config of the running app
        self.app = app
        # running state memory
        self.data = {}
        # the state connections keeped by this app
        self.connections = connections
        self.connections_pending = connections

    def stop(self):
        # disconnect all jack ports
        for ports in self.connections:
            # allow user to regex port expression on jack clients that randon their port names
            origin = [ data.name for data in self.opendsp.jack.get_ports(ports['origin']) ]
            dest = [ data.name for data in self.opendsp.jack.get_ports(ports['dest']) ]
            if len(origin) > 0 and len(dest) > 0:
                self.opendsp.cmd("/usr/bin/jack_disconnect \"{port_origin}\" \"{port_dest}\"".format(port_origin=origin[0], port_dest=dest[0]))
        # kill the app process and clear object state
        self.data['proc'].terminate()
        del self.data
        self.data = {}

    def start(self):
        # init connections pending
        self.connections_pending = self.connections

        # setup app arguments
        argments = ""
        if 'args' in self.app:
            argments += "{args_app} ".format(args_app=self.app['args'])
        if 'args' in self.config:
            argments += "{args_config} ".format(args_config=self.config['args'])
        if 'project' in self.config:
            argments += "{arg_project} {path_project}{file_project} ".format(arg_project=self.app.get('project_arg', ""), path_project=self.app.get('path', ""), file_project=self.config['project'].replace(" ", "\\ "))

        # construct call
        call = "{cmd_call} {args}".format(cmd_call=self.app['bin'], args=argments).replace("\"", "")

        if 'display' in self.config:        
            # start the app with or without display
            if 'native' in self.config['display']:
                self.data['proc'] = self.opendsp.display(call)
            elif 'virtual' in self.config['display']:
                self.data['proc'] = self.opendsp.display_virtual(call)
        else:
            self.data['proc'] = self.opendsp.background(call)

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

    def load_project(self, project):
        try:
            # stop the current app process
            self.stop()
            # assign to config object
            self.config['project'] = project
            # restart it again
            self.start()
        except Exception as e:
            print("error trying to load project {name_project} on app {name_app}: {message_error}".format(name_project=project, name_app=self.app['name'], message_error=str(e)))

    def check_health(self):
        pass

    def connection_handler(self):
        # iterate over all connections that we need to watch
        connections_made = []
        for ports in self.connections_pending:
            # allow user to regex port expression on jack clients that randon their port names
            origin = [ data.name for data in self.opendsp.jack.get_ports(ports['origin']) ]
            dest = [ data.name for data in self.opendsp.jack.get_ports(ports['dest']) ]
            if len(origin) > 0 and len(dest) > 0:
                self.opendsp.cmd("/usr/bin/jack_connect \"{port_origin}\" \"{port_dest}\"".format(port_origin=origin[0], port_dest=dest[0]))                        
                connections_made.append(ports)
                print("app connect found: {port_origin} {port_dest}".format(port_origin=origin[0], port_dest=dest[0]))
            else:
                print("app connect looking for origin({port_origin}) and dest({port_dest})".format(port_origin=ports['origin'], port_dest=ports['dest']))
        # clear the connections made from connections to make   
        self.connections_pending = [ ports for ports in self.connections_pending if ports not in connections_made ]
