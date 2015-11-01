# -*- coding: utf-8
# -*- test-case-name: omnipresence.plugins.geonames.test_geonames
"""Event plugins for GeoNames services."""


from collections import namedtuple
from datetime import datetime
try:
    import pytz
except ImportError:
    pytz = None
import urllib

from twisted.internet.defer import inlineCallbacks, returnValue

from ...humanize import ago
from ...message import collapse
from ...plugin import EventPlugin, UserVisibleError
from ...web.http import default_agent, read_json_body


class Location(namedtuple('Location', ['name', 'lat', 'lng'])):
    """A container for a location's name, latitude, and longitude."""

    def __str__(self):
        # The GeoNames API occasionally returns strings instead of
        # numeric values in its JSON output.
        try:
            lat, lng = float(self.lat), float(self.lng)
        except ValueError:
            return u'{} ({}, {})'.format(self.name, self.lat, self.lng)
        return u'{} ({:.2f}, {:.2f})'.format(self.name, lat, lng)


class GeoNamesMixin(object):
    """A mixin for plugins that query the GeoNames API."""

    endpoint_uri = 'http://api.geonames.org/'

    def __init__(self):
        self.agent = default_agent
        #: Time provider that can be stubbed out for unit tests, given
        #: that time is being computed locally as with tzdata requests.
        self.utcnow = datetime.utcnow

    def request(self, action, params, username):
        """Make a request to the GeoNames API."""
        return self.agent.request('GET', '{}{}?{}&username={}'.format(
            self.endpoint_uri, action, urllib.urlencode(params), username))

    @inlineCallbacks
    def geocode(self, query, username):
        """Return a `Deferred` yielding a `Location` object for the
        string *query*, or raise `UserVisibleError` if no matches could
        be found."""
        params = [('maxRows', 1), ('style', 'FULL'), ('q', query)]
        response = yield self.request('searchJSON', params, username)
        data = yield read_json_body(response)
        if not data.get('geonames'):
            raise UserVisibleError(u"Couldn't find the location {}."
                                   .format(query))
        details = data['geonames'][0]
        canonical = filter(None, [details.get('name'),
                                  details.get('adminName1'),
                                  details.get('countryName')])
        returnValue(Location(
            u', '.join(canonical), details['lat'], details['lng']))


class Time(GeoNamesMixin, EventPlugin):
    def __init__(self):
        super(Time, self).__init__()

    @inlineCallbacks
    def on_command(self, msg):
        if not msg.content:
            raise UserVisibleError('Please specify a location.')
        if pytz and msg.content in pytz.all_timezones:
            time = (self.utcnow().replace(tzinfo=pytz.utc)
                        .astimezone(pytz.timezone(msg.content))
                        .strftime('%Y-%m-%d %H:%M'))
            returnValue(u'{} (tz database): {}'.format(msg.content, time))
        username = msg.settings.get('geonames.username')
        location = yield self.geocode(msg.content, username)
        params = zip(['lat', 'lng'], location[1:])
        response = yield self.request('timezoneJSON', params, username)
        data = yield read_json_body(response)
        if 'time' not in data:
            raise UserVisibleError(u'There is no time information for {}.'
                                   .format(location))
        returnValue(u'{}: {}'.format(location, data['time']))

    def on_cmdhelp(self, msg):
        return collapse("""\
            \x1Flocation\x1F - Look up the current date and time in a
            given location using GeoNames <http://geonames.org/>.
            Case-sensitive tz database names are also supported.
            """)


class Weather(GeoNamesMixin, EventPlugin):
    @inlineCallbacks
    def on_command(self, msg):
        if not msg.content:
            raise UserVisibleError('Please specify a location.')
        username = msg.settings.get('geonames.username')
        location = yield self.geocode(msg.content, username)
        params = zip(['lat', 'lng'], location[1:])
        response = yield self.request('findNearByWeatherJSON',
                                      params, username)
        data = yield read_json_body(response)
        if 'weatherObservation' not in data:
            raise UserVisibleError(u'There is no weather information for {}.'
                                   .format(location))
        observation = data['weatherObservation']
        temp = float(observation['temperature'])
        weather = u'{:.1f}°C/{:.1f}°F'.format(temp, temp * 1.8 + 32)
        if observation.get('weatherCondition', 'n/a') != 'n/a':
            weather += u', ' + observation['weatherCondition'].strip()
        if observation.get('clouds', 'n/a') != 'n/a':
            weather += u', ' + observation['clouds'].strip()
        wind_speed = int(observation.get('windSpeed', 0))
        if 'windDirection' in observation and wind_speed:
            weather += (u', winds from {}° at {} kt'.format(
                observation['windDirection'], wind_speed))
        weather += u', {0}% humidity'.format(observation['humidity'])
        try:
            dt = ago(datetime.strptime(observation['datetime'],
                                       '%Y-%m-%d %H:%M:%S'),
                     self.utcnow())
        except ValueError:
            dt = observation['datetime'] + u' UTC'
        returnValue(u'{}: {} from {} ({}) as of {}'.format(
            location, weather,
            observation['stationName'], observation['ICAO'], dt))

    def on_cmdhelp(self, msg):
        return collapse("""\
            \x1Flocation\x1F - Look up the current weather conditions in
            a given location using GeoNames <http://geonames.org/>.
            """)
