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
    virtual_desktop = None
    is_vdisplay_on = False
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
            
        if "virtual_desktop" in self.params:
            self.virtual_desktop = self.params["virtual_desktop"]

        # start main lv2 host. ingen
        # clean environment, sometimes client creates a config file that mess with server init
        try:
            for sock in glob.glob("/tmp/ingen.sock*"):
                os.remove(sock)
            if os.path.exists("/home/opendsp/.config/ingen/options.ttl"): 
                os.remove("/home/opendsp/.config/ingen/options.ttl")
        except:
            pass
        
        if self.virtual_desktop != None:   
            self.ingen = self.opendsp.virtual_display("/usr/bin/ingen -eg -f --graph-directory={data_path}/{app_path}/projects/".format(data_path=self.opendsp.data_path, app_path=self.app_path))
            self.is_vdisplay_on = True  
            # wait client response to start with bundle load             
            time.sleep(4)
        else:
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
        # filter data to get only ingen for outputs:
        # outputs
        jack_audio_lsp = map(lambda data: data.name, self.opendsp.jack.get_ports(name_pattern='ingen', is_audio=True, is_output=True))
        for audio_port in jack_audio_lsp:
            if audio_port in self.audio_port_out:
                continue
            try:
                # get the channel based on any number present on port name
                channel = int(re.search(r'\d+', audio_port).group())     
                if self.mixer != None:
                    self.opendsp.jack.connect(audio_port, "mixer:channel_{channel}".format(channel))
                else:
                    self.opendsp.jack.connect(audio_port, "system:playback_{channel}".format(channel))
                
                if self.opendsp.visualizer_proc != None:
                    self.opendsp.jack.connect(audio_port, 'projectM-jack:input')
            except:
                pass
            self.audio_port_out.append(audio_port)
        
        #
        if self.mixer != None:
            jack_audio_lsp = map(lambda data: data.name, self.opendsp.jack.get_ports(name_pattern='mixer', is_audio=True, is_output=True))            
            for mixer_port in jack_audio_lsp:
                if mixer_port in self.mixer_port_out:
                    continue
                try:
                    # get the channel based on any number present on port name
                    channel = int(re.search(r'\d+', mixer_port).group())     
                    self.opendsp.jack.connect(mixer_port, "system:playback_{channel}".format(channel))
                except:
                    pass
                self.mixer_port_out.append(mixer_port)
                
        # check for deleted or renamed port
        tmp_audio_port_out = self.audio_port_out
        for audio_port in tmp_audio_port_out:
            if audio_port in jack_audio_lsp:
                continue
            self.audio_port_out.remove(audio_port)                
                
        # inputs
        jack_audio_lsp = map(lambda data: data.name, self.opendsp.jack.get_ports(name_pattern='ingen', is_audio=True, is_input=True))
        for audio_port in jack_audio_lsp:
            if audio_port in self.audio_port_in:
                continue
            try:
                # get the channel based on any number present on port name
                channel = int(re.search(r'\d+', audio_port).group())    
                self.opendsp.jack.connect(audio_port, "system:capture_{channel}".format(channel))
            except:
                pass
            self.audio_port_in.append(audio_port)

        # check for deleted or renamed port
        tmp_audio_port_in = self.audio_port_in
        for audio_port in tmp_audio_port_in:
            if audio_port in jack_audio_lsp:
                continue
            self.audio_port_in.remove(audio_port)

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
                self.opendsp.jack.connect("OpenDSP_RT:out_{channel}".format(channel), midi_port)
                # connect OpenDSP_RT:out_ output to ingen control also... for midi cc map
                self.opendsp.jack.connect("OpenDSP_RT:out_{channel}".format(channel), 'ingen:control')
            except:
                time.sleep(2)
            self.midi_port_in.append(midi_port)

        # check for deleted or renamed port
        tmp_midi_port_in = self.midi_port_in
        for midi_port in tmp_midi_port_in:
            if midi_port in jack_midi_lsp:
                continue
            self.midi_port_in.remove(midi_port)
            
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
        data = "[] a patch:Delete ; patch:subject </main/*> .\\0"
        self.ingen_socket.send(data.encode('utf-8'))
        
    def save_project(self, project):
        pass

    def load_mixer(self, config):
        # its part of plugmod config, you use as virtual mixer or direct analog output
        self.ecasound = subprocess.Popen('/usr/bin/ecasound -c', env={'LANG': 'C', 'TERM': 'xterm-256color', 'SHELL': '/bin/bash', 'PATH': '/usr/sbin:/usr/bin:/usr/lib/jvm/default/bin:/usr/bin/site_perl:/usr/bin/vendor_perl:/usr/bin/core_perl', '_': '/usr/bin/opendspd', 'USER': 'opendsp'}, stdin=subprocess.PIPE)
        self.opendsp.set_realtime(self.ecasound.pid)

        # load mixer config setup
        cmd = "cs-load {data_path}/{app_path}/mixer/{mixer}.ecs\\n".format(data_path=self.opendsp.data_path, app_path=self.app_path, mixer=self.mixer)
        self.ecasound.stdin.write(cmd.encode())
        self.ecasound.stdin.flush()
        self.ecasound.stdin.write(b'start\n')
        self.ecasound.stdin.flush()

    def clear_mixer(self):
        # also finish ecasound instance
        self.ecasound.stdin.write(b'stop\n')
        self.ecasound.stdin.flush()

    def program_change(self, program, bank):
        pass
