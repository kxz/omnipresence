"""Unit tests for human-readable data presentations."""
# pylint: disable=missing-docstring,too-few-public-methods


from datetime import datetime

from twisted.trial import unittest

from .. import humanize


class AgoTestCase(unittest.TestCase):
    def setUp(self):
        self.then = datetime(2000, 1, 1)

    def _test(self, now, humanized):
        self.assertEqual(humanize.ago(self.then, now), humanized)

    def test_just_now(self):
        self._test(self.then, 'just now')

    def test_seconds(self):
        self._test(datetime(2000, 1, 1, 0, 0, 30), '30 seconds ago')

    def test_a_minute(self):
        self._test(datetime(2000, 1, 1, 0, 1, 30), 'a minute ago')

    def test_minutes(self):
        self._test(datetime(2000, 1, 1, 0, 30), '30 minutes ago')

    def test_an_hour(self):
        self._test(datetime(2000, 1, 1, 1, 30), 'an hour ago')

    def test_hours(self):
        self._test(datetime(2000, 1, 1, 12), '12 hours ago')

    def test_yesterday(self):
        self._test(datetime(2000, 1, 2, 12), 'yesterday')

    def test_days(self):
        self._test(datetime(2000, 1, 5), '4 days ago')

    def test_a_week(self):
        self._test(datetime(2000, 1, 10), 'a week ago')

    def test_weeks(self):
        self._test(datetime(2000, 1, 15), '2 weeks ago')


class AndifyTestCase(unittest.TestCase):
    def test_two(self):
        self.assertEqual(
            humanize.andify(['this', 'that']),
            'this and that')

    def test_two_comma(self):
        self.assertEqual(
            humanize.andify(['this', 'that'], two_comma=True),
            'this, and that')

    def test_three(self):
        self.assertEqual(
            humanize.andify(['this', 'that', 'the other']),
            'this, that, and the other')
        self.assertEqual(
            humanize.andify(['this', 'that', 'the other'], two_comma=True),
            'this, that, and the other')


class DurationToTimedeltaTestCase(unittest.TestCase):
    def _test(self, duration, total_seconds):
        self.assertEqual(
            humanize.duration_to_timedelta(duration).total_seconds(),
            total_seconds)

    def test_invalid(self):
        self._test('lorem ipsum', 0)

    def test_simple(self):
        self._test('3d', 259200)

    def test_full(self):
        self._test('1w1d1h1m1s', 694861)


class ReadableDurationTestCase(unittest.TestCase):
    def _test(self, duration, humanized):
        self.assertEqual(humanize.readable_duration(duration), humanized)

    def test_invalid(self):
        self._test('lorem ipsum', 'instant')

    def test_simple_singular(self):
        self._test('1h', 'hour')

    def test_simple_plural(self):
        self._test('3d', '3 days')

    def test_initial_singular(self):
        self._test('1h45m', 'hour and 45 minutes')

    def test_succeeding_singular(self):
        self._test('1d1h1m1s',
                   'day, 1 hour, 1 minute, and 1 second')
