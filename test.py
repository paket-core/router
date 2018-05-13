"""Test the PaKeT API."""
import json
import os
import pprint
import unittest

import webserver.validation

import api
import db
import logger
import paket

db.DB_NAME = 'test.db'
webserver.validation.NONCES_DB_NAME = 'nonce_test.db'
LOGGER = logger.logging.getLogger('pkt.api.test')
logger.setup()
APP = webserver.setup(api.BLUEPRINT)


class TestAPI(unittest.TestCase):
    """Test our API."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.issuer = api.paket.ISSUER
        self.issuer_seed = 'SC2PO5YMP7VISFX75OH2DWETTEZ4HVZOECMDXOZIP3NBU3OFISSQXAEP'
        self.keypair = paket.get_keypair()
        self.pubkey = self.keypair.address().decode()
        self.seed = self.keypair.seed().decode()
        self.host = 'http://localhost'

    def setUp(self):
        try:
            os.unlink(db.DB_NAME)
            os.unlink(webserver.validation.NONCES_DB_NAME)
        except FileNotFoundError:
            pass
        api.init_sandbox()
        APP.testing = True
        self.app = APP.test_client()
        with APP.app_context():
            db.init_db()

    def tearDown(self):
        os.unlink(db.DB_NAME)
        os.unlink(webserver.validation.NONCES_DB_NAME)

    def call(self, path, expected_code=None, fail_message=None, auth=False, **kwargs):
        """Post data to API server."""
        if auth:
            fingerprint = webserver.validation.generate_fingerprint(
                "{}/v{}/{}".format(self.host, api.VERSION, path), kwargs)
            signature = webserver.validation.sign_fingerprint(fingerprint, self.seed)
            LOGGER.info(fingerprint)
            headers = {'Pubkey': self.pubkey, 'Fingerprint': fingerprint, 'Signature': signature}
        else:
            headers = None
        response = self.app.post("/v{}/{}".format(api.VERSION, path), headers=headers, data=kwargs)
        response = dict(status_code=response.status_code, **json.loads(response.data.decode()))
        if expected_code:
            self.assertEqual(response['status_code'], expected_code, "{} ({})".format(
                fail_message, response.get('error')))
        return response

    def test_fresh_db(self):
        """Make sure packages table exists and is empty."""
        self.assertEqual(db.get_packages(), [], 'packages found in fresh db')
        self.assertEqual(len(db.get_users().keys()), 4, 'too many users found in fresh db')

    def test_create(self):
        """Create a new account."""
        with self.assertRaises(KeyError):
            self.call('bul_account', 409, 'could not verify account does not exist', queried_pubkey=self.pubkey)
        unsigned = api.paket.prepare_create_account(self.issuer, self.pubkey)
            self.call('prepare_create_account', 409, 'could not verify account does not exist', queried_pubkey=self.pubkey)
        builder = api.paket.stellar_base.builder.Builder(horizon=api.paket.HORIZON, secret=self.issuer_seed)
        builder.import_from_xdr(unsigned)
        builder.sign()
        api.paket.submit(builder)
        self.assertEqual(api.paket.get_bul_account(self.pubkey, True)['BUL balance'], False)

    def test_trust(self):
        """Extend trust."""
        self.test_create()
        with self.assertRaises(api.paket.MissingTrust):
            api.paket.get_bul_account(self.pubkey)
        unsigned = api.paket.prepare_trust(self.pubkey)
        builder = api.paket.stellar_base.builder.Builder(horizon=api.paket.HORIZON, secret=self.seed)
        builder.import_from_xdr(unsigned)
        builder.sign()
        api.paket.submit(builder)

    def test_register(self):
        """Register a new user and recover it."""
        phone_number = str(os.urandom(8))
        #except paket.StellarTransactionFailed:
        #    pass
        #self.call(
        #    'register_user', 201, 'user creation failed', pubkey=self.pubkey,
        #    full_name='First Last', phone_number=phone_number, paket_user='stam')
        #LOGGER.info(
        #    "new user account: %s",
        #    self.call('bul_account', 200, 'can not get balance', queried_pubkey=self.pubkey)['balance'])
        #self.assertEqual(
        #    self.call(
        #        'recover_user', 200, 'can not recover user', self.pubkey
        #    )['user_details']['phone_number'],
        #    phone_number, 'user phone_number does not match')

    def test_send_buls(self):
        """Send BULs and check balance."""
        self.test_register()
        start_balance = self.call(
            'bul_account', 200, 'can not get balance', queried_pubkey=self.pubkey)['balance']
        amount = 123
        self.call(
            'send_buls', 201, 'can not send buls', paket.ISSUER.address().decode(), paket.ISSUER.seed().decode(),
            to_pubkey=self.pubkey, amount_buls=amount)
        end_balance = self.call(
            'bul_account', 200, 'can not get balance', queried_pubkey=self.pubkey)['balance']
        self.assertEqual(end_balance - start_balance, amount, 'balance does not add up after send')

    def test_two_stage_send_buls(self):
        """Send BULs and check balance without holding private keys in the server."""
        if not USE_HORIZON:
            return LOGGER.error('not running two stage test with mock paket')
        source = db.get_user(db.get_pubkey_from_paket_user('ISSUER'))
        target = db.get_user(db.get_pubkey_from_paket_user('RECIPIENT'))
        start_balance = self.call(
            'bul_account', 200, 'can not get balance', queried_pubkey=target['pubkey'])['balance']
        amount = 123
        unsigned_tx = self.call(
            'prepare_send_buls', 200, 'can not prepare send', from_pubkey=source['pubkey'],
            to_pubkey=target['pubkey'], amount_buls=amount)['transaction']
        builder = paket.stellar_base.builder.Builder(horizon=paket.HORIZON, secret=source['seed'])
        builder.import_from_xdr(unsigned_tx)
        builder.sign()
        signed_tx = builder.gen_te().xdr().decode()
        self.call(
            'submit_transaction', 200, 'submit transaction failed',
            source['pubkey'], transaction=signed_tx)
        end_balance = self.call(
            'bul_account', 200, 'can not get balance', queried_pubkey=target['pubkey'])['balance']
        return self.assertEqual(end_balance - start_balance, amount, 'balance does not add up after send')
