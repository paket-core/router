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
        events=get_events(package['escrow_pubkey']))


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
            CREATE TABLE events(
                event_type VARCHAR(20),
                timestamp TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
                location VARCHAR(22),
                paket_user VARCHAR(56),
                escrow_pubkey VARCHAR(56),
                FOREIGN KEY(escrow_pubkey) REFERENCES packages(escrow_pubkey))''')
        LOGGER.debug('events table created')


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


def get_package(escrow_pubkey):
    """Get package details."""
    with SQL_CONNECTION() as sql:
        sql.execute("SELECT * FROM packages WHERE escrow_pubkey = %s", (escrow_pubkey,))
        try:
            return dict(enrich_package(sql.fetchone()))
        except TypeError:
            raise UnknownPaket("paket {} is not valid".format(escrow_pubkey))


def get_packages(user_pubkey=None):
    """Get a list of packages."""
    with SQL_CONNECTION() as sql:
        if user_pubkey:
            sql.execute("""
                SELECT * FROM packages
                WHERE launcher_pubkey = %s
                OR recipient_pubkey = %s""", (user_pubkey, user_pubkey))
        else:
            sql.execute('SELECT * FROM packages')
        return [enrich_package(row) for row in sql.fetchall()]


def add_event(escrow_pubkey, user_pubkey, event_type, location):
    """Add a package event."""
    with SQL_CONNECTION() as sql:
        sql.execute("""
            INSERT INTO events (event_type, location, paket_user, escrow_pubkey)
            VALUES (%s, %s, %s, %s)
        """, (event_type, location, user_pubkey, escrow_pubkey))


def get_events(escrow_pubkey):
    """Get all package events."""
    with SQL_CONNECTION() as sql:
        sql.execute("""
            SELECT * FROM events WHERE escrow_pubkey = %s
            ORDER BY timestamp ASC""", (escrow_pubkey,))
        return [{
            key.decode('utf8') if isinstance(key, bytes) else key: val for key, val in event.items()}
                for event in sql.fetchall()]
