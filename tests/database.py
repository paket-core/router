"""Test the PAKET API database."""
import unittest

import util.logger
import db

LOGGER = util.logger.logging.getLogger('pkt.api.test.db')
util.logger.setup()

class TestDatabase(unittest.TestCase):
    """Test the API's database."""

    def setUp(self):
        assert db.DB_NAME.startswith('test'), "refusing to test on db named {}".format(db.DB_NAME)
        LOGGER.info('clearing database')
        db.util.db.clear_tables(db.SQL_CONNECTION, db.DB_NAME)

    def test_init(self):
        """Test that the db is clean."""
        self.assertEqual(len(db.get_packages()), 0)

    def internal_test_create_package(self, package_kwargs):
        """Test that package is created properly."""
        db.create_package(**package_kwargs)

        # Disable enrich_package, which is only mock data.
        db.enrich_package = lambda x: x
        # Need to add launcher_pubkey which is the custdian
        self.assertDictEqual(
            db.get_package(package_kwargs['escrow_pubkey']), dict(package_kwargs, custodian_pubkey='launcher_pubkey'))


    def test_update_custodian(self):
        """Test update of custodian."""
        package_kwargs = {
            'escrow_pubkey': 'escrow_pubkey',
            'launcher_pubkey': 'launcher_pubkey',
            'recipient_pubkey': 'recipient_pubkey',
            'deadline': 1,
            'payment': 2,
            'collateral': 3,
            'set_options_transaction': 'set_options_transaction',
            'refund_transaction': 'refund_transaction',
            'merge_transaction': 'merge_transaction',
            'payment_transaction': 'payment_transaction'}
        self.internal_test_create_package(package_kwargs)
        new_custodian = 'new_custodian'
        db.update_custodian(package_kwargs['escrow_pubkey'], new_custodian)
        self.assertDictEqual(
            db.get_package(package_kwargs['escrow_pubkey']), dict(package_kwargs, custodian_pubkey=new_custodian))
