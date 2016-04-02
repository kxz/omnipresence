# -*- coding: utf-8
"""Unit tests for reply chunking and buffering."""
# pylint: disable=missing-docstring,too-few-public-methods


from twisted.trial.unittest import TestCase

from ....compat import length_hint
from ....message import collapse
from ....message.buffering import ReplyBuffer


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
