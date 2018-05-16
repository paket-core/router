"""Test the PaKeT API."""
import json
import os
import time
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
        self.funded_seed = 'SDJGBJZMQ7Z4W3KMSMO2HYEV56DJPOZ7XRR7LJ5X2KW6VKBSLELR7MRQ'
        self.funded_account = paket.get_keypair(seed=self.funded_seed)
        self.funded_pubkey = self.funded_account.address().decode()
        LOGGER.info('init done')

    def setUp(self):
        LOGGER.info('setting up')
        try:
            os.unlink(db.DB_NAME)
        except FileNotFoundError:
            pass
        try:
            os.unlink(webserver.validation.NONCES_DB_NAME)
        except FileNotFoundError:
            pass

    def tearDown(self):
        LOGGER.info('tearing down')
        self.setUp()

    def call(self, path, expected_code=None, fail_message=None, seed=None, **kwargs):
        """Post data to API server."""
        LOGGER.info("calling %s", path)
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

    def submit(self, transaction, seed=None, error='error submitting transaction'):
        """Submit a transaction, optionally adding seed's signature."""
        if seed:
            builder = paket.stellar_base.builder.Builder(horizon=paket.HORIZON, secret=seed)
            builder.import_from_xdr(transaction)
            builder.sign()
            transaction = builder.gen_te().xdr().decode()
        return self.call('submit_transaction', 200, error, transaction=transaction)

    def test_fresh_db(self):
        """Make sure packages table exists and is empty."""
        LOGGER.info('testing fresh db')
        db.init_db()
        self.assertEqual(db.get_packages(), [], 'packages found in fresh db')

    def inner_test_no_exist(self):
        """Check a non existing account."""
        keypair = paket.get_keypair()
        LOGGER.info("testing %s does not exist", keypair)
        pubkey = keypair.address().decode()
        response = self.call('bul_account', 409, 'could not verify account does not exist', queried_pubkey=pubkey)
        self.assertEqual(response['error'], "no account found for {}".format(pubkey))
        return keypair, pubkey

    def inner_test_create(self):
        """Create a new account."""
        keypair, pubkey = self.inner_test_no_exist()
        LOGGER.info("testing creation of %s", keypair)
        unsigned = self.call(
            'prepare_create_account', 200, 'could not get create account transaction',
            from_pubkey=self.funded_pubkey, new_pubkey=pubkey)['transaction']
        self.submit(unsigned, self.funded_seed, 'failed submitting create transaction')
        response = self.call('bul_account', 409, 'could not verify account does not trust', queried_pubkey=pubkey)
        self.assertEqual(response['error'], "account {} does not trust {} from {}".format(
            pubkey, paket.BUL_TOKEN_CODE, paket.ISSUER))
        return keypair, pubkey

    def inner_test_trust(self):
        """Extend trust."""
        keypair, pubkey = self.inner_test_create()
        LOGGER.info("testing trust for %s", keypair)
        seed = keypair.seed().decode()
        unsigned = self.call('prepare_trust', 200, 'could not get trust transaction', from_pubkey=pubkey)['transaction']
        self.submit(unsigned, seed, 'failed submitting trust transaction')
        response = self.call('bul_account', 200, 'could not get bul account after trust', queried_pubkey=pubkey)
        self.assertEqual(response['BUL balance'], 0)
        return pubkey, seed

    def send(self, from_seed, to_pubkey, amount_buls):
        """Send BULs between accounts."""
        from_pubkey = paket.get_keypair(seed=from_seed).address().decode()
        LOGGER.info("sending %s from %s to %s", amount_buls, from_pubkey, to_pubkey)
        unsigned = self.call(
            'prepare_send_buls', 200, "can not prepare send from {} to {}".format(from_pubkey, to_pubkey),
            from_pubkey=from_pubkey, to_pubkey=to_pubkey, amount_buls=amount_buls)['transaction']
        self.submit(unsigned, from_seed, 'failed submitting send transaction')

    def test_send(self, amount_buls=10):
        """Send BULs between accounts."""
        pubkey, seed = self.inner_test_trust()
        source_start_balance = self.call(
            'bul_account', 200, 'can not get source account balance', queried_pubkey=self.funded_pubkey)['BUL balance']
        target_start_balance = self.call(
            'bul_account', 200, 'can not get target account balance', queried_pubkey=pubkey)['BUL balance']
        LOGGER.info("testing send from issuer to %s", pubkey)
        self.send(self.funded_seed, pubkey, amount_buls)
        source_end_balance = self.call(
            'bul_account', 200, 'can not get source account balance', queried_pubkey=self.funded_pubkey)['BUL balance']
        target_end_balance = self.call(
            'bul_account', 200, 'can not get target account balance', queried_pubkey=pubkey)['BUL balance']
        self.assertEqual(source_start_balance - source_end_balance, amount_buls, 'source balance does not add up')
        self.assertEqual(target_end_balance - target_start_balance, amount_buls, 'target balance does not add up')
        return pubkey, seed

    def test_package(self):
        """Launch a package with payment and collateral, accept by courier and then by recipient."""
        db.init_db()
        payment, collateral = 5, 10
        deadline = int(time.time())

        launcher_pubkey, launcher_seed = self.test_send(payment)
        courier_pubkey, courier_seed = self.test_send(collateral)
        recipient_pubkey, recipient_seed = self.inner_test_trust()
        escrow_pubkey, escrow_seed = self.inner_test_trust()

        LOGGER.info(
            "launching escrow: %s, launcher: %s, courier: %s, recipient: %s",
            escrow_pubkey, launcher_pubkey, courier_pubkey, recipient_pubkey)
        escrow_transactions = self.call(
            'prepare_escrow', 201, 'can not prepare escrow transactions', escrow_seed,
            launcher_pubkey=launcher_pubkey, courier_pubkey=courier_pubkey, recipient_pubkey=recipient_pubkey,
            payment_buls=payment, collateral_buls=collateral, deadline_timestamp=deadline)
        self.submit(escrow_transactions['set_options_transaction'], escrow_seed, 'failed submitting set opts')
        LOGGER.info(self.call(
            'bul_account', 200, 'can not get escrow account balance', queried_pubkey=escrow_pubkey))
        self.send(launcher_seed, escrow_pubkey, payment)
        self.send(courier_seed, escrow_pubkey, collateral)
        self.call(
            'accept_package', 200, 'courier could not accept package', courier_seed, escrow_pubkey=escrow_pubkey)
        self.submit(escrow_transactions['payment_transaction'], recipient_seed, 'failed submitting payment')
        self.call(
            'accept_package', 200, 'recipient could not accept package', recipient_seed, escrow_pubkey=escrow_pubkey)
        self.submit(escrow_transactions['merge_transaction'], None, 'failed submitting payment')
