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
import logging

class App:

    def __init__(self, config, app, connections, opendsp):
        # OpenDSP Core instance
        self.opendsp = opendsp
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
        self.opendsp.jackd.disconnect(self.connections)
        # kill the app process and clear object state
        self.opendsp.stop_proc(self.data['proc'])
        del self.data
        self.data = {}

    def start(self):
        # setup cmd call and arguments
        call = self.app['bin'].split(" ")
        # ecosystem defined args
        if 'args' in self.app:
            call.extend(self.app['args'].split(" "))
        # project load parameter
        if 'project' in self.config:
            project_arg = "<prj>"
            path_project = [path
                            for path in self.config.get('path', "").split("/")
                            if path != '']
            project = "{data}/{path}/{project}".format(data=self.opendsp.path_data,
                                                       path="/".join(path_project),
                                                       project=self.config['project']).strip()
            if 'project_arg' in self.app:
                project_arg = self.app['project_arg']
            call.extend([prj.replace("<prj>", project)
                         for prj in project_arg.split(" ")])
        # mod defined args
        if 'args' in self.config:
            call.extend(self.config['args'].split(" "))

        # where are we going to run this app?
        if 'display' in self.config:
            self.data['proc'] = self.opendsp.start_proc(call, self.config['display'])
        else:
            self.data['proc'] = self.opendsp.start_proc(call)

        # set limits?
        if 'limits' in self.app:
            self.opendsp.set_limits(self.data['proc'].pid, self.app['limits'])

        # set realtime priority?
        if 'realtime' in self.app:
            self.opendsp.set_realtime(self.data['proc'].pid, int(self.app['realtime']))

        # generate a list from, parsed by ','
        if 'audio_input' in self.app:
            self.data['audio_input'] = [audio_input.strip()
                                        for audio_input in self.app['audio_input'].split(",")]
        if 'audio_output' in self.app:
            self.data['audio_output'] = [audio_output.strip()
                                         for audio_output in self.app['audio_output'].split(",")]
        if 'midi_input' in self.app:
            self.data['midi_input'] = [midi_input.strip()
                                       for midi_input in self.app['midi_input'].split(",")]
        if 'midi_output' in self.app:
            self.data['midi_output'] = [midi_output.strip()
                                        for midi_output in self.app['midi_output'].split(",")]

    def load_project(self, project):
        try:
            # stop the current app process
            self.stop()
            # assign to config object
            self.config['project'] = project
            # restart it again
            self.start()
        except Exception as e:
            logging.error("error loading project {project} on app {app}: {message}"
                          .format(project=project,
                                  app=self.app['name'],
                                  message=str(e)))

    def check_health(self):
        pass

    def connection_handler(self):
        # any pending connections to handle?
        if len(self.connections_pending) > 0:
            # generic opendsp call to connect port pairs, returns the non connected ports - still pending...
            self.connections_pending = self.opendsp.jackd.connect(self.connections_pending)

    def connection_reset(self):
        # reset made up connection only
        if len(self.connections_pending) < len(self.connections):
            # ask opendsp core to do so...
            self.opendsp.jackd.disconnect(self.connections)
        # reset connections pending
        self.connections_pending = self.connections
