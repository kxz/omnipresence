# -*- coding: utf-8
"""Unit tests for IRC message handling."""


import functools
import re

from twisted.trial import unittest

from ..hostmask import Hostmask
from ..message import (Message, chunk,
                       remove_formatting as rm,
                       unclosed_formatting as uc)


class FormattingTestCase(unittest.TestCase):
    def test_removal(self):
        self.assertEqual(rm('lorem ipsum'), 'lorem ipsum')
        self.assertEqual(rm('lorem \x03ipsum'), 'lorem ipsum')
        self.assertEqual(rm('dolor \x032,12sit'), 'dolor sit')
        self.assertEqual(rm('\x02a\x0Fm\x033et'), 'amet')

    def test_unclosed(self):
        self.assertEqual(uc('lorem ipsum'), frozenset())
        self.assertEqual(uc('lorem \x03ipsum'), frozenset())
        self.assertEqual(uc('dolor \x032,12sit'),
                         frozenset(['\x032,12']))
        self.assertEqual(uc('dolor \x031,12\x032sit'),
                         frozenset(['\x032,12']))
        self.assertEqual(uc('\x02a\x0F\x1Fm\x033et'),
                         frozenset(['\x1F', '\x033']))


class ExtractionTestCase(unittest.TestCase):
    prototype = Message(None, 'nick!user@host', 'privmsg')

    def sample(self, *args, **kwargs):
        return self.prototype._replace(*args, **kwargs)

    def test_extraction(self):
        e = functools.partial(Message.extract_command,
                              prefixes=['!', 'bot:', 'bot,'])
        self.assertEqual(
            e(self.sample(action='topic')),
            None)
        self.assertEqual(
            e(self.sample(content='ipsum')),
            None)
        self.assertEqual(
            e(self.sample(content='!help')),
            self.sample(action='command', target='nick',
                        subaction='help', content=''))
        self.assertEqual(
            e(self.sample(content='bot: help')),
            self.sample(action='command', target='nick',
                        subaction='help', content=''))
        self.assertEqual(
            e(self.sample(content='bot, help me')),
            self.sample(action='command', target='nick',
                        subaction='help', content='me'))
        self.assertEqual(
            e(self.sample(content='!help >')),
            self.sample(action='command', target='nick',
                        subaction='help', content=''))
        self.assertEqual(
            e(self.sample(content='!help > other')),
            self.sample(action='command', target='other',
                        subaction='help', content=''))


class BufferingTestCase(unittest.TestCase):
    def collapse(self, s):
        """Return *s* with runs of whitespace self.collapsed to a single
        space, and any preceding or trailing whitespace removed."""
        return re.sub(r'\s+', ' ', s).strip()

    def test_type(self):
        self.assertRaises(TypeError, chunk(42))

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
