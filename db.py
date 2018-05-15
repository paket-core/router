"""PaKeT database interface."""
import contextlib
import logging
import random
import sqlite3

LOGGER = logging.getLogger('pkt.db')
DB_NAME = 'paket.db'


def enrich_package(package):
    """Add some mock data to the package."""
    return dict(
        package,
        blockchain_url="https://testnet.stellarchain.io/address/{}".format(package['launcher_pubkey']),
        paket_url="https://paket.global/paket/{}".format(package['escrow_pubkey']),
        my_role=random.choice(['launcher', 'courier', 'recipient']),
        status=random.choice(['waiting pickup', 'in transit', 'delivered']),
        events=[dict(
            event_type=random.choice(['change custodian', 'in transit', 'passed customs']),
            timestamp=random.randint(1523530844, 1535066871),
            paket_user=random.choice(['Israel', 'Oren', 'Chen']),
            GPS=(random.uniform(-180, 180), random.uniform(-90, 90))
        ) for i in range(10)])


class UnknownUser(Exception):
    """Unknown user ID."""


class DuplicateUser(Exception):
    """Duplicate user."""


class UnknownPaket(Exception):
    """Unknown paket ID."""


@contextlib.contextmanager
def sql_connection(db_name=None):
    """Context manager for querying the database."""
    try:
        connection = sqlite3.connect(db_name or DB_NAME)
        connection.row_factory = sqlite3.Row
        yield connection.cursor()
        connection.commit()
    except sqlite3.Error as db_exception:
        raise db_exception
    finally:
        if 'connection' in locals():
            # noinspection PyUnboundLocalVariable
            connection.close()


def init_db():
    """Initialize the database."""
    with sql_connection() as sql:
        # Not using IF EXISTS here in case we want different handling.
        sql.execute('SELECT name FROM sqlite_master WHERE type = "table" AND name = "packages"')
        if len(sql.fetchall()) == 1:
            LOGGER.debug('database already exists')
            return
        sql.execute('''
            CREATE TABLE packages(
                escrow_pubkey VARCHAR(42) UNIQUE,
                launcher_pubkey VARCHAR(42),
                recipient_pubkey VARCHAR(42),
                custodian_pubkey VARCHAR(42),
                deadline INTEGER,
                payment INTEGER,
                collateral INTEGER,
                set_options_transaction VARCHAR(1024),
                refund_transaction VARCHAR(1024),
                merge_transaction VARCHAR(1024),
                payment_transaction VARCHAR(1024),
                kwargs VARCHAR(1024))''')
        LOGGER.debug('packages table created')


def create_package(
        escrow_pubkey, launcher_pubkey, recipient_pubkey, deadline, payment, collateral,
        set_options_transaction, refund_transaction, merge_transaction, payment_transaction):
    """Create a new package row."""
    with sql_connection() as sql:
        sql.execute("""
            INSERT INTO packages (
                escrow_pubkey, launcher_pubkey, recipient_pubkey, custodian_pubkey, deadline, payment, collateral,
                set_options_transaction, refund_transaction, merge_transaction, payment_transaction
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", (
                escrow_pubkey, launcher_pubkey, recipient_pubkey, launcher_pubkey, deadline, payment, collateral,
                set_options_transaction, refund_transaction, merge_transaction, payment_transaction))


def get_package(escrow_pubkey):
    """Get package details."""
    with sql_connection() as sql:
        sql.execute("SELECT * FROM packages WHERE escrow_pubkey = ?", (escrow_pubkey,))
        try:
            return enrich_package(sql.fetchone())
        except TypeError:
            raise UnknownPaket("paket {} is not valid".format(escrow_pubkey))


def get_packages(user_pubkey=None):
    """Get a list of packages."""
    with sql_connection() as sql:
        if user_pubkey:
            sql.execute("""
                SELECT * FROM packages
                WHERE launcher_pubkey = ?
                OR courier_pubkey = ?
                OR recipient_pubkey = ?
                OR custodian_pubkey = ?
            """, (user_pubkey, user_pubkey, user_pubkey, user_pubkey))
        else:
            sql.execute('SELECT * FROM packages')
        return [enrich_package(row) for row in sql.fetchall()]


def update_custodian(escrow_pubkey, custodian_pubkey):
    """Update a package's custodian."""
    with sql_connection() as sql:
        sql.execute(
            "UPDATE packages SET custodian_pubkey = ? WHERE escrow_pubkey = ?", (custodian_pubkey, escrow_pubkey))
