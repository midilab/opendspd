# opendspd
OpenDSP Service Core

STILL UNDER DEVELOPMENT!

OpenDSP is a small linux sub-distro aimed for a general DSP - Digital Signal Processing - on portable headless devices like ARM and Intel Computing.
  - Realtime kernel
  - DSP Core - Collection of basis apps for DSP used for OpenDSP Apps.

OpenDSPd is daemon/service for controlled DSP environment on headless unix machines.
    A OpenDSP Application is:
        + DSP apps dependencies - not part of the package, its a dependency for install this one.
        + Non Session Manager session directory for factory default base app root structure and configuration - the new save projects will be saved in a different directory
        + MIDI/OSC Command mapping script for the user interface - mididings for MIDI and xdotool for X11 apps interface


Directory structures
/usr/share/opendsp/
/usr/bin/opendspd
/usr/lib/opendsp/

API
openDSP(app_name)
closeDSP(app_name)
saveDSP(id)
saveDSPSession(id) // if id do not exist, create a new project(saveAS like)
openDSPSession(id)
closeDSPSession(id)

shutdown()
reboot()

MIDIDINGS for main MIDI control
http://das.nasophon.de/mididings/
Manual: http://dsacre.github.io/mididings/doc/

PYLIBLO
for OSC control
http://das.nasophon.de/pyliblo/

sudo pip install pyliblo psutil

sudo pacman -S mididings 
#boost boost-libs

# for headless shit
sudo pacman -S xf86-video-dummy

The APP writer needs:
+ Script to tell what commands from MIDI or OSC will be mapped to what UI functions.
+ Script to interact with the real apps and create the UI functions MAP for the first script
+ Non Session Manager Session Files

All the saved projects are Non session manager projects plus the apps other project files 

opendsp: a package to transform your archlinux into a headless blackbox for DSP, controlled via MIDI/OSC using external usb controller or ethernet.
  - Headless
  - MIDI/OSC control API for non-session-managment(channel 16 on MIDI) and APPs
    + loadApp(): Loads default installed initial session for App - readonly 
    + loadSession(): Loads a user saved App session 
    + saveSession():
    + saveSessionAs():

  - usb storage automount for apps usage or save in a HDD partition/path

    + File structure to organize the open and save functionalities
    /opendsp/[ap_name]/
    /opendsp/

  - mounting share via samba for configs, apps, sessions?
    + /config
    + /app
      - tracker
      - DSP rack
      - looper
    + /session: 1-knob for seletion and a save button. 2-CC number for selection and a save button. saveas action saves the session to the next avaliable session slot
      - /1
      - /2
      - /3
      - /4
      - /...
      - /128

opendsp-tracker: a tracker for your opendsp blackbox 
  - non-session-manager session files
  - opendsp control script - middings will read this script
  - the tracker app

opendsp-efxbox: a efx rack processment for your opendsp blackbox

opendsp-rack: a rack for DSP plugins

opendsp-multirack-looper: a multitrack audio looper

