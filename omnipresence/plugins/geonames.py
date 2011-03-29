import datetime
import json
import urllib

import pytz
from twisted.internet import defer, threads
from twisted.plugin import IPlugin
from zope.interface import implements

from omnipresence import util
from omnipresence.iomnipresence import ICommand


class GeoNamesCommand(object):
    def find_location(self, query):
        """
        Find a location in GeoNames' database.  Return a tuple
        containing a canonical name, latitude, and longitude, or None if
        no matches could be found.
        """        
        params = urllib.urlencode({'maxRows': 1, 'style': 'FULL', 'q': query})
        response = self.factory.get_http('http://ws.geonames.org/searchJSON?%s'
                                          % params, defer=False)
        data = json.loads(response[1])
        
        if 'geonames' not in data or not data['geonames']:
            return None
        
        details = data['geonames'][0]
        
        canonical = details['name']
        if ('adminName1' in details) and (details['adminName1']):
            canonical = u'%s, %s' % (canonical, details['adminName1'])
        if ('countryName' in details) and (details['countryName']):
            canonical = u'%s, %s' % (canonical, details['countryName'])
        lat = details['lat']
        lng = details['lng']
        
        return (canonical, lat, lng)


class TimeLookup(GeoNamesCommand):
    """
    \x02%s\x02 \x1Flocation\x1F - Look up the current date and time in
    a given location, courtesy of GeoNames <http://geonames.org/>.
    Case-sensitive tz database names are also supported.
    """
    implements(IPlugin, ICommand)
    name = 'time'
    
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
        
        d = threads.deferToThread(self.get_location_time, args[1])
        d.addCallback(self.reply, bot, prefix, reply_target, channel, args)
        return d
    
    def get_location_time(self, query):
        details = self.find_location(query)
        
        if not details:
            return None
        
        (canonical, lat, lng) = details
        
        params = urllib.urlencode({'lat': lat, 'lng': lng})
        response = self.factory.get_http('http://ws.geonames.org/timezoneJSON?%s'
                                          % params, defer=False)
        
        return (canonical, lat, lng, response)
    
    def reply(self, time, bot, prefix, reply_target, channel, args):
        if not time:
            bot.reply(prefix, channel,
                      "Time service: Couldn't find the location \x02%s\x02."
                       % args[1])
            return
        
        (canonical, lat, lng, response) = time
        data = json.loads(response[1])
        
        if 'time' not in data:
            bot.reply(prefix, channel,
                      (u'Time service: There is no time information for '
                       u'%s (%.2f, %.2f).' % (canonical, lat, lng))
                       .encode(self.factory.encoding))
            return
        
        bot.reply(reply_target, channel,
                  ('Time service: %s (%.2f, %.2f) %s'
                   % (canonical, lat, lng, data['time'])) \
                  .encode(self.factory.encoding))


class WeatherLookup(GeoNamesCommand):
    """
    \x02%s\x02 \x1Flocation\x1F - Look up the current weather conditions
    in a given location, courtesy of GeoNames <http://geonames.org/>.
    """
    implements(IPlugin, ICommand)
    name = 'weather'
    
    def execute(self, bot, prefix, reply_target, channel, args):
        args = args.split(None, 1)
        
        if len(args) < 2:
            bot.reply(prefix, channel, 'Please specify a location.')
            return
        
        d = threads.deferToThread(self.get_location_weather, args[1])
        d.addCallback(self.reply, bot, prefix, reply_target, channel, args)
        return d
    
    def get_location_weather(self, query):
        details = self.find_location(query)
        
        if not details:
            return None
        
        (canonical, lat, lng) = details
        
        params = urllib.urlencode({'lat': lat, 'lng': lng})
        response = self.factory.get_http('http://ws.geonames.org/findNearByWeatherJSON?%s'
                                          % params, defer=False)
        
        return (canonical, lat, lng, response)
    
    def reply(self, weather, bot, prefix, reply_target, channel, args):
        if not weather:
            bot.reply(prefix, channel,
                      "Weather service: Couldn't find the location \x02%s\x02."
                       % args[1])
            return
        
        (canonical, lat, lng, response) = weather
        data = json.loads(response[1])
        
        if 'weatherObservation' not in data:
            bot.reply(prefix, channel,
                      (u'Weather service: There is no weather information for '
                       u'%s (%.2f, %.2f).' % (canonical, lat, lng))
                       .encode(self.factory.encoding))
            return
        
        observation = data['weatherObservation']

        temp = float(observation['temperature'])
        weather = u'%d\xb0C/%d\xb0F' % (round(temp), round(temp * 1.8 + 32))
        if 'weatherCondition' in observation and observation['weatherCondition'] != 'n/a':
            weather += ', ' + observation['weatherCondition'].strip()
        if 'clouds' in observation and observation['clouds'] != 'n/a':
            weather += ', ' + observation['clouds'].strip()
        if 'windDirection' in observation and 'windSpeed' in observation and int(observation['windSpeed']) > 0:
            weather += (u', winds from %s\xb0 at %d kt'
                          % (observation['windDirection'],
                             int(observation['windSpeed'])))
        weather += ', %d%% humidity' % observation['humidity']
        
        try:
            dt = util.ago(datetime.datetime.strptime(observation['datetime'],
                                                     '%Y-%m-%d %H:%M:%S'),
                          datetime.datetime.utcnow())
        except ValueError:
            dt = observation['datetime'] + ' UTC'
        
        bot.reply(reply_target, channel,
                  ('Weather service: %s (%.2f, %.2f) %s from %s [%s] as of %s'
                    % (canonical, observation['lat'], observation['lng'],
                       weather, observation['stationName'], observation['ICAO'],
                       dt)).encode(self.factory.encoding))

time = TimeLookup()
weather = WeatherLookup()
