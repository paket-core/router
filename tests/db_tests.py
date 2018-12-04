"""Test the PAKET API database."""
import time
import unittest

import paket_stellar
import util.logger

import db

LOGGER = util.logger.logging.getLogger('pkt.router.test')


def create_tables():
    """Create tables if they does not exists"""
    try:
        LOGGER.info('creating tables...')
        db.init_db()
    except db.util.db.mysql.connector.ProgrammingError:
        LOGGER.info('tables already exists')


def clear_tables():
    """Clear all tables in db"""
    assert db.DB_NAME.startswith('test'), "refusing to test on db named {}".format(db.DB_NAME)
    LOGGER.info('clearing database')
    db.util.db.clear_tables(db.SQL_CONNECTION, db.DB_NAME)


class DbBaseTest(unittest.TestCase):
    """Base class for db tests."""

    @classmethod
    def setUpClass(cls):
        """Setting up class fixture before running tests."""
        create_tables()

    def setUp(self):
        """Setting up the test fixture before exercising it."""
        clear_tables()

    @staticmethod
    def generate_keypair():
        """Generate new stellar keypair."""
        keypair = paket_stellar.get_keypair()
        pubkey = keypair.address().decode()
        seed = keypair.seed().decode()
        return pubkey, seed

    def prepare_package_members(self):
        """Prepare launcher, courier, recipient and escrow keys"""
        launcher = self.generate_keypair()
        courier = self.generate_keypair()
        recipient = self.generate_keypair()
        escrow = self.generate_keypair()
        return {
            'launcher': launcher, 'courier': courier,
            'recipient': recipient, 'escrow': escrow}


class CreatePackageTest(DbBaseTest):
    """Creating package test."""

    def test_create_package(self):
        """Creating package test."""
        package_members = self.prepare_package_members()
        package_id = 'package_1'
        db.create_package(
            package_id, package_members['escrow'][0], package_members['launcher'][0], package_members['recipient'][0],
            '+490857461783', '+4904597863891', 50000000, 100000000, time.time(), 'Package description',
            '12.970686,77.595590', '41.156193,-8.637541', 'India Bengaluru', 'Spain Porto', '12.970686,77.595590', None)
        events = db.get_package_events(package_id)
        packages = db.get_packages(package_members['launcher'][0])
        self.assertEqual(len(packages), 1,
                         "should be 1 created package, {} got instead".format(len(packages)))
        self.assertEqual(len(events), 1,
                         "created package should contain 1 event, {} got instead".format(len(events)))
        self.assertEqual(
            packages[0]['package_id'], package_id,
            "stored package_id is: {}, but package was creating with: {}".format(
                packages[0]['package_id'], package_id))
        self.assertEqual(
            packages[0]['escrow_pubkey'], package_members['escrow'][0],
            "stored escrow_pubkey is: {}, but package was creating with: {}".format(
                packages[0]['escrow_pubkey'], package_members['escrow'][0]))
        self.assertEqual(
            packages[0]['launcher_pubkey'], package_members['launcher'][0],
            "stored launcher_pubkey is: {}, but package was creating with: {}".format(
                packages[0]['launcher_pubkey'], package_members['launcher'][0]))
        self.assertEqual(
            packages[0]['recipient_pubkey'], package_members['recipient'][0],
            "stored recipient_pubkey is: {}, but package was creating with: {}".format(
                packages[0]['recipient_pubkey'], package_members['recipient'][0]))
        self.assertEqual(
            events[0]['event_type'], 'launched',
            "created event '{}', but must be 'launched'".format(
                events[0]['event_type']))
        self.assertEqual(
            packages[0]['launch_date'], events[0]['timestamp'],
            "package has launch date {}, but was launched at {}".format(
                packages[0]['launch_date'], events[0]['timestamp']))
        self.assertEqual(
            events[0]['user_pubkey'], package_members['launcher'][0],
            "created event for user: {}, but must be for: {}".format(
                events[0]['user_pubkey'], package_members['launcher'][0]))


class GetPackageTest(DbBaseTest):
    """Getting package test."""

    def test_get_package(self):
        """Getting package test."""
        package_members = self.prepare_package_members()
        package_id = 1
        db.create_package(
            package_id, package_members['escrow'][0], package_members['launcher'][0], package_members['recipient'][0],
            '+490857461783', '+4904597863891', 50000000, 100000000, time.time(), 'Package description',
            '12.970686,77.595590', '41.156193,-8.637541', 'India Bengaluru', 'Spain Porto', '12.970686,77.595590', None)
        package = db.get_package(package_id)
        self.assertEqual(
            package['escrow_pubkey'], package_members['escrow'][0],
            "returned package with escrow_pubkey: {}, but {} expected".format(
                package['escrow_pubkey'], package_members['escrow'][0]))
        self.assertEqual(
            package['launcher_pubkey'], package_members['launcher'][0],
            "returned package with launcher_pubkey: {}, but {} expected".format(
                package['launcher_pubkey'], package_members['launcher'][0]))
        self.assertEqual(
            package['recipient_pubkey'], package_members['recipient'][0],
            "returned package with recipient_pubkey: {}, but {} expected".format(
                package['recipient_pubkey'], package_members['recipient'][0]))

    def test_invalid_package(self):
        """Getting package with invalid package_id"""
        with self.assertRaises(db.UnknownPackage, msg='UnknownPackage was not raised on invalid pubkey'):
            db.get_package('invalid package_id')


class GetPackagesTest(DbBaseTest):
    """Getting packages test."""

    def test_get_packages(self):
        """Getting packages test."""
        for i in range(5):
            package_members = self.prepare_package_members()
            db.create_package(
                i, package_members['escrow'][0], package_members['launcher'][0], package_members['recipient'][0],
                '+490857461783', '+4904597863891', i * 10 ** 7, i * 2 * 10 ** 7, time.time(),
                'Package description', '12.970686,77.595590', '41.156193,-8.637541',
                'India Bengaluru', 'Spain Porto', '12.970686,77.595590', None)
        packages = db.get_packages()
        self.assertEqual(len(packages), 5, "expected 5 packages, {} got instead".format(len(packages)))

    def test_get_user_packages(self):
        """Getting user packages test."""
        user = self.generate_keypair()
        first_package_members = self.prepare_package_members()
        first_package_id, second_package_id, third_package_id = ('package_{}'.format(i) for i in range(3))
        LOGGER.info('creating package with user role: launcher')
        db.create_package(
            first_package_id, first_package_members['escrow'][0], user[0], first_package_members['recipient'][0],
            '+490857461783', '+4904597863891', 50000000, 100000000, time.time(), 'Package description',
            '12.970686,77.595590', '41.156193,-8.637541', 'India Bengaluru', 'Spain Porto', '12.970686,77.595590', None)
        second_package_members = self.prepare_package_members()
        LOGGER.info('creating package with user role: recipient')
        db.create_package(
            second_package_id, second_package_members['escrow'][0], second_package_members['launcher'][0], user[0],
            '+490857461783', '+4904597863891', 50000000, 100000000, time.time(), 'Package description',
            '12.970686,77.595590', '41.156193,-8.637541', 'India Bengaluru', 'Spain Porto', '12.970686,77.595590', None)
        third_package_members = self.prepare_package_members()
        LOGGER.info('creating package with user role: courier')
        db.create_package(
            third_package_id, third_package_members['escrow'][0], third_package_members['launcher'][0],
            third_package_members['recipient'][0], '+490857461783', '+4904597863891',
            50000000, 100000000, time.time(), 'Package description', '12.970686,77.595590', '41.156193,-8.637541',
            'India Bengaluru', 'Spain Porto', '12.970686,77.595590', None)
        db.add_event(user[0], 'couriered', '12.970686,77.595590', third_package_id)

        packages = db.get_packages(user[0])
        self.assertEqual(len(packages), 3, "3 packages expected, {} got instead".format(len(packages)))
        package = next((
            package for package in packages if package['launcher_pubkey'] == user[0]), None)
        self.assertEqual(package['user_role'], 'launcher',
                         "expected role: 'launcher', '{}' got instead".format(package['user_role']))
        self.assertEqual(package['custodian_pubkey'], user[0],
                         "{} expected as custodian, {} got instead".format(user[0], package['custodian_pubkey']))
        package = next((
            package for package in packages if package['recipient_pubkey'] == user[0]), None)
        self.assertEqual(package['user_role'], 'recipient',
                         "expected role: 'recipient', '{}' got instead".format(package['user_role']))
        self.assertEqual(package['custodian_pubkey'], second_package_members['launcher'][0],
                         "{} expected as custodian, {} got instead".format(
                             second_package_members['launcher'][0], package['custodian_pubkey']))
        package = next((
            package for package in packages
            if user[0] not in (package['recipient_pubkey'], package['launcher_pubkey'])), None)
        self.assertEqual(package['user_role'], 'courier',
                         "expected role: 'courier', '{}' got instead".format(package['user_role']))
        self.assertEqual(package['custodian_pubkey'], user[0],
                         "{} expected as custodian, {} got instead".format(user[0], package['custodian_pubkey']))


class AddEventTest(DbBaseTest):
    """Adding event test."""

    def test_add_event(self):
        """Adding event test."""
        package_members = self.prepare_package_members()
        package_id = 'package_1'
        db.create_package(
            package_id, package_members['escrow'][0], package_members['launcher'][0], package_members['recipient'][0],
            '+490857461783', '+4904597863891', 50000000, 100000000, time.time(), 'Package description',
            '12.970686,77.595590', '41.156193,-8.637541', 'India Bengaluru', 'Spain Porto', '12.970686,77.595590', None)
        db.add_event(package_members['courier'][0], 'couriered', '12.970686,77.595590', package_id)
        events = db.get_package_events(package_id)
        self.assertEqual(len(events), 2, "2 events expected, but {} got instead".format(len(events)))
        couriered_event = next((event for event in events if event['event_type'] == 'couriered'), None)
        self.assertIsNotNone(couriered_event, "expected event with event_type: 'couriered', None got instead")
        self.assertEqual(
            couriered_event['user_pubkey'], package_members['courier'][0],
            "expected event with user_pubkey: {}, but {} got instead".format(
                package_members['courier'][0], couriered_event['user_pubkey']))


class GetEventsTest(DbBaseTest):
    """Getting events test."""

    def test_get_events(self):
        """Getting event test."""
        package_members = self.prepare_package_members()
        first_package_id, second_package_id = 'first_package', 'second_package'
        db.create_package(
            first_package_id, package_members['escrow'][0], package_members['launcher'][0],
            package_members['recipient'][0], '+490857461783', '+4904597863891', 50000000, 100000000,
            time.time(), 'Package description', '12.970686,77.595590', '41.156193,-8.637541',
            'India Bengaluru', 'Spain Porto', '12.970686,77.595590', None)
        new_package_members = self.prepare_package_members()
        db.create_package(
            second_package_id, new_package_members['escrow'][0], new_package_members['launcher'][0],
            new_package_members['recipient'][0], '+490857461783', '+4904597863891', 50000000, 100000000,
            time.time(), 'Package description', '12.970686,77.595590', '41.156193,-8.637541',
            'India Bengaluru', 'Spain Porto', '12.970686,77.595590', None)
        for user in new_package_members:
            db.add_event(new_package_members[user][0], 'new event',
                         '12.970686,77.595590', second_package_id)
        events = db.get_package_events(first_package_id)
        self.assertEqual(len(events), 1, "expected 1 event for package: '{}', but '{}' got instead".format(
            package_members['escrow'][0], len(events)))
        events = db.get_package_events(second_package_id)
        self.assertEqual(len(events), 5, "expected 5 events for package: '{}', but '{}' got instead".format(
            package_members['escrow'][0], len(events)))

    def test_get_escrow_events(self):
        """Getting escrow events test."""
        packages_members = [self.prepare_package_members() for _ in range(3)]
        packages = [db.create_package(index, members['escrow'][0], members['launcher'][0], members['recipient'][0],
                                      '+490857461783', '+4904597863891', 50000000, 100000000, time.time(),
                                      'Package description', '12.970686,77.595590', '41.156193,-8.637541',
                                      'India Bengaluru', 'Spain Porto', '12.970686,77.595590', None)
                    for index, members in enumerate(packages_members)]
        for package in packages:
            events = db.get_package_events(package['package_id'])
            self.assertEqual(len(events), 1,
                             "1 event expected for package: {}, but {} got instead".format(
                                 package['package_id'], len(events)))

        for index, package in enumerate(packages):
            for _ in range(index):
                db.add_event(package['launcher_pubkey'], 'new event', '12.970686,77.595590', package['package_id'])
        for index, package in enumerate(packages):
            events = db.get_package_events(package['package_id'])
            self.assertEqual(len(events), index+1, "{} event expected for package: {}, but {} got instead".format(
                index + 1, package['package_id'], len(events)))
