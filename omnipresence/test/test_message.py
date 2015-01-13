# -*- coding: utf-8
"""Unit tests for IRC message handling."""
# pylint: disable=missing-docstring,too-few-public-methods


import re

from twisted.trial import unittest

from ..hostmask import Hostmask
from ..message import Message, chunk
from ._helpers import DummyConnection


class RawParsingTestCase(unittest.TestCase):
    def setUp(self):
        self.connection = DummyConnection()

    def _from_raw(self, raw):
        return Message.from_raw(self.connection, raw)

    def test_channel_message(self):
        msg = self._from_raw(':nick!user@host PRIVMSG #foo :lorem ipsum')
        self.assertEqual(msg.actor, Hostmask('nick', 'user', 'host'))
        self.assertEqual(msg.action, 'privmsg')
        self.assertEqual(msg.venue, '#foo')
        self.assertIsNone(msg.target)
        self.assertIsNone(msg.subaction)
        self.assertEqual(msg.content, 'lorem ipsum')
        self.assertFalse(msg.private)

    def test_private_message(self):
        msg = self._from_raw(':nick!user@host PRIVMSG foo :lorem ipsum')
        self.assertEqual(msg.actor, Hostmask('nick', 'user', 'host'))
        self.assertEqual(msg.action, 'privmsg')
        self.assertEqual(msg.venue, 'foo')
        self.assertIsNone(msg.target)
        self.assertIsNone(msg.subaction)
        self.assertEqual(msg.content, 'lorem ipsum')
        self.assertTrue(msg.private)

    def test_channel_notice(self):
        msg = self._from_raw(':nick!user@host NOTICE #foo :lorem ipsum')
        self.assertEqual(msg.actor, Hostmask('nick', 'user', 'host'))
        self.assertEqual(msg.action, 'notice')
        self.assertEqual(msg.venue, '#foo')
        self.assertIsNone(msg.target)
        self.assertIsNone(msg.subaction)
        self.assertEqual(msg.content, 'lorem ipsum')
        self.assertFalse(msg.private)

    def test_private_notice(self):
        msg = self._from_raw(':nick!user@host NOTICE foo :lorem ipsum')
        self.assertEqual(msg.actor, Hostmask('nick', 'user', 'host'))
        self.assertEqual(msg.action, 'notice')
        self.assertEqual(msg.venue, 'foo')
        self.assertIsNone(msg.target)
        self.assertIsNone(msg.subaction)
        self.assertEqual(msg.content, 'lorem ipsum')
        self.assertTrue(msg.private)

    def test_unknown(self):
        msg = self._from_raw(':nick!user@host NONSENSE a b c :foo bar')
        self.assertEqual(msg.actor, Hostmask('nick', 'user', 'host'))
        self.assertEqual(msg.action, 'unknown')
        self.assertIsNone(msg.venue)
        self.assertIsNone(msg.target)
        self.assertEqual(msg.subaction, 'NONSENSE')
        self.assertEqual(msg.content, 'a b c :foo bar')
        self.assertFalse(msg.private)


class ExtractionTestCase(unittest.TestCase):
    def setUp(self):
        self.connection = DummyConnection()
        self.prototype = Message(self.connection, 'nick!user@host', 'privmsg')

    def _extract(self, content):
        return self.prototype._replace(content=content).extract_command(
            prefixes=['!', 'bot:', 'bot,'])

    def test_ignore_non_privmsg(self):
        self.assertIsNone(Message(
            self.connection, 'nick!user@host', 'topic').extract_command())

    def test_ignore_missing_prefix(self):
        self.assertIsNone(self._extract('ipsum'))

    def test_simple_command(self):
        msg = self._extract('!help')
        self.assertEqual(msg.action, 'command')
        self.assertEqual(msg.target, 'nick')
        self.assertEqual(msg.subaction, 'help')
        self.assertEqual(msg.content, '')

    def test_simple_command_with_long_prefix(self):
        msg = self._extract('bot: help')
        self.assertEqual(msg.action, 'command')
        self.assertEqual(msg.target, 'nick')
        self.assertEqual(msg.subaction, 'help')
        self.assertEqual(msg.content, '')

    def test_command_with_arguments(self):
        msg = self._extract('bot, help me')
        self.assertEqual(msg.action, 'command')
        self.assertEqual(msg.target, 'nick')
        self.assertEqual(msg.subaction, 'help')
        self.assertEqual(msg.content, 'me')

    def test_command_redirection(self):
        msg = self._extract('!help > other')
        self.assertEqual(msg.action, 'command')
        self.assertEqual(msg.target, 'other')
        self.assertEqual(msg.subaction, 'help')
        self.assertEqual(msg.content, '')

    def test_empty_command_redirection(self):
        msg = self._extract('!help >')
        self.assertEqual(msg.action, 'command')
        self.assertEqual(msg.target, 'nick')
        self.assertEqual(msg.subaction, 'help')
        self.assertEqual(msg.content, '')


class BufferingTestCase(unittest.TestCase):
    def collapse(self, s):
        """Return *s* with runs of whitespace collapsed to a single
        space, and any preceding or trailing whitespace removed."""
        return re.sub(r'\s+', ' ', s).strip()

    def test_type(self):
        self.assertRaises(TypeError, chunk, 42)

    def test_trivial(self):
        self.assertEqual(list(chunk('')), [])

    def test_str(self):
        message = self.collapse("""Esed volobore fermentum eleifend
            curae non inciduipit consequam deliquatue, tisi vulluptatet
            tristique. Odolorperos litora leo adignim feugiatue;
            dipiscipitismodi hendip iniam estrudismod nonsequam. Odolupt
            faciduisit litora, utetumm vullandigna henis tismolortis
            faciduisi odipsumsan, adit adio curae. Msandre psusto
            nonummy susciduipit adionsequat dolent faccummy alisis
            molore; veros sustrud alis hendipisim suscilla vitae. Taciti
            nonum aliscil facilisse cor; mollis summy modipsustie
            blaorismod dolortis. Enibh facincilitismod inim, pratisl
            alisi, urna eum, elesequ tet inceptosismoloreet sequis
            suscipit. Sumsandre ea amcommo ipsustrud auguero esse
            consequ. Illam quat ullutpat ametumm eugait, magniamet
            erostin iuscipit henit eriure irilla velestionse montes
            lobortis. Lor feugiatue nullum. Uamconum andrero facinci
            vulluptatum. Nisim netus fames esting vendipissit commolum
            facidunt.""")
        buf = chunk(message)
        self.assertEqual(next(buf), self.collapse("""Esed volobore
            fermentum eleifend curae non inciduipit consequam
            deliquatue, tisi vulluptatet tristique. Odolorperos litora
            leo adignim feugiatue; dipiscipitismodi hendip iniam
            estrudismod nonsequam. Odolupt faciduisit litora, utetumm
            vullandigna henis"""))
        self.assertEqual(next(buf), self.collapse("""tismolortis
            faciduisi odipsumsan, adit adio curae. Msandre psusto
            nonummy susciduipit adionsequat dolent faccummy alisis
            molore; veros sustrud alis hendipisim suscilla vitae. Taciti
            nonum aliscil facilisse cor; mollis summy modipsustie
            blaorismod"""))
        self.assertEqual(next(buf), self.collapse("""dolortis. Enibh
            facincilitismod inim, pratisl alisi, urna eum, elesequ tet
            inceptosismoloreet sequis suscipit. Sumsandre ea amcommo
            ipsustrud auguero esse consequ. Illam quat ullutpat ametumm
            eugait, magniamet erostin iuscipit henit eriure irilla"""))
        self.assertEqual(next(buf), self.collapse("""velestionse montes
            lobortis. Lor feugiatue nullum. Uamconum andrero facinci
            vulluptatum. Nisim netus fames esting vendipissit commolum
            facidunt."""))
        self.assertRaises(StopIteration, next, buf)

    def test_unicode(self):
        message = self.collapse(u"""
            《施氏食狮史》
            石室诗士施氏，嗜狮，誓食十狮。
            氏时时适市视狮。
            十时，适十狮适市。
            是时，适施氏适市。
            氏视是十狮，恃矢势，使是十狮逝世。
            氏拾是十狮尸，适石室。
            石室湿，氏使侍拭石室。
            石室拭，氏始试食是十狮。
            食时，始识是十狮尸，实十石狮尸。
            试释是事。
            """)
        buf = chunk(message)
        self.assertEqual(next(buf), self.collapse(u"""
            《施氏食狮史》
            石室诗士施氏，嗜狮，誓食十狮。
            氏时时适市视狮。
            十时，适十狮适市。
            是时，适施氏适市。
            氏视是十狮，恃矢势，使是十狮逝世。
            氏拾是十狮尸，适石室。
            """).encode('utf-8'))
        self.assertEqual(next(buf), self.collapse(u"""
            石室湿，氏使侍拭石室。
            石室拭，氏始试食是十狮。
            食时，始识是十狮尸，实十石狮尸。
            试释是事。
            """).encode('utf-8'))
        self.assertRaises(StopIteration, next, buf)

    def test_formatting(self):
        message = self.collapse("""\x0314Esed volobore fermentum
            eleifend curae non inciduipit consequam deliquatue, tisi
            vulluptatet tristique. Odolorperos litora leo adignim
            feugiatue; dipiscipitismodi hendip iniam estrudismod
            nonsequam. Odolupt faciduisit litora, utetumm vullandigna
            henis tismolortis faciduisi odipsumsan, adit adio curae.
            Msandre psusto nonummy susciduipit adionsequat dolent
            faccummy alisis molore; veros sustrud alis hendipisim
            suscilla vitae. Taciti nonum aliscil facilisse cor; mollis
            summy modipsustie blaorismod dolortis. Enibh facincilitismod
            inim, pratisl alisi, urna eum, elesequ tet
            inceptosismoloreet sequis suscipit. Sumsandre ea amcommo
            ipsustrud auguero esse consequ. Illam quat ullutpat ametumm
            eugait, magniamet erostin iuscipit henit eriure irilla
            velestionse montes lobortis. Lor feugiatue nullum. Uamconum
            andrero facinci vulluptatum. Nisim netus fames esting
            vendipissit commolum facidunt.""")
        buf = chunk(message)
        self.assertEqual(next(buf), self.collapse("""\x0314Esed volobore
            fermentum eleifend curae non inciduipit consequam
            deliquatue, tisi vulluptatet tristique. Odolorperos litora
            leo adignim feugiatue; dipiscipitismodi hendip iniam
            estrudismod nonsequam. Odolupt faciduisit litora, utetumm
            vullandigna henis"""))
        self.assertEqual(next(buf), self.collapse("""\x0314tismolortis
            faciduisi odipsumsan, adit adio curae. Msandre psusto
            nonummy susciduipit adionsequat dolent faccummy alisis
            molore; veros sustrud alis hendipisim suscilla vitae. Taciti
            nonum aliscil facilisse cor; mollis summy modipsustie
            blaorismod"""))
        self.assertEqual(next(buf), self.collapse("""\x0314dolortis. Enibh
            facincilitismod inim, pratisl alisi, urna eum, elesequ tet
            inceptosismoloreet sequis suscipit. Sumsandre ea amcommo
            ipsustrud auguero esse consequ. Illam quat ullutpat ametumm
            eugait, magniamet erostin iuscipit henit eriure irilla"""))
        self.assertEqual(next(buf), self.collapse("""\x0314velestionse
            montes lobortis. Lor feugiatue nullum. Uamconum andrero
            facinci vulluptatum. Nisim netus fames esting vendipissit
            commolum facidunt."""))
        self.assertRaises(StopIteration, next, buf)
