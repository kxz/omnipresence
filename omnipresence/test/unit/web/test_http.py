"""Tests for HTTP machinery."""
# pylint: disable=missing-docstring,too-few-public-methods


from __future__ import print_function
import json

from twisted.test.proto_helpers import StringTransport
from twisted.trial.unittest import TestCase
from twisted.web.client import Response
from twisted.web.http_headers import Headers

from ....web.http import read_json_body


class ReadJSONBodyTestCase(TestCase):
    def test_simple(self):
        data = [{'foo': 'bar', 'index': i} for i in xrange(10000)]
        json_str = json.dumps(data)
        response = Response(('HTTP', 1, 1), 200, 'OK', Headers(),
                            StringTransport())
        finished = read_json_body(response)
        finished.addCallback(self.assertEqual, data)
        chunk_length = 1000
        for start in xrange(0, len(json_str), chunk_length):
            response._bodyDataReceived(json_str[start:start + chunk_length])
        response._bodyDataFinished()
        return finished
