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

    @staticmethod
    def cleanup():
        """Remove db files."""
        try:
            os.unlink(db.DB_NAME)
        except FileNotFoundError:
            pass
        try:
            os.unlink(webserver.validation.NONCES_DB_NAME)
        except FileNotFoundError:
            pass
        assert not os.path.isfile(db.DB_NAME)
        assert not os.path.isfile(webserver.validation.NONCES_DB_NAME)

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

    def create_account(self, from_pubkey, new_pubkey, starting_balance=50000000, seed=None):
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

    def prepare_escrow(self, payment, collateral, deadline):
        """Create launcher, courier, recipient, escrow accounts and call prepare_escrow"""
        LOGGER.info('preparing package accounts')
        launcher = self.create_and_setup_new_account(payment)
        courier = self.create_and_setup_new_account(collateral)
        recipient = self.create_and_setup_new_account()
        escrow = self.create_and_setup_new_account()

        LOGGER.info(
            "launching escrow: %s, launcher: %s, courier: %s, recipient: %s",
            escrow[0], launcher[0], courier[0], recipient[0])
        escrow_transactions = self.call(
            'prepare_escrow', 201, 'can not prepare escrow transactions', escrow[1],
            launcher_pubkey=launcher[0], courier_pubkey=courier[0], recipient_pubkey=recipient[0],
            payment_buls=payment, collateral_buls=collateral, deadline_timestamp=deadline)

        return {
            'launcher': launcher,
            'courier': courier,
            'recipient': recipient,
            'escrow': escrow,
            'transactions': escrow_transactions
        }


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
        new_account = self.create_and_setup_new_account(50000000)
        data_set = [
            self.funded_pubkey,  # valid public key
            new_account[0]  # valid public key of just created new account
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

    def test_send(self):
        """Test sending BULs (in stroops amount) between accounts."""
        amount_stroops = 15000000
        account = self.create_and_setup_new_account()
        source_start_balance = self.call(
            'bul_account', 200, 'can not get source account balance', queried_pubkey=self.funded_pubkey)['bul_balance']
        target_start_balance = self.call(
            'bul_account', 200, 'can not get target account balance', queried_pubkey=account[0])['bul_balance']
        LOGGER.info("testing send from issuer to %s", account[0])
        self.send(self.funded_seed, account[0], amount_stroops)
        source_end_balance = self.call(
            'bul_account', 200, 'can not get source account balance', queried_pubkey=self.funded_pubkey)['bul_balance']
        target_end_balance = self.call(
            'bul_account', 200, 'can not get target account balance', queried_pubkey=account[0  ])['bul_balance']
        self.assertEqual(source_start_balance - source_end_balance, amount_stroops, 'source balance does not add up')
        self.assertEqual(target_end_balance - target_start_balance, amount_stroops, 'target balance does not add up')


class TestPackage(BaseOperations):
    """Package tests"""

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
        payment, collateral = 50000000, 100000000
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
        courier_result_balance = courier_bul_balance + payment + collateral
        courier_actual_balance = self.call(
            'bul_account', 200, 'can not get escrow account balance', queried_pubkey=courier[0])['bul_balance']
        self.assertEqual(courier_actual_balance, courier_result_balance)

        launcher_xlm_balance = self.call(
            'bul_account', 200, 'can not get escrow account balance', queried_pubkey=launcher[0])['xlm_balance']
        escrow_xlm_balance = self.call(
            'bul_account', 200, 'can not get escrow account balance', queried_pubkey=escrow[0])['xlm_balance']
        self.submit(escrow_transactions['merge_transaction'], None, 'merge')
        self.assertLessEqual(self.call(
            'bul_account', 200, 'can not get escrow account balance', queried_pubkey=launcher[0]
        )['xlm_balance'] - launcher_xlm_balance - escrow_xlm_balance, 1000, 'xlm not merged back')


class TestAPI(BaseOperations):
    """API tests. It focused on testing API endpoints by posting valid and invalid data"""

    @classmethod
    def setUpClass(cls):
        """Prepare the class fixture"""
        LOGGER.info('setting up')
        cls.cleanup()
        db.init_db()

    @classmethod
    def tearDownClass(cls):
        """Deconstructing the class fixture"""
        LOGGER.info('tearing down')
        cls.cleanup()

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
                LOGGER.info('submiting invalid transaction: %s', invalid_transaction)
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
                LOGGER.info('querying information about account: %s', account)
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
                LOGGER.info('querying information about invalid account: %s', pubkey)
                self.call('bul_account', 409, 'could not verify account exist', queried_pubkey=pubkey)

    def test_invalid_prepare_create_account(self):
        """Test prepare_account endpoint on invalid public keys"""
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
            LOGGER.info('querying prepare create invalid new account: %s from invalid account: %s',
                        new_pubkey, from_pubkey)
            self.call('prepare_create_account', 500, 'unexpected server response for prepare_create_account',
                      from_pubkey=from_pubkey, new_pubkey=new_pubkey)

    def test_prepare_create_account(self):
        """Test prepare_account endpoint on valid public keys"""
        keypair = paket.get_keypair()
        pubkey = keypair.address().decode()
        LOGGER.info('querying prepare create account for public key: %s', pubkey)
        self.call('prepare_create_account', 200, 'could not get create account transaction',
                  from_pubkey=self.funded_pubkey, new_pubkey=pubkey)

    def test_prepare_send_buls(self):
        """Test prepare_send_buls endpoint on valid public key"""
        pubkey, _ = self.create_and_setup_new_account()
        LOGGER.info('querying prepare send buls for user: %s', pubkey)
        self.call('prepare_send_buls', 200, 'can not prepare send from {} to {}'.format(self.funded_pubkey, pubkey),
                  from_pubkey=self.funded_pubkey, to_pubkey=pubkey, amount_buls=5)

    def test_invalid_prepare_send_buls(self):
        """Test prepare_send_buls endpoint on invalid public key"""
        pubkey = 'SGBJZMQ7ZMSMO2HYEV56DXRR7LJ5X2KW6VKR7MRQ'
        LOGGER.info('querying prepare send buls for invalid user: %s', pubkey)
        self.call('prepare_send_buls', 500, 'can not prepare send from {} to {}'.format(self.funded_pubkey, pubkey),
                  from_pubkey=self.funded_pubkey, to_pubkey=pubkey, amount_buls=5)

    def test_prepare_trust(self):
        """Test prepare_trust endpoint on valid pubkey"""
        keypair = paket.get_keypair()
        pubkey = keypair.address().decode()
        self.create_account(from_pubkey=self.funded_pubkey, new_pubkey=pubkey, seed=self.funded_seed)
        LOGGER.info('querying prepare trust for user: %s', pubkey)
        self.call('prepare_trust', 200, 'could not get trust transaction', from_pubkey=pubkey)

    def test_invalid_prepare_trust(self):
        """Test prepare_trust endpoint on invalid pubkey"""
        pubkey = 'SDJGJZM7Z4W3KMSM2HYEVJPOZ7XRR7LJ5XKW6VKBSR7MRQ'
        LOGGER.info('querying prepare trust for invalid user: %s', pubkey)
        self.call('prepare_trust', 500, 'could not get trust transaction', from_pubkey=pubkey)

    def test_accept_package(self):
        """Test accept_package endpoint on valid public key"""
        payment, collateral = 50000000, 100000000
        deadline = int(time.time())
        escrow_stuff = self.prepare_escrow(payment, collateral, deadline)

        self.submit(escrow_stuff['transactions']['set_options_transaction'],
                    escrow_stuff['escrow'][1], 'set escrow options')
        self.send(escrow_stuff['launcher'][1], escrow_stuff['escrow'][0], payment)
        self.send(escrow_stuff['courier'][1], escrow_stuff['escrow'][0], collateral)
        for member in (escrow_stuff['courier'], escrow_stuff['recipient']):
            LOGGER.info('accepting package: %s for user %s', escrow_stuff['escrow'][0], member[1])
            self.call('accept_package', 200, 'member could not accept package',
                      member[1], escrow_pubkey=escrow_stuff['escrow'][0])

    def test_unauth_accept_package(self):
        """Test accept_package endpoint on unauthorized request"""
        escrow_pubkey = 'SDJGJZM7Z4W3KMSM2HYEVJPOZ7XRR7LJ5XKW6VKBSR7MRQ'
        LOGGER.info('trying accept package without authorization')
        self.call('accept_package', 400, 'courier could not accept package', escrow_pubkey=escrow_pubkey)

    def test_invalid_accept_package(self):
        """Test accept_package endpoint on invalid public keys"""
        account = self.create_and_setup_new_account()
        escrow_pubkey = 'SDJGJZM7Z4W3KMSM2HYEVJPOZ7XRR7LJ5XKW6VKBSR7MRQ'
        LOGGER.info('trying accept invalid package: %s for user: %s', escrow_pubkey, account[0])
        self.call('accept_package', 500, 'user could not accept package',
                  seed=account[1], escrow_pubkey=escrow_pubkey)

    def test_my_packages(self):
        """Test my_packages endpoint on valid pubkey"""
        account = self.create_and_setup_new_account()
        LOGGER.info('querying packages for new user: %s', account[0])
        packages = self.call(path='my_packages', expected_code=200,
                             fail_message='does not get ok status code on valid request', seed=account[1],
                             user_pubkey=account[0])['packages']
        self.assertTrue(len(packages) == 0)

        payment, collateral = 50000000, 100000000
        deadline = int(time.time())
        escrow_stuff = self.prepare_escrow(payment, collateral, deadline)
        LOGGER.info('querying packages for user: %s', escrow_stuff['launcher'][0])
        packages = self.call(path='my_packages', expected_code=200,
                             fail_message='does not get ok status code on valid request',
                             seed=escrow_stuff['launcher'][1], user_pubkey=escrow_stuff['launcher'][0])['packages']
        self.assertTrue(len(packages) == 1)
        self.assertEqual(packages[0]['deadline'], deadline)
        self.assertEqual(packages[0]['escrow_pubkey'], escrow_stuff['escrow'][0])
        self.assertEqual(packages[0]['collateral'], collateral)
        self.assertEqual(packages[0]['payment'], payment)

    def test_unauth_my_packages(self):
        """Test my_packages endpoint on unauthorized request"""
        LOGGER.info('querying packages without authorization')
        self.call(path='my_packages', expected_code=400,
                  fail_message='does not get unauthorized status code on unauthorized request',
                  user_pubkey=self.funded_pubkey)

    def test_invalid_my_packages(self):
        """Test my_packages endpoint on invalid public key"""
        pubkey = 'SDJGJZM7Z4W3KMSM2HYEVJPOZ7XRR7LJ5XKW6VKBSR7MRQ'
        LOGGER.info('querying packages for invalid user: %s', pubkey)
        self.call(path='my_packages', expected_code=500,
                  fail_message='does not get server error status code on invalid request',
                  seed=self.funded_seed, user_pubkey=pubkey)

    def test_prepare_escrow(self):
        """Test prepare_escrow endpoint on valid public keys"""
        payment, collateral = 50000000, 100000000
        deadline = int(time.time())
        LOGGER.info('preparing new escrow')
        self.prepare_escrow(payment, collateral, deadline)

    def test_unauth_prepare_escrow(self):
        """Test prepare_escrow on unauthorized request"""
        payment, collateral = 50000000, 100000000
        deadline = int(time.time())

        LOGGER.info('preparing accounts')
        launcher = self.create_and_setup_new_account(payment)
        courier = self.create_and_setup_new_account(collateral)
        recipient = self.create_and_setup_new_account()
        escrow = self.create_and_setup_new_account()

        LOGGER.info(
            'launching escrow: %s, launcher: %s, courier: %s, recipient: %s without authorization',
            escrow[0], launcher[0], courier[0], recipient[0])
        self.call(
            'prepare_escrow', 400, 'does not get unauthorized status code on unauthorized request',
            launcher_pubkey=launcher[0], courier_pubkey=courier[0], recipient_pubkey=recipient[0],
            payment_buls=payment, collateral_buls=collateral, deadline_timestamp=deadline)

    def test_invalid_prepare_escrow(self):
        """Test prepare_escrow on invalid public keys"""
        payment, collateral = 50000000, 100000000
        deadline = int(time.time())

        LOGGER.info('preparing accounts')
        launcher = 'SDJBZMQ7Z43KMSMO2HYE56DJPO7XRR7L5X2KW6KBSLELR7MRQ'
        courier = 'SDBJZMQ7Z4W3KMSMO2HYEV56DJPOZ7XRR7LJ5X2KW6VKBSLEL'
        recipient = 'DJJZMQ7Z4W3KMSMO2HYEV56DJPOZ7XRR7LJ5X2K6KBSLELR7MR'
        escrow = self.create_and_setup_new_account()

        LOGGER.info(
            'launching escrow: %s with invalid launcher: %s, courier: %s, recipient: %s',
            escrow[0], launcher[0], courier[0], recipient[0])
        self.call(
            'prepare_escrow', 500, 'does not get internal server error status code on invalid request', escrow[1],
            launcher_pubkey=launcher, courier_pubkey=courier, recipient_pubkey=recipient,
            payment_buls=payment, collateral_buls=collateral, deadline_timestamp=deadline)

    def test_package(self):
        """Test package endpoint on valid public key"""
        payment, collateral = 50000000, 100000000
        deadline = int(time.time())
        LOGGER.info('preparing new escrow')
        escrow_stuff = self.prepare_escrow(payment, collateral, deadline)
        LOGGER.info('querying package with valid escrow pubkey: %s', escrow_stuff['escrow'][0])
        package = self.call(path='package', expected_code=200,
                            fail_message='does not get ok status code on valid request',
                            escrow_pubkey=escrow_stuff['escrow'][0])['package']
        self.assertEqual(package['deadline'], deadline)
        self.assertEqual(package['escrow_pubkey'], escrow_stuff['escrow'][0])
        self.assertEqual(package['collateral'], collateral)
        self.assertEqual(package['payment'], payment)

    def test_invalid_package(self):
        """Test package endpoint on invalid public key"""
        pubkey = 'DJJZMQ7Z4W3KMSMO2HYEV56DJPOZ7XRR7LJ5X2K6KBSLELR7MR'
        LOGGER.info('querying package with invalid pubkey: %s', pubkey)
        self.call(path='package', expected_code=500,
                  fail_message='does not get internal server error code on invalid request', escrow_pubkey=pubkey)
