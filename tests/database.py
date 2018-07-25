"""Test the PAKET API database."""
import tests


class TestDatabase(tests.unittest.TestCase):
    """Test the API's database."""

    def setUp(self):
        tests.clear_tables()

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





class CreatePackageTest(tests.unittest.TestCase):
    """"""

    def test_create_package(self):
        """"""
