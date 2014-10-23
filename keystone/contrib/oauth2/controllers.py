# Copyright 2013 OpenStack Foundation
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import json
import urllib

from keystone import exception
from keystone.common import controller
from keystone.common import dependency
from keystone.common import wsgi
from keystone.contrib.oauth2 import core as oauth2
from keystone.contrib.oauth2 import validator
from keystone.i18n import _
from keystone.models import token_model

from oauthlib.oauth2 import WebApplicationServer, FatalClientError, OAuth2Error


@dependency.requires('oauth2_api')	
class ConsumerCrudV3(controller.V3Controller):

    collection_name = 'consumers'
    member_name = 'consumer'

    @classmethod
    def base_url(cls, context, path=None):
        """Construct a path and pass it to V3Controller.base_url method."""

        path = '/OS-OAUTH2/' + cls.collection_name
        return super(ConsumerCrudV3, cls).base_url(context, path=path)

    @controller.protected()
    def list_consumers(self, context):
        ref = self.oauth2_api.list_consumers()
        return ConsumerCrudV3.wrap_collection(context, ref)

    @controller.protected()
    def create_consumer(self, context, consumer):
        ref = self._assign_unique_id(self._normalize_dict(consumer))
        consumer_ref = self.oauth2_api.create_consumer(ref)
        return ConsumerCrudV3.wrap_member(context, consumer_ref)

    @controller.protected()
    def get_consumer(self, context, consumer_id):
        consumer_ref = self.oauth2_api.get_consumer(consumer_id)
        return ConsumerCrudV3.wrap_member(context, consumer_ref)

    @controller.protected() 
    def update_consumer(self, context, consumer_id, consumer):
        self._require_matching_id(consumer_id, consumer)
        ref = self._normalize_dict(consumer)
        self._validate_consumer_ref(ref)
        ref = self.oauth2_api.update_consumer(consumer_id, ref)
        return ConsumerCrudV3.wrap_member(context, ref)

    def _validate_consumer_ref(self, consumer):
        if 'secret' in consumer:
            msg = _('Cannot change consumer secret')
            raise exception.ValidationError(message=msg)

    @controller.protected()
    def delete_consumer(self, context, consumer_id):
        # TODO(garcianavalon) revoke and delete consumer tokens
        self.oauth2_api.delete_consumer(consumer_id)

@dependency.requires('oauth2_api')  
class AuthorizationCodeEndpointV3(controller.V3Controller):

    collection_name = 'authorization_codes'
    member_name = 'authorization_code'

    @controller.protected()
    def list_authorization_codes(self, context):
        """Description of the controller logic."""
        ref = self.oauth2_api.list_authorization_codes()
        return AuthorizationCodeEndpointV3.wrap_collection(context, ref)

@dependency.requires('oauth2_api', 'token_provider_api')  
class OAuth2ControllerV3(controller.V3Controller):

    collection_name = 'not_used'
    member_name = 'not_used'

    def _extract_user_id_from_token(self, token_id):
        user_token = token_model.KeystoneToken(
                            token_id=token_id,
                            token_data=self.token_provider_api.validate_token(
                                token_id))
        return user_token.user_id

    @controller.protected()
    def request_authorization_code(self, context):
        request_validator = validator.OAuth2Validator()
        server = WebApplicationServer(request_validator)
        # Validate request
        headers = context['headers']
        body = context['query_string']
        uri = self.base_url(context, context['path'])
        http_method = 'GET'

        try:
            scopes, credentials = server.validate_authorization_request(
                uri, http_method , body, headers)
            # scopes will hold default scopes for client, i.e.
            #['https://example.com/userProfile', 'https://example.com/pictures']

            # credentials is a dictionary of
            # {
            #     'client_id': 'foo',
            #     'redirect_uri': 'https://foo.com/welcome_back',
            #     'response_type': 'code',
            #     'state': 'randomstring',
            #     'request' : The request object created internally. 
            # }
            # these credentials will be needed in the post authorization view and
            # should be persisted between. None of them are secret but take care
            # to ensure their integrity if embedding them in the form or cookies.

            # NOTE(garcianavalon) We are not storing this for now, 
            # but might do it in the future
            request = credentials.pop('request')
            
            # get the user id to identify the credentials in later stages
            credentials['user_id'] = self._extract_user_id_from_token(
                                                    context['token_id'])
            
            credentials_ref = self._assign_unique_id(self._normalize_dict(credentials))
            self.oauth2_api.store_consumer_credentials(credentials_ref)

            # Present user with a nice form where client (id foo) request access to
            # his default scopes (omitted from request), after which you will
            # redirect to his default redirect uri (omitted from request).
            
            # This JSON is to be used by the next layer (ie a Django server) to populate the view
            return { 'data': { # TODO(garcianavalon) find a better name for this
                        'consumer': {
                            'id':credentials['client_id']
                            # TODO(garcianavalon) add consumer description
                        },
                        'redirect_uri':credentials['redirect_uri'],
                        'requested_scopes':request.scopes
                    }}
            
        except FatalClientError as e:
            raise exception.ValidationError(message=e.error)


    @controller.protected()
    def create_authorization_code(self, context, user_auth):
        request_validator = validator.OAuth2Validator()
        server = WebApplicationServer(request_validator)
        # Validate request
        headers = context['headers']
        body = user_auth
        uri = self.base_url(context, context['path'])
        http_method = 'POST'

        # Fetch authorized scopes from the request
        scopes = body.get('scopes')
        if not scopes:
            raise exception.ValidationError(attribute='scopes', target='request')

        # Fetch the credentials saved in the pre authorization phase
        client_id = body.get('client_id')
        if not client_id:
            raise exception.ValidationError(attribute='client_id', target='request')

        user_id = self._extract_user_id_from_token(context['token_id'])
        credentials = self.oauth2_api.get_consumer_credentials(client_id,
                                                            user_id)

        try:
            headers, body, status = server.create_authorization_response(
                uri, http_method, body, headers, scopes, credentials)
            # headers = {'Location': 'https://foo.com/welcome_back?code=somerandomstring&state=xyz'}, this might change to include suggested headers related
            # to cache best practices etc.
            # body = '', this might be set in future custom grant types
            # status = 302, suggested HTTP status code

            response = wsgi.render_response(body,
                                            status=(302, 'Found'),
                                            headers=headers.items())
            return response

        except FatalClientError as e:
            raise exception.ValidationError(message=e.error)

        except OAuth2Error as e:
            # Less grave errors will be reported back to client
            # TODO(garcianavalon) decide how I'm I going to redirect cos redirects should be handled by an upper layer
            raise exception.ValidationError(message=e.error)

    def create_access_token(self, context, token_request):
        request_validator = validator.OAuth2Validator()
        server = WebApplicationServer(request_validator)

        # Validate request

        headers = context['headers']
        # NOTE(garcianavalon) Work around the keystone limitation with content types
        # Keystone only accepts JSON bodies while OAuth2.0 (RFC 6749) requires 
        # x-www-form-urlencoded
        # We leave it like this to support future versions where the use of 
        # x-www-form-urlencoded is accepted
        if headers['Content-Type'] == 'application/x-www-form-urlencoded':
            body = context['query_string']
        elif headers['Content-Type'] == 'application/json':
            
            if not 'code' in token_request:
                msg = _('code missing in request body: %s') %token_request
                raise exception.ValidationError(message=msg)
            body = urllib.urlencode(token_request)
        else:
            msg = _('Content-Type: %s is not supported') %headers['Content-Type']
            raise exception.ValidationError(message=msg) 

        # check headers for authentication
        authmethod, auth = headers['Authorization'].split(' ', 1)
        if authmethod.lower() != 'basic':
            msg = _('Authorization error: %s. Only HTTP Basic is supported') %headers['Authorization']
            raise exception.ValidationError(message=msg)

        uri = self.base_url(context, context['path'])
        http_method = 'POST'
        
        # Extra credentials you wish to include
        credentials = None # TODO(garcianavalon)

        headers, body, status = server.create_token_response(
            uri, http_method, body, headers, credentials)

        # headers will contain some suggested headers to add to your response
        # {
        #     'Content-Type': 'application/json',
        #     'Cache-Control': 'no-store',
        #     'Pragma': 'no-cache',
        # }
        # body will contain the token in json format and expiration from now
        # in seconds.
        # {
        #     'access_token': 'sldafh309sdf',
        #     'refresh_token': 'alsounguessablerandomstring',
        #     'expires_in': 3600,
        #     'scopes': [
        #         'https://example.com/userProfile',
        #         'https://example.com/pictures'
        #     ],
        #     'token_type': 'Bearer'
        # }
        # body will contain an error code and possibly an error description if
        # the request failed, also in json format.
        # {
        #     'error': 'invalid_grant_type',
        #     'description': 'athorizatoin_coed is not a valid grant type'
        # }
        # status will be a suggested status code, 200 on ok, 400 on bad request
        # and 401 if client is trying to use an invalid authorization code,
        # fail to authenticate etc.

        # NOTE(garcianavalon) oauthlib returns the body as a JSON string already,
        # and the Keystone base controlers expect a dictionary  
        body = json.loads(body)

        if status == 200:
            response = wsgi.render_response(body,
                                        status=(status, 'OK'),
                                        headers=headers.items())
            return response
        # Build the error message and raise the corresponding error
        msg = _(body['error'])
        if hasattr(body, 'description'):
            msg = msg + ': ' + _(body['description'])
        if status == 400:
            raise exception.ValidationError(message=msg)
        elif status == 401:
            # TODO(garcianavalon) custom exception class
            raise exception.Unauthorized(message=msg)