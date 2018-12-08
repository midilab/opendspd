from abc import ABCMeta, abstractmethod

class App(metaclass=ABCMeta):
    
    odsp = None
    params = None
            
    def __init__(self, openDspManager):
        self.odsp = openDspManager
        # set params
        self.params = self.odsp.getAppParams()

    @abstractmethod
    def start(self):
        """ Little description

        Parameters
        ----------
        param1 : str
          Param 1 description
        param2 : integer
          Param 2 description

        Returns
        -------
        An description of what it needs to return
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
