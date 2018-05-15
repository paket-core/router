"""Test the PaKeT API."""
import json
import os
import unittest

# pylint: disable=import-error
import logger
# pylint: enable=import-error
import webserver.validation

import api
import db
import paket

db.DB_NAME = 'test.db'
webserver.validation.NONCES_DB_NAME = 'nonce_test.db'
LOGGER = logger.logging.getLogger('pkt.api.test')
logger.setup()
APP = webserver.setup(api.BLUEPRINT)
APP.testing = True


class TestAPI(unittest.TestCase):
    """Test our API."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.app = APP.test_client()
        self.host = 'http://localhost'
        self.funded_account = paket.get_keypair(seed='SDJGBJZMQ7Z4W3KMSMO2HYEV56DJPOZ7XRR7LJ5X2KW6VKBSLELR7MRQ')

        self.launcher = paket.get_keypair()
        self.courier = paket.get_keypair()
        self.recipient = paket.get_keypair()

    def setUp(self):
        try:
            os.unlink(db.DB_NAME)
        except FileNotFoundError:
            pass
        try:
            os.unlink(webserver.validation.NONCES_DB_NAME)
        except FileNotFoundError:
            pass

    def tearDown(self):
        self.setUp()

    def call(self, path, expected_code=None, fail_message=None, seed=None, **kwargs):
        """Post data to API server."""
        if seed:
            fingerprint = webserver.validation.generate_fingerprint(
                "{}/v{}/{}".format(self.host, api.VERSION, path), kwargs)
            signature = webserver.validation.sign_fingerprint(fingerprint, seed)
            headers = {
                'Pubkey': paket.get_keypair(seed=seed).address().decode(),
                'Fingerprint': fingerprint, 'Signature': signature}
        else:
            headers = None
        response = self.app.post("/v{}/{}".format(api.VERSION, path), headers=headers, data=kwargs)
        response = dict(real_status_code=response.status_code, **json.loads(response.data.decode()))
        if expected_code:
            self.assertEqual(response['real_status_code'], expected_code, "{} ({})".format(
                fail_message, response.get('error')))
        return response

    def test_fresh_db(self):
        """Make sure packages table exists and is empty."""
        db.init_db()
        self.assertEqual(db.get_packages(), [], 'packages found in fresh db')

    def inner_test_no_exist(self):
        """Check a non existing account."""
        keypair = paket.get_keypair()
        pubkey = keypair.address().decode()
        response = self.call('bul_account', 409, 'could not verify account does not exist', queried_pubkey=pubkey)
        self.assertEqual(response['error'], "no account found for {}".format(pubkey))
        return keypair, pubkey

    def inner_test_create(self):
        """Create a new account."""
        keypair, pubkey = self.inner_test_no_exist()
        unsigned = self.call(
            'prepare_create_account', 200, 'could not get create account transaction',
            from_pubkey=self.funded_account.address().decode(), new_pubkey=pubkey)['transaction']
        builder = paket.stellar_base.builder.Builder(horizon=paket.HORIZON, secret=self.funded_account.seed())
        builder.import_from_xdr(unsigned)
        builder.sign()
        self.call(
            'submit_transaction', 200, 'could not submit create transaction',
            transaction=builder.gen_te().xdr().decode())
        response = self.call('bul_account', 409, 'could not verify account does not trust', queried_pubkey=pubkey)
        self.assertEqual(response['error'], "account {} does not trust {} from {}".format(
            pubkey, paket.BUL_TOKEN_CODE, paket.ISSUER))
        return keypair, pubkey

    def test_trust(self):
        """Extend trust."""
        keypair, pubkey = self.inner_test_create()
        seed = keypair.seed().decode()
        unsigned = self.call('prepare_trust', 200, 'could not get trust transaction', from_pubkey=pubkey)['transaction']
        builder = paket.stellar_base.builder.Builder(horizon=paket.HORIZON, secret=seed)
        builder.import_from_xdr(unsigned)
        builder.sign()
        self.call(
            'submit_transaction', 200, 'could not submit trust transaction',
            transaction=builder.gen_te().xdr().decode())
        response = self.call('bul_account', 200, 'could not get bul account after trust', queried_pubkey=pubkey)
        self.assertEqual(response['BUL balance'], 0)
        print(keypair)
        return keypair, pubkey, seed
