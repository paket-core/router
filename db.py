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
        paket_url="https://paket.global/paket/{}".format(package['paket_id']),
        deadline=random.randint(1523530844, 1555066871),
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
        sql.execute('SELECT name FROM sqlite_master WHERE type = "table" AND name = "users"')
        if len(sql.fetchall()) == 1:
            LOGGER.debug('database already exists')
            return
        sql.execute('''
            CREATE TABLE users(
                pubkey VARCHAR(42) PRIMARY KEY,
                full_name VARCHAR(256),
                phone_number VARCHAR(32),
                paket_user VARCHAR(32) UNIQUE NOT NULL)''')
        LOGGER.debug('users table created')
        sql.execute('''
            CREATE TABLE packages(
                paket_id VARCHAR(42) UNIQUE,
                launcher_pubkey VARCHAR(42),
                recipient_pubkey VARCHAR(42),
                custodian_pubkey VARCHAR(42),
                deadline INTEGER,
                payment INTEGER,
                collateral INTEGER,
                refund_transaction VARCHAR(1024),
                payment_transaction VARCHAR(1024),
                kwargs VARCHAR(1024))''')
        LOGGER.debug('packages table created')
        # This table should vanish once we are in production.
        sql.execute('''
            CREATE TABLE keys(
                pubkey VARCHAR(42) PRIMARY KEY,
                seed VARCHAR(42) UNIQUE)''')
        LOGGER.warning('keys table created')


def get_pubkey_from_paket_user(paket_user):
    """
    Get the pubkey associated with a paket_user. Raise exception if paket_user is unknown.
    For debug only.
    """
    LOGGER.warning("getting key for %s", paket_user)
    with sql_connection() as sql:
        sql.execute('SELECT pubkey FROM users WHERE paket_user = ?', (paket_user,))
        try:
            return sql.fetchone()[0]
        except TypeError:
            raise UnknownUser("unknown user {}".format(paket_user))


def create_user(pubkey, paket_user, seed=None):
    """Create a new user."""
    with sql_connection() as sql:
        try:
            sql.execute("INSERT INTO users (pubkey, paket_user) VALUES (?, ?)", (pubkey, paket_user))
            if seed is not None:
                sql.execute("INSERT INTO keys (pubkey, seed) VALUES (?, ?)", (pubkey, seed))
        except sqlite3.IntegrityError as exception:
            bad_column_name = str(exception).split('.')[-1]
            bad_value = locals().get(bad_column_name)
            raise DuplicateUser("{} {} is non unique".format(bad_column_name, bad_value))


def get_user(pubkey):
    """Get user details."""
    with sql_connection() as sql:
        sql.execute("""
            SELECT * FROM users
            LEFT JOIN keys on users.pubkey = keys.pubkey
            WHERE users.pubkey = ?""", (pubkey,))
        user = sql.fetchone()
        if user is None:
            raise UnknownUser("Unknown user with pubkey {}".format(pubkey))
        return {key: user[key] for key in user.keys()} if user else None


def update_user_details(pubkey, full_name, phone_number):
    """Update user details."""
    with sql_connection() as sql:
        sql.execute("""
            UPDATE users SET
            full_name = ?,
            phone_number = ?
            WHERE pubkey = ?""", (full_name, phone_number, pubkey))
    return get_user(pubkey)


def get_users():
    """Get list of users and their details - for debug only."""
    with sql_connection() as sql:
        sql.execute('SELECT * FROM users')
        users = sql.fetchall()
    return {user['pubkey']: {key: user[key] for key in user.keys() if key != 'pubkey'} for user in users}


def create_package(
        paket_id, launcher_pubkey, recipient_pubkey, deadline, payment, collateral,
        refund_transaction, payment_transaction):
    """Create a new package row."""
    with sql_connection() as sql:
        sql.execute("""
            INSERT INTO packages (
                paket_id, launcher_pubkey, recipient_pubkey, custodian_pubkey, deadline, payment, collateral,
                refund_transaction, payment_transaction
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""", (
                paket_id, launcher_pubkey, recipient_pubkey, launcher_pubkey, deadline, payment, collateral,
                refund_transaction, payment_transaction))


def get_package(paket_id):
    """Get package details."""
    with sql_connection() as sql:
        sql.execute("SELECT * FROM packages WHERE paket_id = ?", (paket_id,))
        try:
            return enrich_package(sql.fetchone())
        except TypeError:
            raise UnknownPaket("paket {} is not valid".format(paket_id))


def get_packages():
    """Get a list of packages."""
    with sql_connection() as sql:
        sql.execute('SELECT paket_id, launcher_pubkey, custodian_pubkey, recipient_pubkey FROM packages')
        return [enrich_package(row) for row in sql.fetchall()]


def update_custodian(paket_id, custodian_pubkey):
    """Update a package's custodian."""
    with sql_connection() as sql:
        sql.execute("UPDATE packages SET custodian_pubkey = ? WHERE paket_id = ?", (custodian_pubkey, paket_id))
