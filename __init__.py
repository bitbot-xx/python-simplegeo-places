from _version import __version__

API_VERSION = '1.0'

from httplib2 import Http
import oauth2 as oauth
from urlparse import urljoin
import time

from jsonutil import jsonutil as json

def json_decode(jsonstr):
    try:
        return json.loads(jsonstr)
    except (ValueError, TypeError), le:
        raise DecodeError(jsonstr, le)

def json_decode(jsonstr):
    try: 
        return json.loads(jsonstr)
    except (ValueError, TypeError), le:
        raise DecodeError(jsonstr, le)

class Client(object):
    realm = "http://api.simplegeo.com"
    endpoints = {
        'endpoints': 'endpoints.json',
        'places': 'places/%(simplegeohandle)s.json',
        'create': 'places',
        'search': 'places/%(lat)s,%(lon)s?q=%(query)s&category=%(category)s',
    }

    def __init__(self, key, secret, api_version=API_VERSION, host="api.simplegeo.com", port=80):
        self.host = host
        self.port = port
        self.consumer = oauth.Consumer(key, secret)
        self.key = key
        self.secret = secret
        self.api_version = api_version
        self.signature = oauth.SignatureMethod_HMAC_SHA1()
        self.uri = "http://%s:%s" % (host, port)
        self.http = Http()

    def get_endpoint_descriptions(self):
        """Describe known endpoints."""
        endpoint = self.endpoint('endpoints')
        return json_decode(self._request(endpoint, "GET")[1])

    def endpoint(self, name, **kwargs):
        """Not used directly. Finds and formats the endpoints as needed for any type of request."""
        try:
            endpoint = self.endpoints[name]
        except KeyError:
            raise Exception('No endpoint named "%s"' % name)
        try:
            endpoint = endpoint % kwargs
        except KeyError, e:
            raise TypeError('Missing required argument "%s"' % (e.args[0],))
        return urljoin(urljoin(self.uri, self.api_version + '/'), endpoint)

    def add_record(self, record):
        """Create a new record, returns a 301 to the location of the resource."""
        endpoint = self.endpoint('create')
        self._request(endpoint, "POST", record.to_json())

    def get_record(self, simplegeohandle):
        """Return a record for a place."""
        endpoint = self.endpoint('places', simplegeohandle=simplegeohandle)
        result = self._request(endpoint, 'GET')[1]
        return Record.from_json(result)

    def update_record(self, record):
        """Update a record."""
        endpoint = self.endpoint('places', simplegeohandle=record.simplegeohandle)
        return self._request(endpoint, 'POST', record.to_json())[1]

    def delete_record(self, simplegeohandle):
        """Delete a record."""
        endpoint = self.endpoint('places', simplegeohandle=simplegeohandle)
        return self._request(endpoint, 'DELETE')[1]

    def search(self, lat, lon, query='', category=''):
        """Search for places near a lat/lon."""
        endpoint = self.endpoint('search', lat=lat, lon=lon, query=query, category=category)
        result = self._request(endpoint, 'GET')[1]

        fc = json_decode(result)
        return set(Record.from_dict(f) for f in fc['features'])

    def _request(self, endpoint, method, data=None):
        """
        Not used directly by code external to this lib. Performs the
        actual request against the API, including passing the
        credentials with oauth.  Returns a tuple of (headers as dict,
        body as string).
        """
        if data is not None and not isinstance(data, basestring):
             raise TypeError("data is required to be None or a string or unicode, not %s" % (type(data),))
        params = {}
        body = data
        request = oauth.Request.from_consumer_and_token(self.consumer,
            http_method=method, http_url=endpoint, parameters=params)

        request.sign_request(self.signature, self.consumer, None)
        headers = request.to_header(self.realm)
        headers['User-Agent'] = 'SimpleGeo Places Client v%s' % __version__

        resp, content = self.http.request(endpoint, method, body=body, headers=headers)

        if resp['status'][0] not in ('2', '3'):
            raise APIError(int(resp['status']), content, resp)

        return resp, content

class Record:
    def __init__(self, lat, lon, simplegeohandle=None, recordid=None, type='object', created=None, **kwargs):
        """
        The simplegeohandle and the recordid are both optional -- you
        have have one or the other or both or neither.

        A simplegeohandle is globally unique and is assigned by the
        Places service. It is returned from the Places service in the
        response to a request to add a place to the Places database
        (the add_record method).

        A recordid is scoped to your particular user account and is
        chosen by you. The only use for the recordid is in case you
        call add_record and you have already previously added that
        record to the database -- if there is already a record from
        your user account with the same recordid then the Places
        service will return that record to you, along with that
        records simplegeohandle, instead of making a second, duplicate
        record.
        """
        self.simplegeohandle = simplegeohandle
        self.recordid = recordid
        self.lon = lon
        self.lat = lat
        self.type = type
        if created is None:
            self.created = int(time.time())
        else:
            self.created = created
        self.__dict__.update(kwargs)

    @classmethod
    def from_dict(cls, data):
        assert data
        coord = data['geometry']['coordinates']
        record = cls(simplegeohandle=data.get('simplegeohandle'), recordid=data.get('recordid'), lat=coord[1], lon=coord[0])
        record.type = data['properties']['type']
        record.created = data.get('created', record.created)
        record.__dict__.update(dict((k, v) for k, v in data['properties'].iteritems()
                                    if k not in ('type', 'created')))
        return record

    def to_dict(self):
        return {
            'type': 'Feature',
            'simplegeohandle': self.simplegeohandle,
            'recordid': self.recordid,
            'created': self.created,
            'geometry': {
                'type': 'Point',
                'coordinates': [self.lon, self.lat],
            },
            'properties': dict((k, v) for k, v in self.__dict__.iteritems()
                                        if k not in ('lon', 'lat', 'simplegeohandle', 'recordid', 'created')),
        }

    @classmethod
    def from_json(cls, jsonstr):
        return cls.from_dict(json_decode(jsonstr))

    def to_json(self):
        return json.dumps(self.to_dict())


class APIError(Exception):
    """Base exception for all API errors."""

    def __init__(self, code, msg, headers, description=''):
        self.code = code
        self.msg = msg
        self.headers = headers
        self.description = description

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        return "%s (#%s) %s" % (self.msg, self.code, self.description)

class DecodeError(APIError):
    """There was a problem decoding the API's JSON response."""

    def __init__(self, body, le):
        super(DecodeError, self).__init__(None, "Could not decode JSON", None, repr(le))
        self.body = body

    def __repr__(self):
        return "%s content: %s" % (self.description, self.body)

