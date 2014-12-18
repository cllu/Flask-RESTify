# -*- coding: utf-8 -*-

__author__ = 'Chunliang Lyu'
__email__ = 'hi@chunlianglyu.com'
__version__ = '0.1.3'
__all__ = ('Api', 'Resource', 'Packable', 'JSONEncoder')

from functools import wraps

from flask import request, url_for, current_app, make_response
from flask.views import MethodView
from werkzeug.wrappers import Response as ResponseBase

from .jsons import JSONEncoder, dumps
from .packable import Packable


def unpack(value):
    """Return a three tuple of data, code, and headers"""
    if not isinstance(value, tuple):
        return value, 200, {}

    try:
        data, code, headers = value
        return data, code, headers
    except ValueError:
        pass

    try:
        data, code = value
        return data, code, {}
    except ValueError:
        pass

    return value, 200, {}



# This dictionary contains any kwargs that are to be passed to the json.dumps
# function, used below.
settings = {}


def output_json(data, code, headers=None):
    """Makes a Flask response with a JSON encoded body"""

    # If we're in debug mode, and the indent is not set, we set it to a
    # reasonable value here.  Note that this won't override any existing value
    # that was set.  We also set the "sort_keys" value.
    local_settings = settings.copy()
    if current_app.debug:
        local_settings.setdefault('indent', 4)
        local_settings.setdefault('sort_keys', True)

    # We also add a trailing newline to the dumped JSON if the indent value is
    # set - this makes using `curl` on the command line much nicer.
    dumped = dumps(data, **local_settings)
    if 'indent' in local_settings:
        dumped += '\n'

    resp = make_response(dumped, code)
    resp.headers.extend(headers or {})
    return resp
DEFAULT_REPRESENTATIONS = {'application/json': output_json}


class Api(object):
    """
    The main entry point for the application.
    You need to initialize it with a Flask Application: ::

    Alternatively, you can use :meth:`init_app` to set the Flask application
    after it has been constructed.

    :param app: the Flask application object
    :type app: flask.Flask
    :param prefix: Prefix all routes with a value, eg v1 or 2010-04-01
    :type prefix: str
    :param default_mediatype: The default media type to return
    :type default_mediatype: str
    :param decorators: Decorators to attach to every resource
    :type decorators: list
    :param url_part_order: A string that controls the order that the pieces
        of the url are concatenated when the full url is constructed.  'b'
        is the blueprint (or blueprint registration) prefix, 'a' is the api
        prefix, and 'e' is the path component the endpoint is added with

    """

    def __init__(self, app=None, prefix='',
                 default_mediatype='application/json', decorators=None,
                 url_part_order='bae'):
        self.representations = dict(DEFAULT_REPRESENTATIONS)
        self.urls = {}
        self.prefix = prefix
        self.default_mediatype = default_mediatype
        self.decorators = decorators if decorators else []
        self.url_part_order = url_part_order
        self.blueprint_setup = None
        self.resources = []

        self.endpoints = {}

        self.app = None
        if app is not None:
            self.app = app
            self.init_app(app)

    def init_app(self, app):
        """Initialize this class with the given :class:`flask.Flask`
        application or :class:`flask.Blueprint` object.

        :param app: the Flask application or blueprint object
        :type app: flask.Flask

        Examples::

            api = Api()
            api.add_resource(...)
            api.init_app(app)

        """
        self.app = app
        app.json_encoder = JSONEncoder
        if len(self.resources) > 0:
            for resource, urls, kwargs in self.resources:
                self._register_view(app, resource, *urls, **kwargs)

    def _complete_url(self, url_part, registration_prefix):
        """This method is used to defer the construction of the final url in
        the case that the Api is created with a Blueprint.

        :param url_part: The part of the url the endpoint is registered with
        :param registration_prefix: The part of the url contributed by the
            blueprint.  Generally speaking, BlueprintSetupState.url_prefix
        """
        parts = {
            'b': registration_prefix,
            'a': self.prefix,
            'e': url_part
        }
        return ''.join(parts[key] for key in self.url_part_order if parts[key])

    def mediatypes_method(self):
        """Return a method that returns a list of mediatypes
        """
        return lambda resource_cls: self.mediatypes() + [self.default_mediatype]

    def add_resource(self, resource, *urls, **kwargs):
        """Adds a resource to the api.

        :param resource: the class name of your resource
        :type resource: :class:`Resource`
        :param urls: one or more url routes to match for the resource, standard
                     flask routing rules apply.  Any url variables will be
                     passed to the resource method as args.
        :type urls: str

        :param endpoint: endpoint name (defaults to :meth:`Resource.__name__.lower`
            Can be used to reference this route in :class:`fields.Url` fields
        :type endpoint: str

        Additional keyword arguments not specified above will be passed as-is
        to :meth:`flask.Flask.add_url_rule`.

        Examples::

            api.add_resource(HelloWorld, '/', '/hello')
            api.add_resource(Foo, '/foo', endpoint="foo")
            api.add_resource(FooSpecial, '/special/foo', endpoint="foo")

        """
        if self.app is not None:
            self._register_view(self.app, resource, *urls, **kwargs)
        else:
            self.resources.append((resource, urls, kwargs))

    def _register_view(self, app, resource, *urls, **kwargs):
        endpoint = kwargs.pop('endpoint', None) or resource.__name__.lower()

        if endpoint in app.view_functions.keys():
            previous_view_class = app.view_functions[endpoint].__dict__['view_class']

            # if you override the endpoint with a different class, avoid the collision by raising an exception
            if previous_view_class != resource:
                raise ValueError('This endpoint (%s) is already set to the class %s.' % (endpoint, previous_view_class.__name__))

        resource.mediatypes = self.mediatypes_method()  # Hacky
        resource.endpoint = endpoint
        resource_func = self.output(resource.as_view(endpoint))

        for decorator in self.decorators:
            resource_func = decorator(resource_func)

        for url in urls:
            rule = self._complete_url(url, '')
            # Add the url to the application or blueprint
            app.add_url_rule(rule, view_func=resource_func, **kwargs)

    def output(self, resource):
        """Wraps a resource (as a flask view function), for cases where the
        resource does not directly return a response object

        :param resource: The resource as a flask view function
        """
        @wraps(resource)
        def wrapper(*args, **kwargs):
            resp = resource(*args, **kwargs)

            # during exception handling, we may already generate valid response object
            # especially used in Flask-Login, (Response, int)
            if isinstance(resp, tuple):
                return resp

            if isinstance(resp, ResponseBase):  # There may be a better way to test
                return resp
            data, code, headers = unpack(resp)
            return self.make_response(data, code, headers=headers)
        return wrapper

    def url_for(self, resource, **values):
        """Generates a URL to the given resource."""
        return url_for(resource.endpoint, **values)

    def make_response(self, data, *args, **kwargs):
        """Looks up the representation transformer for the requested media
        type, invoking the transformer to create a response object. This
        defaults to (application/json) if no transformer is found for the
        requested mediatype.

        :param data: Python object containing response data to be transformed
        """
        for mediatype in self.mediatypes() + [self.default_mediatype]:
            if mediatype in self.representations:
                resp = self.representations[mediatype](data, *args, **kwargs)
                resp.headers['Content-Type'] = mediatype
                return resp

    def mediatypes(self):
        """Returns a list of requested mediatypes sent in the Accept header"""
        return [h for h, q in request.accept_mimetypes]

    def representation(self, mediatype):
        """Allows additional representation transformers to be declared for the
        api. Transformers are functions that must be decorated with this
        method, passing the mediatype the transformer represents. Three
        arguments are passed to the transformer:

        * The data to be represented in the response body
        * The http status code
        * A dictionary of headers

        The transformer should convert the data appropriately for the mediatype
        and return a Flask response object.

        Ex::

            @api.representation('application/xml')
            def xml(data, code, headers):
                resp = make_response(convert_data_to_xml(data), code)
                resp.headers.extend(headers)
                return resp
        """
        def wrapper(func):
            self.representations[mediatype] = func
            return func
        return wrapper

    def model(self):
        """decorator to annotate API response model
        """
        def wrapper(func):
            return func
        return wrapper

    def endpoint(self, parameters=None, responses=None):
        """decorator to annotate method parameters/responses
        """
        def wrapper(func):
            func.parameters = parameters
            func.responses = responses
            return func
        return wrapper


class Resource(MethodView):
    """
    Represents an abstract RESTful resource. Concrete resources should
    extend from this class and expose methods for each supported HTTP
    method. If a resource is invoked with an unsupported HTTP method,
    the API will return a response with status 405 Method Not Allowed.
    Otherwise the appropriate method is called and passed all arguments
    from the url rule used when adding the resource to an Api instance. See
    :meth:`~flask.ext.restful.Api.add_resource` for details.
    """
    representations = None
    method_decorators = []

    def dispatch_request(self, *args, **kwargs):

        # Taken from flask
        #noinspection PyUnresolvedReferences
        meth = getattr(self, request.method.lower(), None)
        if meth is None and request.method == 'HEAD':
            meth = getattr(self, 'get', None)
        assert meth is not None, 'Unimplemented method %r' % request.method

        for decorator in self.method_decorators:
            meth = decorator(meth)

        resp = meth(*args, **kwargs)

        if isinstance(resp, ResponseBase):  # There may be a better way to test
            return resp

        representations = self.representations or {}

        #noinspection PyUnresolvedReferences
        for mediatype in self.mediatypes():
            if mediatype in representations:
                data, code, headers = unpack(resp)
                resp = representations[mediatype](data, code, headers)
                resp.headers['Content-Type'] = mediatype
                return resp

        return resp

