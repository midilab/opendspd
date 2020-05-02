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
import glob

if __name__ == '__main__':

    try:
        # read actual mod loaded data
        with open("/var/tmp/opendsp-run-data", "r") as mod_setup:
            data_mod = mod_setup.readlines()
    except:
        print("<openbox_pipe_menu><separator label=\"OpenDSP not running\" /></openbox_pipe_menu>")
        exit()

    if len(data_mod) <= 1:
        print("<openbox_pipe_menu><separator label=\"No mod loaded\" /></openbox_pipe_menu>")
        exit()

    if len(data_mod) <= 2:
        print("<openbox_pipe_menu><separator label=\"No main app\" /></openbox_pipe_menu>")
        exit()

    if len(data_mod) <= 5:
        print("<openbox_pipe_menu><separator label=\"No main app config\" /></openbox_pipe_menu>")
        exit()

    #opendsp_user_data_path
    #mod_name
    #app_name
    #mod_project_path
    #mod_project_name
    #mod_project_extension
    path_data = data_mod[0].replace('\n', '')
    name_mod = data_mod[1].replace('\n', '')
    # check for the existence of lines above...
    app_name = data_mod[2].replace('\n', '')
    path_project = data_mod[3].replace('\n', '')
    name_project = data_mod[4].replace('\n', '')
    extension = ""
    if len(data_mod) > 5:
        extension = data_mod[5].replace('\n', '')

    dir_list = glob.glob("{path_project}/*{extension}".format(path_project=path_project, extension=extension))
    project_list = [ os.path.basename(path_project) for path_project in sorted(dir_list) ]

    # make me a menu please
    menu = "<openbox_pipe_menu>"
    menu += "<separator label=\"{}\"/>".format(name_mod)
    for idx, project in enumerate(project_list,1):
        menu += "<item label=\"{}: {}\">".format(idx, project)
        menu += "<action name=\"Execute\"><command>send_osc 8000 /opendsp/project/load {} 0</command></action>".format(idx)
        menu += "</item>"
    menu += "</openbox_pipe_menu>"

    print(menu)
