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

# MIDI Support
from mididings import *

class plugmod():

    __ingen = None
    __ingen_socket = None
    __ecasound = None
    __odspc = None

    __project_path = 'plugmod'
    __project = None
    __bank = None
    __project_bundle = None

    # internal mixer mode use ecasound as main virtual mixing console
    # external mixer mode directs each module output to his closest number on system output
    __mixer_mode = 'internal' # 'external'
    __mixer_model = 'mixer422'
    #__mono_mode = true

    __midi_processor = [
        #Filter(PROGRAM) >> Process(self.app_program_change)
        ChannelFilter(1) >> Filter(NOTE, PROGRAM, CTRL) >> Port(1) >> Channel(1),
        ChannelFilter(2) >> Filter(NOTE, PROGRAM, CTRL) >> Port(2) >> Channel(1),
        ChannelFilter(3) >> Filter(NOTE, PROGRAM, CTRL) >> Port(3) >> Channel(1),
        ChannelFilter(4) >> Filter(NOTE, PROGRAM, CTRL) >> Port(4) >> Channel(1),
        ChannelFilter(15) >> Filter(CTRL) >> Port(5) >> Channel(1), # for mixer cc control
    ]

    def get_midi_processor(self):
        return self.__midi_processor            

    def __init__(self, openDspCtrl):
        self.__odspd = openDspCtrl

    def start(self):
        # start main lv2 host. ingen
        # clean his environment
        for sock in glob.glob("/tmp/ingen.sock*"):
            os.remove(sock)
        if os.path.exists("~/.config/ingen/options.ttl"): 
            os.remove("~/.config/ingen/options.ttl")
        self.__ingen = subprocess.Popen(['/usr/bin/ingen', '-e', '-d', '-f'])
        self.__odspd.setRealtime(self.__ingen.pid)
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
        
        #self.load_project(0, 'FACTORY')
        self.load_project(1)

    def stop(self):
        #client.close()
        pass

    def load_project(self, project):
        self.__project = str(project)
        #self.__bank = bank

        # get project name by prefix number
        # list all <project>_*, get first one
        project_file = glob.glob(self.__odspd.__data_path + '/' + self.__project_path + '/' + str(project) + '_*')
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
        subprocess.call(['/usr/bin/jack_connect', 'OpenDSP:out_1', 'ingen:event_in_1'], shell=False)
        subprocess.call(['/usr/bin/jack_connect', 'OpenDSP:out_2', 'ingen:event_in_2'], shell=False)
        subprocess.call(['/usr/bin/jack_connect', 'OpenDSP:out_3', 'ingen:event_in_3'], shell=False)
        subprocess.call(['/usr/bin/jack_connect', 'OpenDSP:out_4', 'ingen:event_in_4'], shell=False)
        
        if self.__mixer_mode == 'internal':
            # connect ingen outputs to mixer
            subprocess.call(['/usr/bin/jack_connect', 'ingen:audio_out_1', 'mixer:channel_1'], shell=False)
            subprocess.call(['/usr/bin/jack_connect', 'ingen:audio_out_2', 'mixer:channel_2'], shell=False)
            subprocess.call(['/usr/bin/jack_connect', 'ingen:audio_out_3', 'mixer:channel_3'], shell=False)
            subprocess.call(['/usr/bin/jack_connect', 'ingen:audio_out_4', 'mixer:channel_4'], shell=False)
        else: # if self.__mixer_mode == 'external':
            # connect ingen outputs to direct sound card output
            subprocess.call(['/usr/bin/jack_connect', 'ingen:audio_out_1', 'system:playback_1'], shell=False)
            subprocess.call(['/usr/bin/jack_connect', 'ingen:audio_out_2', 'system:playback_2'], shell=False)
            subprocess.call(['/usr/bin/jack_connect', 'ingen:audio_out_3', 'system:playback_3'], shell=False)
            subprocess.call(['/usr/bin/jack_connect', 'ingen:audio_out_4', 'system:playback_4'], shell=False)
        
    def save_project(self, project):
        pass

    def load_mixer(self, config):
        # its part of plugmod config, you use as virtual mixer or direct analog output
        self.__ecasound = subprocess.Popen('/usr/bin/ecasound -c', shell=True, env={'LANG': 'C', 'TERM': 'xterm-256color', 'SHELL': '/bin/bash', 'PATH': '/usr/sbin:/usr/bin:/usr/lib/jvm/default/bin:/usr/bin/site_perl:/usr/bin/vendor_perl:/usr/bin/core_perl', '_': '/usr/bin/opendspd', 'USER': 'opendsp'}, stdin=subprocess.PIPE)
        #self.__ecasound = subprocess.Popen('/usr/bin/ecasound -c -R:/home/opendsp/.ecasound/ecasounrc', shell=True, env={'LANG': 'C', 'TERM': 'xterm-256color', 'SHELL': '/bin/bash', 'PATH': '/usr/local/sbin:/usr/local/bin:/usr/bin:/usr/lib/jvm/default/bin:/usr/bin/site_perl:/usr/bin/vendor_perl:/usr/bin/core_perl', '_': '/usr/bin/opendspd','ECASOUND_LOGFILE': '/home/opendsp/log', 'USER': 'opendsp'}, stdin=subprocess.PIPE)
        #time.sleep(2)
        self.__odspd.setRealtime(self.__ecasound.pid)

        # load mixer config 
        
        cmd = 'cs-load ' + self.__odspd.__data_path + '/' + self.__project_path + '/mixer/' + self.__mixer_model + '.ecs\n'
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

    def project_change(self, project):
        pass
