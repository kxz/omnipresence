"""twistd plugin for Omnipresence."""


from twisted.application.service import ServiceMaker


omnipresence = ServiceMaker(
    'Omnipresence', 'omnipresence.service',
    'An IRC utility bot.', 'omnipresence')
