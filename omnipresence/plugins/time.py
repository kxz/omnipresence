from zope.interface import implements
from twisted.plugin import IPlugin
from omnipresence.iomnipresence import ICommand

import datetime
import json
import pytz
import urllib

class TimeCommand(object):
    """
    \x02%s\x02 \x1Flocation\x1F - Look up the current date and time in a given 
    location, courtesy of GeoNames <http://geonames.org/>.  Case-sensitive tz 
    database names are also supported.
    """
    implements(IPlugin, ICommand)
    name = 'time'
    
    def reply_with_time(self, response, bot, user, channel, args, canonical, lat, lng):
        data = json.loads(response[1])
        
        if 'time' not in data:
            bot.reply(user, channel,
                      'Time service: There is no time information for \x02%s\x02.'
                       % args[1])
            return
        
        bot.reply(user, channel,
                  ('Time service: %s (%.2f, %.2f) %s'
                   % (canonical, lat, lng, data['time'])) \
                  .encode(self.factory.encoding))
    
    def find_location(self, response, bot, user, channel, args):
        data = json.loads(response[1])
        
        if 'geonames' not in data or len(data['geonames']) < 1:
            bot.reply(user, channel,
                      "Time service: Couldn't find the location \x02%s\x02."
                       % args[1])
            return
        
        details = data['geonames'][0]
        
        canonical = details['name']
        if ('adminName1' in details) and (details['adminName1']):
            canonical = u'%s, %s' % (canonical, details['adminName1'])
        if ('countryName' in details) and (details['countryName']):
            canonical = u'%s, %s' % (canonical, details['countryName'])
        
        lat = details['lat']
        lng = details['lng']
        
        d = self.factory.get_http('http://ws.geonames.org/timezoneJSON?lat=%f&lng=%f' % (lat, lng))
        d.addCallback(self.reply_with_time, bot, user, channel, args, canonical, lat, lng)
        d.addErrback(bot.reply_with_error, user, channel, args[0])
    
    def execute(self, bot, user, channel, args):
        args = args.split(None, 1)
        
        if len(args) < 2:
            bot.reply(user, channel, 'Please specify a location.')
            return
        
        if args[1] in pytz.all_timezones:
            time = datetime.datetime.utcnow() \
                    .replace(tzinfo=pytz.utc) \
                    .astimezone(pytz.timezone(args[1])) \
                    .strftime('%Y-%m-%d %H:%M')
            bot.reply(user, channel, 'Time service: %s (tz database) %s'
                                      % (args[1], time))
            return
        
        d = self.factory.get_http('http://ws.geonames.org/searchJSON?maxRows=1&style=FULL&q=%s' % urllib.quote(args[1]))
        d.addCallback(self.find_location, bot, user, channel, args)
        return d

timecommand = TimeCommand()