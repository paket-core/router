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


class BaseOperations(unittest.TestCase):
    """Base class for PaKet tests that implements methods for posting data to API server."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.app = APP.test_client()
        self.host = 'http://localhost'
        self.funded_seed = 'SDJGBJZMQ7Z4W3KMSMO2HYEV56DJPOZ7XRR7LJ5X2KW6VKBSLELR7MRQ'
        self.funded_account = paket.get_keypair(seed=self.funded_seed)
        self.funded_pubkey = self.funded_account.address().decode()
        LOGGER.info('init done')

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

    def submit(self, transaction, seed=None, description='unknown'):
        """Submit a transaction, optionally adding seed's signature."""
        LOGGER.info("trying to submit %s transaction", description)
        if seed:
            builder = paket.stellar_base.builder.Builder(horizon=paket.HORIZON, secret=seed)
            builder.import_from_xdr(transaction)
            builder.sign()
            transaction = builder.gen_te().xdr().decode()
        return self.call(
            'submit_transaction', 200, "failed submitting {} transaction".format(description), transaction=transaction)

    def create_account(self, from_pubkey, new_pubkey, starting_balance=5, seed=None):
        """Create account with starting balance"""
        LOGGER.info('creating %s from %s', new_pubkey, from_pubkey)
        unsigned = self.call(
            'prepare_create_account', 200, 'could not get create account transaction',
            from_pubkey=from_pubkey, new_pubkey=new_pubkey, starting_balance=starting_balance)['transaction']
        response = self.submit(unsigned, seed, 'create account')
        return response

    def create_and_setup_new_account(self, amount_buls=None):
        """Create account. Add trust and send initial ammount of BULs (if specified)"""
        keypair = paket.get_keypair()
        pubkey = keypair.address().decode()
        seed = keypair.seed().decode()
        self.create_account(from_pubkey=self.funded_pubkey, new_pubkey=pubkey, seed=self.funded_seed)
        self.trust(pubkey, seed)
        if amount_buls is not None:
            self.send(from_seed=self.funded_seed, to_pubkey=pubkey, amount_buls=amount_buls)
        return pubkey, seed

    def trust(self, pubkey, seed=None):
        """Submit trust transaction for specified account"""
        LOGGER.info('adding trust for %s', pubkey)
        unsigned = self.call('prepare_trust', 200, 'could not get trust transaction', from_pubkey=pubkey)['transaction']
        return self.submit(unsigned, seed, 'add trust')

    def send(self, from_seed, to_pubkey, amount_buls):
        """Send BULs between accounts."""
        from_pubkey = paket.get_keypair(seed=from_seed).address().decode()
        description = "sending {} from {} to {}".format(amount_buls, from_pubkey, to_pubkey)
        LOGGER.info(description)
        unsigned = self.call(
            'prepare_send_buls', 200, "can not prepare send from {} to {}".format(from_pubkey, to_pubkey),
            from_pubkey=from_pubkey, to_pubkey=to_pubkey, amount_buls=amount_buls)['transaction']
        return self.submit(unsigned, from_seed, description)


class TestAccount(BaseOperations):
    """Account tests"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def test_no_exist(self):
        """Check no existing accounts"""
        keypair = paket.get_keypair()
        valid_pubkey = keypair.address().decode()
        data_set = [
            valid_pubkey,  # valid public key
            'GBNDWBDLL5UOD36KN3BOOKIQPCNIN3QRUO7RMN37WNBSFCPIKWJ',  # invalid public key
            'Lorem ipsum dolor sit amet',  # random text
            144  # random number
        ]
        for pubkey in data_set:
            with self.subTest(pubkey=pubkey):
                response = self.call('bul_account', 409,
                                     'could not verify account does not exist', queried_pubkey=pubkey)
                self.assertEqual(response['error'], "no account found for {}".format(pubkey))

    def test_exist(self):
        """Check existing accounts"""
        # TODO: need to add more existing accounts
        data_set = [
            self.funded_pubkey  # valid public key
        ]
        for pubkey in data_set:
            with self.subTest(pubkey=pubkey):
                self.call('bul_account', 200, 'could not verify account exist', queried_pubkey=pubkey)

    def test_create_account(self):
        """Create new account"""
        keypair = paket.get_keypair()
        pubkey = keypair.address().decode()
        LOGGER.info("testing creation of %s", keypair)
        response = self.create_account(from_pubkey=self.funded_pubkey, new_pubkey=pubkey, seed=self.funded_seed)
        self.assertEqual(response['response']['result_xdr'], 'AAAAAAAAAGQAAAAAAAAAAQAAAAAAAAAAAAAAAAAAAAA=')
        return keypair, pubkey

    def test_trust(self):
        """Extend trust."""
        keypair = paket.get_keypair()
        pubkey = keypair.address().decode()
        self.create_account(from_pubkey=self.funded_pubkey, new_pubkey=pubkey, seed=self.funded_seed)
        response = self.call('bul_account', 409, 'could not verify account does not trust', queried_pubkey=pubkey)
        self.assertEqual(response['error'], "account {} does not trust {} from {}".format(
            pubkey, paket.BUL_TOKEN_CODE, paket.ISSUER))
        LOGGER.info("testing trust for %s", keypair)
        self.trust(pubkey, keypair.seed().decode())
        response = self.call('bul_account', 200, 'could not get bul account after trust', queried_pubkey=pubkey)
        self.assertEqual(response['BUL balance'], 0)
        return pubkey, keypair.seed().decode()

    def test_send(self, amount_buls=10):
        """Send BULs between accounts."""
        pubkey, seed = self.create_and_setup_new_account()
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


class TestPackage(BaseOperations):
    """Package tests"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def setUp(self):
        """Prepare the test fixture"""
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

    def test_package(self):
        """Launch a package with payment and collateral, accept by courier and then by recipient."""
        db.init_db()
        payment, collateral = 5, 10
        deadline = int(time.time())

        LOGGER.info('preparing accounts')
        launcher_pubkey, launcher_seed = self.create_and_setup_new_account(payment)
        courier_pubkey, courier_seed = self.create_and_setup_new_account(collateral)
        recipient_pubkey, recipient_seed = self.create_and_setup_new_account()
        escrow_pubkey, escrow_seed = self.create_and_setup_new_account()

        LOGGER.info(
            "launching escrow: %s, launcher: %s, courier: %s, recipient: %s",
            escrow_pubkey, launcher_pubkey, courier_pubkey, recipient_pubkey)
        escrow_transactions = self.call(
            'prepare_escrow', 201, 'can not prepare escrow transactions', escrow_seed,
            launcher_pubkey=launcher_pubkey, courier_pubkey=courier_pubkey, recipient_pubkey=recipient_pubkey,
            payment_buls=payment, collateral_buls=collateral, deadline_timestamp=deadline)
        self.submit(escrow_transactions['set_options_transaction'], escrow_seed, 'set escrow options')
        LOGGER.info(self.call(
            'bul_account', 200, 'can not get escrow account balance', queried_pubkey=escrow_pubkey))
        self.send(launcher_seed, escrow_pubkey, payment)
        self.send(courier_seed, escrow_pubkey, collateral)
        self.call(
            'accept_package', 200, 'courier could not accept package', courier_seed, escrow_pubkey=escrow_pubkey)
        self.submit(escrow_transactions['payment_transaction'], recipient_seed, 'payment')
        self.call(
            'accept_package', 200, 'recipient could not accept package', recipient_seed, escrow_pubkey=escrow_pubkey)
        self.submit(escrow_transactions['merge_transaction'], None, 'merge')
