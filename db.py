"""PaKeT database interface."""
import logging
import os

import util.db

LOGGER = logging.getLogger('pkt.db')
DB_HOST = os.environ.get('PAKET_DB_HOST', '127.0.0.1')
DB_PORT = int(os.environ.get('PAKET_DB_PORT', 3306))
DB_USER = os.environ.get('PAKET_DB_USER', 'root')
DB_PASSWORD = os.environ.get('PAKET_DB_PASSWORD')
DB_NAME = os.environ.get('PAKET_DB_NAME', 'paket')
SQL_CONNECTION = util.db.custom_sql_connection(DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME)


class UnknownUser(Exception):
    """Unknown user ID."""


class DuplicateUser(Exception):
    """Duplicate user."""


class UnknownPaket(Exception):
    """Unknown paket ID."""


def jsonable(list_of_dicts):
    """Fix for mysql-connector bug which makes sql.fetchall() return some keys as (unjsonable) bytes."""
    return [{
        key.decode('utf8') if isinstance(key, bytes) else key: val for key, val in dict_.items()}
            for dict_ in list_of_dicts]


def init_db():
    """Initialize the database."""
    with SQL_CONNECTION() as sql:
        sql.execute('''
            CREATE TABLE packages(
                escrow_pubkey VARCHAR(56) UNIQUE,
                launcher_pubkey VARCHAR(56),
                recipient_pubkey VARCHAR(56),
                launcher_contact VARCHAR(32),
                recipient_contact VARCHAR(32),
                payment INTEGER,
                collateral INTEGER,
                deadline INTEGER,
                description VARCHAR(300),
                photo BLOB NULL,
                from_location VARCHAR(24),
                to_location VARCHAR(24))''')
        LOGGER.debug('packages table created')
        sql.execute('''
            CREATE TABLE events(
                timestamp TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
                user_pubkey VARCHAR(56) NOT NULL, 
                event_type VARCHAR(20) NOT NULL, 
                location VARCHAR(24) NOT NULL, 
                escrow_pubkey VARCHAR(56) NULL, 
                kwargs LONGTEXT NULL,
                FOREIGN KEY(escrow_pubkey) REFERENCES packages(escrow_pubkey))''')
        LOGGER.debug('events table created')


def add_event(user_pubkey, event_type, location, escrow_pubkey=None, kwargs=None):
    """Add a package event."""
    with SQL_CONNECTION() as sql:
        sql.execute("""
            INSERT INTO events (user_pubkey, event_type, location, escrow_pubkey, kwargs)
            VALUES (%s, %s, %s, %s, %s)
        """, (user_pubkey, event_type, location, escrow_pubkey, kwargs))


def get_events(max_events_num):
    """Get all user and package events up to a limit."""
    with SQL_CONNECTION() as sql:
        sql.execute("SELECT * FROM events LIMIT %s", (int(max_events_num),))
        events = jsonable(sql.fetchall())
        return {
            'packages_events': [event for event in events if event['escrow_pubkey'] is not None],
            'user_events': [event for event in events if event['escrow_pubkey'] is None]}


def get_package_events(escrow_pubkey):
    """Get a list of events relating to a package."""
    with SQL_CONNECTION() as sql:
        sql.execute("""
                    SELECT timestamp, user_pubkey, event_type, location, kwargs FROM events
                    WHERE escrow_pubkey = %s
                    ORDER BY timestamp ASC""", (escrow_pubkey,))
        return jsonable(sql.fetchall())


def enrich_package(package, user_role=None, user_pubkey=None):
    """Add some periferal data to the package object."""
    package['blockchain_url'] = "https://testnet.stellarchain.io/address/{}".format(package['escrow_pubkey'])
    package['paket_url'] = "https://paket.global/paket/{}".format(package['escrow_pubkey'])
    package['events'] = get_package_events(package['escrow_pubkey'])
    event_types = {event['event_type'] for event in package['events']}
    package['launch_date'] = package['events'][0]['timestamp']

    if 'received' in event_types:
        package['status'] = 'delivered'
    elif 'couriered' in event_types:
        package['status'] = 'in transit'
    elif 'launched' in event_types:
        package['status'] = 'waiting pickup'
    else:
        package['status'] = 'unknown'

    if user_role:
        package['user_role'] = user_role
    elif user_pubkey:
        if user_pubkey == package['launcher_pubkey']:
            package['user_role'] = 'launcher'
        elif user_pubkey == package['recipient_pubkey']:
            package['user_role'] = 'recipient'
        else:
            package['user_role'] = 'unknown'

    return package


def create_package(
        escrow_pubkey, launcher_pubkey, recipient_pubkey, launcher_contact, recipient_contact,
        payment, collateral, deadline, description, from_location, to_location, event_location, photo=None):
    """Create a new package row."""
    with SQL_CONNECTION() as sql:
        sql.execute("""
            INSERT INTO packages (
                escrow_pubkey, launcher_pubkey, recipient_pubkey, launcher_contact, recipient_contact,
                payment, collateral, deadline, description, phone, from_location, to_location
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""", (
                escrow_pubkey, launcher_pubkey, recipient_pubkey, launcher_contact, recipient_contact,
                payment, collateral, deadline, description, photo, from_location, to_location))
    add_event(launcher_pubkey, 'launched', event_location, escrow_pubkey)
    return enrich_package(get_package(escrow_pubkey))


def get_package(escrow_pubkey):
    """Get package details."""
    with SQL_CONNECTION() as sql:
        sql.execute("SELECT * FROM packages WHERE escrow_pubkey = %s", (escrow_pubkey,))
        try:
            return enrich_package(sql.fetchone())
        except TypeError:
            raise UnknownPaket("paket {} is not valid".format(escrow_pubkey))


def get_packages(user_pubkey=None):
    """Get a list of packages."""
    with SQL_CONNECTION() as sql:
        if user_pubkey:
            sql.execute("""
            SELECT * FROM packages
            WHERE launcher_pubkey = %s""", (user_pubkey,))
            launched = [enrich_package(row, user_role='launcher') for row in sql.fetchall()]
            sql.execute("""
            SELECT * FROM packages
            WHERE recipient_pubkey = %s""", (user_pubkey,))
            received = [enrich_package(row, user_role='recipient') for row in sql.fetchall()]
            sql.execute("""
            SELECT * FROM packages
            WHERE escrow_pubkey IN (
                SELECT escrow_pubkey FROM events
                WHERE event_type = 'couriered' AND user_pubkey = %s)""", (user_pubkey,))
            couriered = [enrich_package(row, user_role='courier') for row in sql.fetchall()]
            return [
                dict(package, custodian_pubkey=package['events'][-1]['user_pubkey'])
                for package in launched + received + couriered]
        sql.execute('SELECT * FROM packages')
        return [enrich_package(row) for row in sql.fetchall()]
