# opendspd

![Image of OpenDSP Plugmod and DX7  view](https://raw.githubusercontent.com/midilab/opendsp/master/doc/plugmod-opendsp.jpg)

OpenDSPd is daemon/service for controlled DSP environment on headless unix machines. 
This service core gives you a clean and simple interface to code your own headless MIDI/OSC responsive DSP box. 
Code your own opendsp app by glueing your prefered linux DSP apps on a integrated ecosystem that are able to: 

+ Route, exchange and control MIDI/OSC devices and it self. 
+ Automate user interface tasks to make your app ecosystem works like a real headless music or video standalone gear for professional usage on studio or live stage.

## OpenDSP Apps

OpenDSP application is a sub-set of N applications with a predefined state relation between then called Mod.
  
A Mod can have any number of applications and audio/video connections between then as far as you processor can handle it all.  
  
By merging different applications you can achieve different kinda of DSP tasks to use as a standalone dedicated audio/video gear in an automated way via MIDI and OSC protocols or via common mouse/keyboard and monitor desktop station.  
  
You can write your own Mod with a very few lines of configuration, just check some examples at mod/ directory of user data partition.  

Examples can be found inside data/ directory.  
  
## App main interface

By making use of Mod config files you can define your own with a few lines of configuration  
  
On the above example you setup a standalone tracker with visualization responds to audio on your screen and a keyboard used as a midi controller to play some sunvox synthesizers.    

```ini
[app1]
name: sunvox-lofi
path: /projects/sunvox/
project: Transient - Can It Be Beautiful.sunvox
display: virtual
midi_input: "opendsp:1"
audio_output: "opendsp:1, opendsp:2"

[app2]
name: lebiniou
path: /projects/lebiniou/
args: -x 640 -y 480
project: "opendsp,opendsp2"
display: native
audio_input: "sunvox:1, sunvox:2"

[app3]
name: input2midi
path: /projects/input2midi/
project: inputtomidi.json
midi_output: "opendsp:1"
```

## Ecosystem DSP applications

You can create Mods ussing the following opensource applications ecosystem:

+ loopers  
– giada  
– luppp  
+ djing  
– mixxx  
– wxax  
+ daw/sequencer  
– lmms  
– hydrogen  
– qtractor  
– non-daw  
– non-mixer  
– non-sequencer  
+ trackers  
– sunvox  
– milkytrack  
+ modular synthesis  
– carla  
– carla-rack  
– ingen  
+ video  
– lebiniou  
– xjadeo  
– vlc  
+ modular programming  
– puredata  
– non-session-manager  
+ audio plugins  
410 audio plugins, from effects to classic synthesizer emulations  
