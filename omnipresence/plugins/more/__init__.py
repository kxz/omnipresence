# -*- test-case-name: omnipresence.plugins.help.test
"""Event plugins for reading command reply buffers."""


from ...plugin import EventPlugin


class Default(EventPlugin):
    def on_command(self, msg):
        return

    def on_cmdhelp(self, msg):
        return
