from ConfigParser import SafeConfigParser


class ConfigParser(SafeConfigParser):
    """An extension of Python's built-in `~ConfigParser.ConfigParser`.
    """

    # Option names need to be parsed case-sensitively, as they are used to
    # determine things like modules to import.
    optionxform = str

    def getdefault(self, section, option, default=None):
        """Return the value of the specified option in the specified
        section, or *default* if no such option exists."""
        if self.has_option(section, option):
            return self.get(section, option)
        return default

    def getspacelist(self, *args, **kwargs):
        """Return the value of the specified option, converted to a list
        by splitting on whitespace."""
        return self.get(*args, **kwargs).split()
