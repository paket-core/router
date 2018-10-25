"""PaKeT database interface."""
import base64
import json
import logging
import os
import time

import paket_stellar
import util.db
import util.distance
import util.geodecoding

import events
import notifications

LOGGER = logging.getLogger('pkt.db')
DB_HOST = os.environ.get('PAKET_DB_HOST', '127.0.0.1')
DB_PORT = int(os.environ.get('PAKET_DB_PORT', 3306))
DB_USER = os.environ.get('PAKET_DB_USER', 'root')
DB_PASSWORD = os.environ.get('PAKET_DB_PASSWORD')
DB_NAME = os.environ.get('PAKET_DB_NAME', 'paket')
SQL_CONNECTION = util.db.custom_sql_connection(DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME)

notifications.NOTIFICATION_CODES[events.LAUNCHED] = 100
notifications.NOTIFICATION_CODES[events.COURIER_CONFIRMED] = 101
notifications.NOTIFICATION_CODES[events.COURIERED] = 102
notifications.NOTIFICATION_CODES[events.RELAY_REQUIRED] = 103
notifications.NOTIFICATION_CODES[events.RECEIVED] = 104
notifications.NOTIFICATION_CODES[events.LOCATION_CHANGED] = 105
notifications.NOTIFICATION_CODES[events.ESCROW_XDRS_ASSIGNED] = 110
notifications.NOTIFICATION_CODES[events.RELAY_XDRS_ASSIGNED] = 111


class UnknownPackage(Exception):
    """Unknown package ID."""


def jsonable(list_of_dicts):
    """Fix for mysql-connector bug which makes sql.fetchall() return some keys as (unjsonable) bytes."""
    return [{
        key.decode('utf8') if isinstance(key, bytes) else key: val for key, val in dict_.items()
    } for dict_ in list_of_dicts]


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
                payment BIGINT,
                collateral BIGINT,
                deadline INTEGER,
                description VARCHAR(300),
                from_location VARCHAR(24),
                to_location VARCHAR(24),
                from_address VARCHAR(200),
                to_address VARCHAR(200))''')
        LOGGER.debug('packages table created')
        sql.execute('''
            CREATE TABLE events(
                timestamp TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
                user_pubkey VARCHAR(56) NOT NULL,
                event_type VARCHAR(20) NOT NULL,
                location VARCHAR(24) NOT NULL,
                escrow_pubkey VARCHAR(56) NULL,
                kwargs LONGTEXT NULL,
                photo_id INTEGER NULL,
                FOREIGN KEY(escrow_pubkey) REFERENCES packages(escrow_pubkey))''')
        LOGGER.debug('events table created')
        sql.execute('''
            CREATE TABLE photos(
                photo_id INTEGER NOT NULL AUTO_INCREMENT PRIMARY KEY,
                escrow_pubkey VARCHAR(56) NOT NULL,
                event_type VARCHAR(20) NOT NULL,
                photo LONGTEXT NOT NULL)''')
        LOGGER.debug('photos table created')


def accept_package(user_pubkey, escrow_pubkey, location, kwargs=None, photo=None):
    """Accept a package."""
    package = get_package(escrow_pubkey)
    event_type = events.RECEIVED if package['recipient_pubkey'] == user_pubkey else events.COURIERED
    add_event(user_pubkey, event_type, location, escrow_pubkey, kwargs=kwargs, photo=photo)


def confirm_couriering(user_pubkey, escrow_pubkey, location, kwargs=None, photo=None):
    """Add event to package, which indicates that user became courier."""
    add_event(user_pubkey, events.COURIER_CONFIRMED, location, escrow_pubkey, kwargs=kwargs, photo=photo)


def send_notification(event_type, escrow_pubkey):
    """Send notification to users."""
    if not escrow_pubkey or event_type not in (
            events.LAUNCHED, events.COURIER_CONFIRMED, events.COURIERED, events.RECEIVED):
        return

    package = get_package(escrow_pubkey)
    notification_body = 'Please check your Packages archive for more details'
    notification_code = notifications.NOTIFICATION_CODES[event_type]
    if event_type == events.LAUNCHED:
        notifications.send_notifications(
            tokens=get_active_tokens(package['recipient_pubkey']),
            title="You have new package {}".format(package['short_package_id']),
            body=notification_body,
            notification_code=notification_code,
            short_package_id=package['short_package_id'])
    elif event_type == events.COURIER_CONFIRMED:
        notifications.send_notifications(
            tokens=get_active_tokens(package['launcher_pubkey']),
            title="Courier confirmed for package {}".format(package['short_package_id']),
            body=notification_body,
            notification_code=notification_code,
            short_package_id=package['short_package_id'])
    elif event_type == events.COURIERED:
        notifications.send_notifications(
            tokens=get_active_tokens(package['recipient_pubkey']),
            title="Your package {} in transit".format(package['short_package_id']),
            body=notification_body,
            notification_code=notification_code,
            short_package_id=package['short_package_id'])
    elif event_type == events.RECEIVED:
        notifications.send_notifications(
            tokens=get_active_tokens(package['launcher_pubkey']),
            title="Your package {} delivered".format(package['short_package_id']),
            body=notification_body,
            notification_code=notification_code,
            short_package_id=package['short_package_id'])


def add_event(user_pubkey, event_type, location, escrow_pubkey=None, kwargs=None, photo=None):
    """Add a package event."""
    with SQL_CONNECTION() as sql:
        photo_id = None
        if photo is not None:
            photo = base64.b64encode(photo)
            sql.execute("""
                INSERT INTO photos (escrow_pubkey, event_type, photo)
                VALUES (%s, %s, %s)""", (escrow_pubkey, event_type, photo))
            sql.execute('SELECT photo_id FROM photos ORDER BY photo_id DESC LIMIT 1')
            photo_id = sql.fetchone()['photo_id']

        sql.execute("""
            INSERT INTO events (user_pubkey, event_type, location, escrow_pubkey, kwargs, photo_id)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (user_pubkey, event_type, location, escrow_pubkey, kwargs, photo_id))
    send_notification(event_type, escrow_pubkey)


def assign_xdrs(escrow_pubkey, user_pubkey, location, kwargs, photo=None):
    """Assign XDR transactions to package."""
    package = get_package(escrow_pubkey)
    if user_pubkey == package['launcher_pubkey']:
        if package['escrow_xdrs'] is not None:
            raise AssertionError('package already has escrow XDRs')
        add_event(user_pubkey, events.ESCROW_XDRS_ASSIGNED, location, escrow_pubkey, kwargs, photo=photo)
    elif user_pubkey in [event['user_pubkey']
                         for event in package['events'] if event['event_type'] == events.COURIERED]:
        add_event(user_pubkey, events.RELAY_XDRS_ASSIGNED, location, escrow_pubkey, kwargs, photo=photo)
    else:
        raise AssertionError('user unauthorized to assign XDRs')


def request_relay(user_pubkey, escrow_pubkey, location, kwargs, photo=None):
    """Add `relay required` event."""
    # check if package exist
    get_package(escrow_pubkey)
    add_event(user_pubkey, events.RELAY_REQUIRED, location, escrow_pubkey, kwargs=kwargs, photo=photo)


def get_events(max_events_num):
    """Get all user and package events up to a limit."""
    with SQL_CONNECTION() as sql:
        sql.execute("SELECT * FROM events LIMIT %s", (int(max_events_num),))
        return jsonable(sql.fetchall())


def get_package_events(escrow_pubkey):
    """Get a list of events relating to a package."""
    with SQL_CONNECTION() as sql:
        sql.execute("""
            SELECT timestamp, user_pubkey, event_type, location, kwargs, photo_id
            FROM events
            WHERE escrow_pubkey = %s
            ORDER BY timestamp ASC""", (escrow_pubkey,))
        return jsonable(sql.fetchall())


def set_package_status(package, event_types):
    """Set package status depending on package events."""
    if events.RECEIVED in event_types:
        package['status'] = 'delivered'
    elif events.COURIERED in event_types:
        package['status'] = 'in transit'
    elif events.LAUNCHED in event_types:
        package['status'] = 'waiting pickup'
    else:
        package['status'] = 'unknown'


def set_short_package_id(package):
    """Set short package id, based on country code of destination and last three letters of package id."""
    try:
        country_code = util.geodecoding.gps_to_country_code(package['to_location'])
    except util.geodecoding.GeodecodingError as exc:
        LOGGER.error(str(exc))
        country_code = ''
    three_letters_code = package['escrow_pubkey'][-3:]
    package['short_package_id'] = "{}-{}".format(country_code or 'XX', three_letters_code)


def set_user_role(package, user_role, user_pubkey):
    """Set user role."""
    if user_role:
        package['user_role'] = user_role
    elif user_pubkey:
        if user_pubkey == package['launcher_pubkey']:
            package['user_role'] = 'launcher'
        elif user_pubkey == package['recipient_pubkey']:
            package['user_role'] = 'recipient'
        elif user_pubkey in [event['user_pubkey']
                             for event in package['events'] if event['event_type'] == events.COURIERED]:
            package['user_role'] = 'courier'
        else:
            package['user_role'] = 'unknown'


def extract_xdrs(package):
    """Extract XDR transactions from package events."""
    escrow_xdrs_event = next(
        (event for event in package['events'] if event['event_type'] == events.ESCROW_XDRS_ASSIGNED), None)
    package['escrow_xdrs'] = json.loads(
        escrow_xdrs_event['kwargs'])['escrow_xdrs'] if escrow_xdrs_event is not None else None
    relay_xdrs_events = [json.loads(event['kwargs'])['relay_xdrs']
                         for event in package['events'] if event['event_type'] == events.RELAY_XDRS_ASSIGNED]
    package['relays_xdrs'] = relay_xdrs_events


def enrich_package(package, user_role=None, user_pubkey=None, check_solvency=False, check_escrow=False):
    """Add some periferal data to the package object."""
    package['blockchain_url'] = "https://testnet.steexp.com/account/{}#signing".format(package['escrow_pubkey'])
    package['paket_url'] = "https://paket.global/paket/{}".format(package['escrow_pubkey'])
    package['events'] = get_package_events(package['escrow_pubkey'])
    event_types = {event['event_type'] for event in package['events']}
    if package['events']:
        package['custodian_pubkey'] = package['events'][-1]['user_pubkey']
        launch_event = next((event for event in package['events'] if event['event_type'] == events.LAUNCHED), None)
        package['launch_date'] = launch_event['timestamp'] if launch_event is not None else None
    else:
        package['custodian_pubkey'] = None
        package['launch_date'] = None
        LOGGER.warning("eventless package: %s", package)

    extract_xdrs(package)
    set_package_status(package, event_types)
    set_user_role(package, user_role, user_pubkey)
    set_short_package_id(package)

    if check_solvency:
        launcher_account = paket_stellar.get_bul_account(package['launcher_pubkey'])
        package['launcher_solvency'] = launcher_account['bul_balance'] >= package['payment']

    if check_escrow:
        escrow_account = paket_stellar.get_bul_account(package['escrow_pubkey'])
        package['payment_deposited'] = escrow_account['bul_balance'] >= package['payment']
        package['collateral_deposited'] = escrow_account['bul_balance'] >= package['payment'] + package['collateral']
        package['correctly_deposited'] = escrow_account['bul_balance'] == package['payment'] + package['collateral']

    return package


# pylint: disable=too-many-locals
def create_package(
        escrow_pubkey, launcher_pubkey, recipient_pubkey, launcher_contact, recipient_contact, payment, collateral,
        deadline, description, from_location, to_location, from_address, to_address, event_location, photo=None):
    """Create a new package row."""
    with SQL_CONNECTION() as sql:
        sql.execute("""
            INSERT INTO packages (
                escrow_pubkey, launcher_pubkey, recipient_pubkey, launcher_contact, recipient_contact, payment,
                collateral, deadline, description, from_location, to_location, from_address, to_address
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""", (
                escrow_pubkey, launcher_pubkey, recipient_pubkey, launcher_contact, recipient_contact, payment,
                collateral, deadline, description, from_location, to_location, from_address, to_address))
    add_event(launcher_pubkey, events.LAUNCHED, event_location, escrow_pubkey, photo=photo)
    return get_package(escrow_pubkey)
# pylint: enable=too-many-locals


def get_package(escrow_pubkey, check_escrow=False):
    """Get package details."""
    with SQL_CONNECTION() as sql:
        sql.execute("SELECT * FROM packages WHERE escrow_pubkey = %s", (escrow_pubkey,))
        try:
            return enrich_package(sql.fetchone(), check_escrow=check_escrow)
        except TypeError:
            raise UnknownPackage("paket {} is not valid".format(escrow_pubkey))


def get_available_packages(location, radius=5):
    """Get available packages with acceptable deadline."""
    with SQL_CONNECTION() as sql:
        current_time = int(time.time())
        sql.execute("""
            SELECT escrow_pubkey as package_escrow_pubkey, packages.* FROM packages
            HAVING ((
                SELECT event_type FROM events
                WHERE escrow_pubkey = package_escrow_pubkey AND event_type != %s
                ORDER BY timestamp DESC LIMIT 1)
                IN (%s, %s))
            AND deadline > %s""", (events.LOCATION_CHANGED, events.LAUNCHED, events.RELAY_REQUIRED, current_time))
        packages = [enrich_package(row, check_solvency=True) for row in sql.fetchall()]
        filtered_by_location = [package for package in packages if util.distance.haversine(
            location, package['from_location']) <= radius]
        return filtered_by_location


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
                WHERE event_type IN(%s, %s) AND user_pubkey = %s)""",
                        (events.COURIERED, events.COURIER_CONFIRMED, user_pubkey))
            couriered = [enrich_package(row, user_role='courier') for row in sql.fetchall()]
            return launched + received + couriered
        sql.execute('SELECT * FROM packages')
        return [enrich_package(row) for row in sql.fetchall()]


def get_event_photo_by_id(photo_id):
    """Get event photo by photo id."""
    with SQL_CONNECTION() as sql:
        sql.execute('''
            SELECT * FROM photos
            WHERE photo_id = %s''', (photo_id,))
        try:
            return sql.fetchall()[0]
        except IndexError:
            return None


def get_event_photos(escrow_pubkey, event_type):
    """Get event photos."""
    with SQL_CONNECTION() as sql:
        sql.execute('''
            SELECT * FROM photos
            WHERE escrow_pubkey = %s AND event_type = %s''', (escrow_pubkey, event_type))
        return sql.fetchall()


def get_package_photo(escrow_pubkey):
    """Get package photo."""
    event_photos = get_event_photos(escrow_pubkey, 'launched')
    return event_photos[0] if event_photos else None


def changed_location(user_pubkey, location, escrow_pubkey, kwargs=None, photo=None):
    """Add new `location changed` event for package."""
    add_event(user_pubkey, events.LOCATION_CHANGED, location, escrow_pubkey, kwargs=kwargs, photo=photo)


def get_active_tokens(user_pubkey):
    """Get all active user notification tokens."""
    with SQL_CONNECTION() as sql:
        sql.execute('''
            SELECT DISTINCT token AS notification_token FROM notification_tokens
            WHERE user_pubkey = %s
            HAVING ((
                SELECT active FROM notification_tokens
                WHERE user_pubkey = %s
                AND token = notification_token
                ORDER BY timestamp DESC LIMIT 1) = TRUE)''', (user_pubkey, user_pubkey))
        return [row['notification_token'] for row in sql.fetchall()]
