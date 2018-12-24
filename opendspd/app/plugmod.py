# -*- coding: utf-8 -*-

# OpenDSP Plugmod Application
# Copyright (C) 2015-2018 Romulo Silva <contact@midilab.co>
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

import time, subprocess, os, socket, glob, re

# import abstract App class interface
from . import App

class plugmod(App):

    __ingen = None
    __ingen_socket = None
    __ecasound = None

    __app_path = 'plugmod'
    __project_bundle = None

    # addons
    # internal mixer mode use ecasound as main virtual mixing console
    # external mixer mode directs each module output to his mirroed number on system output
    __mixer = None # external, no internal mixer is the default 'internal' # 'external'
    __visualizer = None
    __is_visual_on = False
    
    # make use of vdisplay for user app manament via VNC and Xvfb
    __virtual_desktop = False
    __is_vdisplay_on = False
    __ingen_client = None
    
    __project = None
    __bank = None
    
    __audio_port_out = []
    __audio_port_in = []
    __midi_port_in = []
    
    def get_midi_processor(self):
        # realtime midi processing routing rules - based on mididings environment
        self.__midi_processor = "ChannelFilter(" + str(1) + ") >> Filter(NOTE, PROGRAM, CTRL) >> Port(1) >> Channel(1), ChannelFilter(" + str(2) + ") >> Filter(NOTE, PROGRAM, CTRL) >> Port(2) >> Channel(1), ChannelFilter(" + str(3) + ") >> Filter(NOTE, PROGRAM, CTRL) >> Port(3) >> Channel(1), ChannelFilter(" + str(4) + ") >> Filter(NOTE, PROGRAM, CTRL) >> Port(4) >> Channel(1)"
        if self.__mixer != None:
            self.__midi_processor = self.__midi_processor + ", ChannelFilter(" + str(15) + ") >> Filter(CTRL) >> Port(15) >> Channel(1)"
        return self.__midi_processor 

    def start(self):

        if "mixer" in self.params:
            self.__mixer = self.params["mixer"]    
            
        if "visualizer" in self.params:   
            self.__visualizer = self.params["visualizer"]  
            
        if "virtual_desktop" in self.params:
            self.__virtual_desktop = self.params["virtual_desktop"]

        # start main lv2 host. ingen
        # clean environment, sometimes client creates a config file that mess with server later
        try:
            for sock in glob.glob("/tmp/ingen.sock*"):
                os.remove(sock)
            if os.path.exists("/home/opendsp/.config/ingen/options.ttl"): 
                os.remove("/home/opendsp/.config/ingen/options.ttl")
        except:
            pass
            
        if self.__virtual_desktop != None:   
            self.__ingen = self.odsp.start_virtual_display_app('/usr/bin/ingen -eg  --graph-directory=/home/opendsp/data/plugmod/')
            self.__is_vdisplay_on = True            
        else:
            self.__ingen = subprocess.Popen(['/usr/bin/ingen', '-e', '-d', '-f', '--graph-directory=/home/opendsp/data/plugmod/'])
            
        self.odsp.setRealtime(self.__ingen.pid)
        
        while os.path.exists("/tmp/ingen.sock") == False:
            # TODO: max time to wait for
            pass

        #self.__ingen_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        #self.__ingen_socket.connect("/tmp/ingen.sock")
        self.__ingen_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        connected = False
        while connected == False:
            try:
                self.__ingen_socket.connect(("localhost", 16180))
                connected = True
            except:
                pass
                
        # start main mixer?
        if self.__mixer != None:
            self.load_mixer(self.__mixer)
        else:
            pass            
        
        self.load_project(self.params["project"])
        
    def run(self):
        # connect all the midi and audio from outside world to ingen world
        # do it once on first run, then on eternal loop to check for new connections
        self.manageAudioConnections()
        self.manageMidiConnections()
        
        # do we want to start visualizer?
        if self.__visualizer != None and self.__is_visual_on == False:
            # for now only "projectm", so no check...
            projectm = self.odsp.start_display_app('/usr/bin/projectM-jack')
            self.odsp.setRealtime(projectm.pid, -50)
            # wait projectm to comes up and them set it full screen
            time.sleep(20)
            subprocess.call(['/usr/bin/xdotool', 'key', 'f'], shell=True)
            self.__is_visual_on = True
        
        #if self.__virtual_desktop != None and self.__is_vdisplay_on == False:   
        #    self.__ingen_client = self.odsp.start_virtual_display_app('/usr/bin/ingen -g')
        #    #self.odsp.setRealtime(self.__ingen_client.pid)
        #    self.__is_vdisplay_on = True
            
        time.sleep(10)

    def manageAudioConnections(self):
        # filter data to get only ingen for outputs:
        # outputs
        jack_audio_lsp = self.jack.get_ports(name_pattern='ingen', is_audio=True, is_output=True)
        for audio_port in jack_audio_lsp:
            if audio_port.name in self.__audio_port_out:
                continue
            try:
                # get the channel based on any number present on port name
                channel = int(re.search(r'\d+', audio_port.name).group())     
                if self.__mixer != None:
                    self.jack.connect(audio_port.name, 'mixer:channel_' + str(channel))
                else:
                    self.jack.connect(audio_port.name, 'system:playback_' + str(channel))
            except:
                pass
            self.__audio_port_out.append(audio_port.name)
                
        # inputs
        jack_audio_lsp = self.jack.get_ports(name_pattern='ingen', is_audio=True, is_input=True)
        for audio_port in jack_audio_lsp:
            if audio_port.name in self.__audio_port_in:
                continue
            try:
                # get the channel based on any number present on port name
                channel = int(re.search(r'\d+', audio_port.name).group())    
                self.jack.connect(audio_port.name, 'system:capture_' + str(channel))
            except:
                pass
            self.__audio_port_in.append(audio_port.name)

    def manageMidiConnections(self):  
        # filter data to get only ingen:
        # input
        jack_midi_lsp = self.jack.get_ports(name_pattern='ingen', is_midi=True, is_input=True)
        for midi_port in jack_midi_lsp:
            
            if midi_port.name in self.__midi_port_in:
                continue
            try:
                # get the channel based on any number present on port name
                channel = int(re.search(r'\d+', midi_port.name).group())  
                self.jack.connect('OpenDSP_RT:out_' + str(channel), midi_port.name)
            except:
                pass
            self.__midi_port_in.append(midi_port.name)
            
    def stop(self):
        #client.close()
        pass

    def load_project(self, project):
        data = ''
        self.__project = str(project)
        #self.__bank = bank

        # get project name by prefix number
        # list all <project>_*, get first one
        project_file = glob.glob(self.odsp.getDataPath() + '/' + self.__app_path + '/*_' + str(project) + '.ingen')
        if len(project_file) > 0:
            self.__project_bundle = project_file[0]
            # send load bundle request and also unload old bundle in case we have anything loaded
            ## Load /old.lv2
            # the idea: create a graph block on each track add request.
            # create audio output, audio input, midi output and midi input??? do we???
            #patch:sequenceNumber "1"^^xsd:int ;
            data = '[] a patch:Copy ; patch:subject <file://' + self.__project_bundle + '/> ; patch:destination </main> .\0'
            # Replace /old.lv2 with /new.lv2
            #data = '[] a patch:Patch ; patch:subject </> ; patch:remove [ ingen:loadedBundle <file:///old.lv2/> ]; patch:add [ ingen:loadedBundle <file:///new.lv2/> ] .\0'
        else:
            # do what? create a new one?
            data = ''
        
        # send initial command
        self.__ingen_socket.send(data.encode('utf-8'))
        resp = self.__ingen_socket.recv(2048)
        print('Received ' + repr(resp))
        
    def save_project(self, project):
        pass

    def load_mixer(self, config):
        # its part of plugmod config, you use as virtual mixer or direct analog output
        self.__ecasound = subprocess.Popen('/usr/bin/ecasound -c', shell=True, env={'LANG': 'C', 'TERM': 'xterm-256color', 'SHELL': '/bin/bash', 'PATH': '/usr/sbin:/usr/bin:/usr/lib/jvm/default/bin:/usr/bin/site_perl:/usr/bin/vendor_perl:/usr/bin/core_perl', '_': '/usr/bin/opendspd', 'USER': 'opendsp'}, stdin=subprocess.PIPE)
        self.odsp.setRealtime(self.__ecasound.pid)

        # load mixer config setup
        cmd = 'cs-load ' + self.odsp.getDataPath() + '/' + self.__app_path + '/mixer/' + self.__mixer_model + '.ecs\n'
        self.__ecasound.stdin.write(cmd.encode())
        self.__ecasound.stdin.flush()
        self.__ecasound.stdin.write(b'start\n')
        self.__ecasound.stdin.flush()

        # connect opendsp midi out into ecasound midi in
        self.jack.connect('OpenDSP_RT:out_15', 'alsa_midi:ecasound (in)')
        self.jack.connect('system:playback_1', 'mixer:master_1')
        self.jack.connect('system:playback_2', 'mixer:master_2')
        
    def clear_mixer(self):
        # also finish ecasound instance
        self.__ecasound.stdin.write(b'stop\n')
        self.__ecasound.stdin.flush()

    def load_project_request(self, event):
        self.load_project(event.data2)

    def save_project_request(self, event):
        self.save_project(event.data2)

    def program_change(self, event): #program, bank):
        pass
        #print("opendsp event incomming: " + str(event.data1) + ":" + str(event.data2) + ":" + str(event.channel) + ":" + str(event.type))
