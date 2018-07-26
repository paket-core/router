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
