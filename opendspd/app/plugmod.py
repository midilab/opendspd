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

import time, subprocess, os, socket, glob

# import abstract App class interface
from . import App

class plugmod(App):

    __ingen = None
    __ingen_socket = None
    __ecasound = None

    __app_path = 'plugmod'
    __project_bundle = None

    # internal mixer mode use ecasound as main virtual mixing console
    # external mixer mode directs each module output to his mirroed number on system output
    __mixer_mode = 'internal' # 'external'
    __mixer_model = 'mixer422'
    #__mono_mode = true

    __project = None
    __bank = None
    
    def get_midi_processor(self):
        # realtime midi processing routing rules - based on mididings environment
        self.__midi_processor = "ChannelFilter(" + str(1) + ") >> Filter(NOTE, PROGRAM, CTRL) >> Port(1) >> Channel(1), ChannelFilter(" + str(2) + ") >> Filter(NOTE, PROGRAM, CTRL) >> Port(2) >> Channel(1), ChannelFilter(" + str(3) + ") >> Filter(NOTE, PROGRAM, CTRL) >> Port(3) >> Channel(1), ChannelFilter(" + str(4) + ") >> Filter(NOTE, PROGRAM, CTRL) >> Port(4) >> Channel(1), ChannelFilter(" + str(15) + ") >> Filter(CTRL) >> Port(15) >> Channel(1)"
        return self.__midi_processor 

    def start(self):

        self.__mixer_mode = self.params["mixer_mode"]
        self.__mixer_model = self.params["mixer_model"]        

        # start main lv2 host. ingen
        # clean his environment
        for sock in glob.glob("/tmp/ingen.sock*"):
            os.remove(sock)
        if os.path.exists("/home/opendsp/.config/ingen/options.ttl"): 
            os.remove("/home/opendsp/.config/ingen/options.ttl")
        self.__ingen = subprocess.Popen(['/usr/bin/ingen', '-e', '-d', '-f'])
        self.odsp.setRealtime(self.__ingen.pid)
        time.sleep(2)
        
        if os.path.exists("/tmp/ingen.sock"):
            #self.__ingen_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            #self.__ingen_socket.connect("/tmp/ingen.sock")
            self.__ingen_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.__ingen_socket.connect(("localhost", 16180))
        else:
            print("Couldn't Connect to ingen socket!")
    
        # start main mixer?
        if self.__mixer_mode == 'internal':
            self.load_mixer(self.__mixer_model)
        elif self.__mixer_mode == 'external':
            pass            
        
        #self.load_project(0, 'FACTORY')
        self.load_project(self.params["project"])

    def stop(self):
        #client.close()
        pass

    def load_project(self, project):
        self.__project = str(project)
        #self.__bank = bank

        # get project name by prefix number
        # list all <project>_*, get first one
        project_file = glob.glob(self.odsp.getDataPath() + '/' + self.__app_path + '/' + str(project) + '_*')
        if len(project_file) > 0:
            self.__project_bundle = project_file[0]
        else:
            # do what? create a new one?
            pass    
        
        # send load bundle request and also unload old bundle in case we have anything loaded
        ## Load /old.lv2
        # the idea: create a graph block on each track add request.
        # create audio output, audio input, midi output and midi input
        #patch:sequenceNumber "1"^^xsd:int ;
        data = '[] a patch:Copy ; patch:subject <file://' + self.__project_bundle + '/> ; patch:destination </main> .\0'
    
        # Replace /old.lv2 with /new.lv2
        #data = '[] a patch:Patch ; patch:subject </> ; patch:remove [ ingen:loadedBundle <file:///old.lv2/> ]; patch:add [ ingen:loadedBundle <file:///new.lv2/> ] .\0'

        # send load bundle command
        self.__ingen_socket.send(data.encode('utf-8'))
        resp = self.__ingen_socket.recv(2048)
        print('Received ' + repr(resp))
        time.sleep(4)
        
        # connect midi input to ingen modules
        subprocess.call(['/usr/bin/jack_connect', 'OpenDSP_RT:out_1', 'ingen:event_in_1'], shell=False)
        subprocess.call(['/usr/bin/jack_connect', 'OpenDSP_RT:out_2', 'ingen:event_in_2'], shell=False)
        subprocess.call(['/usr/bin/jack_connect', 'OpenDSP_RT:out_3', 'ingen:event_in_3'], shell=False)
        subprocess.call(['/usr/bin/jack_connect', 'OpenDSP_RT:out_4', 'ingen:event_in_4'], shell=False)
        
        if self.__mixer_mode == 'internal':
            # connect ingen outputs to mixer. todo: loop thru existent mixer channels inputs instead of hardcoded
            subprocess.call(['/usr/bin/jack_connect', 'ingen:audio_out_1', 'mixer:channel_1'], shell=False)
            subprocess.call(['/usr/bin/jack_connect', 'ingen:audio_out_2', 'mixer:channel_2'], shell=False)
            subprocess.call(['/usr/bin/jack_connect', 'ingen:audio_out_3', 'mixer:channel_3'], shell=False)
            subprocess.call(['/usr/bin/jack_connect', 'ingen:audio_out_4', 'mixer:channel_4'], shell=False)
        elif self.__mixer_mode == 'external':
            # connect ingen outputs to direct sound card output. todo: loop thru existent playback outputs instead of hardcoded
            subprocess.call(['/usr/bin/jack_connect', 'ingen:audio_out_1', 'system:playback_1'], shell=False)
            subprocess.call(['/usr/bin/jack_connect', 'ingen:audio_out_2', 'system:playback_2'], shell=False)
            #subprocess.call(['/usr/bin/jack_connect', 'ingen:audio_out_3', 'system:playback_3'], shell=False)
            #subprocess.call(['/usr/bin/jack_connect', 'ingen:audio_out_4', 'system:playback_4'], shell=False)
        
    def save_project(self, project):
        pass

    def load_mixer(self, config):
        # its part of plugmod config, you use as virtual mixer or direct analog output
        self.__ecasound = subprocess.Popen('/usr/bin/ecasound -c', shell=True, env={'LANG': 'C', 'TERM': 'xterm-256color', 'SHELL': '/bin/bash', 'PATH': '/usr/sbin:/usr/bin:/usr/lib/jvm/default/bin:/usr/bin/site_perl:/usr/bin/vendor_perl:/usr/bin/core_perl', '_': '/usr/bin/opendspd', 'USER': 'opendsp'}, stdin=subprocess.PIPE)
        #self.__ecasound = subprocess.Popen('/usr/bin/ecasound -c -R:/home/opendsp/.ecasound/ecasounrc', shell=True, env={'LANG': 'C', 'TERM': 'xterm-256color', 'SHELL': '/bin/bash', 'PATH': '/usr/local/sbin:/usr/local/bin:/usr/bin:/usr/lib/jvm/default/bin:/usr/bin/site_perl:/usr/bin/vendor_perl:/usr/bin/core_perl', '_': '/usr/bin/opendspd','ECASOUND_LOGFILE': '/home/opendsp/log', 'USER': 'opendsp'}, stdin=subprocess.PIPE)
        #time.sleep(2)
        self.odsp.setRealtime(self.__ecasound.pid)

        # load mixer config 
        
        cmd = 'cs-load ' + self.odsp.getDataPath() + '/' + self.__app_path + '/mixer/' + self.__mixer_model + '.ecs\n'
        self.__ecasound.stdin.write(cmd.encode())
        self.__ecasound.stdin.flush()
        time.sleep(1)
        self.__ecasound.stdin.write(b'start\n')
        self.__ecasound.stdin.flush()
        time.sleep(2)

        # connect opendsp midi out into ecasound midi in 
        subprocess.call(['/usr/bin/jack_connect', 'OpenDSP:out_15', 'alsa_midi:ecasound (in)'], shell=False)
        
    def clear_mixer(self):
        # also finish ecasound instance
        self.__ecasound.stdin.write(b'stop\n')
        self.__ecasound.stdin.flush()

    def load_project_request(self, event):
        self.load_project(event.data2, 'FACTORY')

    def save_project_request(self, event):
        self.save_project(event.data2, 'FACTORY')

    def program_change(self, event): #program, bank):
        pass
        #print("opendsp event incomming: " + str(event.data1) + ":" + str(event.data2) + ":" + str(event.channel) + ":" + str(event.type))
