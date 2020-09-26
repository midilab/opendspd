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
    menu += "<separator label=\"Manage\"/>"

    # display menu
    menu += "<menu id=\"opendsp-display\" label=\"Display\">"
    menu += "<separator label=\"Force Display\"/>"
    # do not force display setup
    menu += "<item label=\"Disable\">"
    menu += "<action name=\"Execute\"><command>send_osc 8000 /opendsp/display/force_screen 'off'</command></action>"
    menu += "</item>"
    # force into native
    menu += "<item label=\"Native HDMI\">"
    menu += "<action name=\"Execute\"><command>send_osc 8000 /opendsp/display/force_screen 'native'</command></action>"
    menu += "</item>"
    # force into virtual
    menu += "<item label=\"Virtual VNC\">"
    menu += "<action name=\"Execute\"><command>send_osc 8000 /opendsp/display/force_screen 'virtual'</command></action>"
    menu += "</item>"
    menu += "</menu>"

    # tools menu
    menu += "<menu id=\"opendsp-tools\" label=\"Tools\">"
    menu += "<separator label=\"Tools\"/>"
    # global change password
    menu += "<item label=\"Change password\">"
    menu += "<action name=\"Execute\"><command>/usr/bin/urxvt -e /usr/bin/changepassword</command></action>"
    menu += "</item>"
    # resizesd 
    if os.path.exists("/usr/bin/resizesd"):
        menu += "<item label=\"Resize SD user data\">"
        menu += "<action name=\"Execute\"><command>/sbin/sudo /usr/bin/urxvt -e /sbin/sudo /usr/bin/resizesd</command></action>"
        menu += "</item>"
    menu += "</menu>"

    # updates menu
    menu += "<menu id=\"opendsp-updates\" label=\"Updates\">"
    menu += "<separator label=\"Updates\"/>"
    # opendspd
    menu += "<item label=\"OpenDSP Daemon\">"
    menu += "<action name=\"Execute\"><command>/sbin/sudo /usr/bin/urxvt -e /usr/bin/opendspd-update</command></action>"
    menu += "</item>"
    # vlc youtube script to stream play update(look mom! no ads!)
    menu += "<item label=\"VLC Youtube\">"
    menu += "<action name=\"Execute\"><command>/sbin/sudo /usr/bin/urxvt -e /usr/bin/vlc-youtube-update</command></action>"
    menu += "</item>"
    menu += "</menu>"

    # start, stop, restart menu
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


    menu += "</openbox_pipe_menu>"

    print(menu)

