from opendspd import opendspd

class App:

    # Core singleton instance
    opendsp = None
    config = None
    app = None
    data = {}

    def __init__(self, config, app):
        self.config = config
        self.app = app
        # opendsp Core is a singleton
        self.opendsp = opendspd.Core()

    def __del__(self):
        self.data['proc'].kill()

    def start(self):
        argments = None

        if 'project' in self.config:
            argments = "{0}{1}".format(self.app['path'], self.config['project'].replace("\"", ""))
                
        if 'display' in self.config:        
            # start the app with or without display
            if 'native' in self.config['display']:
                self.data['proc'] = self.opendsp.display(self.app['bin'], argments)
            elif 'virtual' in self.config['display']:
                self.data['proc'] = self.opendsp.display_virtual(self.app['bin'], argments)
        else:
            self.data['proc'] = self.opendsp.background(self.app['bin'], argments)

        # generate a list from, parsed by ','
        if 'audio_input' in self.app:
            self.data['audio_input'] = [ audio_input for audio_input in self.app['audio_input'].split(",") ]
        if 'audio_output' in self.app:
            self.data['audio_output'] = [ audio_output for audio_output in self.app['audio_output'].split(",") ]
        if 'midi_input' in self.app:
            self.data['midi_input'] = [ midi_input for midi_input in self.app['midi_input'].split(",") ]
        if 'midi_output' in self.app:
            self.data['midi_output'] = [ midi_output for midi_output in self.app['midi_output'].split(",") ]

        if 'realtime' in self.app:
            self.opendsp.set_realtime(self.data['proc'].pid, int(self.app['realtime']))  

