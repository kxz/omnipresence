from zope.interface import implements
from twisted.plugin import IPlugin
from omnipresence.iomnipresence import ICommand
from omnipresence import util

class HelpCommand(object):
    """
    \x02%s\x02 [\x1Fkeyword\x1F] - List the keywords of available commands, or, 
    given a keyword, get detailed help on a specific command.
    """
    implements(IPlugin, ICommand)
    name = 'help'
    
    def execute(self, bot, prefix, reply_target, channel, args):
        args = args.split()
        
        if len(args) > 1 and args[1]:
            if args[1] in self.factory.commands:
                help_text = self.factory.commands[args[1]].__doc__
                
                if help_text:
                    help_text = ' '.join(help_text.strip().split())
                else:
                    help_text = 'No further help is available for \x02%s\x02.'
            else:
                help_text = 'There is no command with the keyword \x02%s\x02.'
            
            help_text = help_text % args[1]
        else:
            keywords = sorted(self.factory.commands)
            help_text = (
                'Available commands: \x02%s\x02. For further help, use '
                '\x02%s\x02 \x1Fkeyword\x1F. To redirect a command reply '
                'to another user, use \x1Fcommand\x1F \x02>\x02 \x1Fnick\x1F. '
                '%s' % (
                    '\x02, \x02'.join(keywords), args[0],
                    self.factory.config.getdefault('help', 'list_suffix', '')))

        bot.reply(reply_target, channel, help_text)

helpcommand = HelpCommand()
