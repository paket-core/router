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
/prepare_escrow_transactions. Make sure that the payment is not larger than
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
    'tags': [
        'wallet'
    ],
    'parameters': [
        {
            'name': 'transaction',
            'in': 'formData',
            'description': 'Transaction to submit',
            'required': True,
            'type': 'string',
        }
    ],
    'responses': {
        '200': {
            'description': 'success'
        }
    }
}

BUL_ACCOUNT = {
    'tags': [
        'wallet'
    ],
    'parameters': [
        {
            'name': 'queried_pubkey',
            'in': 'query',
            'schema': {
                'type': 'string',
                'format': 'string'
            }
        }
    ],
    'responses': {
        '200': {
            'description': 'balance in BULs',
            'schema': {
                'properties': {
                    'available_buls': {
                        'type': 'integer',
                        'format': 'int32',
                        'minimum': 0,
                        'description': 'funds available for usage in buls'
                    }
                }
            }
        }
    }
}

SEND_BULS = {
    'tags': [
        'wallet'
    ],
    'parameters': [
        {
            'name': 'Pubkey',
            'required': True,
            'in': 'header',
            'schema': {
                'type': 'string',
                'format': 'string'
            }
        },
        {
            'name': 'Fingerprint',
            'required': True,
            'in': 'header',
            'schema': {
                'type': 'string',
                'format': 'string'
            }
        },
        {
            'name': 'Signature',
            'required': True,
            'in': 'header',
            'schema': {
                'type': 'string',
                'format': 'string'
            }
        },
        {
            'name': 'to_pubkey',
            'in': 'formData',
            'description': 'target pubkey for transfer',
            'required': True,
            'type': 'string'
        },
        {
            'name': 'amount_buls',
            'in': 'formData',
            'description': 'amount to transfer',
            'required': True,
            'type': 'integer'
        }
    ],
    'responses': {
        '200': {
            'description': 'transfer request sent'
        }
    }
}

PREPARE_SEND_BULS = {
    'tags': [
        'wallet'
    ],
    'parameters': [
        {
            'name': 'from_pubkey',
            'in': 'query',
            'description': 'target pubkey for transfer',
            'required': True,
            'type': 'string'
        },
        {
            'name': 'to_pubkey',
            'in': 'query',
            'description': 'target pubkey for transfer',
            'required': True,
            'type': 'string'
        },
        {
            'name': 'amount_buls',
            'in': 'query',
            'description': 'amount to transfer',
            'required': True,
            'type': 'integer'
        }
    ],
    'responses': {
        '200': {
            'description': 'transfer request sent'
        }
    }
}

PRICE = {
    'tags': [
        'wallet'
    ],
    'responses': {
        '200': {
            'description': 'buy and sell prices',
            'schema': {
                'properties': {
                    'buy_price': {
                        'type': 'integer',
                        'format': 'int32',
                        'minimum': 0,
                        'description': 'price for which a BUL may me purchased'
                    },
                    'sell_price': {
                        'type': 'integer',
                        'format': 'int32',
                        'minimum': 0,
                        'description': 'price for which a BUL may me sold'
                    }
                }
            }
        }
    }
}

LAUNCH_PACKAGE = {
    'tags': [
        'packages'
    ],
    'parameters': [
        {
            'name': 'Pubkey',
            'required': True,
            'in': 'header',
            'schema': {
                'type': 'string',
                'format': 'string'
            }
        },
        {
            'name': 'Fingerprint',
            'required': True,
            'in': 'header',
            'schema': {
                'type': 'string',
                'format': 'string'
            }
        },
        {
            'name': 'Signature',
            'required': True,
            'in': 'header',
            'schema': {
                'type': 'string',
                'format': 'string'
            }
        },
        {
            'name': 'recipient_pubkey',
            'in': 'formData',
            'description': 'Recipient pubkey',
            'required': True,
            'type': 'string'
        },
        {
            'name': 'courier_pubkey',
            'in': 'formData',
            'description': 'Courier pubkey (can be id for now)',
            'required': True,
            'type': 'string'
        },
        {
            'name': 'deadline_timestamp',
            'in': 'formData',
            'description': 'Deadline timestamp',
            'required': True,
            'type': 'integer',
            'example': 1520948634
        },
        {
            'name': 'payment_buls',
            'in': 'formData',
            'description': 'BULs promised as payment',
            'required': True,
            'type': 'integer'
        },
        {
            'name': 'collateral_buls',
            'in': 'formData',
            'description': 'BULs required as collateral',
            'required': True,
            'type': 'integer'
        }
    ],
    'responses': {
        '200': {
            'description': 'Package launched',
            'content': {
                'schema': {
                    'type': 'string',
                    'example': 'PKT-12345'
                },
                'example': {
                    'PKT-id': 1001
                }
            }
        }
    }
}

ACCEPT_PACKAGE = {
    'tags': [
        'packages'
    ],
    'parameters': [
        {
            'name': 'Pubkey',
            'required': True,
            'in': 'header',
            'schema': {
                'type': 'string',
                'format': 'string'
            }
        },
        {
            'name': 'Fingerprint',
            'required': True,
            'in': 'header',
            'schema': {
                'type': 'string',
                'format': 'string'
            }
        },
        {
            'name': 'Signature',
            'required': True,
            'in': 'header',
            'schema': {
                'type': 'string',
                'format': 'string'
            }
        },
        {
            'name': 'paket_id',
            'in': 'formData',
            'description': 'PKT id',
            'required': True,
            'type': 'string',
        },
        {
            'name': 'payment_transaction',
            'in': 'formData',
            'description': 'Payment transaction of a previously launched package, required only if confirming receipt',
            'required': False,
            'type': 'string',
        }
    ],
    'responses': {
        '200': {
            'description': 'Package accept requested'
        }
    }
}

RELAY_PACKAGE = {
    'tags': [
        'packages'
    ],
    'parameters': [
        {
            'name': 'Pubkey',
            'required': True,
            'in': 'header',
            'schema': {
                'type': 'string',
                'format': 'string'
            }
        },
        {
            'name': 'Fingerprint',
            'required': True,
            'in': 'header',
            'schema': {
                'type': 'string',
                'format': 'string'
            }
        },
        {
            'name': 'Signature',
            'required': True,
            'in': 'header',
            'schema': {
                'type': 'string',
                'format': 'string'
            }
        },
        {
            'name': 'paket_id',
            'in': 'formData',
            'description': 'PKT id',
            'required': True,
            'type': 'string',
        },
        {
            'name': 'courier_pubkey',
            'in': 'formData',
            'description': 'Courier pubkey',
            'required': True,
            'type': 'string'
        },
        {
            'name': 'payment_buls',
            'in': 'formData',
            'description': 'BULs promised as payment',
            'required': True,
            'type': 'integer'
        }
    ],
    'responses': {
        '200': {
            'description': 'Package launched',
            'content': {
                'schema': {
                    'type': 'string',
                    'example': 'PKT-12345'
                },
                'example': {
                    'PKT-id': 1001
                }
            }
        }
    }
}

REFUND_PACKAGE = {
    'tags': [
        'packages'
    ],
    'parameters': [
        {
            'name': 'Pubkey',
            'required': True,
            'in': 'header',
            'schema': {
                'type': 'string',
                'format': 'string'
            }
        },
        {
            'name': 'Fingerprint',
            'required': True,
            'in': 'header',
            'schema': {
                'type': 'string',
                'format': 'string'
            }
        },
        {
            'name': 'Signature',
            'required': True,
            'in': 'header',
            'schema': {
                'type': 'string',
                'format': 'string'
            }
        },
        {
            'name': 'paket_id',
            'in': 'formData',
            'description': 'PKT id',
            'required': True,
            'type': 'string',
        },
        {
            'name': 'refund_transaction',
            'in': 'formData',
            'description': 'Refund transaction of a previously launched package',
            'required': True,
            'type': 'string',
        }
    ],
    'responses': {
        '200': {
            'description': 'Package launched',
            'content': {
                'schema': {
                    'type': 'string',
                    'example': 'PKT-12345'
                },
                'example': {
                    'PKT-id': 1001
                }
            }
        }
    }
}

MY_PACKAGES = {
    'tags': [
        'packages'
    ],
    'parameters': [
        {
            'name': 'Pubkey',
            'required': True,
            'in': 'header',
            'schema': {
                'type': 'string',
                'format': 'string'
            }
        },
        {
            'name': 'Fingerprint',
            'required': True,
            'in': 'header',
            'schema': {
                'type': 'string',
                'format': 'string'
            }
        },
        {
            'name': 'Signature',
            'required': True,
            'in': 'header',
            'schema': {
                'type': 'string',
                'format': 'string'
            }
        },
        {
            'name': 'show_inactive',
            'in': 'query',
            'description': 'include inactive packages in response',
            'required': False,
            'type': 'boolean',
        },
        {
            'name': 'from_date',
            'in': 'query',
            'description': 'show only packages from this date forward',
            'required': False,
            'type': 'string'
        }
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
    'tags': [
        'packages'
    ],
    'parameters': [
        {
            'name': 'paket_id',
            'in': 'query',
            'description': 'PKT id',
            'required': True,
            'type': 'string',
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

REGISTER_USER = {
    'tags': [
        'users'
    ],
    'parameters': [
        {
            'name': 'Pubkey',
            'required': True,
            'in': 'header',
            'schema': {
                'type': 'string',
                'format': 'string'
            }
        },
        {
            'name': 'Fingerprint',
            'required': True,
            'in': 'header',
            'schema': {
                'type': 'string',
                'format': 'string'
            }
        },
        {
            'name': 'Signature',
            'required': True,
            'in': 'header',
            'schema': {
                'type': 'string',
                'format': 'string'
            }
        },
        {
            'name': 'paket_user',
            'in': 'formData',
            'description': 'User unique callsign',
            'required': True,
            'type': 'string'
        },
        {
            'name': 'full_name',
            'in': 'formData',
            'description': 'Full name of user',
            'required': True,
            'type': 'string'
        },
        {
            'name': 'phone_number',
            'in': 'formData',
            'description': 'User phone number',
            'required': True,
            'type': 'string'
        }
    ],
    'responses': {
        '201': {
            'description': 'user details registered.'
        }
    }
}

RECOVER_USER = {
    'tags': [
        'users'
    ],
    'parameters': [
        {
            'name': 'Pubkey',
            'required': True,
            'in': 'header',
            'schema': {
                'type': 'string',
                'format': 'string'
            }
        },
        {
            'name': 'Fingerprint',
            'required': True,
            'in': 'header',
            'schema': {
                'type': 'string',
                'format': 'string'
            }
        },
        {
            'name': 'Signature',
            'required': True,
            'in': 'header',
            'schema': {
                'type': 'string',
                'format': 'string'
            }
        }
    ],
    'responses': {
        '200': {
            'description': 'user details retrieved.'
        }
    }
}

FUND = {
    'tags': [
        'debug'
    ],
    'parameters': [
        {
            'name': 'Pubkey',
            'required': True,
            'in': 'header',
            'schema': {
                'type': 'string',
                'format': 'string'
            }
        },
    ],
    'responses': {
        '200': {
            'description': 'funding successful',
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

USERS = {
    'tags': [
        'debug'
    ],
    'responses': {
        '200': {
            'description': 'a list of users',
            'schema': {
                'properties': {
                    'available_buls': {
                        'type': 'integer',
                        'format': 'int32',
                        'minimum': 0,
                        'description': 'funds available for usage in buls'
                    }
                }
            }
        }
    }
}

PACKAGES = {
    'tags': [
        'debug'
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
