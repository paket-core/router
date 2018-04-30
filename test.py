"""Test the PaKeT API."""
import json
import os
import unittest

import api.server
import api.routes
import db
import logger
import paket

USE_HORIZON = bool(os.environ.get('PAKET_TEST_USE_HORIZON'))
db.DB_NAME = 'test.db'
LOGGER = logger.logging.getLogger('pkt.api.test')
logger.setup()


class MockPaket:
    """Mock paket package."""

    def __init__(self):
        self.balances = {}

    def __getattr__(self, name):
        """Inherit all paket attributes that are not overwritten."""
        return getattr(paket, name)

    def new_account(self, pubkey):
        """Create a new account."""
        if pubkey in self.balances:
            raise paket.StellarTransactionFailed('account exists')
        self.balances[pubkey] = 0.0

    def trust(self, keypair):
        """Trust an account."""
        if keypair.address().decode() not in self.balances:
            raise paket.StellarTransactionFailed('account does not exists')

    def get_bul_account(self, pubkey):
        """Get account details of pubkey."""
        return {'balance': self.balances[pubkey]}

    def send_buls(self, from_pubkey, to_pubkey, amount):
        """Get account details of pubkey."""
        if from_pubkey != paket.ISSUER.address().decode():
            if self.balances[from_pubkey] < amount:
                raise paket.StellarTransactionFailed('insufficient funds')
            self.balances[from_pubkey] -= amount
        self.balances[to_pubkey] += amount


if not USE_HORIZON:
    api.server.paket = api.routes.paket = MockPaket()


class TestAPI(unittest.TestCase):
    """Test our API."""

    def setUp(self):
        try:
            os.unlink(db.DB_NAME)
        except FileNotFoundError:
            pass
        api.server.APP.testing = True
        self.app = api.server.APP.test_client()
        with api.server.APP.app_context():
            db.init_db()

    def tearDown(self):
        os.unlink(db.DB_NAME)

    def call(self, call_type, path, expected_code=None, fail_message=None, pubkey=None, **kwargs):
        """Post data to API server."""
        if call_type == 'post':
            call_func = self.app.post
        elif call_type == 'get':
            call_func = self.app.get
        if pubkey:
            headers = {'Pubkey': pubkey, 'Fingerprint': '', 'Signature': ''}
        else:
            headers = None
        response = call_func("/v{}/{}".format(api.routes.VERSION, path), headers=headers, data=kwargs)
        response = dict(status_code=response.status_code, **json.loads(response.data.decode()))
        if expected_code:
            self.assertEqual(response['status_code'], expected_code, "{} ({})".format(
                fail_message, response.get('error')))
        return response

    def test_fresh_db(self):
        """Make sure packages table exists and is empty."""
        self.assertEqual(db.get_packages(), [], 'packages found in empty db')
        self.assertEqual(db.get_users(), {}, 'users found in empty db')

    def test_register(self):
        """Register a new user and recover it."""
        phone_number = str(os.urandom(8))
        self.call(
            'post', 'register_user', 201, 'user creation failed', pubkey='stam',
            full_name='First Last', phone_number=phone_number, paket_user='stam')
        self.assertEqual(
            self.call('post', 'recover_user', 200, 'can not recover user', 'stam')['user_details']['phone_number'],
            phone_number, 'user phone_number does not match')

    def test_send_buls(self):
        """Send BULs and check balance."""
        api.server.init_sandbox(True, False, False)
        self.test_register()

        start_balance = self.call('get', 'bul_account', 200, 'can not get balance', queried_pubkey='stam')['balance']
        amount = 123
        self.call('post', 'send_buls', 201, 'can not send buls', 'ISSUER', to_pubkey='stam', amount_buls=amount)
        end_balance = self.call('get', 'bul_account', 200, 'can not get balance', queried_pubkey='stam')['balance']
        self.assertEqual(end_balance - start_balance, amount, 'balance does not add up after send')

    def test_two_stage_send_buls(self):
        """Send BULs and check balance without holding private keys in the server."""
        if not USE_HORIZON:
            return LOGGER.error('not running two stage test with mock paket')
        api.server.init_sandbox(True, False, False)
        source = db.get_user(db.get_pubkey_from_paket_user('ISSUER'))
        target = db.get_user(db.get_pubkey_from_paket_user('RECIPIENT'))
        start_balance = self.call(
            'get', 'bul_account', 200, 'can not get balance', queried_pubkey=target['pubkey'])['balance']
        amount = 123
        unsigned_tx = self.call(
            'get', 'prepare_send_buls', 200, 'can not prepare send', from_pubkey=source['pubkey'],
            to_pubkey=target['pubkey'], amount_buls=amount)['transaction']
        builder = paket.stellar_base.builder.Builder(horizon=paket.HORIZON, secret=source['seed'])
        builder.import_from_xdr(unsigned_tx)
        builder.sign()
        signed_tx = builder.gen_te().xdr().decode()
        self.call(
            'post', 'submit_transaction', 200, 'submit transaction failed',
            source['pubkey'], transaction=signed_tx)
        end_balance = self.call(
            'get', 'bul_account', 200, 'can not get balance', queried_pubkey=target['pubkey'])['balance']
        return self.assertEqual(end_balance - start_balance, amount, 'balance does not add up after send')
