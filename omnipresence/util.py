from ConfigParser import SafeConfigParser

class OmnipresenceConfigParser(SafeConfigParser):
    # Option names need to be parsed case-sensitively, as they are used to 
    # determine things like modules to import.
    optionxform = str

    def getdefault(self, section, option, default):
        if self.has_option(section, option):
            return self.get(section, option)

        return default

    def getspacelist(self, *args, **kwargs):
        value = self.get(*args, **kwargs)
        return map(lambda x: x.strip(), value.split())


def canonicalize(name):
    return name.lower().replace('[',  '{').replace(']',  '}') \
                       .replace('\\', '|').replace('^',  '~')
