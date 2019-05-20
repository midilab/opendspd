# -*- coding: utf-8 -*-

# OpenDSP Plugmod Application
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
import time
import subprocess
import os
import socket
import glob
import re

# import abstract App class interface
from . import App

class plugmod(App):

    ingen = None
    ingen_socket = None
    ecasound = None

    app_path = 'plugmod'
    project_bundle = None

    # addons
    # internal mixer mode use ecasound as main virtual mixing console
    # external mixer mode directs each module output to his mirroed number on system output
    mixer = None # external, no internal mixer is the default 'internal' # 'external'
    
    # make use of vdisplay for user app manament via VNC and Xvfb
    display = None
    ingen_client = None
    
    project = None
    bank = None
    
    audio_port_out = []
    audio_port_in = []
    midi_port_in = []
    mixer_port_out = []
    
    def start(self):

        if "mixer" in self.params:
            self.mixer = self.params["mixer"]    
            
        if "display" in self.params:
            self.display = self.params["display"]

        # start main lv2 host. ingen
        # clean environment, sometimes client creates a config file that mess with server init
        try:
            for sock in glob.glob("/tmp/ingen.sock*"):
                os.remove(sock)
            if os.path.exists("/home/opendsp/.config/ingen/options.ttl"): 
                os.remove("/home/opendsp/.config/ingen/options.ttl")
        except:
            pass
        
        if self.display == "virtual":   
            self.ingen = self.opendsp.virtual_display("/usr/bin/ingen -eg -f --graph-directory={data_path}/{app_path}/projects/".format(data_path=self.opendsp.data_path, app_path=self.app_path))
            # wait client response to start with bundle load             
            time.sleep(4)
        elif self.display == "native":
            self.ingen = self.opendsp.display("/usr/bin/ingen -eg -f --graph-directory={data_path}/{app_path}/projects/".format(data_path=self.opendsp.data_path, app_path=self.app_path))
            # wait client response to start with bundle load             
            time.sleep(4)
        elif self.display == None:
            self.ingen = subprocess.Popen(['/usr/bin/ingen', '-e', '-d', '-f'])
            
        self.opendsp.set_realtime(self.ingen.pid)
        
        while not os.path.exists("/tmp/ingen.sock"):
            # TODO: max time to wait for
            print("waiting ingen file socket")
            time.sleep(1)

        connected = False
        while not connected:
            try:
                #self.ingen_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                #self.ingen_socket.connect("/tmp/ingen.sock")
                self.ingen_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                connected = True
            except:
                print("error creating socket for ingen, trying again...")
                time.sleep(1)

        connected = False
        while not connected:
            try:
                self.ingen_socket.connect(("localhost", 16180))
                connected = True
            except:
                print("waiting ingen socket")
                time.sleep(1)
                
        # start main mixer?
        if self.mixer:
            self.load_mixer(self.mixer)          
        
        self.load_project(self.params["project"])

    def stop(self):
        pass

    def run(self):
        # connect all the midi and audio from outside world to ingen world
        self.manage_audio_connections()
        self.manage_midi_connections()

    def midi_processor_queue(self, event):
        #event.value
        if event.ctrl == 119:
            #LOAD_PROJECT
            self.load_project(event.value)
        if event.ctrl == 118:
            #NEW PROJECT
            self.new_project()
            return
        if event.ctrl == 117:
            #LOAD_APP_NEXT_PROJECT
            self.load_project(project+1)
            return
        if event.ctrl == 116:
            #LOAD_APP_PREV_PROJECT
            self.load_project(project-1)
            return
        if event.ctrl == 115:
            #SAVE_PROJECT
            self.save_project()
            return

    def get_midi_processor(self):
        midi_processor = ""
        for x in range(1,4):
            # realtime midi processing routing rules - based on mididings environment
            midi_processor += "{channel}: Filter(NOTE, PROGRAM, CTRL) >> Channel(1) >> Port({channel}), ".format(channel=x)
        if self.mixer != None:
            midi_processor += "{channel}: Filter(CTRL) >> Channel(1) >> Port({channel}), ".format(channel=14)
        return midi_processor[:-2]

    def manage_audio_connections(self):
        # iterate over all ingen outputs, check if the on ingen side we got any mapped name following the following:
        # ingen:system_playback_1 goes to system:playback_1
        jack_audio_outputs = [data.name for data in self.opendsp.jack.get_ports(is_audio=True, is_output=True)]
        jack_audio_inputs = [data.name for data in self.opendsp.jack.get_ports(is_audio=True, is_input=True)]
        
        ingen_audio_outputs = list(filter(lambda output_port: True if 'ingen' in output_port else False, jack_audio_outputs))      
        system_inputs = list(filter(lambda input_port: True if 'ingen' not in input_port else False, jack_audio_inputs))
        # create the map abstraction by cut everything before ':' and them replacing first occurence of '_' by ':'
        ingen_outputs = list(map(lambda output_port: { 'jack': output_port, 'mapped': output_port[output_port.find(':')+1:].replace('_', ':', 1) }, ingen_audio_outputs))

        # outputs
        for ingen_output in ingen_outputs:
            if ingen_output['jack'] in self.audio_port_out:
                continue
            for system_input in system_inputs:
                if ingen_output['mapped'] in system_input:
                    self.opendsp.jack.connect(ingen_output['jack'], system_input)
                    self.audio_port_out.append(ingen_output['jack'])

        ingen_audio_inputs = list(filter(lambda input_port: True if 'ingen' in input_port else False, jack_audio_inputs))
        system_outputs = list(filter(lambda output_port: True if 'ingen' not in output_port else False, jack_audio_outputs))
        # create the map abstraction by cut everything before ':' and them replacing first occurence of '_' by ':'
        ingen_inputs = list(map(lambda input_port: { 'jack': input_port, 'mapped': input_port[input_port.find(':')+1:].replace('_', ':', 1) }, ingen_audio_inputs))      
        
        # inputs
        for ingen_input in ingen_inputs:
            if ingen_input['jack'] in self.audio_port_in:
                continue
            for system_output in system_outputs:
                if ingen_input['mapped'] in system_output:
                    self.opendsp.jack.connect(system_output, ingen_input['jack'])
                    self.audio_port_in.append(ingen_input['jack'])
                            
    def manage_midi_connections(self):  
        # filter data to get only ingen:
        # input
        jack_midi_lsp = map(lambda data: data.name, self.opendsp.jack.get_ports(name_pattern='ingen', is_midi=True, is_input=True))
        for midi_port in jack_midi_lsp:
            if midi_port in self.midi_port_in:
                continue
            try:
                # get the channel based on any number present on port name
                channel = int(re.search(r'\d+', midi_port).group())  
                self.opendsp.jack.connect("midi:out_{channel}".format(channel=channel), midi_port)
                # connect midi:out_ output to ingen control also... for midi cc map
                self.opendsp.jack.connect("midi:out_{channel}".format(channel=channel), 'ingen:control')
            except:
                time.sleep(1)
            self.midi_port_in.append(midi_port)
            
    def __del__(self):
        self.ingen.kill()
        if self.mixer != None:
            self.ecasound.kill()

    def load_project(self, project):
        data = ''
        self.project = project
        #self.bank = bank

        # get project name by prefix number
        # list all <project>_*, get first one
        project_file = glob.glob("{data_path}/{app_path}/projects/*_{project}.ingen".format(data_path=self.opendsp.data_path, app_path=self.app_path, project=project))
        if len(project_file) > 0:
            self.project_bundle = project_file[0]
            # send load bundle request and also unload old bundle in case we have anything loaded
            ## Load /old.lv2
            # the idea: create a graph block on each track add request.
            # create audio output, audio input, midi output and midi input??? do we???
            #patch:sequenceNumber "1"^^xsd:int ;
            data = "[] a patch:Copy ; patch:subject <file://{bundle_path}/> ; patch:destination </main> .\0".format(bundle_path=self.project_bundle)
            # Replace /old.lv2 with /new.lv2
            #data = '[] a patch:Patch ; patch:subject </> ; patch:remove [ ingen:loadedBundle <file:///old.lv2/> ]; patch:add [ ingen:loadedBundle <file:///new.lv2/> ] .\0'
        else:
            project_file = glob.glob("{data_path}/{app_path}/projects/*.ingen".format(data_path=self.opendsp.data_path, app_path=self.app_path))
            if len(project_file) > 0:
                self.project_bundle = project_file[0]
                data = "[] a patch:Copy ; patch:subject <file://{project_bundle}/> ; patch:destination </main> .\\0".format(project_bundle=self.project_bundle)
            else:
                data = ""
        
        # send command
        self.ingen_socket.send(data.encode('utf-8'))

    def new_project(self):
        # delete 
        #data = '[] a patch:Delete ; patch:subject </main> ; patch:body [ a ingen:Arc ; ingen:incidentTo </main> ] .\0'
        #self.ingen_socket.send(data.encode('utf-8'))
        #data = '[] a patch:Delete ; patch:subject </main> .\0'
        data = '[] a patch:Delete ; patch:subject </main/*> .\0'
        self.ingen_socket.send(data.encode('utf-8'))
        
    def save_project(self, project):
        pass

    def load_mixer(self, config):
        # its part of plugmod config, you use as virtual mixer or direct analog output
        self.ecasound = subprocess.Popen(['/usr/bin/ecasound', '-c'], env={'LANG': 'C', 'TERM': 'xterm-256color', 'SHELL': '/bin/bash', 'PATH': '/usr/sbin:/usr/bin:/usr/lib/jvm/default/bin:/usr/bin/site_perl:/usr/bin/vendor_perl:/usr/bin/core_perl', '_': '/usr/bin/opendspd', 'USER': 'opendsp'}, stdin=subprocess.PIPE)
        self.opendsp.set_realtime(self.ecasound.pid)

        # load mixer config setup
        cmd = "cs-load {data_path}/{app_path}/mixer/{mixer}.ecs".format(data_path=self.opendsp.data_path, app_path=self.app_path, mixer=self.mixer)
        self.ecasound.stdin.write(cmd.encode() + b'\n')
        self.ecasound.stdin.flush()
        self.ecasound.stdin.write(b'start\n')
        self.ecasound.stdin.flush()

    def clear_mixer(self):
        # also finish ecasound instance
        self.ecasound.stdin.write(b'stop\n')
        self.ecasound.stdin.flush()

    def program_change(self, program, bank):
        pass
