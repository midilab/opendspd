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

class plugmod():

    __ingen = []
    __ecasound = None
    __odspc = None

    __project_path = '/home/opendsp/data/plugmod'
    __project_config = None
    __project = None
    __bank = None

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
        self.clear_modules()
        self.clear_mixer()

        # list all <project>_*, get first one
        project_file = glob.glob(self.__project_path + '/' + str(project) + '_*')
        # read file
        self.__project_config.read(project_file[0])

        # multi or single patch?
        # if its multi start ingen for midi splitter
        self.__ingen = subprocess.Popen(['/usr/bin/ingen', '-e', '-d', self.__project_path + '/module/midi_splitter.ingen'])
        self.__odspd.setRealtime(self.__ingen.pid)
        time.sleep(5)
        subprocess.call(['/usr/bin/jack_connect', 'OpenDSP:out_1', 'ingen:control'], shell=False)

        # is there a load mixer request?
        if 'mixer' in config self.__project_config:
            # load mixer and all modules related to each channel config. channelX, sendA/sendB, master 
            self.load_mixer(self.__project_config)
        else:
            # in case no mixer request, load all modules requested on config file
            for module in self.__project_config:
                self.load_module(module, None, None)

    def save_project(self, project):
        pass

    def load_mixer(self, config):
        # start main mixer
        self.__ecasound = subprocess.Popen('/usr/bin/ecasound -c', shell=True, env={'LANG': 'C', 'TERM': 'xterm-256color', 'SHELL': '/bin/bash', 'PATH': '/usr/sbin:/usr/bin:/usr/lib/jvm/default/bin:/usr/bin/site_perl:/usr/bin/vendor_perl:/usr/bin/core_perl', '_': '/usr/bin/opendspd', 'USER': 'opendsp'}, stdin=subprocess.PIPE)
        #self.__ecasound = subprocess.Popen('/usr/bin/ecasound -c -R:/home/opendsp/.ecasound/ecasounrc', shell=True, env={'LANG': 'C', 'TERM': 'xterm-256color', 'SHELL': '/bin/bash', 'PATH': '/usr/local/sbin:/usr/local/bin:/usr/bin:/usr/lib/jvm/default/bin:/usr/bin/site_perl:/usr/bin/vendor_perl:/usr/bin/core_perl', '_': '/usr/bin/opendspd','ECASOUND_LOGFILE': '/home/opendsp/log', 'USER': 'opendsp'}, stdin=subprocess.PIPE)
        time.sleep(2)
        self.__odspd.setRealtime(self.__ecasound.pid)
        
        # load mixer config and start him
        cmd = 'cs-load /home/opendsp/data/plugmod/mixer/' + config['mixer']['model'] + '.ecs\n'
        self.__ecasound.stdin.write(cmd.encode())
        self.__ecasound.stdin.flush()
        time.sleep(2)
        self.__ecasound.stdin.write(b'start\n')
        self.__ecasound.stdin.flush()
        time.sleep(4)
        
        # connect opendsp midi out into ecasound midi in 
        subprocess.call(['/usr/bin/jack_connect', 'alsa_midi:ecasound (in)', 'OpenDSP:out_1'], shell=False)
        
        # load and connect all modules
        for path in config['mixer']:
            if 'channel' in path:
				print("loading channel module: " + config['mixer'][path])
				output_port = "mixer:channel_" + str(path[-1])
                input_port = None
            elif 'send' in path:
                print("loading send module: " + config['mixer'][path])
                output_port = "mixer:return_" + str(path[-1])
                input_port = "mixer:send_" + str(path[-1])
            elif 'master' in path:
                #print("loading master module: " + config['mixer'][path])
                #output_port = "mixer:master_" + str(1)
                #input_port = "mixer:master_" + str(1)
                return
            self.load_module(config[config['mixer'][path]], output_port, input_port)
        
    def clear_mixer(self):
		# also finish ecasound instance
        self.__ecasound.stdin.write(b'stop\n')
        self.__ecasound.stdin.flush()

    def load_module(self, config, output_port, input_port):
        module = config['module']
        midi_channel = config['channel']
        bank = config['bank']
        program = config['program']

        # one mod-host per module instance to get advantage over multi core processors
        # before call a new host-mod instance confirm it we doesnt already has one for the matter... if we do have just clear and load new module schema
        # also check if we have a mixer load request, if we do not, just plug module output to stereo output, or user requested Output number on config.
        
        # start lv2 host 
        #self.__ingen = subprocess.Popen(['/usr/bin/ingen -e -d -u `pidof jackd` /home/opendsp/ingen_desk.ingen'])
        self.__ingen = subprocess.Popen(['/usr/bin/ingen', '-e', '-d', self.__project_path + '/module/' + module + '.ingen'])
        self.__odspd.setRealtime(self.__ingen.pid)
        time.sleep(5)
        
        # for multi config get midi from midi splitter
        subprocess.call('/usr/bin/jack_connect ingen:event_out_' + midi_channel + ' ingen-01:control', shell=True)
        # single mode? get midi data from OpenDSP midi in
        #subprocess.call('/usr/bin/jack_connect OpenDSP:out_1 ingen-01:control', shell=True)

        # if output_port != None:
        # connect to specified output_port
        subprocess.call('/usr/bin/jack_connect ingen-01:audio_out_1 ' + output_port, shell=True)
        #subprocess.call('/usr/bin/jack_connect ingen-01:audio_out_2 ' + output_port, shell=True)
        # else:
        # connect to default output_port
        ##subprocess.call('/usr/bin/jack_connect ingen-01:audio_out_1 ' + default??, shell=True)
        #subprocess.call('/usr/bin/jack_connect ingen-01:audio_out_2 ' + default??, shell=True)        
        
        # if input_port != None:
        # connect to specified input_port
        # else:
        # connect to default input_port
        
    def clear_modules(self):
		# clear and terminate all ingen instances
        pass

    def load_project_request(self, event):
        self.load_project(event.data2, 'FACTORY')

    def save_project_request(self, event):
        self.save_project(event.data2, 'FACTORY')

    def program_change(self, event): #program, bank):
        pass
        #print("opendsp event incomming: " + str(event.data1) + ":" + str(event.data2) + ":" + str(event.channel) + ":" + str(event.type))

    def project_change(self, project):
        pass
