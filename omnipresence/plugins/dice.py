from collections import defaultdict, Counter
from random import randint

from twisted.plugin import IPlugin
from zope.interface import implements

from omnipresence.iomnipresence import ICommand
from omnipresence.ircutil import canonicalize
from omnipresence.util import andify


MAX_DIE_GROUP_SIZE = 42


def format_rolls(rolls):
    """Return a string representing the given *rolls* and their sum, in
    the form `"1 2 3 4 = 10"`."""
    rolls = list(rolls)
    if not rolls:
        return 'no rolls'
    return '\x02{}\x02 = {}'.format(' '.join(str(r) for r in sorted(rolls)),
                                    sum(rolls))


def roll_dice(dice):
    """Return random rolls for the *dice* given as an iterable
    containing some combination of individual die group specifications
    as strings, such as `"2d6"`.  Integers are accepted as dice; they
    "roll" to themselves."""
    rolls = []
    for die_group in dice:
        number, d, size = die_group.rpartition('d')
        constant = not d
        # Set the number of dice to 1 if this is a "constant" integer
        # die, or there is no number specified (so "d8" == "1d8").
        if constant or not number:
            number = 1
        try:
            number = int(number)
            size = int(size)
        except ValueError:
            raise ValueError('Invalid die group specification {}.'
                             .format(die_group))
        if number < 1:
            raise ValueError('Invalid number of dice {}.'.format(number))
        if size < 1:
            raise ValueError('Invalid die size {}.'.format(size))
        if len(rolls) + number > MAX_DIE_GROUP_SIZE:
            raise ValueError('Cannot roll more than {} dice at once.'
                             .format(MAX_DIE_GROUP_SIZE))
        for i in xrange(number):
            rolls.append(size if constant else randint(1, size))
    return rolls


class Dice(object):
    """
    \x02%s\x02 [\x1Faction\x1F] - With no action, display the dice in
    your die bank. With \x02show\x02 [\x1Fnick\x1F], show the dice in
    the die bank belonging to the user with the given nick. With
    \x02roll\x02 \x1Fdice\x1F, roll the given dice; \x02add\x02
    additionally adds the result to your die bank. With \x02use\x02
    \x1Frolls\x1F, remove the given rolls from your die bank. With
    \x02clear\x02, remove all rolls from your die bank.
    """
    implements(IPlugin, ICommand)
    name = 'dice'

    def __init__(self):
        self.banks = defaultdict(Counter)
        """User die banks, keyed by a (channel, nick) tuple."""

    def execute(self, bot, prefix, reply_target, channel, args):
        nick = canonicalize(prefix.split('!', 1)[0].strip())
        args = args.split(None, 2)
        if len(args) < 2:
            args.append('show')
        if args[1] == 'show':
            if len(args) < 3:
                # Show the user's own die bank if no nick is
                # provided in the command.
                requested_nick = nick
            else:
                requested_nick = canonicalize(args[2])
            rolls = self.banks[(channel, requested_nick)].elements()
            if not rolls:
                # The bank is empty.
                bot.reply(reply_target, channel, 'Empty bank.')
                return
            bot.reply(reply_target, channel,
                      'Bank has {}.'.format(format_rolls(rolls)))
            return
        if args[1] in ('roll', 'add'):
            if len(args) < 3:
                bot.reply(prefix, channel,
                          'Please specify dice to roll.')
                return
            dice = args[2].split()
            try:
                rolls = roll_dice(dice)
            except ValueError as e:
                # Just pass the error message up to the user.
                bot.reply(prefix, channel, str(e))
                return
            message = 'Rolled {}.'.format(format_rolls(rolls))
            if args[1] == 'add':
                bank = self.banks[(channel, nick)]
                bank.update(rolls)
                message += ' Bank now has {}.'.format(
                    format_rolls(bank.elements()))
            bot.reply(reply_target, channel, message)
            return
        if args[1] == 'use':
            if len(args) < 3:
                bot.reply(prefix, channel,
                          'Please specify rolls to use.')
                return
            try:
                rolls = map(int, args[2].split())
            except ValueError as e:
                bot.reply(prefix, channel,
                          '{} is not a valid roll.'.format(str(e)))
                return
            # Figure out if the specified rolls actually exist by
            # duplicating the bank, subtracting the rolls from it,
            # and bailing if any of the counts are negative.
            new_bank = Counter(self.banks[(channel, nick)])
            new_bank.subtract(rolls)
            negatives = sorted([
                roll for roll, count in new_bank.iteritems() if count < 0])
            if negatives:
                bot.reply(prefix, channel,
                          'You do not have enough {} in your die '
                          'bank to use those rolls.'.format(
                              andify(['{}s'.format(n) for n in negatives])))
                return
            self.banks[(channel, nick)] = new_bank
            bot.reply(reply_target, channel,
                      'Used {}. Bank now has {}.'.format(
                          format_rolls(rolls),
                          format_rolls(new_bank.elements())))
            return
        if args[1] == 'clear':
            del self.banks[(channel, nick)]
            bot.reply(reply_target, channel, 'Bank cleared.')
            return
        bot.reply(prefix, channel,
                  'Unrecognized subcommand \x02%s\x02.' % args[1])
        return


default = Dice()
