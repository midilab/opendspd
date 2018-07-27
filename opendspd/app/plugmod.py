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

class plugmod():

    __modhost = None
    __ecasound = None
    __odspc = None

    __project_path = '/home/opendsp/app/plugmod'
    __project = None
    __bank = None

    def __init__(self, openDspCtrl):
        self.__odspd = openDspCtrl

    def start(self):
        self.__modhost = subprocess.Popen(['/usr/local/bin/mod-host', '-v'],stdin=subprocess.PIPE)
        #self.__modhost = subprocess.Popen(['/usr/local/bin/mod-host', '-i'],stdin=subprocess.PIPE) #,stdout=subprocess.PIPE)
        self.__odspd.setRealtime(self.__modhost)
        #time.sleep(1)
        subprocess.call('/usr/bin/jack_connect mod-host:midi_in ttymidi:MIDI_in', shell=True)
        #self.load_project(0, 'FACTORY')
        #self.load_project(6, 'FACTORY')

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
