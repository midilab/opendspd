import time
import threading

from opendspd import opendspd

from . import app

class Mod:

    # Core singleton instance
    opendsp = None

    # App objects map
    app = {}

    # config data
    config_mod = None
    config_app = None

    # running state
    running = False

    # running thread
    thread = None

    def __init__(self, config_mod, config_app):
        self.config_mod = config_mod
        self.config_app = config_app
        # opendsp Core is a singleton
        self.opendsp = opendspd.Core()

    def __del__(self):
        self.running = False
        # delete all Apps objects
        for app in self.app:
            del app

    def start(self):
        # construct a list of apps config objects to be used as mod apps ecosystem
        apps = [ self.config_mod[app] for app in self.config_mod if 'app' in app ]
        # one app per config entry
        for config in apps:
            name_app = config.get('name')
            if name_app in self.config_app:
                # instantiate App object and keep track of it on app map
                self.app[name_app] = app.App(config, self.config_app[name_app])
                self.app[name_app].start()

        # thread the run method until we're dead
        self.thread = threading.Thread(target=self.run, args=(), daemon=True)
        self.thread.start()

    def run(self):
        self.running = True
        while self.running:
            time.sleep(5)
            # manage connections
            #self.opendsp.jack()...
