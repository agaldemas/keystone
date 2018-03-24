# Copyright (C) 2015 Universidad Politecnica de Madrid
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
import uuid

from keystone import config
from keystone.assignment.backends.sql import AssignmentType

CONF = config.CONF
DEFAULT_DOMAIN = CONF.identity.default_domain_id

# Utils
def find_id(elements, attr='name', value=None):
    return next(r for r in elements if r[attr] == value)['id']

# Catalog, endpoints and services
KEYSTONE_PUBLIC_ADDRESS = 'keystone'
KEYSTONE_ADMIN_ADDRESS = 'keystone'
KEYSTONE_INTERNAL_ADDRESS = 'keystone'

_REGIONS = [
    'MNCA',
]

REGIONS = []
for region in _REGIONS:
    REGIONS.append({
        'id': region,
        'description': '',
        'extra': json.dumps({}),
    })

_SERVICE_CATALOG = [
    {
        'endpoints': [
            {
                'region': _REGIONS[0],
                'adminURL': 'http://{url}:{port}/v3/'.format(
                    url=KEYSTONE_ADMIN_ADDRESS,
                    port=CONF.admin_port),
                'internalURL': 'http://{url}:{port}/v3/'.format(
                    url=KEYSTONE_INTERNAL_ADDRESS,
                    port=CONF.admin_port),
                'publicURL': 'http://{url}:{port}/v3/'.format(
                    url=KEYSTONE_PUBLIC_ADDRESS,
                    port=CONF.public_port)
            }
        ],
        'type': 'identity',
        'name': 'keystone'
    }
]

SERVICES = []
ENDPOINTS = []
for service_data in _SERVICE_CATALOG:
    service_id = uuid.uuid4().hex

    SERVICES.append({
        'id': service_id,
        'type': service_data['type'],
        'enabled': True,
        'extra': json.dumps({
            'name': service_data['name'],
        }),
    })


    # Create endpoints
    for endpoint_data in service_data['endpoints']:
        interfaces = [
            ('public', endpoint_data['publicURL']),
            ('admin', endpoint_data['adminURL']),
            ('internal', endpoint_data['internalURL']),
        ]
        for interface in interfaces:
            ENDPOINTS.append({
                'id': uuid.uuid4().hex,
                'service_id': service_id,
                'url': interface[1],
                'region_id': endpoint_data['region'],
                'interface': interface[0],
                'extra': json.dumps({}),
            })

# Endpoint Group Filters
ENDPOINT_GROUPS = []

# one for each region
for region in _REGIONS:
    ENDPOINT_GROUPS.append({
        'id': uuid.uuid4().hex,
        'name': region + ' Region Group',
        'filters': json.dumps({'region_id': region}),
    })

# one for each identity service
for service in [s for s in SERVICES if s['type'] == 'identity']:
    ENDPOINT_GROUPS.append({
        'id': uuid.uuid4().hex,
        'name': json.loads(service['extra'])['name'] + ' Identity Group',
        'filters': json.dumps({'service_id': service['id']}),
    })


# Keystone Roles
KEYSTONE_ROLES = [
    {
        'id': uuid.uuid4().hex,
        'name': 'member',
        'extra': json.dumps({}),
    },
    {
        'id': uuid.uuid4().hex,
        'name': 'owner',
        'extra': json.dumps({}),
    },
    {
        'id': uuid.uuid4().hex,
        'name': 'trial',
        'extra': json.dumps({
            'is_default': True
        })
    },
    {
        'id': uuid.uuid4().hex,
        'name': 'basic',
        'extra': json.dumps({
            'is_default': True
        })
    },
    {
        'id': uuid.uuid4().hex,
        'name': 'community',
        'extra': json.dumps({
            'is_default': True
        })
    },
    {
        'id': uuid.uuid4().hex,
        'name': 'admin',
        'extra': json.dumps({
            'is_default': True
        })
    },
]

# Projects
PROJECTS = [
    {
        'id': 'idm_project',
        'name': 'idm',
        'description':'',
        'enabled': True,
        'domain_id': DEFAULT_DOMAIN,
        'extra': json.dumps({
            'is_default': True,
        })
    },
]

# Users
USERS = [
    {
        'id': 'idm_user',
        'name': 'idm',
        'username': 'idm',
        'enabled': True,
        'default_project_id': find_id(PROJECTS, value='idm'),
        'domain_id': DEFAULT_DOMAIN,
        'extra': json.dumps({}),
    },
]

# Keystone role assignments
ASSIGNMENTS = [
    {
        'role_id': find_id(KEYSTONE_ROLES, value='admin'),
        'actor_id': find_id(USERS, value='idm'),
        'target_id': find_id(PROJECTS, value='idm'),
        'type': AssignmentType.USER_PROJECT,
        'inherited': False,
    },
    {
        'role_id': find_id(KEYSTONE_ROLES, value='owner'),
        'actor_id': find_id(USERS, value='idm'),
        'target_id': find_id(PROJECTS, value='idm'),
        'type': AssignmentType.USER_PROJECT,
        'inherited': False,
    },
]

# Internal FIWARE roles and permissions
_IDM_ADMIN_APP_NAME = 'idm_admin_app'

APPLICATIONS = [
    {
        'id': _IDM_ADMIN_APP_NAME,
        'name': _IDM_ADMIN_APP_NAME,
        'description': (
            'Application that acts as the IdM itself. To see the administration '
            'section of the web portal grant provider to a user in this application.'
        ),
        'grant_type': 'authorization_code',
        'client_type': 'confidential',
        'redirect_uris': json.dumps([]),
        'response_type': 'code',
        'secret':  uuid.uuid4().hex,
        'scopes': json.dumps([]),
        'extra': json.dumps({
            'is_default': True,
        }),
    },
]

_INTERNAL_ROLES_PERM_NAME = 'Get and assign all internal application roles'
_MANAGE_APP_PERM_NAME = 'Manage the application'
_MANAGE_ROLES_PERM_NAME = 'Manage roles'
_ALL_PUBLIC_PERM_NAME = 'Get and assign all public application roles'
_MANAGE_AUTH_PERM_NAME = 'Manage Authorizations'
_OWNED_ROLES_PERM_NAME = 'Get and assign only public owned roles'

FIWARE_PERMISSIONS = [
    {
        'id': 'manage-application',
        'name': _MANAGE_APP_PERM_NAME,
        'application_id': find_id(APPLICATIONS, value=_IDM_ADMIN_APP_NAME),
        'is_internal': True,
    },
    {
        'id': 'manage-roles',
        'name': _MANAGE_ROLES_PERM_NAME,
        'application_id': find_id(APPLICATIONS, value=_IDM_ADMIN_APP_NAME),
        'is_internal': True,
    },
    {
        'id': 'get-assign-public-roles',
        'name': _ALL_PUBLIC_PERM_NAME,
        'application_id': find_id(APPLICATIONS, value=_IDM_ADMIN_APP_NAME),
        'is_internal': True,
    },
    {
        'id': 'manage-authorizations',
        'name': _MANAGE_AUTH_PERM_NAME,
        'application_id': find_id(APPLICATIONS, value=_IDM_ADMIN_APP_NAME),
        'is_internal': True,
    },
    {
        'id': 'get-assign-public-owned-roles',
        'name': _OWNED_ROLES_PERM_NAME,
        'application_id': find_id(APPLICATIONS, value=_IDM_ADMIN_APP_NAME),
        'is_internal': True,
    },
    {
        'id': 'get-assign-internal-roles',
        'name': _INTERNAL_ROLES_PERM_NAME,
        'application_id': find_id(APPLICATIONS, value=_IDM_ADMIN_APP_NAME),
        'is_internal': True,
    },
]

_PROVIDER_ROLE_NAME = 'Provider'
_PURCHASER_ROLE_NAME = 'Purchaser'

FIWARE_ROLES = [
    {
        'id': 'provider',
        'name': _PROVIDER_ROLE_NAME,
        'application_id': find_id(APPLICATIONS, value=_IDM_ADMIN_APP_NAME),
        'is_internal': True,
    },
    {
        'id': 'purchaser',
        'name': _PURCHASER_ROLE_NAME,
        'application_id': find_id(APPLICATIONS, value=_IDM_ADMIN_APP_NAME),
        'is_internal': True,
    },
]

# FIWARE role assignments
FIWARE_ROLE_PERMISSION = [
    {
        'role_id': find_id(FIWARE_ROLES, value=_PROVIDER_ROLE_NAME),
        'permission_id': find_id(FIWARE_PERMISSIONS, value=_INTERNAL_ROLES_PERM_NAME),
    },
    {
        'role_id': find_id(FIWARE_ROLES, value=_PROVIDER_ROLE_NAME),
        'permission_id': find_id(FIWARE_PERMISSIONS, value=_MANAGE_APP_PERM_NAME),
    },
    {
        'role_id': find_id(FIWARE_ROLES, value=_PROVIDER_ROLE_NAME),
        'permission_id': find_id(FIWARE_PERMISSIONS, value=_MANAGE_ROLES_PERM_NAME),
    },
    {
        'role_id': find_id(FIWARE_ROLES, value=_PROVIDER_ROLE_NAME),
        'permission_id': find_id(FIWARE_PERMISSIONS, value=_ALL_PUBLIC_PERM_NAME),
    },
    {
        'role_id': find_id(FIWARE_ROLES, value=_PROVIDER_ROLE_NAME),
        'permission_id': find_id(FIWARE_PERMISSIONS, value=_MANAGE_AUTH_PERM_NAME),
    },
    {
        'role_id': find_id(FIWARE_ROLES, value=_PROVIDER_ROLE_NAME),
        'permission_id': find_id(FIWARE_PERMISSIONS, value=_OWNED_ROLES_PERM_NAME),
    },
    {
        'role_id': find_id(FIWARE_ROLES, value=_PURCHASER_ROLE_NAME),
        'permission_id': find_id(FIWARE_PERMISSIONS, value=_ALL_PUBLIC_PERM_NAME),
    },
]

FIWARE_ROLE_USER = [
    {
        'role_id': find_id(FIWARE_ROLES, value=_PROVIDER_ROLE_NAME),
        'user_id': find_id(USERS, value='idm'),
        'organization_id': find_id(PROJECTS, value='idm'),
        'application_id': find_id(APPLICATIONS, value=_IDM_ADMIN_APP_NAME),

    },
]

# Finally export all the data
DATA = [
    ('region', REGIONS),
    ('service', SERVICES),
    ('endpoint', ENDPOINTS),
    ('endpoint_group', ENDPOINT_GROUPS),
    ('role', KEYSTONE_ROLES),
    ('user', USERS),
    ('project', PROJECTS),
    ('assignment', ASSIGNMENTS),
    ('consumer_oauth2', APPLICATIONS),
    ('role_fiware', FIWARE_ROLES),
    ('permission_fiware', FIWARE_PERMISSIONS),
    ('role_permission_fiware', FIWARE_ROLE_PERMISSION),
    ('role_user_fiware', FIWARE_ROLE_USER),
]
