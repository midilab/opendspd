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
        # midi standard cmd byte definitions
        self.midi_cmd = {'cc': 0xB0,
                         'note_on': 0x90,
                         'note_off': 0x80,
                         'pitch_bend': 0xE0,
                         'program_change': 0xC0}
        # all procs and threads references managed by opendsp
        self.proc = {}
        self.devices = {}
        self.thread = {}
        # midi registers
        self.midi_register = {'mod_id': 0,
                         'bank_id': 0,
                         'project_id': 0}

    def stop(self):
        # disconnect all ports
        for port in self.connections:
            self.opendsp.jackd.disconnect(self.connections)
        # destroying rtmidi object
        del self.midi_out
        # stop all procs
        for proc in self.proc:
            self.opendsp.stop_proc(self.proc[proc])
        del self.proc
        self.proc = {}
        # stop all midi devices
        for device in self.devices:
            self.opendsp.stop_proc(self.devices[device])
        del self.devices
        self.devices = {}
        # stop threads
        #...

    def start(self):
        # start a2jmidid to bridge midi data
        self.proc['a2jmidid'] = self.opendsp.start_proc(['/usr/bin/a2jmidid', '-u'])
        # set cpu afinnity
        if 'cpu' in self.opendsp.config['system']['system']:
            self.opendsp.set_cpu("a2jmidid", self.opendsp.config['system']['system']['cpu'])
        # set it +4 for realtime priority
        if 'realtime' in self.opendsp.config['system']['system']:
            self.opendsp.set_realtime("a2jmidid", 4)

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
        self.proc['mididings'] = self.opendsp.start_proc(['/usr/bin/mididings',
                                                          '-R', '-c', 'midiRT', '-o', '16', rules])

        # set cpu afinnity
        if 'cpu' in self.opendsp.config['system']['system']:
            self.opendsp.set_cpu("mididings", self.opendsp.config['system']['system']['cpu'])
        # set it +4 for realtime priority
        if 'realtime' in self.opendsp.config['system']['system']:
            self.opendsp.set_realtime("mididings", 4)

        # channel 16 are mean to control opendsp interface
        self.port_add('midiRT:out_16', 'OpenDSP:in_1')

        # virtual midi output port for generic usage
        self.midi_out = rtmidi.RtMidiOut()
        # creates alsa_midi:RtMidiOut Client opendsp (out)
        self.midi_out.openVirtualPort("opendsp")
        # add to state
        #self.port_add('alsa_midi:RtMidiOut', 'midiRT:in_1')

        # start on-board midi? (only if your hardware has onboard serial uart)
        if 'midi' in self.opendsp.config['system']:
            # run on background
            self.proc['onboard'] = self.opendsp.start_proc(['/usr/bin/ttymidi',
                                                            '-s', self.opendsp.config['system']['midi']['device'],
                                                            '-b', self.opendsp.config['system']['midi']['baudrate']])
            
            # set cpu afinnity
            if 'cpu' in self.opendsp.config['system']['system']:
                self.opendsp.set_cpu("ttymidi", self.opendsp.config['system']['system']['cpu'])
            # set it +4 for realtime priority
            if 'realtime' in self.opendsp.config['system']['system']:
                self.opendsp.set_realtime("ttymidi", 4)

            # add to state
            self.port_add('ttymidi:MIDI_in', 'midiRT:in_1')

    def send_message(self, cmd, data1, data2, channel):
        if cmd in self.midi_cmd:
            status = (self.midi_cmd[cmd] & 0xf0) | ((channel-1) & 0xf0)
            message = (status, data1, data2)
            logging.debug("sending midi message {cmd}: {message}"
                          .format(cmd=cmd, message=message))
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

            # MOD manage: 3 CCs, 2 interfaces
            if event.ctrl == 79:
                # change mod by value
                if self.opendsp.mod is not None:
                    mod = self.opendsp.mod.get_mod_by_idx(event.value)
                    if mod is not None:
                        self.opendsp.load_mod(mod)
                return
            if event.ctrl == 85:
                # change mod select CC: select mod(knob)
                self.midi_register['mod_id'] = event.value
                return
            if event.ctrl == 86:
                # change mod by select CC: change mod(button)
                if self.opendsp.mod is not None:
                    mod = self.opendsp.mod.get_mod_by_idx(self.midi_register['mod_id'])
                    if mod is not None:
                        self.opendsp.load_mod(mod)
                return

            # MOD Project: manage 4 CCs, 2 interfaces
            if event.ctrl == 87:
                # change project by value
                if self.opendsp.mod is not None:
                    project = self.opendsp.mod.get_project_by_idx(event.value)
                    if project is not None:
                        self.opendsp.mod.load_project(project)
                return
            if event.ctrl == 88:
                # change project bank id CC: selec project bank(knob)
                self.midi_register['bank_id'] = event.value
                return
            if event.ctrl == 89:
                # change project id CC: selec project(knob)
                self.midi_register['project_id'] = event.value
                return
            if event.ctrl == 90:
                # change project by select CC
                if self.opendsp.mod is not None:
                    # self.midi_register['bank_id'] # not implemented yet...
                    project = self.opendsp.mod.get_project_by_idx(self.midi_register['project_id'])
                    if project is not None:
                        self.opendsp.mod.load_project(project)
                return            

            # OpenDSP manage
            if event.ctrl == 83:
                # restart opendspd
                self.opendsp.restart()
                return

            if event.ctrl == 80:
                # force display
                logging.info("force display!")
                if 0 <= event.value <= 41:
                    if 'force_display' in self.opendsp.config['system']['system']:
                        del self.opendsp.config['system']['system']['force_display']
                    else:
                        return
                elif 42 <= event.value <= 84:
                    self.opendsp.config['system']['system']['force_display'] = 'native'
                elif 85 <= event.value <= 127:
                    self.opendsp.config['system']['system']['force_display'] = 'virtual'
                self.opendsp.save_system()
                self.opendsp.restart()
                return

    def processor(self):
        # opendsp midi controlled via program changes and cc messages on channel 16
        run([PortFilter(1) >> Filter(PROGRAM|CTRL) >> Call(thread=self.midi_queue)])

    def handle(self):
        """Midi handler
        called by core on each run cycle
        """
        try:
            self.lookup()
            self.connections_pending = self.opendsp.jackd.connect(self.connections_pending)
        except Exception as e:
            logging.error("error on midi handle process: {}".format(e))

    def lookup(self):
        """Hid Lookup
        take cares of user on the fly
        hid devices connections
        """
        # to use jamrouter we need to disable -Xseq on jackd or make aj2midid not make use of hardware devices -u only
        new_devices = [device for device in glob.glob("/dev/midi*") if device not in self.devices]
        # get new devices up and running
        for device in new_devices:
            priority = int(self.opendsp.config['system']['system']['realtime'])+4
            # search for midi devices
            self.devices[device] = self.opendsp.start_proc(['/usr/bin/jamrouter', '-M', 'generic', '-D', device, '-o', 'midiRT:in_1', '-y', str(priority), '-Y', str(priority), '-j', '-z.06']) # -z.94 max
            # get process name(since jamrouter gets new process each new instance)
            #process = subprocess.check_output(['/usr/bin/ps', '-p', str(self.devices[device].pid), '-o', 'comm=']).decode()
            process = 'jamrouter'
            # set cpu afinnity
            if 'cpu' in self.opendsp.config['system']['system']:
                self.opendsp.set_cpu(process, self.opendsp.config['system']['system']['cpu'])
            # set it +4 for realtime priority
            if 'realtime' in self.opendsp.config['system']['system']:
                self.opendsp.set_realtime(process, 4)

    def port_add(self, origin, dest):
        """Connection Port Add
        create a new connection state to handle
        """
        connection = {'origin': origin, 'dest': dest}
        self.connections.append(connection)
        self.connections_pending.append(connection)
