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

class vcs():

    __vcs = None
    __odspc = None

    __project_config = None
    __project = None
    __bank = None

    def __init__(self, openDspCtrl):
        self.__odspd = openDspCtrl
        self.__project_config = configparser.ConfigParser()

    def start(self):
        # start main mixer
        #self.__vcs = subprocess.Popen('/usr/bin/projectM-jack', shell=True, env={'LANG': 'C', 'TERM': 'xterm-256color', 'SHELL': '/bin/bash', 'PATH': '/usr/local/sbin:/usr/local/bin:/usr/bin:/usr/lib/jvm/default/bin:/usr/bin/site_perl:/usr/bin/vendor_perl:/usr/bin/core_perl', '_': '/usr/bin/opendspd', 'USER': 'opendsp', 'DISPLAY': ':0', 'XAUTHORITY': '/tmp/.Xauthority'}, stdin=subprocess.PIPE)
        #self.__ecasound = subprocess.Popen('/usr/local/bin/ecasound -c -R:/home/opendsp/.ecasound/ecasounrc', shell=True, env={'LANG': 'C', 'TERM': 'xterm-256color', 'SHELL': '/bin/bash', 'PATH': '/usr/local/sbin:/usr/local/bin:/usr/bin:/usr/lib/jvm/default/bin:/usr/bin/site_perl:/usr/bin/vendor_perl:/usr/bin/core_perl', '_': '/usr/bin/opendspd','ECASOUND_LOGFILE': '/home/opendsp/log', 'USER': 'opendsp'}, stdin=subprocess.PIPE)
        self.__vcs = subprocess.Popen('/usr/bin/projectM-jack', stdin=subprocess.PIPE)
        time.sleep(2)
        
        self.__odspd.setRealtime(self.__vcs.pid)
        #subprocess.call(['/usr/bin/jack_connect', 'system:capture_1', 'projectM-jack:input'], shell=False)
        #subprocess.call(['/usr/bin/jack_connect', 'system:capture_2', 'projectM-jack:input'], shell=False)
        self.load_project(0, 'FACTORY')
        #self.load_project(1, 'FACTORY')

    def stop(self):
        pass

    def load_project(self, project, bank):
        self.__project = str(project)
        self.__bank = bank
        subprocess.call("/usr/bin/xdotool key ctrl+n" ,shell=True)
        time.sleep(60)
        #subprocess.call("/usr/bin/xdotool key ctrl+p" ,shell=True)
        #time.sleep(60)

    def save_project(self, project):
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
