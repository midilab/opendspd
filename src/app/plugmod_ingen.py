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

import time, subprocess, os

class plugmod_ingen():

    __modhost = None
    __ecasound = None
    __odspc = None

    __project_path = '/home/opendsp/app/plugmod'
    __project = None
    __bank = None

    def __init__(self, openDspCtrl):
        self.__odspd = openDspCtrl

    def start(self):
        # start main mixer
        #self.__ecasound = subprocess.Popen(['/usr/bin/ecasound', '-c', '-s:/home/opendsp/app/plugmod/mixer4.ecs'], stdin=subprocess.PIPE, env=os.environ.copy(), shell=True)
        self.__ecasound = subprocess.Popen('/usr/bin/ecasound -c', shell=True, env={'LANG': 'C', 'TERM': 'xterm-256color', 'SHELL': '/bin/bash', 'PATH': '/usr/local/sbin:/usr/local/bin:/usr/bin:/usr/lib/jvm/default/bin:/usr/bin/site_perl:/usr/bin/vendor_perl:/usr/bin/core_perl', '_': '/usr/bin/opendspd', 'USER': 'opendsp'}, stdin=subprocess.PIPE)
        self.__odspd.setRealtime(self.__ecasound)

        ##self.__ecasound = ECA_CONTROL_INTERFACE()
        ##self.__ecasound.command("cs-load '/home/opendsp/app/plugmod/mixer4.ecs'")
        ##self.__ecasound.command("start")

        ##self.__ecasound.communicate('cs-load /home/opendsp/app/plugmod/mixer4.ecs')
        ##self.__ecasound.communicate('start')
        self.__ecasound.stdin.write('cs-load /home/opendsp/app/plugmod/mixer4.ecs\n')
        time.sleep(1)
        self.__ecasound.stdin.write('start\n')
        time.sleep(2)
        subprocess.call(['/usr/bin/jack_connect', 'alsa_midi:ecasound (in)', 'ttymidi:MIDI_in'], shell=False)
#mixer:channel_1
#mixer:channel_2
#mixer:channel_3
#mixer:channel_4
#mixer:return_1
#mixer:return_2
#mixer:return_3
#mixer:return_4
#mixer:out_1
#mixer:out_2
#mixer:send_1
#mixer:send_2
#alsa_midi:ecasound (out)
#alsa_midi:ecasound (in)

        # start lv2 host 
        #self.__ingen = subprocess.Popen(['/usr/bin/ingen -e -d -u `pidof jackd` /home/opendsp/ingen_desk.ingen'])
        self.__ingen = subprocess.Popen(['/usr/bin/ingen', '-e', '-d', '/home/opendsp/ingen.ingen'])
        #self.__ingen = subprocess.Popen(['/usr/bin/ingen', '-e'])
        self.__odspd.setRealtime(self.__ingen)
        time.sleep(18)
        subprocess.call('/usr/bin/jack_connect ingen:control ttymidi:MIDI_in', shell=True)
        #self.load_project(0, 'FACTORY')
        #self.load_project(1, 'FACTORY')

        # connect mixer and lv2 host
        subprocess.call('/usr/bin/jack_connect ingen:audio_out_1 mixer:channel_1', shell=True)
        subprocess.call('/usr/bin/jack_connect ingen:audio_out_2 mixer:channel_2', shell=True)
        subprocess.call('/usr/bin/jack_connect ingen:audio_out_3 mixer:channel_3', shell=True)
        subprocess.call('/usr/bin/jack_connect ingen:audio_out_4 mixer:channel_4', shell=True)
        subprocess.call('/usr/bin/jack_connect ingen:audio_out_5 mixer:return_1', shell=True)
        subprocess.call('/usr/bin/jack_connect ingen:audio_out_6 mixer:return_2', shell=True)
        subprocess.call('/usr/bin/jack_connect ingen:audio_out_7 mixer:return_3', shell=True)
        subprocess.call('/usr/bin/jack_connect ingen:audio_out_8 mixer:return_4', shell=True)
        subprocess.call('/usr/bin/jack_connect ingen:audio_in_1 mixer:send_1', shell=True)
        subprocess.call('/usr/bin/jack_connect ingen:audio_in_2 mixer:send_2', shell=True)

    def stop(self):
        pass

    def load_project(self, project, bank):
        self.__project = str(project)
        self.__bank = bank
        self.clear_plugins()
        self.__modhost.stdin.write('load ' + self.__project_path + '/' + self.__project + '/load\n')

    def clear_plugins(self):
        self.__modhost.stdin.write('feature_enable processing 0\n')
        self.__modhost.stdin.write('remove -1\n')
        self.__modhost.stdin.write('feature_enable link 0\n')
        self.__modhost.stdin.write('midi_program_listen 1 1\n')
        self.__modhost.stdin.write('feature_enable processing 2\n')

    def load_request(self, event):
        self.load_project(event.data2, 'FACTORY')

    def program_change(self, program, bank):
        pass

    def project_change(self, project):
        pass
