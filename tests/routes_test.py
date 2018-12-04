"""Tests for routes module"""
import json
import time
import unittest

import paket_stellar
import stellar_base.keypair
import util.db
import util.logger
import webserver.validation

import routes

LOGGER = util.logger.logging.getLogger('pkt.router.test')
APP = webserver.setup(routes.BLUEPRINT)
APP.testing = True


def create_account():
    """Generate new keypair."""
    LOGGER.info('generating new keypair')
    keypair = stellar_base.Keypair.random()
    address = keypair.address().decode()
    seed = keypair.seed().decode()
    LOGGER.info("keypair generated (%s, %s)", address, seed)
    return address, seed


def clear_tables():
    """Clear all tables in db"""
    assert routes.db.DB_NAME.startswith('test'), "refusing to test on db named {}".format(routes.db.DB_NAME)
    LOGGER.info('clearing database')
    routes.db.util.db.clear_tables(routes.db.SQL_CONNECTION, routes.db.DB_NAME)


class RouterBaseTest(unittest.TestCase):
    """Base class for routes tests."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.app = APP.test_client()
        self.host = 'http://localhost'
        LOGGER.info('init done')

    def setUp(self):
        """Setting up the test fixture before exercising it."""
        try:
            routes.db.init_db()
        except util.db.mysql.connector.ProgrammingError:
            LOGGER.info('tables already exists')
        clear_tables()

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

    def create_package(self, package_id, payment, collateral, deadline, location):
        """Create launcher, courier, recipient, escrow accounts and call create_package."""
        launcher = create_account()
        courier = create_account()
        recipient = create_account()
        escrow = create_account()

        LOGGER.info(
            "creating package: %s, escrow:  %s, launcher: %s, courier: %s, recipient: %s",
            package_id, escrow[0], launcher[0], courier[0], recipient[0])
        package = self.call(
            'create_package', 201, 'can not create package', launcher[1], package_id=package_id,
            escrow_pubkey=escrow[0], recipient_pubkey=recipient[0], launcher_phone_number='+380659731849',
            recipient_phone_number='+380671976311', payment_buls=payment, collateral_buls=collateral,
            deadline_timestamp=deadline, description='Package description', from_location='12.970686,77.595590',
            to_location='41.156193,-8.637541', from_address='India Bengaluru',
            to_address='Spain Porto', event_location=location)

        return {
            'launcher': launcher,
            'courier': courier,
            'recipient': recipient,
            'escrow': escrow,
            'package': package}


class CreatePackageTest(RouterBaseTest):
    """Test for create_package endpoint."""

    def test_create_package(self):
        """Test create_package endpoint."""
        payment, collateral = 50000000, 100000000
        deadline = int(time.time())
        package_id = 'package_1'
        LOGGER.info('creating new package')
        self.create_package(package_id, payment, collateral, deadline, '12.970686,77.595590')

    def test_create_with_location(self):
        """Test create_package endpoint with used optional location arg."""
        payment, collateral = 50000000, 100000000
        deadline = int(time.time())
        location = '-37.4244753,-12.4845718'
        package_id = 'package_1'
        LOGGER.info("preparing new escrow at location: %s", location)
        self.create_package(package_id, payment, collateral, deadline, location)
        events = routes.db.get_package_events(package_id)
        self.assertEqual(
            len(events), 1,
            "expected 1 event for package: {}, {} got instead".format(package_id, len(events)))
        self.assertEqual(
            events[0]['location'], location,
            "expected location: {} for package: {}, {} got instead".format(
                location, package_id, events[0]['location']))


class AcceptPackageTest(RouterBaseTest):
    """Test for accept_package endpoint."""

    def test_accept_package(self):
        """Test accepting package."""
        payment, collateral = 50000000, 100000000
        deadline = int(time.time())
        package_id = 'package_1'
        package = self.create_package(package_id, payment, collateral, deadline, '12.970686,77.595590')
        for member in (package['courier'], package['recipient']):
            LOGGER.info('accepting package: %s for user %s', package_id, member[1])
            self.call(
                'accept_package', 200, 'member could not accept package',
                member[1], package_id=package_id, location='12.970686,77.595590')
            events = routes.db.get_package_events(package_id)
            expected_event_type = 'couriered' if member == package['courier'] else 'received'
            self.assertEqual(
                events[-1]['event_type'], expected_event_type,
                "'{}' event expected, but '{}' got instead".format(expected_event_type, events[-1]['event_type']))


class MyPackagesTest(RouterBaseTest):
    """Test for my_packages endpoint."""

    def test_my_packages(self):
        """Test getting user packages."""
        account = create_account()
        LOGGER.info('getting packages for new user: %s', account[0])
        packages = self.call(
            path='my_packages', expected_code=200,
            fail_message='does not get ok status code on valid request', seed=account[1],
            user_pubkey=account[0])['packages']
        self.assertTrue(len(packages) == 0)

        payment, collateral = 50000000, 100000000
        deadline = int(time.time())
        package_id = 'package_1'
        package = self.create_package(package_id, payment, collateral, deadline, '12.970686,77.595590')
        LOGGER.info('getting packages for user: %s', package['launcher'][0])
        packages = self.call(
            path='my_packages', expected_code=200,
            fail_message='does not get ok status code on valid request',
            seed=package['launcher'][1], user_pubkey=package['launcher'][0])['packages']
        self.assertTrue(len(packages) == 1)
        self.assertEqual(packages[0]['deadline'], deadline)
        self.assertEqual(packages[0]['escrow_pubkey'], package['escrow'][0])
        self.assertEqual(packages[0]['collateral'], collateral)
        self.assertEqual(packages[0]['payment'], payment)


class PackageTest(RouterBaseTest):
    """Test for package endpoint."""

    def test_package(self):
        """Test package."""
        payment, collateral = 50000000, 100000000
        deadline = int(time.time())
        package_id = 'package_1'
        LOGGER.info('preparing new package')
        package = self.create_package(package_id, payment, collateral, deadline, '12.970686,77.595590')
        LOGGER.info('getting package with valid escrow pubkey: %s', package['escrow'][0])
        package_details = self.call(
            path='package', expected_code=200,
            fail_message='does not get ok status code on valid request',
            package_id=package_id)['package']
        self.assertEqual(package_details['deadline'], deadline)
        self.assertEqual(package_details['escrow_pubkey'], package['escrow'][0])
        self.assertEqual(package_details['collateral'], collateral)
        self.assertEqual(package_details['payment'], payment)


class AddEventTest(RouterBaseTest):
    """Test for add_event endpoint."""

    def test_add_event(self):
        """Test adding event"""
        payment, collateral = 50000000, 100000000
        deadline = int(time.time())
        package_id = 'package_1'
        LOGGER.info('preparing new package')
        package = self.create_package(package_id, payment, collateral, deadline, '12.970686,77.595590')
        self.call(
            path='add_event', expected_code=200,
            fail_message='could not add event', seed=package['launcher'][1],
            package_id=package_id, event_type='package launched', location='32.1245, 22.43153')
