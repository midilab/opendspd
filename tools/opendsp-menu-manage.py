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

if __name__ == '__main__':
    
    # make me a menu please
    menu = "<openbox_pipe_menu>"

    if os.path.exists("/var/tmp/opendsp-run-data"):
        # running
        # stop, restart
        menu += "<item label=\"Stop\">"
        menu += "<action name=\"Execute\"><command>/sbin/sudo /sbin/systemctl stop opendsp</command></action>"
        menu += "</item>"
        menu += "<item label=\"Restart\">"
        menu += "<action name=\"Execute\"><command>/sbin/sudo /sbin/systemctl restart opendsp</command></action>"
        menu += "</item>"
    else:
        # not running
        # start
        menu += "<item label=\"Start\">"
        menu += "<action name=\"Execute\"><command>/sbin/sudo /sbin/systemctl start opendsp</command></action>"
        menu += "</item>"

    # tools: resizesd
    if os.path.exists("/usr/bin/resizesd"):
        menu += "<menu id=\"opendsp-tools\" label=\"Tools\">"
        menu += "<item label=\"Resize SD user data\">"
        menu += "<action name=\"Execute\"><command>/usr/bin/urxvt -e /sbin/sudo /usr/bin/resizesd</command></action>"
        menu += "</item>"
        menu += "</menu>"

    menu += "</openbox_pipe_menu>"

    print(menu)
