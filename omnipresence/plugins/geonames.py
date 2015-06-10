import datetime
import json
import urllib

import pytz
from twisted.internet import defer
from twisted.plugin import IPlugin
from zope.interface import implements

from omnipresence import web
from omnipresence.iomnipresence import ICommand
from omnipresence.util import ago


API_SERVER = 'http://api.geonames.org'
SEARCH_URL = API_SERVER + '/searchJSON?%s'
TIME_URL = API_SERVER + '/timezoneJSON?%s'
WEATHER_URL = API_SERVER + '/findNearByWeatherJSON?%s'


@defer.inlineCallbacks
def find_location(query, username):
    """Find a location in the GeoNames database.  Return a Deferred that
    yields a tuple containing a canonical name, latitude, and longitude,
    or ``None`` if no matches could be found."""
    params = urllib.urlencode({'maxRows': 1, 'style': 'FULL',
                               'q': query, 'username': username})
    headers, content = yield web.request('GET', SEARCH_URL % params)
    data = json.loads(content)
    if not data.get('geonames'):
        defer.returnValue(None)
    details = data['geonames'][0]
    canonical = filter(None, [details.get('name'),
                              details.get('adminName1'),
                              details.get('countryName')])
    defer.returnValue((u', '.join(canonical), details['lat'], details['lng']))

def format_location(location, lat, lng):
    # The GeoNames API occasionally returns strings instead of numeric
    # values in its JSON output.  Fortunately, coercion is easy.
    try:
        lat, lng = float(lat), float(lng)
    except ValueError:
        return u'{0} ({1}, {2})'.format(location, lat, lng)
    return u'{0} ({1:.2f}, {2:.2f})'.format(location, lat, lng)


class TimeLookup(object):
    """
    \x02%s\x02 \x1Flocation\x1F - Look up the current date and time in
    a given location, courtesy of GeoNames <http://geonames.org/>.
    Case-sensitive tz database names are also supported.
    """
    implements(IPlugin, ICommand)
    name = 'time'

    def registered(self):
        self.username = self.factory.config.get('geonames', 'username')

    def execute(self, bot, prefix, reply_target, channel, args):
        args = args.split(None, 1)

        if len(args) < 2:
            bot.reply(prefix, channel, 'Please specify a location.')
            return

        if args[1] in pytz.all_timezones:
            time = datetime.datetime.utcnow() \
                    .replace(tzinfo=pytz.utc) \
                    .astimezone(pytz.timezone(args[1])) \
                    .strftime('%Y-%m-%d %H:%M')
            bot.reply(reply_target, channel, 'Time service: %s (tz database) '
                                             '%s' % (args[1], time))
            return

        d = find_location(args[1], self.username)
        d.addCallback(self.reply, bot, prefix, reply_target, channel, args)
        return d

    @defer.inlineCallbacks
    def reply(self, location, bot, prefix, reply_target, channel, args):
        if not location:
            bot.reply(prefix, channel, "Time service: Couldn't find the "
                                       'location \x02{0}\x02.'.format(args[1]))
            return
        canonical, lat, lng = location
        params = urllib.urlencode({'lat': lat, 'lng': lng,
                                   'username': self.username})
        headers, content = yield web.request('GET', TIME_URL % params)
        data = json.loads(content)
        if 'time' not in data:
            bot.reply(prefix, channel,
                      (u'Time service: There is no time information for '
                       u'{0}.'.format(format_location(*location))))
            return
        bot.reply(reply_target, channel, u'Time service: {0} {1}'.format(
                    format_location(*location), data['time']))


class WeatherLookup(object):
    """
    \x02%s\x02 \x1Flocation\x1F - Look up the current weather conditions
    in a given location, courtesy of GeoNames <http://geonames.org/>.
    """
    implements(IPlugin, ICommand)
    name = 'weather'

    def registered(self):
        self.username = self.factory.config.get('geonames', 'username')

    def execute(self, bot, prefix, reply_target, channel, args):
        args = args.split(None, 1)

        if len(args) < 2:
            bot.reply(prefix, channel, 'Please specify a location.')
            return

        d = find_location(args[1], self.username)
        d.addCallback(self.reply, bot, prefix, reply_target, channel, args)
        return d

    @defer.inlineCallbacks
    def reply(self, location, bot, prefix, reply_target, channel, args):
        if not location:
            bot.reply(prefix, channel, "Weather service: Couldn't find the "
                                       'location \x02{0}\x02.'.format(args[1]))
            return
        canonical, lat, lng = location
        params = urllib.urlencode({'lat': lat, 'lng': lng,
                                   'username': self.username})
        headers, content = yield web.request('GET', WEATHER_URL % params)
        data = json.loads(content)
        if 'weatherObservation' not in data:
            bot.reply(prefix, channel,
                      (u'Weather service: There is no weather information for '
                       u'{0}.'.format(format_location(*location))))
            return
        observation = data['weatherObservation']
        temp = float(observation['temperature'])
        weather = u'%d\u00B0C/%d\u00B0F' % (round(temp), round(temp * 1.8 + 32))
        if observation.get('weatherCondition', 'n/a') != 'n/a':
            weather += u', ' + observation['weatherCondition'].strip()
        if observation.get('clouds', 'n/a') != 'n/a':
            weather += u', ' + observation['clouds'].strip()
        if ('windDirection' in observation and
            int(observation.get('windSpeed', 0)) > 0):
            weather += (u', winds from {0}\u00B0 at {1} kt' \
                          .format(observation['windDirection'],
                                  int(observation['windSpeed'])))
        weather += u', {0}% humidity'.format(observation['humidity'])

        try:
            dt = ago(datetime.datetime.strptime(observation['datetime'],
                                                '%Y-%m-%d %H:%M:%S'),
                     datetime.datetime.utcnow())
        except ValueError:
            dt = observation['datetime'] + u' UTC'

        bot.reply(reply_target, channel,
                  u'Weather service: {0} {1} from {2} [{3}] as of {4}' \
                    .format(format_location(*location), weather,
                            observation['stationName'], observation['ICAO'],
                            dt))

time = TimeLookup()
weather = WeatherLookup()
