# -*- coding: utf-8
"""Unit tests for the geonames event plugin."""
# pylint: disable=missing-docstring,too-few-public-methods


from datetime import datetime

from twisted.internet.defer import inlineCallbacks
from twisted.trial.unittest import TestCase

from ...message import collapse
from ...test.helpers import CommandTestMixin

from . import Time, Weather


class GeoNamesTestMixin(CommandTestMixin):
    def setUp(self):
        super(GeoNamesTestMixin, self).setUp()
        self.connection.settings.set('geonames.username', 'USERNAME')
        self.command.utcnow = lambda: datetime(2015, 11, 1, 22, 04)


class TimeTestCase(GeoNamesTestMixin, TestCase):
    command_class = Time

    @CommandTestMixin.use_cassette('geonames/time-simple')
    @inlineCallbacks
    def test_simple(self):
        yield self.send_command('beijing')
        yield self.assert_reply(
            'Beijing, Beijing, China (39.91, 116.40): 2015-11-02 06:04')

    @inlineCallbacks
    def test_tzdata(self):
        yield self.send_command('UTC')
        yield self.assert_reply('UTC (tz database): 2015-11-01 22:04')


class WeatherTestCase(GeoNamesTestMixin, TestCase):
    command_class = Weather

    @CommandTestMixin.use_cassette('geonames/weather-simple')
    @inlineCallbacks
    def test_simple(self):
        yield self.send_command('beijing')
        yield self.assert_reply(collapse(u"""\
            Beijing, Beijing, China (39.91, 116.40): 2.0°C/35.6°F,
            clouds and visibility OK, 74% humidity from Beijing (ZBAA)
            as of 4 minutes ago"""))
