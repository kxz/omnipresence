from zope.interface import implements
from twisted.plugin import IPlugin
from omnipresence.iomnipresence import ICommand
from omnipresence import util

import json
import urllib

class WeatherCommand(object):
    """
    \x02%s\x02 \x1Flocation\x1F - Look up the current weather conditions in a 
    given location, courtesy of GeoNames <http://geonames.org/>.
    """
    implements(IPlugin, ICommand)
    name = 'weather'
    
    def reply_with_weather(self, response, bot, prefix, reply_target, channel, args):
        data = json.loads(response[1])
        
        if 'weatherObservation' not in data:
            bot.reply(prefix, channel, 'Weather service: There is no weather '
                                       'information for \x02%s\x02.' % args[1])
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
        
        bot.reply(reply_target, channel,
                  ('Weather service: %s [%s] (%.2f, %.2f) %s as of %s UTC'
                    % (observation['stationName'], observation['ICAO'],
                       observation['lat'], observation['lng'], weather,
                       observation['datetime'])).encode(self.factory.encoding))
    
    def find_location(self, response, bot, prefix, reply_target, channel, args):
        data = json.loads(response[1])
        
        if 'geonames' not in data or len(data['geonames']) < 1:
            bot.reply(prefix, channel,
                      "Weather service: Couldn't find the location \x02%s\x02."
                       % args[1])
            return
        
        lat = data['geonames'][0]['lat']
        lng = data['geonames'][0]['lng']
        
        d = self.factory.get_http('http://ws.geonames.org/findNearByWeatherJSON?lat=%f&lng=%f' % (lat, lng))
        d.addCallback(self.reply_with_weather, bot, prefix, reply_target, channel, args)
        d.addErrback(bot.reply_with_error, prefix, channel, args[0])
    
    def execute(self, bot, prefix, reply_target, channel, args):
        args = args.split(None, 1)
        
        if len(args) < 2:
            bot.reply(prefix, channel, 'Please specify a location.')
            return
        
        d = self.factory.get_http('http://ws.geonames.org/searchJSON?maxRows=1&style=FULL&q=%s' % urllib.quote(args[1]))
        d.addCallback(self.find_location, bot, prefix, reply_target, channel, args)
        return d

weathercommand = WeatherCommand()