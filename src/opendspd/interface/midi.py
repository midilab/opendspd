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
import sys
import time
import datetime
import subprocess
import threading
import importlib
import glob
import signal
import psutil
import configparser
import logging

# MIDI Support
from mididings import *
import rtmidi

class MidiInterface():
    """
    ...
    """

    def __init__(self, opendsp):
        self.opendsp = opendsp
        #self.config = opendsp.config['system']['midi']
        # connections state
        self.connections = []
        self.connections_pending = []
        # manage the internal state of user midi input auto connections
        self.hid_devices = []
        self.blacklist = ['OpenDSP',
                          'alsa_midi:Midi Through Port-0',
                          'ttymidi']
        # midi standard cmd byte definitions
        self.midi_cmd = {'cc': 0xB0,
                         'note_on': 0x90,
                         'note_off': 0x80,
                         'pitch_bend': 0xE0,
                         'program_change': 0xC0}
        # all procs and threads references managed by opendsp
        self.proc = {}
        self.thread = {}

    def stop(self):
        # disconnect all ports
        for port in self.connections:
            self.opendsp.jackd.disconnect(self.connections)
        # destroying rtmidi object
        del self.midi_out
        # stop all procs
        for proc in self.proc:
            self.proc[proc].terminate()

    def start(self):
        # start mididings and a thread for midi input user control and feedback listening
        config(backend='jack', client_name='OpenDSP', in_ports=1)
        self.thread['processor'] = threading.Thread(target=self.processor,
                                                         daemon=True,
                                                         args=())
        self.thread['processor'].start()

        channel_list = ", ".join(["{chn}: Channel(1) >> Port({chn})".format(chn=channel)
                                  for channel in range(1, 17)])
        rules = "ChannelSplit({{ {rule_list} }})".format(rule_list=channel_list)

        # call mididings and set it realtime alog with jack - named midi
        self.proc['mididings'] = self.opendsp.run_background(['/usr/bin/mididings',
                                                              '-R', '-c', 'midiRT', '-o', '16', rules])

        # set it +4 for realtime priority
        self.opendsp.set_realtime(self.proc['mididings'].pid, 4)

        # channel 16 are mean to control opendsp interface
        self.port_add('midiRT:out_16', 'OpenDSP:in_1')

        # virtual midi output port for generic usage
        self.midi_out = rtmidi.MidiOut()
        # creates alsa_midi:RtMidiOut Client opendsp (out)
        self.midi_out.open_virtual_port("opendsp")
        # add to state
        #self.port_add('alsa_midi:RtMidiOut', 'midiRT:in_1')

        # start on-board midi? (only if your hardware has onboard serial uart)
        if 'midi' in self.opendsp.config['system']:
            # run on background
            self.proc['onboard'] = self.opendsp.run_background(['/usr/bin/ttymidi',
                                                                '-s', self.opendsp.config['system']['midi']['device'],
                                                                '-b', self.opendsp.config['system']['midi']['baudrate']])
            # set it +4 for realtime priority
            self.opendsp.set_realtime(self.proc['onboard'].pid, 4)

            # add to state
            self.port_add('ttymidi:MIDI_in', 'midiRT:in_1')

        # local midi ports to avoid auto connect
        for app_name in self.opendsp.config['app']:
            if 'midi_output' in self.opendsp.config['app'][app_name]:
                connections = self.opendsp.config['app'][app_name]['midi_output'].replace('"', '')
                self.blacklist.extend([conn.strip() for conn in connections.split(",")])

    def send_message(self, cmd, data1, data2, channel):
        if cmd in self.midi_cmd:
            status = (self.midi_cmd[cmd] & 0xf0) | ((channel-1) & 0xf0)
            message = (status, data1, data2)
            logging.debug("sending midi message {cmd}: {message}".format(cmd=cmd,
                                                                         message=message))
            self.midi_out.send_message(message)

    def midi_queue(self, event):
        # PROGRAM CHANGE messages: for project change at mod level
        if hasattr(event, 'program'):
            if self.opendsp.mod is not None:
                project = self.opendsp.mod.get_project_by_idx(event.program-1)
                if project is not None:
                    self.opendsp.mod.load_project(project)
            return

        # CTRL messages interface
        if hasattr(event, 'ctrl'):
            # change selector - register last received value
            # change mod action (double press to trigger?)
            # change project action (double press to trigger?)

            if event.ctrl == 120:
                if self.opendsp.mod is not None:
                    mod = self.opendsp.mod.get_mod_by_idx(event.value)
                    if mod is not None:
                        self.opendsp.load_mod(mod)
                return
            #if event.ctrl == 114:
            #    # restart opendspd
            #    subprocess.call('/sbin/sudo /usr/bin/systemctl restart opendsp', shell=True)
            #    return

    def processor(self):
        # opendsp midi controlled via program changes and cc messages on channel 16
        run([PortFilter(1) >> Filter(PROGRAM|CTRL) >> Call(thread=self.midi_queue)])

    def handle(self):
        """Midi handler
        called by core on each run cycle
        """
        self.lookup()
        self.connections_pending = self.opendsp.jackd.connect(self.connections_pending)

    def lookup(self):
        """Hid Lookup
        take cares of user on the fly
        hid devices connections
        """
        jack_midi_lsp = [data.name
                         for data in self.opendsp.jackd.client.get_ports(is_midi=True, is_output=True)
                         if all(port.replace("\\", "") not in data.name for port in self.blacklist)]

        for midi_port in jack_midi_lsp:
            midi_port = midi_port.replace(" ", "\\ ").replace("(", "\\(").replace(")", "\\)")
            if midi_port in self.hid_devices:
                continue
            try:
                logging.info("opendsp hid device auto connect: {name_port} -> midiRT:in_1"
                             .format(name_port=midi_port))
                self.port_add(midi_port, 'midiRT:in_1')
                self.hid_devices.append(midi_port)
            except:
                pass

    def port_add(self, origin, dest):
        """Connection Port Add
        create a new connection state to handle
        """
        connection = {'origin': origin, 'dest': dest}
        self.connections.append(connection)
        self.connections_pending.append(connection)
