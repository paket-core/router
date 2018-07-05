"""Test the PaKeT API."""
import json
import time
import unittest

import paket_stellar
import util.logger
import webserver.validation

import routes

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
        self.funded_account = paket_stellar.get_keypair(seed=self.funded_seed)
        self.funded_pubkey = self.funded_account.address().decode()
        LOGGER.info('init done')

    @staticmethod
    def sign_transaction(transaction, seed):
        """Sign transaction with provided seed"""
        builder = paket_stellar.stellar_base.builder.Builder(horizon=paket_stellar.HORIZON, secret=seed)
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
                'Pubkey': paket_stellar.get_keypair(seed=seed).address().decode(),
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

    def create_account(self, from_pubkey, new_pubkey, seed, starting_balance=50000000):
        """Create account with starting balance"""
        LOGGER.info('creating %s from %s', new_pubkey, from_pubkey)
        unsigned = self.call(
            'prepare_account', 200, 'could not get create account transaction',
            from_pubkey=from_pubkey, new_pubkey=new_pubkey, starting_balance=starting_balance)['transaction']
        response = self.submit(unsigned, seed, 'create account')
        return response

    def create_and_setup_new_account(self, amount_buls=None, trust_limit=None):
        """Create account. Add trust and send initial ammount of BULs (if specified)"""
        keypair = paket_stellar.get_keypair()
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
        from_pubkey = paket_stellar.get_keypair(seed=from_seed).address().decode()
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
        keypair = paket_stellar.get_keypair()
        pubkey = keypair.address().decode()
        response = self.call('bul_account', 400, 'could not verify account does not exist', queried_pubkey=pubkey)
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

    def test_account(self):
        """Create new account"""
        keypair = paket_stellar.get_keypair()
        pubkey = keypair.address().decode()
        LOGGER.info("testing creation of %s", keypair)
        response = self.create_account(from_pubkey=self.funded_pubkey, new_pubkey=pubkey, seed=self.funded_seed)
        self.assertEqual(response['response']['result_xdr'], 'AAAAAAAAAGQAAAAAAAAAAQAAAAAAAAAAAAAAAAAAAAA=')
        return keypair, pubkey

    def test_trust(self):
        """Extend trust."""
        keypair = paket_stellar.get_keypair()
        pubkey = keypair.address().decode()
        self.create_account(from_pubkey=self.funded_pubkey, new_pubkey=pubkey, seed=self.funded_seed)
        response = self.call('bul_account', 400, 'could not verify account does not trust', queried_pubkey=pubkey)
        self.assertEqual(response['error'], "account {} does not trust {} from {}".format(
            pubkey, paket_stellar.BUL_TOKEN_CODE, paket_stellar.ISSUER))
        LOGGER.info("testing trust for %s", keypair)
        self.trust(pubkey, keypair.seed().decode())
        response = self.call('bul_account', 200, 'could not get bul account after trust', queried_pubkey=pubkey)
        self.assertEqual(int(response['bul_balance']), 0)
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
            'bul_account', 200, 'can not get target account balance', queried_pubkey=account[0])['bul_balance']
        self.assertEqual(int(source_start_balance or 0) - int(source_end_balance or 0), amount_stroops,
                         'source balance does not add up')
        self.assertEqual(int(target_end_balance or 0) - int(target_start_balance or 0), amount_stroops,
                         'target balance does not add up')


class TestPackage(BaseOperations):
    """Package tests"""

    def test_package(self):
        """Launch a package with payment and collateral, accept by courier and then by recipient."""
        amounts = 50000000, 100000000
        deadline = int(time.time())

        LOGGER.info('preparing accounts')
        launcher = self.create_and_setup_new_account(amounts[0])
        courier = self.create_and_setup_new_account(amounts[1])
        recipient = self.create_and_setup_new_account()
        escrow = self.create_and_setup_new_account(trust_limit=amounts[0] + amounts[1])

        LOGGER.info(
            "launching escrow: %s, launcher: %s, courier: %s, recipient: %s",
            escrow[0], launcher[0], courier[0], recipient[0])
        escrow_transactions = self.call(
            'prepare_escrow', 201, 'can not prepare escrow transactions', escrow[1],
            launcher_pubkey=launcher[0], courier_pubkey=courier[0], recipient_pubkey=recipient[0],
            payment_buls=amounts[0], collateral_buls=amounts[1], deadline_timestamp=deadline)
        self.submit(escrow_transactions['set_options_transaction'], escrow[1], 'set escrow options')
        self.send(launcher[1], escrow[0], amounts[0])
        self.send(courier[1], escrow[0], amounts[1])
        self.call(
            'accept_package', 200, 'courier could not accept package', courier[1], escrow_pubkey=escrow[0])

        courier_bul_balance = self.call(
            'bul_account', 200, 'can not get escrow account balance', queried_pubkey=courier[0])['bul_balance']
        self.submit(escrow_transactions['payment_transaction'], recipient[1], 'payment')
        self.call(
            'accept_package', 200, 'recipient could not accept package', recipient[1], escrow_pubkey=escrow[0])
        courier_result_balance = int(courier_bul_balance or 0) + amounts[0] + amounts[1]
        courier_actual_balance = self.call(
            'bul_account', 200, 'can not get escrow account balance', queried_pubkey=courier[0])['bul_balance']
        self.assertEqual(int(courier_actual_balance), courier_result_balance)

        launcher_xlm_balance = self.call(
            'bul_account', 200, 'can not get escrow account balance', queried_pubkey=launcher[0])['xlm_balance']
        escrow_xlm_balance = self.call(
            'bul_account', 200, 'can not get escrow account balance', queried_pubkey=escrow[0])['xlm_balance']
        self.submit(escrow_transactions['merge_transaction'], None, 'merge')
        launcher_result_balance = self.call(
            'bul_account', 200, 'can not get escrow account balance', queried_pubkey=launcher[0])['xlm_balance']
        self.assertLessEqual(
            int(launcher_result_balance or 0) - int(launcher_xlm_balance or 0) - int(escrow_xlm_balance or 0),
            1000, 'xlm not merged back')


class TestAPI(BaseOperations):
    """API tests. It focused on testing API endpoints by posting valid and invalid data"""

    def test_submit_unsigned(self):
        """Test server behavior on submitting unsigned transactions"""
        keypair = paket_stellar.get_keypair()
        pubkey = keypair.address().decode()
        new_account_pubkey, _ = self.create_and_setup_new_account()
        LOGGER.info('preparing unsigned transactions')
        unsigned_account = self.call(
            'prepare_account', 200, 'could not get create account transaction',
            from_pubkey=self.funded_pubkey, new_pubkey=pubkey)['transaction']
        unsigned_trust = self.call('prepare_trust', 200, 'could not get trust transaction',
                                   from_pubkey=self.funded_pubkey)['transaction']
        unsigned_send_buls = self.call(
            'prepare_send_buls', 200,
            "can not prepare send from {} to {}".format(self.funded_pubkey, new_account_pubkey),
            from_pubkey=self.funded_pubkey, to_pubkey=new_account_pubkey, amount_buls=5)['transaction']

        for unsigned in (unsigned_account, unsigned_trust, unsigned_send_buls):
            with self.subTest(unsigned=unsigned):
                self.call(path='submit_transaction', expected_code=500,
                          fail_message='unexpected server response for submitting unsigned transaction',
                          seed=self.funded_seed, transaction=unsigned)

    def test_submit_signed(self):
        """Test server behavior on submitting signed transactions"""
        keypair = paket_stellar.get_keypair()
        new_pubkey = keypair.address().decode()
        new_seed = keypair.seed().decode()

        # checking create_account transaction
        unsigned_account = self.call(
            'prepare_account', 200, 'could not get create account transaction',
            from_pubkey=self.funded_pubkey, new_pubkey=new_pubkey)['transaction']
        signed_account = self.sign_transaction(unsigned_account, self.funded_seed)
        LOGGER.info('Submitting signed create_account transaction')
        self.call(path='submit_transaction', expected_code=200,
                  fail_message='unexpected server response for submitting signed create_account transaction',
                  seed=self.funded_seed, transaction=signed_account)

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
        keypair = paket_stellar.get_keypair()
        new_pubkey = keypair.address().decode()

        # preparing invalid transactions
        unsigned_prepare_account = self.call(
            'prepare_account', 200, 'could not get create account transaction',
            from_pubkey=self.funded_pubkey, new_pubkey=new_pubkey)['transaction']
        signed_prepare_account = self.sign_transaction(unsigned_prepare_account, self.funded_seed)
        signed_prepare_account = signed_prepare_account.replace('c', 'd', 1).replace('S', 't', 1).replace('a', 'r', 1)

        data_set = [
            signed_prepare_account,
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
            keypair = paket_stellar.get_keypair()
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
        keypair = paket_stellar.get_keypair()
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
                self.call('bul_account', 400, 'could not verify account exist', queried_pubkey=pubkey)

    def test_invalid_prepare_account(self):
        """Test prepare_account endpoint on invalid public keys"""
        keypair = paket_stellar.get_keypair()
        pubkey = keypair.address().decode()
        invalid_from_pubkeys = [
            pubkey, # Unfunded pubkey
            'GBTWWXACDQOSRQ3645B2LA345CRSKSV6MSBUO4LSHC26ZMNOYFN2YJ',  # invalid pubkey
            'Lorem ipsum dolor sit amet',  # random text
            144  # random number
        ]
        invalid_new_pubkeys = invalid_from_pubkeys.copy()
        pubkey_pairs = [(from_pubkey, new_pubkey) for from_pubkey in invalid_from_pubkeys
                        for new_pubkey in invalid_new_pubkeys]

        for from_pubkey, new_pubkey in pubkey_pairs:
            LOGGER.info(
                'querying prepare create invalid new account: %s from invalid account: %s', new_pubkey, from_pubkey)
            self.call(
                'prepare_account', 400, 'unexpected server response for prepare_account',
                from_pubkey=from_pubkey, new_pubkey=new_pubkey)

    def test_prepare_account(self):
        """Test prepare_account endpoint on valid public keys"""
        keypair = paket_stellar.get_keypair()
        pubkey = keypair.address().decode()
        LOGGER.info('querying prepare create account for public key: %s', pubkey)
        self.call('prepare_account', 200, 'could not get create account transaction',
                  from_pubkey=self.funded_pubkey, new_pubkey=pubkey)

    def test_prepare_send_buls(self):
        """Test prepare_send_buls endpoint on valid public key"""
        pubkey, _ = self.create_and_setup_new_account()
        LOGGER.info('querying prepare send buls for user: %s', pubkey)
        self.call('prepare_send_buls', 200, 'can not prepare send from {} to {}'.format(self.funded_pubkey, pubkey),
                  from_pubkey=self.funded_pubkey, to_pubkey=pubkey, amount_buls=50000000)

    def test_prepare_trust(self):
        """Test prepare_trust endpoint on valid pubkey"""
        keypair = paket_stellar.get_keypair()
        pubkey = keypair.address().decode()
        self.create_account(from_pubkey=self.funded_pubkey, new_pubkey=pubkey, seed=self.funded_seed)
        LOGGER.info('querying prepare trust for user: %s', pubkey)
        self.call('prepare_trust', 200, 'could not get trust transaction', from_pubkey=pubkey)

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
        self.assertEqual(packages[0]['collateral'], str(collateral))
        self.assertEqual(packages[0]['payment'], str(payment))

    def test_unauth_my_packages(self):
        """Test my_packages endpoint on unauthorized request"""
        LOGGER.info('querying packages without authorization')
        self.call(path='my_packages', expected_code=400,
                  fail_message='does not get unauthorized status code on unauthorized request',
                  user_pubkey=self.funded_pubkey)

    def test_prepare_escrow(self):
        """Test prepare_escrow endpoint on valid public keys"""
        payment, collateral = 50000000, 100000000
        deadline = int(time.time())
        LOGGER.info('preparing new escrow')
        self.prepare_escrow(payment, collateral, deadline)

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
        self.assertEqual(package['collateral'], str(collateral))
        self.assertEqual(package['payment'], str(payment))
