# -*- coding: utf-8
"""Unit tests for IRC message handling."""
# pylint: disable=missing-docstring,too-few-public-methods


from twisted.trial.unittest import TestCase

from ..compat import length_hint
from ..hostmask import Hostmask
from ..message import Message, MessageType, ReplyBuffer, collapse
from .helpers import DummyConnection


class MessageTestCase(TestCase):
    def test_invalid_action(self):
        self.assertRaises(ValueError, Message, None, False, 'foo')


class RawParsingTestCase(TestCase):
    def setUp(self):
        self.connection = DummyConnection()

    def _from_raw(self, raw, **kwargs):
        msg = Message.from_raw(
            self.connection, False, ':nick!user@host ' + raw, **kwargs)
        if raw:
            self.assertEqual(msg.actor, Hostmask('nick', 'user', 'host'))
        return msg

    def test_quit(self):
        msg = self._from_raw('QUIT :lorem ipsum')
        self.assertEqual(msg.action, MessageType.quit)
        self.assertIsNone(msg.venue)
        self.assertIsNone(msg.target)
        self.assertIsNone(msg.subaction)
        self.assertEqual(msg.content, 'lorem ipsum')
        self.assertFalse(msg.private)

    def test_nick(self):
        msg = self._from_raw('NICK :other')
        self.assertEqual(msg.action, MessageType.nick)
        self.assertIsNone(msg.venue)
        self.assertIsNone(msg.target)
        self.assertIsNone(msg.subaction)
        self.assertEqual(msg.content, 'other')
        self.assertFalse(msg.private)

    def test_channel_message(self):
        msg = self._from_raw('PRIVMSG #foo :lorem ipsum')
        self.assertEqual(msg.action, MessageType.privmsg)
        self.assertEqual(msg.venue, '#foo')
        self.assertIsNone(msg.target)
        self.assertIsNone(msg.subaction)
        self.assertEqual(msg.content, 'lorem ipsum')
        self.assertFalse(msg.private)

    def test_private_message(self):
        msg = self._from_raw('PRIVMSG foo :lorem ipsum')
        self.assertEqual(msg.action, MessageType.privmsg)
        self.assertEqual(msg.venue, 'foo')
        self.assertIsNone(msg.target)
        self.assertIsNone(msg.subaction)
        self.assertEqual(msg.content, 'lorem ipsum')
        self.assertTrue(msg.private)

    def test_ctcp_query(self):
        msg = self._from_raw('PRIVMSG #foo :\x01tag param\x01')
        self.assertEqual(msg.action, MessageType.ctcpquery)
        self.assertEqual(msg.venue, '#foo')
        self.assertIsNone(msg.target)
        self.assertEqual(msg.subaction, 'tag')
        self.assertEqual(msg.content, 'param')
        self.assertFalse(msg.private)

    def test_ctcp_reply(self):
        msg = self._from_raw('NOTICE #foo :\x01tag param\x01')
        self.assertEqual(msg.action, MessageType.ctcpreply)
        self.assertEqual(msg.venue, '#foo')
        self.assertIsNone(msg.target)
        self.assertEqual(msg.subaction, 'tag')
        self.assertEqual(msg.content, 'param')
        self.assertFalse(msg.private)

    def test_channel_notice(self):
        msg = self._from_raw('NOTICE #foo :lorem ipsum')
        self.assertEqual(msg.action, MessageType.notice)
        self.assertEqual(msg.venue, '#foo')
        self.assertIsNone(msg.target)
        self.assertIsNone(msg.subaction)
        self.assertEqual(msg.content, 'lorem ipsum')
        self.assertFalse(msg.private)

    def test_private_notice(self):
        msg = self._from_raw('NOTICE foo :lorem ipsum')
        self.assertEqual(msg.action, MessageType.notice)
        self.assertEqual(msg.venue, 'foo')
        self.assertIsNone(msg.target)
        self.assertIsNone(msg.subaction)
        self.assertEqual(msg.content, 'lorem ipsum')
        self.assertTrue(msg.private)

    def test_action_query(self):
        msg = self._from_raw('PRIVMSG #foo :\x01ACTION lorem ipsum\x01')
        self.assertEqual(msg.action, MessageType.action)
        self.assertEqual(msg.venue, '#foo')
        self.assertIsNone(msg.target)
        self.assertIsNone(msg.subaction)
        self.assertEqual(msg.content, 'lorem ipsum')
        self.assertFalse(msg.private)

    def test_action_reply(self):
        msg = self._from_raw('NOTICE #foo :\x01ACTION lorem ipsum\x01')
        self.assertEqual(msg.action, MessageType.action)
        self.assertEqual(msg.venue, '#foo')
        self.assertIsNone(msg.target)
        self.assertIsNone(msg.subaction)
        self.assertEqual(msg.content, 'lorem ipsum')
        self.assertFalse(msg.private)

    def test_topic(self):
        msg = self._from_raw('TOPIC #foo :lorem ipsum')
        self.assertEqual(msg.action, MessageType.topic)
        self.assertEqual(msg.venue, '#foo')
        self.assertIsNone(msg.target)
        self.assertIsNone(msg.subaction)
        self.assertEqual(msg.content, 'lorem ipsum')
        self.assertFalse(msg.private)

    def test_join(self):
        msg = self._from_raw('JOIN #foo')
        self.assertEqual(msg.action, MessageType.join)
        self.assertEqual(msg.venue, '#foo')
        self.assertIsNone(msg.target)
        self.assertIsNone(msg.subaction)
        self.assertIsNone(msg.content)
        self.assertFalse(msg.private)

    def test_part(self):
        msg = self._from_raw('PART #foo :lorem ipsum')
        self.assertEqual(msg.action, MessageType.part)
        self.assertEqual(msg.venue, '#foo')
        self.assertIsNone(msg.target)
        self.assertIsNone(msg.subaction)
        self.assertEqual(msg.content, 'lorem ipsum')
        self.assertFalse(msg.private)

    def test_part_without_message(self):
        msg = self._from_raw('PART #foo')
        self.assertEqual(msg.action, MessageType.part)
        self.assertEqual(msg.venue, '#foo')
        self.assertIsNone(msg.target)
        self.assertIsNone(msg.subaction)
        self.assertEqual(msg.content, '')
        self.assertFalse(msg.private)

    def test_mode(self):
        msg = self._from_raw('MODE #foo +mo other')
        self.assertEqual(msg.action, MessageType.mode)
        self.assertEqual(msg.venue, '#foo')
        self.assertIsNone(msg.target)
        self.assertIsNone(msg.subaction)
        self.assertEqual(msg.content, '+mo other')
        self.assertFalse(msg.private)

    def test_kick(self):
        msg = self._from_raw('KICK #foo other :lorem ipsum')
        self.assertEqual(msg.action, MessageType.kick)
        self.assertEqual(msg.venue, '#foo')
        self.assertEqual(msg.target, 'other')
        self.assertIsNone(msg.subaction)
        self.assertEqual(msg.content, 'lorem ipsum')
        self.assertFalse(msg.private)

    def test_unknown(self):
        msg = self._from_raw('NONSENSE a b c :foo bar')
        self.assertEqual(msg.action, MessageType.unknown)
        self.assertIsNone(msg.venue)
        self.assertIsNone(msg.target)
        self.assertEqual(msg.subaction, 'NONSENSE')
        self.assertEqual(msg.content, 'a b c :foo bar')
        self.assertFalse(msg.private)

    def test_empty(self):
        msg = self._from_raw('')
        self.assertEqual(msg.action, MessageType.unknown)
        self.assertIsNone(msg.venue)
        self.assertIsNone(msg.target)
        self.assertIsNone(msg.subaction)
        self.assertIsNone(msg.content)
        self.assertFalse(msg.private)

    def test_malformed(self):
        msg = self._from_raw('PRIVMSG')
        self.assertEqual(msg.action, MessageType.unknown)
        self.assertIsNone(msg.venue)
        self.assertIsNone(msg.target)
        self.assertEqual(msg.subaction, 'PRIVMSG')
        self.assertEqual(msg.content, '')
        self.assertFalse(msg.private)

    def test_malformed_with_params(self):
        msg = self._from_raw('KICK not :enough arguments')
        self.assertEqual(msg.action, MessageType.unknown)
        self.assertIsNone(msg.venue)
        self.assertIsNone(msg.target)
        self.assertEqual(msg.subaction, 'KICK')
        self.assertEqual(msg.content, 'not :enough arguments')
        self.assertFalse(msg.private)

    def test_override(self):
        msg = self._from_raw('PRIVMSG #foo :lorem ipsum', venue='foo')
        self.assertEqual(msg.action, MessageType.privmsg)
        self.assertEqual(msg.venue, 'foo')
        self.assertIsNone(msg.target)
        self.assertIsNone(msg.subaction)
        self.assertEqual(msg.content, 'lorem ipsum')
        self.assertTrue(msg.private)


class ExtractionTestCase(TestCase):
    def setUp(self):
        self.connection = DummyConnection()
        self.prototype = Message(
            self.connection, False, 'privmsg', 'nick!user@host')

    def _extract(self, content):
        return self.prototype._replace(content=content).extract_command(
            prefixes=['!', 'bot:', 'bot,'])

    def test_ignore_non_privmsg(self):
        self.assertIsNone(Message(
            self.connection, 'nick!user@host', 'topic').extract_command())

    def test_ignore_missing_prefix(self):
        self.assertIsNone(self._extract('ipsum'))

    def test_ignore_missing_content(self):
        self.assertIsNone(self._extract('!'))

    def test_simple_command(self):
        msg = self._extract('!help')
        self.assertEqual(msg.action, MessageType.command)
        self.assertEqual(msg.target, 'nick')
        self.assertEqual(msg.subaction, 'help')
        self.assertEqual(msg.content, '')

    def test_simple_command_with_long_prefix(self):
        msg = self._extract('bot: help')
        self.assertEqual(msg.action, MessageType.command)
        self.assertEqual(msg.target, 'nick')
        self.assertEqual(msg.subaction, 'help')
        self.assertEqual(msg.content, '')

    def test_command_with_arguments(self):
        msg = self._extract('bot, help me')
        self.assertEqual(msg.action, MessageType.command)
        self.assertEqual(msg.target, 'nick')
        self.assertEqual(msg.subaction, 'help')
        self.assertEqual(msg.content, 'me')

    def test_command_redirection(self):
        msg = self._extract('!help > other')
        self.assertEqual(msg.action, MessageType.command)
        self.assertEqual(msg.target, 'other')
        self.assertEqual(msg.subaction, 'help')
        self.assertEqual(msg.content, '')

    def test_empty_command_redirection(self):
        msg = self._extract('!help >')
        self.assertEqual(msg.action, MessageType.command)
        self.assertEqual(msg.target, 'nick')
        self.assertEqual(msg.subaction, 'help')
        self.assertEqual(msg.content, '')


class ReplyBufferTestCase(TestCase):
    def test_type(self):
        self.assertRaises(TypeError, ReplyBuffer, 42)

    def test_empty_str(self):
        buf = ReplyBuffer('')
        self.assertRaises(StopIteration, next, buf)

    def test_str(self):
        buf = ReplyBuffer(collapse("""Esed volobore fermentum eleifend
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
            facidunt."""))
        self.assertEqual(length_hint(buf), 4)
        self.assertEqual(next(buf), collapse("""Esed volobore fermentum
            eleifend curae non inciduipit consequam deliquatue, tisi
            vulluptatet tristique. Odolorperos litora leo adignim
            feugiatue; dipiscipitismodi hendip iniam estrudismod
            nonsequam. Odolupt faciduisit litora, utetumm vullandigna
            henis"""))
        self.assertEqual(length_hint(buf), 3)
        self.assertEqual(next(buf), collapse("""tismolortis faciduisi
            odipsumsan, adit adio curae. Msandre psusto nonummy
            susciduipit adionsequat dolent faccummy alisis molore; veros
            sustrud alis hendipisim suscilla vitae. Taciti nonum aliscil
            facilisse cor; mollis summy modipsustie blaorismod"""))
        self.assertEqual(length_hint(buf), 2)
        self.assertEqual(next(buf), collapse("""dolortis. Enibh
            facincilitismod inim, pratisl alisi, urna eum, elesequ tet
            inceptosismoloreet sequis suscipit. Sumsandre ea amcommo
            ipsustrud auguero esse consequ. Illam quat ullutpat ametumm
            eugait, magniamet erostin iuscipit henit eriure irilla"""))
        self.assertEqual(length_hint(buf), 1)
        self.assertEqual(next(buf), collapse("""velestionse montes
            lobortis. Lor feugiatue nullum. Uamconum andrero facinci
            vulluptatum. Nisim netus fames esting vendipissit commolum
            facidunt."""))
        self.assertEqual(length_hint(buf), 0)
        self.assertRaises(StopIteration, next, buf)

    def test_unicode(self):
        buf = ReplyBuffer(collapse(u"""
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
            """))
        self.assertEqual(length_hint(buf), 2)
        self.assertEqual(next(buf), collapse(u"""
            《施氏食狮史》
            石室诗士施氏，嗜狮，誓食十狮。
            氏时时适市视狮。
            十时，适十狮适市。
            是时，适施氏适市。
            氏视是十狮，恃矢势，使是十狮逝世。
            氏拾是十狮尸，适石室。
            """).encode('utf-8'))
        self.assertEqual(length_hint(buf), 1)
        self.assertEqual(next(buf), collapse(u"""
            石室湿，氏使侍拭石室。
            石室拭，氏始试食是十狮。
            食时，始识是十狮尸，实十石狮尸。
            试释是事。
            """).encode('utf-8'))
        self.assertEqual(length_hint(buf), 0)
        self.assertRaises(StopIteration, next, buf)

    def test_formatting(self):
        buf = ReplyBuffer(collapse("""\x0314Esed volobore fermentum
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
            vendipissit commolum facidunt."""))
        self.assertEqual(next(buf), collapse("""\x0314Esed volobore
            fermentum eleifend curae non inciduipit consequam
            deliquatue, tisi vulluptatet tristique. Odolorperos litora
            leo adignim feugiatue; dipiscipitismodi hendip iniam
            estrudismod nonsequam. Odolupt faciduisit litora, utetumm
            vullandigna henis"""))
        self.assertEqual(next(buf), collapse("""\x0314tismolortis
            faciduisi odipsumsan, adit adio curae. Msandre psusto
            nonummy susciduipit adionsequat dolent faccummy alisis
            molore; veros sustrud alis hendipisim suscilla vitae. Taciti
            nonum aliscil facilisse cor; mollis summy modipsustie
            blaorismod"""))
        self.assertEqual(next(buf), collapse("""\x0314dolortis. Enibh
            facincilitismod inim, pratisl alisi, urna eum, elesequ tet
            inceptosismoloreet sequis suscipit. Sumsandre ea amcommo
            ipsustrud auguero esse consequ. Illam quat ullutpat ametumm
            eugait, magniamet erostin iuscipit henit eriure irilla"""))
        self.assertEqual(next(buf), collapse("""\x0314velestionse montes
            lobortis. Lor feugiatue nullum. Uamconum andrero facinci
            vulluptatum. Nisim netus fames esting vendipissit commolum
            facidunt."""))

    def test_sequence(self):
        buf = ReplyBuffer(['foo', 'bar', 'baz'])
        self.assertEqual(length_hint(buf), 3)
        self.assertEqual(next(buf), 'foo')
        self.assertEqual(length_hint(buf), 2)
        self.assertEqual(next(buf), 'bar')
        self.assertEqual(length_hint(buf), 1)
        self.assertEqual(next(buf), 'baz')
        self.assertEqual(length_hint(buf), 0)
        self.assertRaises(StopIteration, next, buf)
