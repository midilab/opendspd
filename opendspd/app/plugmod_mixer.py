# -*- coding: utf-8 -*-

# OpenDSP Plugmod Application
# Copyright (C) 2015-2016 Romulo Silva <contact@midilab.co>
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

class plugmod_mixer():

    __modhost = None
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
        # start main mixer
        self.__ecasound = subprocess.Popen('/usr/bin/ecasound -c', shell=True, env={'LANG': 'C', 'TERM': 'xterm-256color', 'SHELL': '/bin/bash', 'PATH': '/usr/sbin:/usr/bin:/usr/lib/jvm/default/bin:/usr/bin/site_perl:/usr/bin/vendor_perl:/usr/bin/core_perl', '_': '/usr/bin/opendspd', 'USER': 'opendsp'}, stdin=subprocess.PIPE)
        #self.__ecasound = subprocess.Popen('/usr/local/bin/ecasound -c -R:/home/opendsp/.ecasound/ecasounrc', shell=True, env={'LANG': 'C', 'TERM': 'xterm-256color', 'SHELL': '/bin/bash', 'PATH': '/usr/local/sbin:/usr/local/bin:/usr/bin:/usr/lib/jvm/default/bin:/usr/bin/site_perl:/usr/bin/vendor_perl:/usr/bin/core_perl', '_': '/usr/bin/opendspd','ECASOUND_LOGFILE': '/home/opendsp/log', 'USER': 'opendsp'}, stdin=subprocess.PIPE)
        time.sleep(2)
        
        #self.__modhost = subprocess.Popen(['/usr/local/bin/mod-host', '-v'], stdin=subprocess.PIPE)
        self.__modhost = subprocess.Popen(['/usr/bin/mod-host', '-i'], stdin=subprocess.PIPE)
        self.__odspd.setRealtime(self.__modhost.pid)
        #self.__modhost.stdin.write(b'connect ttymidi:MIDI_in mod-host:midi_in\n')
        subprocess.call(['/usr/bin/jack_connect', 'mod-host:midi_in', 'OpenDSP:out_1'], shell=False)
        #self.load_project(0, 'FACTORY')
        self.load_project(1, 'FACTORY')

    def stop(self):
        pass

    def load_mixer(self, model):
        #model = self.__project_config.get(mixer, 'Model')
        
        ##self.__ecasound = ECA_CONTROL_INTERFACE()
        ##self.__ecasound.command("cs-load '/home/opendsp/data/plugmod/mixer4.ecs'")
        ##self.__ecasound.command("start")
        cmd = 'cs-load /home/opendsp/data/plugmod/mixer/' + model + '.ecs\n'
        self.__ecasound.stdin.write(cmd.encode())
        self.__ecasound.stdin.flush()
        time.sleep(2)
        self.__ecasound.stdin.write(b'start\n')
        self.__ecasound.stdin.flush()
        time.sleep(2)
        self.__odspd.setRealtime(self.__ecasound.pid)

        #self.__modhost.stdin.write(b"connect ttymidi:MIDI_in 'alsa_midi:ecasound (in)'\n")
        #subprocess.call(['/usr/bin/jack_connect', 'alsa_midi:ecasound (in)', 'ttymidi:MIDI_in'], shell=False)
        subprocess.call(['/usr/bin/jack_connect', 'alsa_midi:ecasound (in)', 'OpenDSP:out_1'], shell=False)

    def clear_mixer(self):
        self.__ecasound.stdin.write(b'stop\n')
        self.__ecasound.stdin.flush()

    def load_plugin(self, plugin, plugin_type):
        mixer_input = ""
        plugin_input = ""
        output_port_1 = ""
        output_port_2 = ""
        input_port_1 = ""
        input_port_2 = ""

        if "input" in plugin_type:
            instance_id = int(plugin_type[-1])
            mixer_input = "channel_" + str(plugin_type[-1])
        elif "send" in plugin_type:
            instance_id = int(plugin_type[-1]) + 100
            plugin_input = "mixer:send_" + str(plugin_type[-1])
            mixer_input = "return_" + str(plugin_type[-1])
        elif "master" in plugin_type:
            return
            #instance_id = 200
        else:
            return
        
        module = self.__project_config.get(plugin, 'Module')
        midi_channel = self.__project_config.get(plugin, 'Channel')
        bank = self.__project_config.get(plugin, 'Bank')
        program = self.__project_config.get(plugin, 'Program')
        
        #mixer_input = self.__project_config.get(plugin, 'MixerInput')

        config = configparser.ConfigParser()
        config.read(self.__project_path + '/' + 'module/' + module + '/config')
        uri = config.get('plugin', 'Uri')
        midi_port = config.get('plugin', 'MidiInPort')
        try:
            output_port_1 = config.get('plugin', 'OutputPort1')
            output_port_2 = config.get('plugin', 'OutputPort2')
            input_port_1 = config.get('plugin', 'InputPort1')
            input_port_2 = config.get('plugin', 'InputPort2')
        except configparser.NoOptionError:
            pass

        filter_instance = instance_id + 50

        # we need to filter midi channel on this plugin
        cmd = 'add http://gareus.org/oss/lv2/midifilter#channelmap ' + str(filter_instance) + '\n'
        self.__modhost.stdin.write(cmd.encode('utf-8'))
        for x in range(1, 17):
            if int(midi_channel) == x:
                cmd = 'param_set ' + str(filter_instance) + ' chn' + str(x) + ' 1.000000\n'
                self.__modhost.stdin.write(cmd.encode('utf-8'))
            else:
                cmd = 'param_set ' + str(filter_instance) + ' chn' + str(x) + ' 0.000000\n'
                self.__modhost.stdin.write(cmd.encode('utf-8'))
        #self.__modhost.stdin.write(b'connect ttymidi:MIDI_in effect_' + str(filter_instance) + ':midiin\n')
        cmd = 'connect OpenDSP:out_1 effect_' + str(filter_instance) + ':midiin\n'
        self.__modhost.stdin.write(cmd.encode('utf-8'))
        # module
        # add module
        cmd = 'add ' + uri + ' ' + str(instance_id) + '\n'
        self.__modhost.stdin.write(cmd.encode('utf-8'))
        cmd = 'connect effect_' + str(filter_instance) + ':midiout effect_' + str(instance_id) + ':' + midi_port + '\n'
        self.__modhost.stdin.write(cmd.encode('utf-8'))
        if "input" in plugin_type:
            cmd = 'connect effect_' + str(instance_id) + ':' + output_port_1 + ' mixer:' + mixer_input + '\n'
            self.__modhost.stdin.write(cmd.encode('utf-8'))
            #self.__modhost.stdin.write(b'connect effect_' + str(instance_id) + ':' + output_port_2 + ' mixer:' + mixer_input + '_2\n')
        else:
            cmd = 'connect effect_' + str(instance_id) + ':' + output_port_1 + ' mixer:' + mixer_input + '_1\n'
            self.__modhost.stdin.write(cmd.encode('utf-8'))
            cmd = 'connect effect_' + str(instance_id) + ':' + output_port_2 + ' mixer:' + mixer_input + '_2\n'
            self.__modhost.stdin.write(cmd.encode('utf-8'))

        if plugin_input != "":
            cmd = 'connect ' + plugin_input + '_1 effect_' + str(instance_id) + ':' + input_port_1 + '\n'
            self.__modhost.stdin.write(cmd.encode('utf-8'))
            cmd = 'connect ' + plugin_input + '_2 effect_' + str(instance_id) + ':' + input_port_2 + '\n'
            self.__modhost.stdin.write(cmd.encode('utf-8'))

        #self.__modhost.stdin.write(b'preset_load ' + str(instance_id) + ' file://' + self.__project_path + '/module/' + module + '/presets/bank_1.ttl#SPACESOUND\n')
        #self.__modhost.stdin.write(b'preset_save ' + str(instance_id) + ' "Preset test" ' + self.__project_path + '/' + 'module/ preset_' + str(instance_id) + '.ttl' + '\n')
        #preset_save 0 "My Preset" /home/user/.lv2/my-presets.lv2 mypreset.ttl

    def load_project(self, project, bank):
        self.__project = str(project)
        self.__bank = bank
        self.clear_plugins()
        self.clear_mixer()

        # list all <project>_*, get first one
        project_file = glob.glob(self.__project_path + '/' + str(project) + '_*')
        # read file
        self.__project_config.read(project_file[0])

        # load mixer
        self.load_mixer(self.__project_config.get('Mixer', 'Model'))

        for (mixer_item, value) in self.__project_config.items('Mixer'):
            self.load_plugin(value, mixer_item)

    def save_project(self, project):
        pass

    def clear_plugins(self):
        self.__modhost.stdin.write(b'feature_enable processing 0\n')
        self.__modhost.stdin.write(b'remove -1\n')
        self.__modhost.stdin.write(b'feature_enable link 0\n')
        #self.__modhost.stdin.write(b'midi_program_listen 1 1\n')
        self.__modhost.stdin.write(b'feature_enable processing 2\n')

    def load_project_request(self, event):
        self.load_project(event.data2, 'FACTORY')

    def save_project_request(self, event):
        self.save_project(event.data2, 'FACTORY')

    def program_change(self, event): #program, bank):
        pass
        #print("opendsp event incomming: " + str(event.data1) + ":" + str(event.data2) + ":" + str(event.channel) + ":" + str(event.type))

    def project_change(self, project):
        pass
