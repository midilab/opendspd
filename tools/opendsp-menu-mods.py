# -*- coding: utf-8 -*-

# OpenDSP Core Daemon
# Copyright (C) 2015-2019 Romulo Silva <contact@midilab.co>
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
# Common system tools
import os
import sys
import glob

if __name__ == '__main__':
    
    try:
        # read actual mod loaded data
        with open("/var/tmp/opendsp-run-data", "r") as mod_setup:
            data_mod = mod_setup.readlines()
    except: 
        print("opendsp not running, please start it first...")
        exit()

    if len(data_mod) < 1:
        print("no run data to read")
        exit()

    #opendsp_user_data_path
    #...
    path_data = data_mod[0].replace('\n', '')

    # read all avaliable mods, we sort glob here to make use of user numbered mods - usefull for MIDI requests
    avaliable_mods = [ os.path.basename(path_mod)[:-4] for path_mod in sorted(glob.glob("{path_data}/mod/*.cfg".format(path_data=path_data))) ]

    # make me a menu please
    menu = "<openbox_pipe_menu>"
    for index, mod in enumerate(avaliable_mods):
        menu += "<item label=\"{id}: {name_mod}\">".format(id=index, name_mod=mod)
        menu += "<action name=\"Execute\"><command>send_midi -J midiRT:in_1 CTRL,16,120,{}</command></action>".format(index)
        menu += "</item>"
    menu += "</openbox_pipe_menu>"

    print(menu)