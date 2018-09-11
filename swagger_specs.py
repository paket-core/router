"""Swagger specifications of Identity Server."""
VERSION = 3
CONFIG = {
    'title': 'PaKeT Router',
    'uiversion': 2,
    'specs_route': '/',
    'specs': [{
        'endpoint': '/',
        'route': '/apispec.json',
    }],
    'info': {
        'title': 'The PaKeT Router Server',
        'version': VERSION,
        'contact': {
            'name': 'The PaKeT Project',
            'email': 'israel@paket.global',
            'url': 'https://router.paket.global',
        },
        'license': {
            'name': 'GNU GPL 3.0',
            'url': 'http://www.gnu.org/licenses/'
        },
        'description': '''
Router Server for The PaKeT Project

What is this?
=============
This page is used as both documentation of our router server and as a sandbox to
test interaction with it. You can use this page to call the RESTful API while
specifying any required or optional parameter. The page also presents curl
commands that can be used to call the server.

Security
========
Our calls are split into the following security levels:
 - Debug functions: require no authentication, available only in debug mode.
 - Anonymous functions: require no authentication.
 - Authenticated functions: require asymmetric key authentication. Not tested
   in debug mode.
    - The **'Pubkey'** header will contain the user's pubkey.
    - The **'Fingerprint'** header is constructed from the comma separated
      concatenation of the called URI, all the arguments (as key=value), and an
      ever increasing nonce (recommended to use Unix time in milliseconds).
    - The **'Signature'** header will contain a Base64 ASCII encoded signature
      on the specified 'Fingerprint', produced by the private key corresponding
      to the specified 'pubkey'.

Walkthrough
===========
The following steps demonstrate the main functionality of the router.

### Creating package
 - To create package you need to call `/create_package` route and  provide
 public key of escrow, courier and recipient,payment and collateral
 in undividable parts of BULs, deadline timestamp, transactions (set options, merge, payments),
 and location (optionally).
 To create transactions you may use `/prepare_escrow` route from bridge server.

### Accepting package
 - To accept package you need to call `/accept_package` route
 with provided escrow public key and location (optionally).

### Adding events
 - Three types of events will be added automatically after calling `/create_package`
 and `/accept_package`. It is `launched`, `couriered` and `received` events.
 In addition to this events you can add another with calling `/add_event` and
 providing escrow public key, event type and location. The separate route designed for
 event about changing location - `/changed_location`.
 Location - string of 24 signs length in format "latitude, longitude" (without parentheses).

### Requesting information about packages
 - You may request information about single package with calling `/package` route and
 providing public key of escrow. Or you can request information about all your packages with
 calling `/my_packages` route.

The API
=======

To play around with the system you will need at least three public keys: a
launcher pubkey, a courier pubkey, and a recipient pubkey. You can use Account Creator
for generating key pairs: https://www.stellar.org/laboratory/#account-creator
        '''
    }
}


CREATE_PACKAGE = {
    'tags': [
        'packages'
    ],
    'parameters': [
        {'name': 'Pubkey', 'in': 'header', 'required': True, 'type': 'string'},
        {'name': 'Fingerprint', 'in': 'header', 'required': True, 'type': 'string'},
        {'name': 'Signature', 'in': 'header', 'required': True, 'type': 'string'},
        {
            'name': 'escrow_pubkey', 'description': 'escrow pubkey',
            'in': 'formData', 'required': True, 'type': 'string'},
        {
            'name': 'recipient_pubkey', 'description': 'recipient pubkey',
            'in': 'formData', 'required': True, 'type': 'string'},
        {
            'name': 'launcher_phone_number', 'description': 'phone number of the launcher',
            'in': 'formData', 'required': True, 'type': 'string'},
        {
            'name': 'recipient_phone_number', 'description': 'phone number of the recipient',
            'in': 'formData', 'required': True, 'type': 'string'},
        {
            'name': 'payment_buls', 'description': 'BULs promised as payment',
            'in': 'formData', 'required': True, 'type': 'integer'},
        {
            'name': 'collateral_buls', 'description': 'BULs promised as collateral',
            'in': 'formData', 'required': True, 'type': 'integer'},
        {
            'name': 'deadline_timestamp', 'description': 'deadline timestamp',
            'in': 'formData', 'required': True, 'type': 'integer'},
        {
            'name': 'description', 'description': 'package description (300 characters max)',
            'in': 'formData', 'required': True, 'type': 'string'},
        {
            'name': 'from_location', 'description': 'GPS location of place where launcher will give package to courier',
            'in': 'formData', 'required': True, 'type': 'string'},
        {
            'name': 'to_location', 'description': 'GPS location of place where package need to be delivered to',
            'in': 'formData', 'required': True, 'type': 'string'},
        {
            'name': 'from_address', 'description': 'Address of place where launcher will give package to courier',
            'in': 'formData', 'required': True, 'type': 'string'},
        {
            'name': 'to_address', 'description': 'Address of place where package need to be delivered to',
            'in': 'formData', 'required': True, 'type': 'string'},
        {
            'name': 'event_location', 'description': 'GPS location of place where launcher submited package info',
            'in': 'formData', 'required': True, 'type': 'string'},
        {
            'name': 'photo', 'description': 'package photo',
            'in': 'formData', 'required': False, 'type': 'file', 'format': 'binary'}
    ],
    'responses': {
        '201': {
            'description': 'package details',
        }
    }
}

ACCEPT_PACKAGE = {
    'tags': ['packages'],
    'parameters': [
        {'name': 'Pubkey', 'in': 'header', 'required': True, 'type': 'string'},
        {'name': 'Fingerprint', 'in': 'header', 'required': True, 'type': 'string'},
        {'name': 'Signature', 'in': 'header', 'required': True, 'type': 'string'},
        {
            'name': 'escrow_pubkey', 'description': 'escrow pubkey (the package ID)',
            'in': 'formData', 'required': True, 'type': 'string',
        },
        {
            'name': 'location', 'description': 'location of place where user accepted package',
            'in': 'formData', 'required': True, 'type': 'string'
        }
    ],
    'responses': {
        '200': {
            'description': 'package custodianship changed'
        }
    }
}

ASSIGN_PACKAGE = {
    'tags': ['packages'],
    'parameters': [
        {'name': 'Pubkey', 'in': 'header', 'required': True, 'type': 'string'},
        {'name': 'Fingerprint', 'in': 'header', 'required': True, 'type': 'string'},
        {'name': 'Signature', 'in': 'header', 'required': True, 'type': 'string'},
        {
            'name': 'escrow_pubkey', 'description': 'escrow pubkey (the package ID)',
            'in': 'formData', 'required': True, 'type': 'string',
        },
        {
            'name': 'location', 'description': 'location of place where user choose package to be courier in',
            'in': 'formData', 'required': True, 'type': 'string'
        }
    ],
    'responses': {
        '200': {
            'description': 'user became courier for package'
        }
    }
}

ASSIGN_XDRS = {
    'tags': ['packages'],
    'parameters': [
        {'name': 'Pubkey', 'in': 'header', 'required': True, 'type': 'string'},
        {'name': 'Fingerprint', 'in': 'header', 'required': True, 'type': 'string'},
        {'name': 'Signature', 'in': 'header', 'required': True, 'type': 'string'},
        {
            'name': 'escrow_pubkey', 'description': 'escrow pubkey (the package ID)',
            'in': 'formData', 'required': True, 'type': 'string',
        },
        {
            'name': 'location', 'description': 'location of place where user accepted package',
            'in': 'formData', 'required': True, 'type': 'string'
        },
        {
            'name': 'kwargs', 'description': 'XDRs transaction in JSON format',
            'in': 'formData', 'required': True, 'type': 'string'
        }
    ],
    'responses': {
        '200': {
            'description': 'added event with XDRs transactions'
        }
    }
}

AVAILABLE_PACKAGES = {
    'tags': ['packages'],
    'parameters': [
        {
            'name': 'location', 'description': 'location of place for searching packages nearby',
            'in': 'formData', 'required': True, 'type': 'string',
        },
        {
            'name': 'radius_num', 'description': 'maximum search radius (in km)',
            'in': 'formData', 'required': False, 'type': 'integer'
        }
    ],
    'responses': {
        '200': {
            'description': 'available for couriering packages'
        }
    }
}

MY_PACKAGES = {
    'tags': ['packages'],
    'parameters': [
        {'name': 'Pubkey', 'in': 'header', 'required': True, 'type': 'string'},
        {'name': 'Fingerprint', 'in': 'header', 'required': True, 'type': 'string'},
        {'name': 'Signature', 'in': 'header', 'required': True, 'type': 'string'},
    ],
    'responses': {
        '200': {
            'description': 'list of packages',
            'schema': {
                'properties': {
                    'packages': {
                        'type': 'array',
                        'items': {
                            '$ref': '#/definitions/Package-info'
                        }
                    }
                }
            }
        }
    }
}

PACKAGE = {
    'tags': ['packages'],
    'parameters': [
        {
            'name': 'escrow_pubkey', 'description': 'escrow pubkey (the package ID)',
            'in': 'formData', 'required': True, 'type': 'string'},
        {
            'name': 'check_escrow', 'description': 'include information about payment and collateral if specified',
            'in': 'formData', 'required': False, 'type': 'integer'}
    ],
    'definitions': {
        'Event': {
            'type': 'object',
            'properties': {
                'event-type': {
                    'type': 'string'
                },
                'timestamp': {
                    'type': 'integer'
                },
                'pubkey': {
                    'type': 'string'
                },
                'location': {
                    'type': 'string'
                }
            }
        },
        'Package-info': {
            'type': 'object',
            'properties': {
                'PKT-id': {
                    'type': 'string'
                },
                'blockchain-url': {
                    'type': 'string'
                },
                'collateral': {
                    'type': 'integer'
                },
                'deadline-timestamp': {
                    'type': 'integer'
                },
                'paket-url': {
                    'type': 'string'
                },
                'payment': {
                    'type': 'integer'
                },
                'recipient-id': {
                    'type': 'string'
                },
                'send-timestamp': {
                    'type': 'integer'
                },
                'status': {
                    'type': 'string'
                },
                'events': {
                    'type': 'array',
                    'items': {
                        '$ref': '#/definitions/Event'
                    }
                }
            }
        }
    },
    'responses': {
        '200': {
            'description': 'a single packages',
            'schema': {
                '$ref': '#/definitions/Package-info'
            }
        }
    }
}

ADD_EVENT = {
    'tags': ['packages'],
    'parameters': [
        {'name': 'Pubkey', 'in': 'header', 'required': True, 'type': 'string'},
        {'name': 'Fingerprint', 'in': 'header', 'required': True, 'type': 'string'},
        {'name': 'Signature', 'in': 'header', 'required': True, 'type': 'string'},
        {
            'name': 'event_type', 'description': 'type of event',
            'in': 'formData', 'required': True, 'type': 'string'},
        {
            'name': 'location', 'description': 'GPS coordinates where event happened',
            'in': 'formData', 'required': True, 'type': 'string'},
        {
            'name': 'escrow_pubkey', 'description': 'pubkey of package escrow',
            'in': 'formData', 'required': False, 'type': 'string'},
        {
            'name': 'kwargs', 'description': 'extra parameters in JSON format',
            'in': 'formData', 'required': False, 'type': 'string'
        }
    ],
    'responses': {
        '200': {'description': 'event successfully added'}
    }
}

CHANGED_LOCATION = {
    'tags': ['packages'],
    'parameters': [
        {'name': 'Pubkey', 'in': 'header', 'required': True, 'type': 'string'},
        {'name': 'Fingerprint', 'in': 'header', 'required': True, 'type': 'string'},
        {'name': 'Signature', 'in': 'header', 'required': True, 'type': 'string'},
        {
            'name': 'escrow_pubkey', 'description': 'pubkey of package escrow',
            'in': 'formData', 'required': True, 'type': 'string'},
        {
            'name': 'location', 'description': 'GPS coordinates where user is at this moment',
            'in': 'formData', 'required': True, 'type': 'string'}
    ],
    'responses': {
        '200': {'description': 'event successfully added'}
    }
}

EVENTS = {
    'tags': ['packages'],
    'parameters': [
        {
            'name': 'max_events_num', 'description': 'limit of queried events',
            'in': 'formData', 'required': False, 'type': 'integer'},
        {
            'name': 'mock', 'description': 'allow mock data in case of empty db',
            'in': 'formData', 'required': False, 'type': 'integer'}
    ],
    'responses': {
        '200': {'description': 'a list of events'}
    }
}

CREATE_MOCK_PACKAGE = {
    'tags': [
        'debug'
    ],
    'parameters': [
        {
            'name': 'escrow_pubkey', 'description': 'escrow pubkey',
            'in': 'formData', 'required': True, 'type': 'string'},
        {
            'name': 'launcher_pubkey', 'description': 'recipient pubkey',
            'in': 'formData', 'required': True, 'type': 'string'},
        {
            'name': 'recipient_pubkey', 'description': 'recipient pubkey',
            'in': 'formData', 'required': True, 'type': 'string'},
        {
            'name': 'launcher_phone_number', 'description': 'phone number of the launcher',
            'in': 'formData', 'required': True, 'type': 'string'},
        {
            'name': 'recipient_phone_number', 'description': 'phone number of the recipient',
            'in': 'formData', 'required': True, 'type': 'string'},
        {
            'name': 'payment_buls', 'description': 'BULs promised as payment',
            'in': 'formData', 'required': True, 'type': 'integer'},
        {
            'name': 'collateral_buls', 'description': 'BULs promised as collateral',
            'in': 'formData', 'required': True, 'type': 'integer'},
        {
            'name': 'deadline_timestamp', 'description': 'deadline timestamp',
            'in': 'formData', 'required': True, 'type': 'integer'},
        {
            'name': 'description', 'description': 'package description (300 characters max)',
            'in': 'formData', 'required': False, 'type': 'string'},
        {
            'name': 'from_location', 'description': 'GPS location of place where launcher will give package to courier',
            'in': 'formData', 'required': False, 'type': 'string'},
        {
            'name': 'to_location', 'description': 'GPS location of place where package need to be delivered to',
            'in': 'formData', 'required': False, 'type': 'string'},
        {
            'name': 'from_address', 'description': 'Address of place where launcher will give package to courier',
            'in': 'formData', 'required': False, 'type': 'string'},
        {
            'name': 'to_address', 'description': 'Address of place where package need to be delivered to',
            'in': 'formData', 'required': False, 'type': 'string'},
        {
            'name': 'event_location', 'description': 'GPS location of place where launcher submited package info',
            'in': 'formData', 'required': False, 'type': 'string'},
        {
            'name': 'photo', 'description': 'package photo',
            'in': 'formData', 'required': False, 'type': 'file', 'format': 'binary'}
    ],
    'responses': {
        '201': {
            'description': 'package details',
        }
    }
}

PACKAGES = {
    'tags': ['debug'],
    'responses': {
        '200': {'description': 'a list of packages'}
    }
}

LOG = {
    'tags': [
        'debug'
    ],
    'parameters': [
        {
            'name': 'lines_num',
            'required': False,
            'in': 'formData',
            'schema': {
                'type': 'integer',
                'format': 'integer'
            }
        },
    ],
    'responses': {
        '200': {
            'description': 'log lines',
        }
    }
}
