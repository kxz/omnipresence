from ConfigParser import SafeConfigParser


class OmnipresenceConfigParser(SafeConfigParser):
    """An extension of ConfigParser with Omnipresence-specific methods."""
    # Option names need to be parsed case-sensitively, as they are used to 
    # determine things like modules to import.
    optionxform = str

    def getdefault(self, section, option, default):
        """Get the value of the specified option in the specified section, or 
        return the given default if this option does not exist."""
        if self.has_option(section, option):
            return self.get(section, option)

        return default

    def getspacelist(self, *args, **kwargs):
        """Get the value of the specified option converted to a list, split 
        on whitespace."""
        return self.get(*args, **kwargs).split()