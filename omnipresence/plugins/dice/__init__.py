# -*- test-case-name: omnipresence.plugins.dice.test_dice
"""Event plugins for storing banks of die rolls used in role-playing
games."""


from collections import defaultdict, Counter
from random import Random

from ...humanize import andify
from ...message import collapse
from ...plugin import SubcommandEventPlugin, UserVisibleError


#: The maximum number of dice that can be rolled at once.
MAX_DIE_GROUP_SIZE = 42


def format_rolls(rolls):
    """Return a string representing the given *rolls* and their sum, in
    the form `"1 2 3 4 = 10"`."""
    rolls = list(rolls)
    if not rolls:
        return 'no rolls'
    return '\x02{}\x02 = {}'.format(
        ' '.join(str(r) for r in sorted(rolls)), sum(rolls))


class Default(SubcommandEventPlugin):
    def __init__(self):
        #: User die banks, keyed by a (channel, nick) tuple.
        self.banks = defaultdict(Counter)
        #: The instance of `random.Random` used for die rolls.  This is
        #: overridden for deterministic testing.
        self.random = Random()

    def roll_dice(self, dice):
        """Return random rolls for the *dice* given as an iterable
        containing some combination of individual die groups as strings,
        such as `"2d6"`.  Integers are accepted as dice; they "roll" to
        themselves."""
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
            for _ in xrange(number):
                rolls.append(size if constant
                             else self.random.randint(1, size))
        return rolls

    def reply_for_roll(self, msg, args, update=False, clear=False):
        nick = msg.connection._lower(msg.actor.nick)
        if not args:
            raise UserVisibleError('Please specify dice to roll.')
        try:
            rolls = self.roll_dice(args.split())
        except ValueError as e:
            raise UserVisibleError(str(e))
        message = 'Rolled {}.'.format(format_rolls(rolls))
        if update:
            if clear:
                self.banks.pop((msg.venue, nick), None)
            bank = self.banks[(msg.venue, nick)]
            bank.update(rolls)
            message += ' Bank now has {}.'.format(
                format_rolls(bank.elements()))
        return message

    def on_empty_subcommand(self, msg):
        return self.on_subcommand_show(msg, '')

    def on_empty_subcmdhelp(self, msg):
        return ('[\x02add\x02 \x1Fdice\x1F | '
                    '\x02clear\x02 | '
                    '\x02new\x02 \x1Fdice\x1F | '
                    '\x02roll\x02 \x1Fdice\x1F | '
                    '\x02show\x02 [\x1Fnick\x1F] | '
                    '\x02use\x02 \x1Frolls\x1F] - '
                'Manage your die bank. '
                'For more details on a specific subcommand, see help '
                'for \x02{0}\x02 \x1Fsubcommand\x1F. '
                'For information on dice notation, see help for '
                '\x02{0} notation\x02.').format(msg.subaction)

    def on_subcommand_add(self, msg, args):
        return self.reply_for_roll(msg, args, update=True)

    def on_subcmdhelp_add(self, msg):
        return ('\x1Fdice\x1F - Roll the given dice and add the '
                'resulting rolls to your die bank.')

    def on_subcommand_clear(self, msg, args):
        nick = msg.connection._lower(msg.actor.nick)
        self.banks.pop((msg.venue, nick), None)
        return 'Bank cleared.'

    def on_subcmdhelp_clear(self, msg):
        return '- Remove all rolls from your die bank.'

    def on_subcommand_new(self, msg, args):
        return self.reply_for_roll(msg, args, update=True, clear=True)

    def on_subcmdhelp_new(self, msg):
        return ('\x1Fdice\x1F - Remove all rolls from your die bank, '
                'then roll the given dice and add the resulting rolls '
                'to your die bank.')

    def on_subcmdhelp_notation(self, msg):
        return ('- Indicate dice using the standard '
                '\x1FA\x1F\x02d\x02\x1FX\x1F notation, where \x1FA\x1F '
                'is the number of dice to roll and \x1FX\x1F is the '
                'die size. '
                'Separate multiple sets of dice with spaces. '
                'Positive integers may also be used as dice; they '
                '"roll" to themselves.')

    def on_subcommand_roll(self, msg, args):
        return self.reply_for_roll(msg, args)

    def on_subcmdhelp_roll(self, msg):
        return ('\x1Fdice\x1F - Roll the given dice without adding the '
                ' resulting rolls to your die bank.')

    def on_subcommand_show(self, msg, args):
        nick = msg.connection._lower(args or msg.actor.nick)
        rolls = self.banks[(msg.venue, nick)].elements()
        return 'Bank has {}.'.format(format_rolls(rolls))

    def on_subcmdhelp_show(self, msg):
        return ('[\x1Fnick\x1F] - Show the rolls in the die bank '
                'belonging to the user with the given nick, or your '
                'own if no nick is provided.')

    def on_subcommand_use(self, msg, args):
        nick = msg.connection._lower(msg.actor.nick)
        if not args:
            raise UserVisibleError('Please specify rolls to use.')
        rolls = []
        for roll in args.split():
            try:
                rolls.append(int(roll))
            except ValueError:
                raise UserVisibleError('{} is not a valid roll.'.format(roll))
        # Figure out if the specified rolls actually exist by
        # duplicating the bank, subtracting the rolls from it,
        # and bailing if any of the counts are negative.
        new_bank = Counter(self.banks[(msg.venue, nick)])
        new_bank.subtract(rolls)
        negatives = sorted([
            roll for roll, count in new_bank.iteritems() if count < 0])
        if negatives:
            raise UserVisibleError(
                'You do not have enough {} in your die bank to use '
                'those rolls.'.format(
                    andify(['{}s'.format(n) for n in negatives])))
        self.banks[(msg.venue, nick)] = new_bank
        return 'Used {}. Bank now has {}.'.format(
            format_rolls(rolls),
            format_rolls(new_bank.elements()))

    def on_subcmdhelp_use(self, msg):
        return '\x1Frolls\x1F - Remove the given rolls from your die bank.'

    def on_nick(self, msg):
        venues = [venue for venue, nick in self.banks
                  if msg.connection.case_mapping.equates(msg.actor.nick, nick)]
        old_nick = msg.connection._lower(msg.actor.nick)
        new_nick = msg.connection._lower(msg.content)
        for venue in venues:
            self.banks[(venue, new_nick)] = self.banks[(venue, old_nick)]
            del self.banks[(venue, old_nick)]
