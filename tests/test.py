"""Test the PaKeT API."""
import json
import os
import os.path
import time
import unittest

import util.logger
import webserver.validation

import routes
import db
import paket

db.DB_NAME = 'test.db'
webserver.validation.NONCES_DB_NAME = 'nonce_test.db'
LOGGER = util.logger.logging.getLogger('pkt.api.test')
util.logger.setup()
APP = webserver.setup(routes.BLUEPRINT)
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

    def sign_transaction(self, transaction, seed):
        """Sign transaction with provided seed"""
        builder = paket.stellar_base.builder.Builder(horizon=paket.HORIZON, secret=seed)
        builder.import_from_xdr(transaction)
        builder.sign()
        signed_transaction = builder.gen_te().xdr().decode()
        return signed_transaction

    def call(self, path, expected_code=None, fail_message=None, seed=None, **kwargs):
        """Post data to API server."""
        LOGGER.info("calling %s", path)
        if seed:
            fingerprint = webserver.validation.generate_fingerprint(
                "{}/v{}/{}".format(self.host, routes.VERSION, path), kwargs)
            signature = webserver.validation.sign_fingerprint(fingerprint, seed)
            headers = {
                'Pubkey': paket.get_keypair(seed=seed).address().decode(),
                'Fingerprint': fingerprint, 'Signature': signature}
        else:
            headers = None
        response = self.app.post("/v{}/{}".format(routes.VERSION, path), headers=headers, data=kwargs)
        response = dict(real_status_code=response.status_code, **json.loads(response.data.decode()))
        if expected_code:
            self.assertEqual(response['real_status_code'], expected_code, "{} ({})".format(
                fail_message, response.get('error')))
        return response

    def submit(self, transaction, seed=None, description='unknown'):
        """Submit a transaction, optionally adding seed's signature."""
        LOGGER.info("trying to submit %s transaction", description)
        if seed:
            transaction = self.sign_transaction(transaction, seed)
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

    def create_and_setup_new_account(self, amount_buls=None, trust_limit=None):
        """Create account. Add trust and send initial ammount of BULs (if specified)"""
        keypair = paket.get_keypair()
        pubkey = keypair.address().decode()
        seed = keypair.seed().decode()
        self.create_account(from_pubkey=self.funded_pubkey, new_pubkey=pubkey, seed=self.funded_seed)
        self.trust(pubkey, seed, trust_limit)
        if amount_buls is not None:
            self.send(from_seed=self.funded_seed, to_pubkey=pubkey, amount_buls=amount_buls)
        return pubkey, seed

    def trust(self, pubkey, seed, limit=None):
        """Submit trust transaction for specified account"""
        LOGGER.info('adding trust for %s (%s)', pubkey, limit)
        unsigned = self.call(
            'prepare_trust', 200, 'could not get trust transaction', from_pubkey=pubkey, limit=limit)['transaction']
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
        self.assertEqual(response['bul_balance'], 0)
        return pubkey, keypair.seed().decode()

    def test_send(self, amount_buls=10):
        """Send BULs between accounts."""
        pubkey, seed = self.create_and_setup_new_account()
        source_start_balance = self.call(
            'bul_account', 200, 'can not get source account balance', queried_pubkey=self.funded_pubkey)['bul_balance']
        target_start_balance = self.call(
            'bul_account', 200, 'can not get target account balance', queried_pubkey=pubkey)['bul_balance']
        LOGGER.info("testing send from issuer to %s", pubkey)
        self.send(self.funded_seed, pubkey, amount_buls)
        source_end_balance = self.call(
            'bul_account', 200, 'can not get source account balance', queried_pubkey=self.funded_pubkey)['bul_balance']
        target_end_balance = self.call(
            'bul_account', 200, 'can not get target account balance', queried_pubkey=pubkey)['bul_balance']
        self.assertEqual(source_start_balance - source_end_balance, amount_buls, 'source balance does not add up')
        self.assertEqual(target_end_balance - target_start_balance, amount_buls, 'target balance does not add up')
        return pubkey, seed


class TestPackage(BaseOperations):
    """Package tests"""

    def cleanup(self):
        """Remove db files."""
        try:
            os.unlink(db.DB_NAME)
        except FileNotFoundError:
            pass
        try:
            os.unlink(webserver.validation.NONCES_DB_NAME)
        except FileNotFoundError:
            pass
        self.assertFalse(os.path.isfile(db.DB_NAME) or os.path.isfile(webserver.validation.NONCES_DB_NAME))

    def setUp(self):
        """Prepare the test fixture"""
        LOGGER.info('setting up')
        self.cleanup()
        db.init_db()

    def tearDown(self):
        LOGGER.info('tearing down')
        self.cleanup()

    def test_package(self):
        """Launch a package with payment and collateral, accept by courier and then by recipient."""
        payment, collateral = 5, 10
        deadline = int(time.time())

        LOGGER.info('preparing accounts')
        launcher = self.create_and_setup_new_account(payment)
        courier = self.create_and_setup_new_account(collateral)
        recipient = self.create_and_setup_new_account()
        escrow = self.create_and_setup_new_account(trust_limit=payment + collateral)

        LOGGER.info(
            "launching escrow: %s, launcher: %s, courier: %s, recipient: %s",
            escrow[0], launcher[0], courier[0], recipient[0])
        escrow_transactions = self.call(
            'prepare_escrow', 201, 'can not prepare escrow transactions', escrow[1],
            launcher_pubkey=launcher[0], courier_pubkey=courier[0], recipient_pubkey=recipient[0],
            payment_buls=payment, collateral_buls=collateral, deadline_timestamp=deadline)
        self.submit(escrow_transactions['set_options_transaction'], escrow[1], 'set escrow options')
        self.send(launcher[1], escrow[0], payment)
        self.send(courier[1], escrow[0], collateral)
        self.call(
            'accept_package', 200, 'courier could not accept package', courier[1], escrow_pubkey=escrow[0])

        courier_bul_balance = self.call(
            'bul_account', 200, 'can not get escrow account balance', queried_pubkey=courier[0])['bul_balance']
        self.submit(escrow_transactions['payment_transaction'], recipient[1], 'payment')
        self.call(
            'accept_package', 200, 'recipient could not accept package', recipient[1], escrow_pubkey=escrow[0])
        self.assertEqual(self.call(
            'bul_account', 200, 'can not get escrow account balance', queried_pubkey=courier[0]
        )['bul_balance'], courier_bul_balance + payment + collateral)

        launcher_xlm_balance = self.call(
            'bul_account', 200, 'can not get escrow account balance', queried_pubkey=launcher[0])['xlm_balance']
        escrow_xlm_balance = self.call(
            'bul_account', 200, 'can not get escrow account balance', queried_pubkey=escrow[0])['xlm_balance']
        self.submit(escrow_transactions['merge_transaction'], None, 'merge')
        self.assertLessEqual(self.call(
            'bul_account', 200, 'can not get escrow account balance', queried_pubkey=launcher[0]
        )['xlm_balance'] - launcher_xlm_balance - escrow_xlm_balance, 0.0001, 'xlm not merged back')


class TestAPI(BaseOperations):
    """API tests. It focused on testing API endpoints by posting valid and invalid data"""

    def test_submit_unsigned_transaction(self):
        """Test server behavior on submitting unsigned transactions"""
        keypair = paket.get_keypair()
        pubkey = keypair.address().decode()
        new_account_pubkey, _ = self.create_and_setup_new_account()
        LOGGER.info('preparing unsigned transactions')
        unsigned_create_account = self.call(
            'prepare_create_account', 200, 'could not get create account transaction',
            from_pubkey=self.funded_pubkey, new_pubkey=pubkey)['transaction']
        unsigned_trust = self.call('prepare_trust', 200, 'could not get trust transaction',
                                   from_pubkey=self.funded_pubkey)['transaction']
        unsigned_send_buls = self.call(
            'prepare_send_buls', 200,
            "can not prepare send from {} to {}".format(self.funded_pubkey, new_account_pubkey),
            from_pubkey=self.funded_pubkey, to_pubkey=new_account_pubkey, amount_buls=5)['transaction']

        for unsigned in (unsigned_create_account, unsigned_trust, unsigned_send_buls):
            with self.subTest(unsigned=unsigned):
                self.call(path='submit_transaction', expected_code=500,
                          fail_message='unexpected server response for submitting unsigned transaction',
                          seed=self.funded_seed, transaction=unsigned)

    def test_submit_signed_transaction(self):
        """Test server behavior on submitting signed transactions"""
        keypair = paket.get_keypair()
        new_pubkey = keypair.address().decode()
        new_seed = keypair.seed().decode()

        # checking create_account transaction
        unsigned_create_account = self.call(
            'prepare_create_account', 200, 'could not get create account transaction',
            from_pubkey=self.funded_pubkey, new_pubkey=new_pubkey)['transaction']
        signed_create_account = self.sign_transaction(unsigned_create_account, self.funded_seed)
        LOGGER.info('Submitting signed create_account transaction')
        self.call(path='submit_transaction', expected_code=200,
                  fail_message='unexpected server response for submitting signed create_account transaction',
                  seed=self.funded_seed, transaction=signed_create_account)

        # checking trust transaction
        unsigned_trust = self.call('prepare_trust', 200,
                                   'could not get trust transaction', from_pubkey=new_pubkey)['transaction']
        signed_trust = self.sign_transaction(unsigned_trust, new_seed)
        LOGGER.info('Submitting signed trust transaction')
        self.call(path='submit_transaction', expected_code=200,
                  fail_message='unexpected server response for submitting signed trust transaction',
                  seed=new_seed, transaction=signed_trust)

        # checking send_buls transaction
        unsigned_send_buls = self.call(
            'prepare_send_buls', 200, "can not prepare send from {} to {}".format(self.funded_pubkey, new_pubkey),
            from_pubkey=self.funded_pubkey, to_pubkey=new_pubkey, amount_buls=5)['transaction']
        signed_send_buls = self.sign_transaction(unsigned_send_buls, self.funded_seed)
        LOGGER.info('Submitting signed send_buls transaction')
        self.call(path='submit_transaction', expected_code=200,
                  fail_message='unexpected server response for submitting signed send_buls transaction',
                  seed=self.funded_seed, transaction=signed_send_buls)

    def test_submit_invalid_transaction(self):
        """Test server behavior on submitting invalid transactions"""
        keypair = paket.get_keypair()
        new_pubkey = keypair.address().decode()

        # preparing invalid transactions
        unsigned_create_account = self.call(
            'prepare_create_account', 200, 'could not get create account transaction',
            from_pubkey=self.funded_pubkey, new_pubkey=new_pubkey)['transaction']
        signed_create_account = self.sign_transaction(unsigned_create_account, self.funded_seed)
        signed_create_account = signed_create_account.replace('c', 'd', 1).replace('S', 't', 1).replace('a', 'r', 1)

        data_set = [
            signed_create_account,
            'TG9yZW0gaXBzdW0gZG9sb3Igc2l0IGFtZXQ=',
            144
        ]
        for invalid_transaction in data_set:
            with self.subTest(transaction=invalid_transaction):
                self.call(path='submit_transaction', expected_code=500,
                          fail_message='unexpected result while submiting invalid transaction',
                          transaction=invalid_transaction)

    def test_bul_account(self):
        """Test server behavior on querying information about valid account"""
        accounts = [self.funded_pubkey]
        # additionally create 3 new accounts
        for _ in range(3):
            keypair = paket.get_keypair()
            pubkey = keypair.address().decode()
            seed = keypair.seed().decode()
            self.create_account(from_pubkey=self.funded_pubkey, new_pubkey=pubkey, seed=self.funded_seed)
            self.trust(pubkey, seed)
            accounts.append(pubkey)

        for account in accounts:
            with self.subTest(account=account):
                self.call('bul_account', 200, 'could not verify account exist', queried_pubkey=account)

    def test_invalid_bul_account(self):
        """Test server behavior on querying information about invalid account"""
        keypair = paket.get_keypair()
        pubkey = keypair.address().decode()

        data_set = [
            pubkey,  # just generated pubkey
            'GBTWWXACDQOSRQ3645B2LA345CRSKSV6MSBUO4LSHC26ZMNOYFN2YJ',  # invalid pubkey
            'Lorem ipsum dolor sit amet',  # random text
            144  # random number
        ]
        for pubkey in data_set:
            with self.subTest(pubkey=pubkey):
                self.call('bul_account', 409, 'could not verify account exist', queried_pubkey=pubkey)

    def test_invalid_prepare_create_account(self):
        """Test prepare_account endpoint with invalid public keys"""
        keypair = paket.get_keypair()
        pubkey = keypair.address().decode()
        invalid_from_pubkeys = [
            pubkey,  # just generated pubkey
            'GBTWWXACDQOSRQ3645B2LA345CRSKSV6MSBUO4LSHC26ZMNOYFN2YJ',  # invalid pubkey
            'Lorem ipsum dolor sit amet',  # random text
            144  # random number
        ]
        invalid_new_pubkeys = invalid_from_pubkeys.copy()
        pubkey_pairs = [(from_pubkey, new_pubkey) for from_pubkey in invalid_from_pubkeys
                        for new_pubkey in invalid_new_pubkeys]

        for from_pubkey, new_pubkey in pubkey_pairs:
            self.call('prepare_create_account', 500, 'unexpected server response for prepare_create_account',
                      from_pubkey=from_pubkey, new_pubkey=new_pubkey)

    def test_valid_prepare_account(self):
        """Test prepare_account endpoint with valid public keys"""
        # Yarik, why are we doing this three times?
        for new_pubkey in [paket.get_keypair().address().decode() for _ in range(3)]:
            self.call('prepare_create_account', 200, 'could not get create account transaction',
                      from_pubkey=self.funded_pubkey, new_pubkey=new_pubkey)

    def test_unauthorized_my_packages(self):
        """Test my_packages endpoint without authorization headers in reqest"""
        self.call(path='my_packages', expected_code=400,
                  fail_message='does not get unauthorized status code on unauthorized request',
                  user_pubkey=self.funded_pubkey)
