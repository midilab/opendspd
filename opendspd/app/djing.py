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

class djing(App):

    __mixxx = None
    __ingen_socket = None
    __ecasound = None

    __app_path = 'djing'
    __project_bundle = None

    # addons
    # internal mixer mode use ecasound as main virtual mixing console
    # external mixer mode directs each module output to his mirroed number on system output
    __mixer = None # external, no internal mixer is the default 'internal' # 'external'
    __visualizer = None
    
    __project = None
    __bank = None
    
    def get_midi_processor(self):
        # realtime midi processing routing rules - based on mididings environment
        self.__midi_processor = "ChannelFilter(" + str(1) + ") >> Filter(NOTE, PROGRAM, CTRL) >> Port(1) >> Channel(1), ChannelFilter(" + str(2) + ") >> Filter(NOTE, PROGRAM, CTRL) >> Port(2) >> Channel(1), ChannelFilter(" + str(3) + ") >> Filter(NOTE, PROGRAM, CTRL) >> Port(3) >> Channel(1), ChannelFilter(" + str(4) + ") >> Filter(NOTE, PROGRAM, CTRL) >> Port(4) >> Channel(1), ChannelFilter(" + str(15) + ") >> Filter(CTRL) >> Port(15) >> Channel(1)"
        return self.__midi_processor 

    def start(self):

        if "visualizer" in self.params:   
            self.__visualizer = self.params["visualizer"]   

        self.__mixxx = self.odsp.start_virtual_display_app('/usr/bin/mixxx --settingsPath /home/opendsp/data/djing/config/ --resourcePath /home/opendsp/data/djing/resource/ -f')
        time.sleep(10)
        #self.odsp.setRealtime(self.__mixxx.pid)
        
    def run(self):
        
        # do we want to start visualizer?
        if self.__visualizer != None:
            # for now only "projectm", so no check...
            projectm = self.odsp.start_display_app('/usr/bin/projectM-jack')
            self.odsp.setRealtime(self.projectm.pid, -50)
            # wait projectm to comes up and them set it full screen
            time.sleep(15)
            subprocess.call(['/usr/bin/xdotool', 'key', 'f'], shell=True)
                    
        while True:
            time.sleep(5)

    def stop(self):
        #client.close()
        pass

    def load_project(self, project):
        data = ""
        self.__project = str(project)
        #self.__bank = bank

        # get project name by prefix number
        # list all <project>_*, get first one
        project_file = glob.glob(self.odsp.getDataPath() + '/' + self.__app_path + '/' + str(project) + '_*')
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
            pass    
        
        # send initial command
        self.__ingen_socket.send(data.encode('utf-8'))
        resp = self.__ingen_socket.recv(2048)
        print('Received ' + repr(resp))
        time.sleep(4)
        
        # connect midi input to ingen modules
        subprocess.call(['/usr/bin/jack_connect', 'OpenDSP_RT:out_1', 'ingen:event_in_1'], shell=False)
        subprocess.call(['/usr/bin/jack_connect', 'OpenDSP_RT:out_2', 'ingen:event_in_2'], shell=False)
        subprocess.call(['/usr/bin/jack_connect', 'OpenDSP_RT:out_3', 'ingen:event_in_3'], shell=False)
        subprocess.call(['/usr/bin/jack_connect', 'OpenDSP_RT:out_4', 'ingen:event_in_4'], shell=False)
        
        if self.__mixer != None:
            # connect ingen outputs to mixer. todo: loop thru existent mixer channels inputs instead of hardcoded
            subprocess.call(['/usr/bin/jack_connect', 'ingen:audio_out_1', 'mixer:channel_1'], shell=False)
            subprocess.call(['/usr/bin/jack_connect', 'ingen:audio_out_2', 'mixer:channel_2'], shell=False)
            subprocess.call(['/usr/bin/jack_connect', 'ingen:audio_out_3', 'mixer:channel_3'], shell=False)
            subprocess.call(['/usr/bin/jack_connect', 'ingen:audio_out_4', 'mixer:channel_4'], shell=False)
        else:
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
        time.sleep(1)
        self.odsp.setRealtime(self.__ecasound.pid)

        # load mixer config setup
        cmd = 'cs-load ' + self.odsp.getDataPath() + '/' + self.__app_path + '/mixer/' + self.__mixer_model + '.ecs\n'
        self.__ecasound.stdin.write(cmd.encode())
        self.__ecasound.stdin.flush()
        time.sleep(1)
        self.__ecasound.stdin.write(b'start\n')
        self.__ecasound.stdin.flush()
        time.sleep(2)

        # connect opendsp midi out into ecasound midi in 
        subprocess.call(['/usr/bin/jack_connect', 'OpenDSP_RT:out_15', 'alsa_midi:ecasound (in)'], shell=False)
        
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
