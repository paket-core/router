"""Tests for routes module"""
import time

import tests


class SubmitTransactionTest(tests.BaseOperations):
    """Test for submit_transaction route."""

    def test_submit_signed(self):
        """Test submitting signed transactions."""
        keypair = tests.paket_stellar.get_keypair()
        new_pubkey = keypair.address().decode()
        new_seed = keypair.seed().decode()

        # checking create_account transaction
        unsigned_account = self.call(
            'prepare_account', 200, 'could not get create account transaction',
            from_pubkey=self.funded_pubkey, new_pubkey=new_pubkey)['transaction']
        signed_account = self.sign_transaction(unsigned_account, self.funded_seed)
        tests.LOGGER.info('Submitting signed create_account transaction')
        self.call(
            path='submit_transaction', expected_code=200,
            fail_message='unexpected server response for submitting signed create_account transaction',
            seed=self.funded_seed, transaction=signed_account)

        # checking trust transaction
        unsigned_trust = self.call(
            'prepare_trust', 200, 'could not get trust transaction', from_pubkey=new_pubkey)['transaction']
        signed_trust = self.sign_transaction(unsigned_trust, new_seed)
        tests.LOGGER.info('Submitting signed trust transaction')
        self.call(
            path='submit_transaction', expected_code=200,
            fail_message='unexpected server response for submitting signed trust transaction',
            seed=new_seed, transaction=signed_trust)

        # checking send_buls transaction
        unsigned_send_buls = self.call(
            'prepare_send_buls', 200, "can not prepare send from {} to {}".format(self.funded_pubkey, new_pubkey),
            from_pubkey=self.funded_pubkey, to_pubkey=new_pubkey, amount_buls=5)['transaction']
        signed_send_buls = self.sign_transaction(unsigned_send_buls, self.funded_seed)
        tests.LOGGER.info('Submitting signed send_buls transaction')
        self.call(
            path='submit_transaction', expected_code=200,
            fail_message='unexpected server response for submitting signed send_buls transaction',
            seed=self.funded_seed, transaction=signed_send_buls)


class BulAccountTest(tests.BaseOperations):
    """Test for bul_account endpoint."""

    def test_bul_account(self):
        """Test getting existing account."""
        accounts = [self.funded_pubkey]
        # additionally create 3 new accounts
        for _ in range(3):
            keypair = tests.paket_stellar.get_keypair()
            pubkey = keypair.address().decode()
            seed = keypair.seed().decode()
            self.create_account(from_pubkey=self.funded_pubkey, new_pubkey=pubkey, seed=self.funded_seed)
            self.trust(pubkey, seed)
            accounts.append(pubkey)

        for account in accounts:
            with self.subTest(account=account):
                tests.LOGGER.info('getting information about account: %s', account)
                self.call('bul_account', 200, 'could not verify account exist', queried_pubkey=account)


class PrepareAccountTest(tests.BaseOperations):
    """Test for prepare_account endpoint."""

    def test_prepare_account(self):
        """Test preparing transaction for creating account."""
        keypair = tests.paket_stellar.get_keypair()
        pubkey = keypair.address().decode()
        tests.LOGGER.info('preparing create account transaction for public key: %s', pubkey)
        self.call(
            'prepare_account', 200, 'could not get create account transaction',
            from_pubkey=self.funded_pubkey, new_pubkey=pubkey)


class PrepareTrustTest(tests.BaseOperations):
    """Test for prepare_trust endpoint."""

    def test_prepare_trust(self):
        """Test preparing transaction for trusting BULs."""
        keypair = tests.paket_stellar.get_keypair()
        pubkey = keypair.address().decode()
        self.create_account(from_pubkey=self.funded_pubkey, new_pubkey=pubkey, seed=self.funded_seed)
        tests.LOGGER.info('querying prepare trust for user: %s', pubkey)
        self.call('prepare_trust', 200, 'could not get trust transaction', from_pubkey=pubkey)


class PrepareSendBulsTest(tests.BaseOperations):
    """Test for prepare_send_buls endpoint."""

    def test_prepare_send_buls(self):
        """Test preparing transaction for sending BULs."""
        pubkey, _ = self.create_and_setup_new_account()
        tests.LOGGER.info('preparing send buls transaction for user: %s', pubkey)
        self.call(
            'prepare_send_buls', 200, 'can not prepare send from {} to {}'.format(self.funded_pubkey, pubkey),
            from_pubkey=self.funded_pubkey, to_pubkey=pubkey, amount_buls=50000000)


class PrepareEscrowTest(tests.BaseOperations):
    """Test for prepare_escrow endpoint."""

    def test_prepare_escrow(self):
        """Test preparing escrow transaction."""
        payment, collateral = 50000000, 100000000
        deadline = int(time.time())
        tests.LOGGER.info('preparing new escrow')
        self.prepare_escrow(payment, collateral, deadline)


class AcceptPackageTest(tests.BaseOperations):
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
            tests.LOGGER.info('accepting package: %s for user %s', escrow_stuff['escrow'][0], member[1])
            self.call(
                'accept_package', 200, 'member could not accept package',
                member[1], escrow_pubkey=escrow_stuff['escrow'][0])


class MyPackagesTest(tests.BaseOperations):
    """Test for my_packages endpoint."""

    def test_my_packages(self):
        """Test getting user packages."""
        account = self.create_and_setup_new_account()
        tests.LOGGER.info('getting packages for new user: %s', account[0])
        packages = self.call(
            path='my_packages', expected_code=200,
            fail_message='does not get ok status code on valid request', seed=account[1],
            user_pubkey=account[0])['packages']
        self.assertTrue(len(packages) == 0)

        payment, collateral = 50000000, 100000000
        deadline = int(time.time())
        escrow_stuff = self.prepare_escrow(payment, collateral, deadline)
        tests.LOGGER.info('querying packages for user: %s', escrow_stuff['launcher'][0])
        packages = self.call(
            path='my_packages', expected_code=200,
            fail_message='does not get ok status code on valid request',
            seed=escrow_stuff['launcher'][1], user_pubkey=escrow_stuff['launcher'][0])['packages']
        self.assertTrue(len(packages) == 1)
        self.assertEqual(packages[0]['deadline'], deadline)
        self.assertEqual(packages[0]['escrow_pubkey'], escrow_stuff['escrow'][0])
        self.assertEqual(packages[0]['collateral'], collateral)
        self.assertEqual(packages[0]['payment'], payment)


class PackageTest(tests.BaseOperations):
    """Test for package endpoint."""

    def test_package(self):
        """Test package."""
        payment, collateral = 50000000, 100000000
        deadline = int(time.time())
        tests.LOGGER.info('preparing new escrow')
        escrow_stuff = self.prepare_escrow(payment, collateral, deadline)
        tests.LOGGER.info('getting package with valid escrow pubkey: %s', escrow_stuff['escrow'][0])
        package = self.call(
            path='package', expected_code=200,
            fail_message='does not get ok status code on valid request',
            escrow_pubkey=escrow_stuff['escrow'][0])['package']
        self.assertEqual(package['deadline'], deadline)
        self.assertEqual(package['escrow_pubkey'], escrow_stuff['escrow'][0])
        self.assertEqual(package['collateral'], collateral)
        self.assertEqual(package['payment'], payment)


class AddEventTest(tests.BaseOperations):
    """Test for add_event endpoint."""

    def test_add_event(self):
        """Test adding event"""
        payment, collateral = 50000000, 100000000
        deadline = int(time.time())
        tests.LOGGER.info('preparing new escrow')
        escrow_stuff = self.prepare_escrow(payment, collateral, deadline)
        self.call(
            path='add_event', expected_code=200,
            fail_message='could not add event', seed=escrow_stuff['launcher'][1],
            escrow_pubkey=escrow_stuff['escrow'][0], event_type='package launched', location='32.1245, 22.43153')
