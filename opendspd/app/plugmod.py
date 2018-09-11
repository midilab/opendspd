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

import time, subprocess, os, glob
import configparser

# MIDI Support
from mididings import *

class plugmod():

    __ingen = None
    __ecasound = None
    __odspc = None

    __project_path = '/home/opendsp/data/plugmod'
    __project_config = None
    __project = None
    __bank = None
    
    __mixer_mode = 'internal' # 'external'
    __mixer_model = 'mixer422'

    __midi_processor = [
        #Filter(PROGRAM) >> Process(self.app_program_change)
        ChannelFilter(1) >> Filter(NOTE, PROGRAM, CTRL) >> Port(1) >> Channel(1),
        ChannelFilter(2) >> Filter(NOTE, PROGRAM, CTRL) >> Port(2) >> Channel(1),
        ChannelFilter(3) >> Filter(NOTE, PROGRAM, CTRL) >> Port(3) >> Channel(1),
        ChannelFilter(4) >> Filter(NOTE, PROGRAM, CTRL) >> Port(4) >> Channel(1),
    ]

    def get_midi_processor(self):
        return self.__midi_processor            

    def __init__(self, openDspCtrl):
        self.__odspd = openDspCtrl
        self.__project_config = configparser.ConfigParser()

    def start(self):
        #self.load_project(0, 'FACTORY')
        self.load_project(1, 'FACTORY')

    def stop(self):
        pass

    def load_project(self, project, bank):
        self.__project = str(project)
        self.__bank = bank

        # list all <project>_*, get first one
        #project_file = glob.glob(self.__project_path + '/' + str(project) + '_*')
        # read file
        #self.__project_config.read(project_file[0])

        # start main mixer?
        if self.__mixer_mode == 'internal':
            self.load_mixer(self.__mixer_model)
        
        # load plugin host    
        self.load_plugin_host('classics')
        
    def save_project(self, project):
        pass

    def load_plugin_host(self, project_name):
        # start main lv2 host. ingen
        self.__ingen = subprocess.Popen(['/usr/bin/ingen', '-e', '-a', '-d', self.__project_path + '/module/' + project_name + '.ingen'])
        self.__odspd.setRealtime(self.__ingen.pid)
        time.sleep(5)
        
        # connect midi input to ingen modules
        subprocess.call(['/usr/bin/jack_connect', 'OpenDSP:out_1', 'ingen:channel_1'], shell=False)
        subprocess.call(['/usr/bin/jack_connect', 'OpenDSP:out_2', 'ingen:channel_2'], shell=False)
        subprocess.call(['/usr/bin/jack_connect', 'OpenDSP:out_3', 'ingen:channel_3'], shell=False)
        subprocess.call(['/usr/bin/jack_connect', 'OpenDSP:out_4', 'ingen:channel_4'], shell=False)
        
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

    def load_mixer(self, config):
        # its part of plugmod config, you use as virtual mixer or direct analog output
        self.__ecasound = subprocess.Popen('/usr/bin/ecasound -c', shell=True, env={'LANG': 'C', 'TERM': 'xterm-256color', 'SHELL': '/bin/bash', 'PATH': '/usr/sbin:/usr/bin:/usr/lib/jvm/default/bin:/usr/bin/site_perl:/usr/bin/vendor_perl:/usr/bin/core_perl', '_': '/usr/bin/opendspd', 'USER': 'opendsp'}, stdin=subprocess.PIPE)
        #self.__ecasound = subprocess.Popen('/usr/bin/ecasound -c -R:/home/opendsp/.ecasound/ecasounrc', shell=True, env={'LANG': 'C', 'TERM': 'xterm-256color', 'SHELL': '/bin/bash', 'PATH': '/usr/local/sbin:/usr/local/bin:/usr/bin:/usr/lib/jvm/default/bin:/usr/bin/site_perl:/usr/bin/vendor_perl:/usr/bin/core_perl', '_': '/usr/bin/opendspd','ECASOUND_LOGFILE': '/home/opendsp/log', 'USER': 'opendsp'}, stdin=subprocess.PIPE)
        #time.sleep(2)
        self.__odspd.setRealtime(self.__ecasound.pid)

        # load mixer config 
        cmd = 'cs-load /home/opendsp/data/plugmod/mixer/' + self.__mixer_model + '.ecs\n'
        self.__ecasound.stdin.write(cmd.encode())
        self.__ecasound.stdin.flush()
        time.sleep(1)
        self.__ecasound.stdin.write(b'start\n')
        self.__ecasound.stdin.flush()
        #time.sleep(4)

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
