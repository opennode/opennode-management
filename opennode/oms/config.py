import ConfigParser
import os

_config = None

def get_config():
    global _config
    if not _config:
        _config = OmsConfig()
    return _config    

class OmsConfig(ConfigParser.ConfigParser):
    def __init__(self, config_name='opennode-oms.conf', config_path='/etc/opennode'):
        super(OmsConfig, self).__init__()
        self.config_path = config_path
        self.config_name = config_name
        # read in OMS configuration values
        self.read(self.detect_configuration_fnm())

    def detect_configuration_fnm(self):
        """ Return a filename of the configuration file. Local file has a higher 
        priority than what's defined in config_path. """
        if os.path.isfile(self.config_name):
            return self.config_name
        elif os.path.isfile(os.path.join([self.config_path, self.config_name])):
            return os.path.join([self.config_path, self.config_name])
        else:
            raise RuntimeError, "Couldn't find OMS configuration file."
