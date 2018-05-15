"""Swagger specifications of Identity Server."""
VERSION = 3
CONFIG = {
    'title': 'PaKeT API',
    'uiversion': 2,
    'specs_route': '/',
    'specs': [{
        'endpoint': '/',
        'route': '/apispec.json',
    }],
    'info': {
        'title': 'The PaKeT Server API',
        'version': VERSION,
        'contact': {
            'name': 'The PaKeT Project',
            'email': 'israel@paket.global',
            'url': 'https://api.paket.global',
        },
        'license': {
            'name': 'GNU GPL 3.0',
            'url': 'http://www.gnu.org/licenses/'
        },
        'description': '''
Web API Server for The PaKeT Project

What is this?
=============
This page is used as both documentation of our server API and as a sandbox to
test interaction with it. You can use this page to call the RESTful API while
specifying any required or optional parameter. The page also presents curl
commands that can be used to call the server.

Our Server
==========
We run a centralized server that can be used to interact with PaKeT's bottom
layers. Since Layer one is completely implemented on top of the Stellar
network, it can be interacted with directly in a fully decentralized fashion.
We created this server only as a gateway to the bottom layers to simplify the
interaction with them.

Security
========
Our calls are split into the following security levels:
 - Debug functions: require no authentication, available only in debug mode.
 - Anonymous functions: require no authentication.
 - Authenticated functions: require asymmetric key authentication. Not tested in debug mode.
    - The 'Pubkey' header will contain the user's pubkey.
    - The 'Fingerprint' header is constructed from the comma separated
      concatenation of the called URI, all the arguments (as key=value), and an
      ever increasing nonce (recommended to use Unix time in milliseconds).
    - The 'Signature' header will contain the signature of the key specified in
      the 'Pubkey' header on the fingerprint specified in the 'Fingerprint'
      header, encoded to Base64 ASCII.

Walkthrough
===========
The following steps demonstrate the main functionality of the API. This requires you to have a Stellar compatible ed25519 keypair with a matching funded Stellar account.  The Stellar account creator is your friend: https://www.stellar.org/laboratory/#account-creator

- Check your account by calling /bul_account - you should get a 409 error saying that the account does not trust BULs.
- Extend trust in BULs from your account by calling /prepare_trust, signing the returned XDR with your private key and submitting it to /submit_transaction.
- Check your account by calling /bul_account - you should now get a BUL balance of 0.
- Transfer some BULs into your accounts. In debug mode, you can call /fund_from_issuer.
- Check your account by calling /bul_account - make sure your balance reflects the transfer.
- Create three new accounts, a courier account, a recipient account, and an
escrow account. Repeat the following steps to create each account
    - Generate a keypair.
    - Call /prepare_create_account from your original (funded) account with the
    new pubkey given as argument, sign the returned transaction, and submit it
    to /submit_transaction.
    - Optionally, check the new account by calling /bul_account - you should get a 409 error saying that the account does not trust BULs.
    - Call /prepare_trust from the new account, sign the returned transaction, and submit it to /submit_transaction.
    - Optionally, call /bul_account and verify your BUL balance is now 0.
- Transfer some BULs to the courier account, either by calling
/fund_from_issuer or by calling /prepare_send_buls from your original account,
signing it, and submitting it to /submit_transaction.
- From your original account, which will be the launcher account, call
/prepare_escrow. Make sure that the payment is not larger than
your BUL balance, and that the collateral is not larger than the BUL balance of
the courier.
- As the escrow account, submit the set options transaction to
/submit_transaction.
- Call /get_bul_account on the escrow account and verify that the signers are
properly set.
- Make note of the BUL balances of the launcher and the courier by calling
/get_bul_account on both.
- Transfer the payment from the launcher to the escrow by calling
/prepare_send_buls, signing the transaction, and submitting it to
/submit_transaction from your launcher account.
- Transfer the collateral from the courier to the escrow by calling
/prepare_send_buls, signing the transaction, and submitting it to
/submit_transaction from the courier account.
- Make note of the BUL balances of the launcher and the courier by calling
/get_bul_account on both.
- Either approve the package receipt by signing the payment transaction and
submitting it to /submit_transaction as the recipient, or wait for the deadline
to pass and submit the refund_transaction to /submit_transaction as the
launcher.
- Optionally, submit the merge account transaction to /submit_transaction for
the launcher to reclaim any unspent XLM that were spent creating the escrow
account.
- Make note of the BUL balances of the launcher and the courier (and,
optionally, the launcher's XLM balance) by calling /get_bul_account on both.

The API
=======
        '''
    }
}

SUBMIT_TRANSACTION = {
    'tags': ['wallet'],
    'parameters': [
        {
            'name': 'transaction', 'description': 'transaction to submit',
            'in': 'formData', 'required': True, 'type': 'string'
        }
    ],
    'responses': {
        '200': {'description': 'horizon response'}
    }
}

BUL_ACCOUNT = {
    'tags': ['wallet'],
    'parameters': [
        {
            'name': 'queried_pubkey', 'description': 'pubkey of the account',
            'in': 'query', 'required': True, 'type': 'string'
        }
    ],
    'responses': {
        '200': {'description': 'account details'}
    }
}

PREPARE_CREATE_ACCOUNT = {
    'tags': ['wallet'],
    'parameters': [
        {
            'name': 'from_pubkey', 'description': 'creating pubkey (must have a funded account)',
            'in': 'query', 'required': True, 'type': 'string'
        },
        {
            'name': 'new_pubkey', 'description': 'pubkey of account to be created',
            'in': 'query', 'required': True, 'type': 'string'
        },
        {
            'name': 'starting_balance', 'description': 'amount of XLM to transfer from creating account',
            'in': 'query', 'required': False, 'type': 'integer'
        }
    ],
    'responses': {
        '201': {'description': 'unsigned account creation transaction'}
    }
}

PREPARE_TRUST = {
    'tags': ['wallet'],
    'parameters': [
        {
            'name': 'from_pubkey', 'description': 'pubkey that wants to add trust in our token',
            'in': 'query', 'required': True, 'type': 'string'
        }
    ],
    'responses': {
        '201': {'description': 'unsigned add trust transaction'}
    }
}

PREPARE_SEND_BULS = {
    'tags': ['wallet'],
    'parameters': [
        {
            'name': 'from_pubkey', 'description': 'target pubkey for transfer',
            'in': 'query', 'required': True, 'type': 'string'
        },
        {
            'name': 'to_pubkey', 'description': 'target pubkey for transfer',
            'in': 'query', 'required': True, 'type': 'string'
        },
        {
            'name': 'amount_buls', 'description': 'amount to transfer',
            'in': 'query', 'required': True, 'type': 'integer'
        }
    ],
    'responses': {
        '200': {'description': 'unsigned BUL transfer transaction'}
    }
}

PREPARE_ESCROW = {
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
            'name': 'courier_pubkey', 'description': 'courier pubkey',
            'in': 'formData', 'required': True, 'type': 'string'},
        {
            'name': 'recipient_pubkey', 'description': 'recipient pubkey',
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
    ],
    'responses': {
        '201': {
            'description': 'escrow transactions',
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
            'name': 'paket_id', 'description': 'PKT id (the escrow pubkey)',
            'in': 'formData', 'required': True, 'type': 'string',
        }
    ],
    'responses': {
        '200': {
            'description': 'package custodianship changed'
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
            'name': 'paket_id', 'description': 'PKT id (the escrow pubkey)',
            'in': 'query', 'required': True, 'type': 'string',
        }
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
                'paket_user': {
                    'type': 'string'
                },
                'GPS': {
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
                'custodian-id': {
                    'type': 'string'
                },
                'deadline-timestamp': {
                    'type': 'integer'
                },
                'my-role': {
                    'type': 'string'
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

FUND_FROM_ISSUER = {
    'tags': ['debug'],
    'parameters': [
        {
            'name': 'funded_pubkey', 'description': 'pubkey of account to be funded',
            'in': 'formData', 'required': True, 'type': 'string'},
        {
            'name': 'funded_buls', 'description': 'amount of BULs to fund the account',
            'in': 'formData', 'required': False, 'type': 'integer'},
    ],
    'responses': {
        '200': {'description': 'funding successful'}
    }
}

USERS = {
    'tags': ['debug'],
    'responses': {
        '200': {'description': 'a list of users'}
    }
}

PACKAGES = {
    'tags': ['debug'],
    'responses': {
        '200': {'description': 'a list of packages'}
    }
}
