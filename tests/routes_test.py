"""Tests for routes module"""
import json
import time
import unittest

import paket_stellar
import util.logger
import webserver.validation

import routes
import tests.db_mockup

LOGGER = util.logger.logging.getLogger('pkt.api.test')
APP = webserver.setup(routes.BLUEPRINT)
APP.testing = True

# pylint: disable=invalid-name
routes.db = tests.db_mockup
# pylint: enable=invalid-name


class ApiBaseTest(unittest.TestCase):
    """Base class for routes tests."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.app = APP.test_client()
        self.host = 'http://localhost'
        self.funded_seed = 'SDJGBJZMQ7Z4W3KMSMO2HYEV56DJPOZ7XRR7LJ5X2KW6VKBSLELR7MRQ'
        self.funded_account = paket_stellar.get_keypair(seed=self.funded_seed)
        self.funded_pubkey = self.funded_account.address().decode()
        LOGGER.info('init done')

    def setUp(self):
        """Setting up the test fixture before exercising it."""
        routes.db.init_db()

    @staticmethod
    def sign_transaction(transaction, seed):
        """Sign transaction with provided seed"""
        builder = paket_stellar.stellar_base.builder.Builder(horizon=paket_stellar.HORIZON_SERVER, secret=seed)
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

    def prepare_escrow(self, payment, collateral, deadline, location=None):
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
            payment_buls=payment, collateral_buls=collateral, deadline_timestamp=deadline, location=location)

        return {
            'launcher': launcher,
            'courier': courier,
            'recipient': recipient,
            'escrow': escrow,
            'transactions': escrow_transactions
        }


class SubmitTransactionTest(ApiBaseTest):
    """Test for submit_transaction route."""

    def test_submit_signed(self):
        """Test submitting signed transactions."""
        keypair = paket_stellar.get_keypair()
        new_pubkey = keypair.address().decode()
        new_seed = keypair.seed().decode()

        # checking create_account transaction
        unsigned_account = self.call(
            'prepare_account', 200, 'could not get create account transaction',
            from_pubkey=self.funded_pubkey, new_pubkey=new_pubkey)['transaction']
        signed_account = self.sign_transaction(unsigned_account, self.funded_seed)
        LOGGER.info('Submitting signed create_account transaction')
        self.call(
            path='submit_transaction', expected_code=200,
            fail_message='unexpected server response for submitting signed create_account transaction',
            seed=self.funded_seed, transaction=signed_account)

        # checking trust transaction
        unsigned_trust = self.call(
            'prepare_trust', 200, 'could not get trust transaction', from_pubkey=new_pubkey)['transaction']
        signed_trust = self.sign_transaction(unsigned_trust, new_seed)
        LOGGER.info('Submitting signed trust transaction')
        self.call(
            path='submit_transaction', expected_code=200,
            fail_message='unexpected server response for submitting signed trust transaction',
            seed=new_seed, transaction=signed_trust)

        # checking send_buls transaction
        unsigned_send_buls = self.call(
            'prepare_send_buls', 200, "can not prepare send from {} to {}".format(self.funded_pubkey, new_pubkey),
            from_pubkey=self.funded_pubkey, to_pubkey=new_pubkey, amount_buls=5)['transaction']
        signed_send_buls = self.sign_transaction(unsigned_send_buls, self.funded_seed)
        LOGGER.info('Submitting signed send_buls transaction')
        self.call(
            path='submit_transaction', expected_code=200,
            fail_message='unexpected server response for submitting signed send_buls transaction',
            seed=self.funded_seed, transaction=signed_send_buls)


class BulAccountTest(ApiBaseTest):
    """Test for bul_account endpoint."""

    def test_bul_account(self):
        """Test getting existing account."""
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
                LOGGER.info('getting information about account: %s', account)
                self.call('bul_account', 200, 'could not verify account exist', queried_pubkey=account)


class PrepareAccountTest(ApiBaseTest):
    """Test for prepare_account endpoint."""

    def test_prepare_account(self):
        """Test preparing transaction for creating account."""
        keypair = paket_stellar.get_keypair()
        pubkey = keypair.address().decode()
        LOGGER.info('preparing create account transaction for public key: %s', pubkey)
        self.call(
            'prepare_account', 200, 'could not get create account transaction',
            from_pubkey=self.funded_pubkey, new_pubkey=pubkey)


class PrepareTrustTest(ApiBaseTest):
    """Test for prepare_trust endpoint."""

    def test_prepare_trust(self):
        """Test preparing transaction for trusting BULs."""
        keypair = paket_stellar.get_keypair()
        pubkey = keypair.address().decode()
        self.create_account(from_pubkey=self.funded_pubkey, new_pubkey=pubkey, seed=self.funded_seed)
        LOGGER.info('querying prepare trust for user: %s', pubkey)
        self.call('prepare_trust', 200, 'could not get trust transaction', from_pubkey=pubkey)


class PrepareSendBulsTest(ApiBaseTest):
    """Test for prepare_send_buls endpoint."""

    def test_prepare_send_buls(self):
        """Test preparing transaction for sending BULs."""
        pubkey, _ = self.create_and_setup_new_account()
        LOGGER.info('preparing send buls transaction for user: %s', pubkey)
        self.call(
            'prepare_send_buls', 200, 'can not prepare send from {} to {}'.format(self.funded_pubkey, pubkey),
            from_pubkey=self.funded_pubkey, to_pubkey=pubkey, amount_buls=50000000)


class PrepareEscrowTest(ApiBaseTest):
    """Test for prepare_escrow endpoint."""

    def test_prepare_escrow(self):
        """Test preparing escrow transaction."""
        payment, collateral = 50000000, 100000000
        deadline = int(time.time())
        LOGGER.info('preparing new escrow')
        self.prepare_escrow(payment, collateral, deadline)

    def test_prepare_with_location(self):
        """Test preparing escrow transaction with used optional location arg."""
        payment, collateral = 50000000, 100000000
        deadline = int(time.time())
        location = '-37.4244753,-12.4845718'
        LOGGER.info("preparing new escrow at location: %s", location)
        escrow_pubkey = self.prepare_escrow(payment, collateral, deadline, location)['escrow']
        events = routes.db.get_events(escrow_pubkey[0])
        self.assertEqual(
            len(events), 1,
            "expected 1 event for escrow: {}, {} got instead".format(escrow_pubkey, len(events)))
        self.assertEqual(
            events[0]['location'], location,
            "expected location: {} for escrow: {}, {} got instead".format(
                location, escrow_pubkey, events[0]['location']))


class AcceptPackageTest(ApiBaseTest):
    """Test for accept_package endpoint."""

    def test_accept_package(self):
        """Test accepting package."""
        payment, collateral = 50000000, 100000000
        deadline = int(time.time())
        escrow_stuff = self.prepare_escrow(payment, collateral, deadline)

        self.submit(
            escrow_stuff['transactions']['set_options_transaction'], escrow_stuff['escrow'][1], 'set escrow options')
        self.send(escrow_stuff['launcher'][1], escrow_stuff['escrow'][0], payment)
        self.send(escrow_stuff['courier'][1], escrow_stuff['escrow'][0], collateral)
        for member in (escrow_stuff['courier'], escrow_stuff['recipient']):
            LOGGER.info('accepting package: %s for user %s', escrow_stuff['escrow'][0], member[1])
            self.call(
                'accept_package', 200, 'member could not accept package',
                member[1], escrow_pubkey=escrow_stuff['escrow'][0])
            events = routes.db.get_events(escrow_stuff['escrow'][0])
            expected_event_type = 'couriered' if member == escrow_stuff['courier'] else 'received'
            self.assertEqual(
                events[-1]['event_type'], expected_event_type,
                "'{}' event expected, but '{}' got instead".format(expected_event_type, events[-1]['event_type']))


class MyPackagesTest(ApiBaseTest):
    """Test for my_packages endpoint."""

    def test_my_packages(self):
        """Test getting user packages."""
        account = self.create_and_setup_new_account()
        LOGGER.info('getting packages for new user: %s', account[0])
        packages = self.call(
            path='my_packages', expected_code=200,
            fail_message='does not get ok status code on valid request', seed=account[1],
            user_pubkey=account[0])['packages']
        self.assertTrue(len(packages) == 0)

        payment, collateral = 50000000, 100000000
        deadline = int(time.time())
        escrow_stuff = self.prepare_escrow(payment, collateral, deadline)
        LOGGER.info('querying packages for user: %s', escrow_stuff['launcher'][0])
        packages = self.call(
            path='my_packages', expected_code=200,
            fail_message='does not get ok status code on valid request',
            seed=escrow_stuff['launcher'][1], user_pubkey=escrow_stuff['launcher'][0])['packages']
        self.assertTrue(len(packages) == 1)
        self.assertEqual(packages[0]['deadline'], deadline)
        self.assertEqual(packages[0]['escrow_pubkey'], escrow_stuff['escrow'][0])
        self.assertEqual(packages[0]['collateral'], collateral)
        self.assertEqual(packages[0]['payment'], payment)


class PackageTest(ApiBaseTest):
    """Test for package endpoint."""

    def test_package(self):
        """Test package."""
        payment, collateral = 50000000, 100000000
        deadline = int(time.time())
        LOGGER.info('preparing new escrow')
        escrow_stuff = self.prepare_escrow(payment, collateral, deadline)
        LOGGER.info('getting package with valid escrow pubkey: %s', escrow_stuff['escrow'][0])
        package = self.call(
            path='package', expected_code=200,
            fail_message='does not get ok status code on valid request',
            escrow_pubkey=escrow_stuff['escrow'][0])['package']
        self.assertEqual(package['deadline'], deadline)
        self.assertEqual(package['escrow_pubkey'], escrow_stuff['escrow'][0])
        self.assertEqual(package['collateral'], collateral)
        self.assertEqual(package['payment'], payment)


class AddEventTest(ApiBaseTest):
    """Test for add_event endpoint."""

    def test_add_event(self):
        """Test adding event"""
        payment, collateral = 50000000, 100000000
        deadline = int(time.time())
        LOGGER.info('preparing new escrow')
        escrow_stuff = self.prepare_escrow(payment, collateral, deadline)
        self.call(
            path='add_event', expected_code=200,
            fail_message='could not add event', seed=escrow_stuff['launcher'][1],
            escrow_pubkey=escrow_stuff['escrow'][0], event_type='package launched', location='32.1245, 22.43153')
