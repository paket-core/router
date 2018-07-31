"""Data base mock-up for tests purposes"""
import logging
import time

LOGGER = logging.getLogger('pkt.db')
PACKAGES = []
EVENTS = []


class UnknownUser(Exception):
    """Unknown user ID."""


class DuplicateUser(Exception):
    """Duplicate user."""


class UnknownPaket(Exception):
    """Unknown paket ID."""


def init_db():
    """Initialize the database."""
    PACKAGES.clear()
    EVENTS.clear()


def add_event(escrow_pubkey, user_pubkey, event_type, location):
    """Add a package event."""
    EVENTS.append({
        'escrow_pubkey': escrow_pubkey, 'user_pubkey': user_pubkey,
        'event_type': event_type, 'location': location, 'timestamp': time.time()})


def get_events(escrow_pubkey):
    """Get all package events."""
    return sorted(
        [event for event in EVENTS if event['escrow_pubkey'] == escrow_pubkey],
        key=lambda event: event['timestamp'])


def enrich_package(package, user_role=None, user_pubkey=None):
    """Add some periferal data to the package object."""
    package['blockchain_url'] = "https://testnet.stellarchain.io/address/{}".format(package['escrow_pubkey'])
    package['paket_url'] = "https://paket.global/paket/{}".format(package['escrow_pubkey'])
    package['events'] = get_events(package['escrow_pubkey'])
    event_types = set([event['event_type'] for event in package['events']])

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
        escrow_pubkey, launcher_pubkey, recipient_pubkey, payment, collateral, deadline,
        set_options_transaction, refund_transaction, merge_transaction, payment_transaction):
    """Create a new package row."""
    PACKAGES.append({
        'escrow_pubkey': escrow_pubkey, 'launcher_pubkey': launcher_pubkey,
        'recipient_pubkey': recipient_pubkey, 'deadline': deadline, 'payment': payment, 'collateral': collateral,
        'set_options_transaction': set_options_transaction, 'refund_transaction': refund_transaction,
        'merge_transaction': merge_transaction, 'payment_transaction': payment_transaction
    })
    add_event(escrow_pubkey, launcher_pubkey, 'launched', None)
    return enrich_package(get_package(escrow_pubkey))


def get_package(escrow_pubkey):
    """Get package details."""
    try:
        return [package for package in PACKAGES if package['escrow_pubkey'] == escrow_pubkey][0]
    except IndexError:
        raise UnknownPaket("paket {} is not valid".format(escrow_pubkey))


def get_packages(user_pubkey=None):
    """Get a list of packages."""
    if user_pubkey:
        packages = [package for package in PACKAGES
                    if package['launcher_pubkey'] == user_pubkey or package['recipient_pubkey'] == user_pubkey
                    or package['escrow_pubkey'] in [event['escrow_pubkey']
                                                    for event in EVENTS if event['event_type'] == 'couriered'
                                                    and event['user_pubkey'] == user_pubkey]]
        return [
            dict(package, custodian_pubkey=package['events'][-1]['user_pubkey'])
            for package in packages]
    return [enrich_package(package) for package in PACKAGES]
