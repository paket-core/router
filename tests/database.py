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
