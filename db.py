"""PaKeT database interface."""
import logging
import os
import random

import util.db

LOGGER = logging.getLogger('pkt.db')
DB_HOST = os.environ.get('PAKET_DB_HOST', '127.0.0.1')
DB_PORT = int(os.environ.get('PAKET_DB_PORT', 3306))
DB_USER = os.environ.get('PAKET_DB_USER', 'root')
DB_PASSWORD = os.environ.get('PAKET_DB_PASSWORD')
DB_NAME = os.environ.get('PAKET_DB_NAME', 'paket')
SQL_CONNECTION = util.db.custom_sql_connection(DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME)


def enrich_package(package):
    """Add some mock data to the package."""
    return dict(
        package,
        blockchain_url="https://testnet.stellarchain.io/address/{}".format(package['launcher_pubkey']),
        paket_url="https://paket.global/paket/{}".format(package['escrow_pubkey']),
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


def init_db():
    """Initialize the database."""
    with SQL_CONNECTION() as sql:
        sql.execute('''
            CREATE TABLE packages(
                escrow_pubkey VARCHAR(56) UNIQUE,
                launcher_pubkey VARCHAR(56),
                recipient_pubkey VARCHAR(56),
                deadline INTEGER,
                payment INTEGER,
                collateral INTEGER,
                set_options_transaction VARCHAR(1024),
                refund_transaction VARCHAR(1024),
                merge_transaction VARCHAR(1024),
                payment_transaction VARCHAR(1024))''')
        LOGGER.debug('packages table created')
        sql.execute('''
            CREATE TABLE custodians(
                timestamp TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
                escrow_pubkey VARCHAR(56),
                custodian_pubkey VARCHAR(56),
                FOREIGN KEY(escrow_pubkey) REFERENCES packages(escrow_pubkey))''')
        LOGGER.debug('custodians table created')


def create_package(
        escrow_pubkey, launcher_pubkey, recipient_pubkey, deadline, payment, collateral,
        set_options_transaction, refund_transaction, merge_transaction, payment_transaction):
    """Create a new package row."""
    with SQL_CONNECTION() as sql:
        sql.execute("""
            INSERT INTO packages (
                escrow_pubkey, launcher_pubkey, recipient_pubkey, deadline, payment, collateral,
                set_options_transaction, refund_transaction, merge_transaction, payment_transaction
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""", (
                escrow_pubkey, launcher_pubkey, recipient_pubkey, deadline, payment, collateral,
                set_options_transaction, refund_transaction, merge_transaction, payment_transaction))
        sql.execute("INSERT INTO custodians (escrow_pubkey, custodian_pubkey) VALUES (%s, %s)", (
            escrow_pubkey, launcher_pubkey))


def get_package(escrow_pubkey):
    """Get package details."""
    with SQL_CONNECTION() as sql:
        sql.execute(
            "SELECT custodian_pubkey FROM custodians WHERE escrow_pubkey = %s ORDER BY timestamp DESC LIMIT 1",
            (escrow_pubkey,))
        custodian_pubkey = sql.fetchall()[0]['custodian_pubkey']
        sql.execute("SELECT * FROM packages WHERE escrow_pubkey = %s", (escrow_pubkey,))
        try:
            return dict(enrich_package(sql.fetchone()), custodian_pubkey=custodian_pubkey)
        except TypeError:
            raise UnknownPaket("paket {} is not valid".format(escrow_pubkey))


def get_packages(user_pubkey=None):
    """Get a list of packages."""
    with SQL_CONNECTION() as sql:
        if user_pubkey:
            sql.execute("""
                SELECT * FROM packages
                WHERE escrow_pubkey IN (
                    SELECT escrow_pubkey FROM custodians WHERE custodian_pubkey = %s)
                OR launcher_pubkey = %s
                OR recipient_pubkey = %s""", (user_pubkey, user_pubkey, user_pubkey))
        else:
            sql.execute('SELECT * FROM packages')
        return [enrich_package(row) for row in sql.fetchall()]


def update_custodian(escrow_pubkey, custodian_pubkey):
    """Update a package's custodian."""
    with SQL_CONNECTION() as sql:
        sql.execute("INSERT INTO custodians (escrow_pubkey, custodian_pubkey) VALUES (%s, %s)", (
            escrow_pubkey, custodian_pubkey))
