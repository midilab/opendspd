# opendspd
OpenDSP Service Core

OpenDSP is a linux sub-distro aimed for a general DSP - Digital Signal Processing - on portable headless devices like ARM and Intel Computing. You can download OpenDSP linux distribution at http://github.com/midilab/opendsp

![Image of OpenDSP Plugmod and DX7  view](https://raw.githubusercontent.com/midilab/opendsp/master/doc/plugmod-opendsp.jpg)

OpenDSPd is daemon/service for controlled DSP environment on headless unix machines. 
This service core gives you a clean and simple interface to code your own headless MIDI/OSC responsive DSP box. 
Code your own opendsp app by glueing your prefered linux DSP apps on a integrated ecosystem that are able to: 

+ Route, exchange and control MIDI/OSC devices and it self. 
+ Automate user interface tasks to make your app ecosystem works like a real headless music or video standalone gear for professional usage on studio or live stage.

## OpenDSP Apps

opendsp-djing: a complete djing environment at the size of your pocket

opendsp-plugmod: a multitrack rack for DSP plugins, just like muse receptor, but its really opensource! 

## OpenDSP Apps to come

opendsp-mapping: a video mapping ecosystem  

opendsp-tracker: a tracker for your opendsp  

opendsp-multirack-looper: a multitrack audio looper  

## App main interface

The most basic app you can write goes along with default App abstract interface  

```python
class App():
    
    @abstractmethod
    def start(self):
        """ Get app ecosystem up and running

        Prepare your OpenDSP app environment before run()
        """                     
        pass

    @abstractmethod
    def run(self):
        """ All the app lifecyle

        Called by Core in endless cycles 
        """                     
        pass
         
    @abstractmethod
    def stop(self):
        pass
         
    @abstractmethod
    def load_project(self, project):
        pass

    @abstractmethod
    def save_project(self, project):
        pass

    @abstractmethod
    def get_midi_processor(self):
        pass
    
    @abstractmethod    
    def midi_processor_queue(self, event):
        pass
```        
