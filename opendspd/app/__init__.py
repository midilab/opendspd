from abc import ABCMeta, abstractmethod

class App(metaclass=ABCMeta):
    
    def __init__(self, opendsp_core):
        self.opendsp = opendsp_core
        self.params = self.opendsp.config['app']

    @abstractmethod
    def start(self):
        """ Get app ecosystem up and running

        Prepare your OpenDSP app environment before run()
        """                     
        pass
 
    @abstractmethod
    def stop(self):
        pass
    
    @abstractmethod
    def run(self):
        """ All the app lifecyle

        Called by Core in endless cycles 
        """                     
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
        
