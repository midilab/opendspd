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

import jack

class JackdInterface():
    """
    ...
    """

    def __init__(self, opendsp):
        self.opendsp = opendsp
        self.config = opendsp.config['system']['audio']
        self.sys_config = opendsp.config['system']['system']
        self.client = None
        self.proc = {}
        self.running = False

    def stop(self):
        # stop all process
        for proc in self.proc:
            self.opendsp.stop_proc(self.proc[proc])
        # reset proc
        del self.proc
        self.proc = {}
        # set running state
        self.running = False

    def start(self):
        # start jack server
        self.proc['jackd'] = self.opendsp.start_proc(['/usr/bin/jackd',
                                                      '-R', '-t10000', '-dalsa',
                                                      '-d', self.config['hardware'],
                                                      '-r', self.config['rate'],
                                                      '-p', self.config['buffer'],
                                                      '-n', self.config['period'],
                                                      '-S',
                                                      '-Xseq'])
        
        # set cpu afinnity? 
        self.opendsp.set_cpu(self.proc['jackd'].pid, self.sys_config['cpu'])

        # set it +4 for realtime priority
        self.opendsp.set_realtime(self.proc['jackd'].pid, 4)

        # start jack client
        self.client = jack.Client('opendsp_jack')
        self.client.activate()

        # set running state
        self.running = True

    def connect(self, connections_pending):
        connections_made = []
        for ports in connections_pending:
            # allow user to regex port expression on jack clients that randon their port names
            origin = [data.name for data in self.client.get_ports(ports['origin'])]
            dest = [data.name for data in self.client.get_ports(ports['dest'])]

            if len(origin) > 0 and len(dest) > 0:
                # port pair already connected? append it to connections_made
                jack_ports = [port.name
                              for port in self.client.get_all_connections(dest[0])
                              if port.name == origin[0]]
                if len(jack_ports) > 0:
                    connections_made.append(ports)
                    continue

                try:
                    self.opendsp.call("/usr/bin/jack_connect \"{port_origin}\" \"{port_dest}\""
                             .format(port_origin=origin[0], port_dest=dest[0]))
                    connections_made.append(ports)
                    logging.info("connect handler found: {port_origin} {port_dest}"
                                 .format(port_origin=origin[0], port_dest=dest[0]))
                except Exception as e:
                    logging.error("error on auto connection: {message}"
                                  .format(message=e))
            else:
                logging.info("connect handler looking for origin({port_origin}) and dest({port_dest})"
                             .format(port_origin=ports['origin'], port_dest=ports['dest']))
        # return connections made successfully
        return [ports for ports in connections_pending if ports not in connections_made]

    def disconnect(self, connections):
        for ports in connections:
            try:
                # allow user to regex port expression on jack clients that randon their port names
                origin = [data.name for data in self.client.get_ports(ports['origin'])]
                dest = [data.name for data in self.client.get_ports(ports['dest'])]
                if len(origin) > 0 and len(dest) > 0:
                    self.opendsp.call("/usr/bin/jack_disconnect \"{port_origin}\" \"{port_dest}\""
                             .format(port_origin=origin[0], port_dest=dest[0]))
            except Exception as e:
                logging.error("error on reset disconnection: {message}"
                              .format(message=e))
