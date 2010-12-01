import time
import random
import unittest
from jsonutil import jsonutil as json
import random
from simplegeo.places import Client, Record, APIError, DecodeError

from decimal import Decimal as D

import os

import mock

MY_OAUTH_KEY = 'MY_OAUTH_KEY'
MY_OAUTH_SECRET = 'MY_SECRET_KEY'
TESTING_LAYER = 'TESTING_LAYER'

API_VERSION = '1.0'
API_HOST = 'api.simplegeo.com'
API_PORT = 80

ENDPOINT_DESCR=json.dumps({
        "GET /1.0/places/<place_id:[a-zA-Z0-9\\.,_-]+>.json": "Return a record for a place.",
        "GET /1.0/endpoints.json": "Describe known endpoints.",
        "POST /1.0/places/<place_id:.*>.json": "Update a record.",
        "GET /1.0/places/<lat:-?[0-9\\.]+>,<lon:-?[0-9\\.]+>/search.json": "Search for places near a lat/lon. Query string includes ?q=term and ?q=term&category=cat",
        "PUT /1.0/places/place.json": "Create a new record, returns a 301 to the location of the resource.",
        "GET /1.0/debug/<number:\\d+>": "Undocumented.",
        "DELETE /1.0/places/<place_id:.*>.json": "Delete a record."})



class ClientTest(unittest.TestCase):
    def setUp(self):
        self.client = Client(MY_OAUTH_KEY, MY_OAUTH_SECRET, API_VERSION, API_HOST, API_PORT)

    def test_wrong_endpoint(self):
        self.assertRaises(Exception, self.client.endpoint, 'recordt')

    def test_missing_argument(self):
        self.assertRaises(Exception, self.client.endpoint, 'places')

    def test_endpoint_descriptions(self):
        mockhttp = mock.Mock()
        mockhttp.request.return_value = ({'status': '200', 'content-type': 'application/json'}, ENDPOINT_DESCR)
        self.client.http = mockhttp
        d = self.client.get_endpoint_descriptions()
        self.failUnless(isinstance(d, dict), d)

    def test_add_record(self):
        mockhttp = mock.Mock()
        newloc = 'http://api.simplegeo.com:80/%s/places/abcdefghijklmnopqrstuvwyz.json' % (API_VERSION,)
        mockhttp.request.return_value = ({'status': '301', 'content-type': 'application/json', 'location': newloc}, json.dumps("Yo dawg, go to the new location: '%s'" % (newloc,)))
        self.client.http = mockhttp

        record = Record(
            layer=TESTING_LAYER,
            id=str(1),
            lat=D('37.8016'),
            lon=D('-122.4783')
        )

        self.client.add_record(record)
        self.assertEqual(mockhttp.method_calls[0][0], 'request')
        self.assertEqual(mockhttp.method_calls[0][1][0], 'http://api.simplegeo.com:80/%s/places/place.json' % (API_VERSION,))
        self.assertEqual(mockhttp.method_calls[0][1][1], 'PUT')
        self.assertEqual(mockhttp.method_calls[0][2]['body'], record.to_json())

    def test_get_record(self):
        simplegeoid = 'abcdefghijklmnopqrstuvwyz'
        resultrecord = Record('a_layer', simplegeoid, D('11.03'), D('10.03'))

        mockhttp = mock.Mock()
        mockhttp.request.return_value = ({'status': '200', 'content-type': 'application/json', }, resultrecord.to_json())
        self.client.http = mockhttp

        res = self.client.get_record(simplegeoid)
        self.assertEqual(mockhttp.method_calls[0][0], 'request')
        self.assertEqual(mockhttp.method_calls[0][1][0], 'http://api.simplegeo.com:80/%s/places/%s.json' % (API_VERSION, simplegeoid))
        self.assertEqual(mockhttp.method_calls[0][1][1], 'GET')
        self.failUnless(isinstance(res, Record), res)
        self.assertEqual(res.to_json(), resultrecord.to_json())

    def test_type_check_request(self):
        self.failUnlessRaises(TypeError, self.client._request, 'whatever', 'POST', {'bogus': "non string"})

    def test_empty_body(self):
        mockhttp = mock.Mock()
        mockhttp.request.return_value = ({'status': '200', 'content-type': 'application/json', }, None)
        self.client.http = mockhttp

        self.client._request("http://anyrandomendpoint", 'POST')

        self.failUnless(mockhttp.method_calls[0][2]['body'] is None, (repr(mockhttp.method_calls[0][2]['body']), type(mockhttp.method_calls[0][2]['body'])))

    def test_dont_json_decode_results(self):
        """ _request() is required to return the exact string that the HTTP
        server sent to it -- no transforming it, such as by json-decoding. """

        EXAMPLE_RECORD_JSONSTR=json.dumps({ 'geometry' : { 'type' : 'Point', 'coordinates' : [D('10.0'), D('11.0')] }, 'id' : 'my_id', 'type' : 'Feature', 'properties' : { 'key' : 'value'  , 'type' : 'object' } })

        mockhttp = mock.Mock()
        mockhttp.request.return_value = ({'status': '200', 'content-type': 'application/json', }, '{ "Hello": "I am a string. \xe2\x9d\xa4" }'.decode('utf-8'))
        self.client.http = mockhttp
        res = self.client._request("http://thing", 'POST')
        self.failUnlessEqual(res, '{ "Hello": "I am a string. \xe2\x9d\xa4" }'.decode('utf-8'))

    def test_dont_Recordify_results(self):
        """ _request() is required to return the exact string that the HTTP
        server sent to it -- no transforming it, such as by json-decoding and
        then constructing a Record. """

        EXAMPLE_RECORD_JSONSTR=json.dumps({ 'geometry' : { 'type' : 'Point', 'coordinates' : [D('10.0'), D('11.0')] }, 'id' : 'my_id', 'type' : 'Feature', 'properties' : { 'key' : 'value'  , 'type' : 'object' } })

        mockhttp = mock.Mock()
        mockhttp.request.return_value = ({'status': '200', 'content-type': 'application/json', }, EXAMPLE_RECORD_JSONSTR)
        self.client.http = mockhttp
        res = self.client._request("http://thing", 'POST')
        self.failUnlessEqual(res, EXAMPLE_RECORD_JSONSTR)

    def test_update_record(self):
        simplegeoid = 'abcdefghijklmnopqrstuvwyz'
        rec = Record(simplegeoid, D('11.03'), D('10.04'))

        mockhttp = mock.Mock()
        mockhttp.request.return_value = ({'status': '200', 'content-type': 'application/json', }, {'token': "this is your polling token"})
        self.client.http = mockhttp

        res = self.client.update_record(rec)
        self.failUnless(isinstance(res, dict), res)
        self.failUnless(res.has_key('token'), res)

        self.assertEqual(mockhttp.method_calls[0][0], 'request')
        self.assertEqual(mockhttp.method_calls[0][1][0], 'http://api.simplegeo.com:80/%s/places/%s.json' % (API_VERSION, simplegeoid))
        self.assertEqual(mockhttp.method_calls[0][1][1], 'POST')
        bodyjson = mockhttp.method_calls[0][2]['body']
        self.failUnless(isinstance(bodyjson, basestring), (repr(bodyjson), type(bodyjson)))
        # If it decoded as valid json then check for some expected fields
        bodyobj = json.loads(bodyjson)
        self.failUnless(bodyobj.get('geometry').has_key('coordinates'), bodyobj)
        self.failUnless(bodyobj.get('geometry').has_key('type'), bodyobj)
        self.failUnlessEqual(bodyobj.get('geometry')['type'], 'Point')

    def test_delete_record(self):
        simplegeoid = 'abcdefghijklmnopqrstuvwyz'

        mockhttp = mock.Mock()
        mockhttp.request.return_value = ({'status': '200', 'content-type': 'application/json', }, "whatever the response body is")
        self.client.http = mockhttp

        res = self.client.delete_record(simplegeoid)
        self.failUnlessEqual(res, "whatever the response body is")

        self.assertEqual(mockhttp.method_calls[0][0], 'request')
        self.assertEqual(mockhttp.method_calls[0][1][0], 'http://api.simplegeo.com:80/%s/places/%s.json' % (API_VERSION, simplegeoid))
        self.assertEqual(mockhttp.method_calls[0][1][1], 'DELETE')

    def test_search(self):
        rec1 = Record('abcdefghijkmlnopqrstuvwyz1', D('11.03'), D('10.04'), type='place', name="Bob's House Of Monkeys", category="monkey dealership")
        rec2 = Record('abcdefghijkmlnopqrstuvwyz2', D('11.03'), D('10.05'), type='place', name="Monkey Food 'R' Us", category="pet food store")

        mockhttp = mock.Mock()
        mockhttp.request.return_value = ({'status': '200', 'content-type': 'application/json', }, json.dumps({'type': "FeatureColllection", 'features': [rec1.to_dict(), rec2.to_dict()]}))
        self.client.http = mockhttp

        lat = D('11.03')
        lon = D('10.04')
        res = self.client.search(lat, lon, query='monkeys', category='animal')
        self.failUnless(isinstance(res, set), (repr(res), type(res)))
        self.failUnlessEqual(len(res), 2)
        self.failUnless(all(isinstance(f, Record) for f in res))
        self.assertEqual(mockhttp.method_calls[0][0], 'request')
        self.assertEqual(mockhttp.method_calls[0][1][0], 'http://api.simplegeo.com:80/%s/places/%s,%s/search.json?q=monkeys&category=animal' % (API_VERSION, lat, lon))
        self.assertEqual(mockhttp.method_calls[0][1][1], 'GET')

    def test_lat_lon_search(self):
        rec1 = Record('abcdefghijkmlnopqrstuvwyz1', D('11.03'), D('10.04'), type='place', name="Bob's House Of Monkeys", category="monkey dealership")
        rec2 = Record('abcdefghijkmlnopqrstuvwyz2', D('11.03'), D('10.05'), type='place', name="Monkey Food 'R' Us", category="pet food store")

        mockhttp = mock.Mock()
        mockhttp.request.return_value = ({'status': '200', 'content-type': 'application/json', }, json.dumps({'type': "FeatureColllection", 'features': [rec1.to_dict(), rec2.to_dict()]}))
        self.client.http = mockhttp

        lat = D('11.03')
        lon = D('10.04')
        res = self.client.search(lat, lon)
        self.failUnless(isinstance(res, set), (repr(res), type(res)))
        self.failUnlessEqual(len(res), 2)
        self.failUnless(all(isinstance(f, Record) for f in res))
        self.assertEqual(mockhttp.method_calls[0][0], 'request')
        self.assertEqual(mockhttp.method_calls[0][1][0], 'http://api.simplegeo.com:80/%s/places/%s,%s/search.json?q=&category=' % (API_VERSION, lat, lon))
        self.assertEqual(mockhttp.method_calls[0][1][1], 'GET')

    def test_get_record_bad_json(self):
        simplegeoid = 'abcdefghijklmnopqrstuvwyz'

        mockhttp = mock.Mock()
        mockhttp.request.return_value = ({'status': '200', 'content-type': 'application/json', }, 'some crap')
        self.client.http = mockhttp

        try:
            res = self.client.get_record(simplegeoid)
        except DecodeError, e:
            self.failUnlessEqual(e.code,None,repr(e.code))
            self.failUnlessEqual(e.msg,"Could not decode JSON",repr(e.msg))
            decode_e = repr(e)

        self.assertEqual(mockhttp.method_calls[0][0], 'request')
        self.assertEqual(mockhttp.method_calls[0][1][0], 'http://api.simplegeo.com:80/%s/places/%s.json' % (API_VERSION, simplegeoid))
        self.assertEqual(mockhttp.method_calls[0][1][1], 'GET')


    def test_APIError(self):
        e = APIError(500, 'whee', {'status': "500"})
        self.failUnlessEqual(e.code, 500)
        self.failUnlessEqual(e.msg, 'whee')
        representation = repr(e)
        string = str(e) 

    def test_get_places_error(self):
        simplegeoid = 'abcdefghijklmnopqrstuvwyz'

        mockhttp = mock.Mock()
        # mockhttp.request.return_value = ({'status': '500', 'content-type': 'application/json', }, None)
        mockhttp.request.return_value = ({'status': '500', 'content-type': 'application/json', }, '{"message": "help my web server is confuzzled"}')
        self.client.http = mockhttp

        try:
            res = self.client.get_record(simplegeoid)
        except APIError, e:
            self.failUnlessEqual(e.code, 500, repr(e.code))
            self.failUnlessEqual(e.msg, '{"message": "help my web server is confuzzled"}', (type(e.msg), repr(e.msg)))

        self.assertEqual(mockhttp.method_calls[0][0], 'request')
        self.assertEqual(mockhttp.method_calls[0][1][0], 'http://api.simplegeo.com:80/%s/places/%s.json' % (API_VERSION, simplegeoid))
        self.assertEqual(mockhttp.method_calls[0][1][1], 'GET')
