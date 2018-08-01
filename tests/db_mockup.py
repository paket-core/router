"""Data base mock-up for tests purposes"""
import logging
import time

import db

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
    return db.enrich_package(get_package(escrow_pubkey))


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
    return [db.enrich_package(package) for package in PACKAGES]
