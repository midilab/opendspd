from abc import ABCMeta, abstractmethod

class App(metaclass=ABCMeta):
    
    odsp = None
    params = None
                
    def __init__(self, openDspManager):
        self.odsp = openDspManager
        # set params
        self.params = self.odsp.getAppParams()
        self.jack = self.odsp.getJackClient()

    @abstractmethod
    def start(self):
        """ Get app ecosystem up and running

        Blah...
        """                     
        pass
 
    @abstractmethod
    def stop(self):
        pass
    
    @abstractmethod
    def run(self):
        """ All the app lifecyle

        This method is called inside a thread and it never returns
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
