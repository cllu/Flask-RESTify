import json
from datetime import datetime

from werkzeug.local import LocalProxy

from .packable import Packable


class JSONEncoder(json.JSONEncoder):
    """
    Handles the following cases:

    - encode datetime as ISO 8601 format
    - automatically decode bytes using utf-8
    - handles Packable objects like User
    - handles LocalProxy object like current_user from flask-login

    - http://en.wikipedia.org/wiki/ISO_8601
    """
    DATE_FORMAT = '%Y-%m-%dT%H:%M:%SZ'

    def default(self, obj):
        if isinstance(obj, datetime):
            if obj.utcoffset() is not None:
                obj = obj - obj.utcoffset()
            return obj.strftime(self.DATE_FORMAT)
        elif isinstance(obj, bytes):
            return obj.decode('utf-8')
        elif isinstance(obj, Packable):
            return obj.pack()
        elif isinstance(obj, LocalProxy) and isinstance(obj._get_current_object(), Packable):
            # the current_user is a proxy object
            return obj.pack()
        return json.JSONEncoder.default(self, obj)


def dumps(values):
    return json.dumps(values, cls=JSONEncoder)


def loads(string):
    """We do not cares about the json decoding and just use the default one
    """
    return json.loads(string, cls=json.JSONDecoder)
