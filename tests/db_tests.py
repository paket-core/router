"""Test the PAKET API database."""
import time

import tests


class CreatePackageTest(tests.DbBaseTest):
    """Creating package test."""

    def test_create_package(self):
        """Creating package test."""
        package_members = self.prepare_package_members()
        tests.db.create_package(
            package_members['escrow'][0], package_members['launcher'][0], package_members['recipient'][0],
            time.time(), 50000000, 100000000, None, None, None, None)
        with tests.db.SQL_CONNECTION() as sql:
            sql.execute('SELECT * FROM packages')
            packages = sql.fetchall()
            sql.execute('SELECT * FROM events')
            events = sql.fetchall()
        self.assertEqual(len(packages), 1, '')
        self.assertEqual(len(events), 1, '')
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
            events[0]['user_pubkey'], package_members['launcher'][0],
            "created event for user: {}, but must be for: {}".format(
                events[0]['user_pubkey'], package_members['launcher'][0]))
        self.assertEqual(
            events[0]['escrow_pubkey'], package_members['escrow'][0],
            "created event for escrow: {}, but must be for: {}".format(
                events[0]['escrow_pubkey'], package_members['escrow'][0]))


class GetPackageTest(tests.DbBaseTest):
    """Getting package test."""

    def test_get_package(self):
        """Getting package test."""
        package_members = self.prepare_package_members()
        tests.db.create_package(
            package_members['escrow'][0], package_members['launcher'][0], package_members['recipient'][0],
            time.time(), 50000000, 100000000, None, None, None, None)
        package = tests.db.get_package(package_members['escrow'][0])
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
        """Getting package with invalid pubkey"""
        with self.assertRaises(tests.db.UnknownPaket, msg='UnknownPaket was not raised on invalid pubkey'):
            tests.db.get_package('invalid pubkey')


class GetPackagesTest(tests.DbBaseTest):
    """Getting packages test."""

    def test_get_packages(self):
        """Getting packages test."""
        for i in range(5):
            package_members = self.prepare_package_members()
            tests.db.create_package(
                package_members['escrow'][0], package_members['launcher'][0], package_members['recipient'][0],
                time.time(), i * 10 ** 7, i * 2 * 10 ** 7, None, None, None, None)
        packages = tests.db.get_packages()
        self.assertEqual(len(packages), 5, "expected 5 packages, {} got instead".format(len(packages)))

    def test_get_user_packages(self):
        """Getting user packages test."""
        user = self.generate_keypair()
        first_package_members = self.prepare_package_members()
        tests.LOGGER.info('creating package with user role: launcher')
        tests.db.create_package(
            first_package_members['escrow'][0], user[0], first_package_members['recipient'][0],
            time.time(), 50000000, 100000000, None, None, None, None)
        second_package_members = self.prepare_package_members()
        tests.LOGGER.info('creating package with user role: recipient')
        tests.db.create_package(
            second_package_members['escrow'][0], second_package_members['launcher'][0], user[0],
            time.time(), 50000000, 100000000, None, None, None, None)
        third_package_members = self.prepare_package_members()
        tests.LOGGER.info('creating package with user role: courier')
        tests.db.create_package(
            third_package_members['escrow'][0], third_package_members['launcher'][0],
            third_package_members['recipient'][0], time.time(), 50000000, 100000000, None, None, None, None)
        tests.db.add_event(third_package_members['escrow'][0], user[0], 'couriered', None)

        packages = tests.db.get_packages(user[0])
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


class AddEventTest(tests.DbBaseTest):
    """Adding event test."""

    def test_add_event(self):
        """Adding event test."""
        package_members = self.prepare_package_members()
        tests.db.create_package(
            package_members['escrow'][0], package_members['launcher'][0], package_members['recipient'][0],
            time.time(), 50000000, 100000000, None, None, None, None)
        tests.db.add_event(package_members['escrow'][0], package_members['courier'][0], 'couriered', None)
        events = tests.db.get_events(package_members['escrow'][0])
        self.assertEqual(len(events), 2, "2 events expected, but {} got instead".format(len(events)))
        couriered_event = next((event for event in events if event['event_type'] == 'couriered'), None)
        self.assertIsNotNone(couriered_event, "expected event with event_type: 'couriered', None got instead")
        self.assertEqual(
            couriered_event['user_pubkey'], package_members['courier'][0],
            "expected event with user_pubkey: {}, but {} got instead".format(
                package_members['courier'][0], couriered_event['user_pubkey']))


class GetEventsTest(tests.DbBaseTest):
    """Getting events test."""

    def test_get_events(self):
        """Getting event test."""
        package_members = self.prepare_package_members()
        tests.db.create_package(
            package_members['escrow'][0], package_members['launcher'][0], package_members['recipient'][0],
            time.time(), 50000000, 100000000, None, None, None, None)
        new_package_members = self.prepare_package_members()
        tests.db.create_package(
            new_package_members['escrow'][0], new_package_members['launcher'][0], new_package_members['recipient'][0],
            time.time(), 50000000, 100000000, None, None, None, None)
        for user in new_package_members:
            tests.db.add_event(new_package_members['escrow'][0], user[0], 'new event', None)
        events = tests.db.get_events(package_members['escrow'][0])
        self.assertEqual(len(events), 1, "expected 1 event for package: '{}', but '{}' got instead".format(
            package_members['escrow'][0], len(events)))
        events = tests.db.get_events(new_package_members['escrow'][0])
        self.assertEqual(len(events), 5, "expected 5 events for package: '{}', but '{}' got instead".format(
            package_members['escrow'][0], len(events)))

    def test_get_escrow_events(self):
        """Getting escrow events test."""
        packages_members = [self.prepare_package_members() for _ in range(3)]
        for members in packages_members:
            tests.db.create_package(
                members['escrow'][0], members['launcher'][0], members['recipient'][0],
                time.time(), 50000000, 100000000, None, None, None, None)
        for members in packages_members:
            events = tests.db.get_events(members['escrow'][0])
            self.assertEqual(len(events), 1, "1 event expected for escrow: {}, but {} got instead".format(
                members['escrow'][0], len(events)))

        for index, members in enumerate(packages_members):
            for _ in range(index):
                tests.db.add_event(members['escrow'][0], members['courier'][0], 'couriered', None)
        for index, members in enumerate(packages_members):
            events = tests.db.get_events(members['escrow'][0])
            self.assertEqual(len(events), index+1, "{} event expected for escrow: {}, but {} got instead".format(
                index + 1, members['escrow'][0], len(events)))
