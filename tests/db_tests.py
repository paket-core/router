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
            events[0]['paket_user'], package_members['launcher'][0],
            "created event for user: {}, but must be for: {}".format(
                events[0]['paket_user'], package_members['launcher'][0]))
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
        user = self.generate_keypair()
        package_members = self.prepare_package_members()
        tests.LOGGER.info('creating package with user role: launcher')
        tests.db.create_package(
            package_members['escrow'][0], user[0], package_members['recipient'][0],
            time.time(), 50000000, 100000000, None, None, None, None)
        package_members = self.prepare_package_members()
        tests.LOGGER.info('creating package with user role: recipient')
        tests.db.create_package(
            package_members['escrow'][0], package_members['launcher'][0], user[0],
            time.time(), 50000000, 100000000, None, None, None, None)
        package_members = self.prepare_package_members()
        tests.LOGGER.info('creating package with user role: courier')
        tests.db.create_package(
            package_members['escrow'][0], package_members['launcher'][0], package_members['recipient'][0],
            time.time(), 50000000, 100000000, None, None, None, None)
        tests.db.add_event(package_members['escrow'][0], user[0], 'couriered', None)

        packages = tests.db.get_packages(user[0])
        self.assertIn('launched', packages, 'result does not contained launched packages')
        self.assertIn('received', packages, 'result does not contained received packages')
        self.assertIn('couriered', packages, 'result does not contained couriered packages')
        self.assertEqual(
            len(packages['launched']), 1,
            "expected 1 launched package, {} got instead".format(len(packages['launched'])))
        self.assertEqual(
            len(packages['received']), 1,
            "expected 1 received package, {} got instead".format(len(packages['received'])))
        self.assertEqual(
            len(packages['couriered']), 1,
            "expected 1 couriered package, {} got instead".format(len(packages['couriered'])))
