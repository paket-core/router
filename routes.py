"""JSON swagger API to PaKeT."""
import os

import flasgger
import flask

import util.logger
import util.conversion
import webserver.validation

import db
import swagger_specs

LOGGER = util.logger.logging.getLogger('pkt.router')
VERSION = swagger_specs.VERSION
PORT = os.environ.get('PAKET_ROUTER_PORT', 8000)
BLUEPRINT = flask.Blueprint('router', __name__)


# Input validators and fixers.
webserver.validation.KWARGS_CHECKERS_AND_FIXERS['_timestamp'] = webserver.validation.check_and_fix_natural
webserver.validation.KWARGS_CHECKERS_AND_FIXERS['_buls'] = webserver.validation.check_and_fix_natural
webserver.validation.KWARGS_CHECKERS_AND_FIXERS['_num'] = webserver.validation.check_and_fix_natural
webserver.validation.KWARGS_CHECKERS_AND_FIXERS['_id'] = webserver.validation.check_and_fix_natural


# Internal error codes
webserver.validation.INTERNAL_ERROR_CODES[db.util.geodecoding.GeodecodingError] = 110
webserver.validation.INTERNAL_ERROR_CODES[db.paket_stellar.NotOnTestnet] = 120
webserver.validation.INTERNAL_ERROR_CODES[db.paket_stellar.StellarTransactionFailed] = 200
webserver.validation.INTERNAL_ERROR_CODES[db.paket_stellar.stellar_base.address.AccountNotExistError] = 201
webserver.validation.INTERNAL_ERROR_CODES[db.paket_stellar.TrustError] = 202
webserver.validation.INTERNAL_ERROR_CODES[db.UnknownPackage] = 400


# Package routes.


# pylint: disable=too-many-locals
@BLUEPRINT.route("/v{}/create_package".format(VERSION), methods=['POST'])
@flasgger.swag_from(swagger_specs.CREATE_PACKAGE)
@webserver.validation.call(
    ['escrow_pubkey', 'recipient_pubkey', 'launcher_phone_number', 'recipient_phone_number',
     'payment_buls', 'collateral_buls', 'deadline_timestamp', 'description',
     'from_location', 'to_location', 'from_address', 'to_address', 'event_location'],
    require_auth=True)
def create_package_handler(
        user_pubkey, escrow_pubkey, recipient_pubkey, launcher_phone_number, recipient_phone_number,
        payment_buls, collateral_buls, deadline_timestamp, description,
        from_location, to_location, from_address, to_address, event_location, photo=None):
    """
    Create a package.
    Use this call to create a new package for delivery.
    ---
    :param user_pubkey:
    :param escrow_pubkey:
    :param recipient_pubkey:
    :param launcher_phone_number:
    :param recipient_phone_number:
    :param payment_buls:
    :param collateral_buls:
    :param deadline_timestamp:
    :param description:
    :param from_location:
    :param to_location:
    :param from_address:
    :param to_address:
    :param event_location:
    :param photo:
    :return:
    """
    package_details = db.create_package(
        escrow_pubkey, user_pubkey, recipient_pubkey, launcher_phone_number, recipient_phone_number,
        payment_buls, collateral_buls, deadline_timestamp, description,
        from_location, to_location, from_address, to_address, event_location, photo)
    return {'status': 201, 'package': package_details}
# pylint: enable=too-many-locals


@BLUEPRINT.route("/v{}/accept_package".format(VERSION), methods=['POST'])
@flasgger.swag_from(swagger_specs.ACCEPT_PACKAGE)
@webserver.validation.call(['escrow_pubkey', 'location'], require_auth=True)
def accept_package_handler(user_pubkey, escrow_pubkey, location, kwargs=None, photo=None):
    """
    Accept a package.
    If the package requires collateral, commit it.
    If user is the package's recipient, release all funds from the escrow.
    ---
    :param user_pubkey:
    :param escrow_pubkey:
    :param location:
    :param kwargs:
    :param photo:
    :return:
    """
    db.accept_package(user_pubkey, escrow_pubkey, location, kwargs=kwargs, photo=photo)
    return {'status': 200}


@BLUEPRINT.route("/v{}/confirm_couriering".format(VERSION), methods=['POST'])
@flasgger.swag_from(swagger_specs.CONFIRM_COURIERING)
@webserver.validation.call(['escrow_pubkey'], require_auth=True)
def confirm_couriering_handler(user_pubkey, escrow_pubkey, location, kwargs=None, photo=None):
    """
    Add event to package, which indicates that user became courier.
    ---
    :param user_pubkey:
    :param escrow_pubkey:
    :param location:
    :param kwargs:
    :param photo:
    :return:
    """
    db.confirm_couriering(user_pubkey, escrow_pubkey, location, kwargs=kwargs, photo=photo)
    return {'status': 200, 'package': db.get_package(escrow_pubkey)}


@BLUEPRINT.route("/v{}/assign_xdrs".format(VERSION), methods=['POST'])
@flasgger.swag_from(swagger_specs.ASSIGN_XDRS)
@webserver.validation.call(['escrow_pubkey', 'location', 'kwargs'], require_auth=True)
def assign_xdrs_handler(user_pubkey, escrow_pubkey, location, kwargs, photo=None):
    """
    Assign XDRs transaction to package.
    ---
    :param user_pubkey:
    :param escrow_pubkey:
    :param location:
    :param kwargs:
    :param photo:
    :return:
    """
    db.assign_xdrs(escrow_pubkey, user_pubkey, location, kwargs=kwargs, photo=photo)
    return {'status': 200}


@BLUEPRINT.route("/v{}/available_packages".format(VERSION), methods=['POST'])
@flasgger.swag_from(swagger_specs.AVAILABLE_PACKAGES)
@webserver.validation.call(['location'])
def available_packages(location, radius_num=5):
    """
    Get available for couriering packages with acceptable deadline.
    Packages filtered by distance and launcher solvency.
    ---
    :return:
    """
    return {'status': 200, 'packages': db.get_available_packages(location, radius_num)}


@BLUEPRINT.route("/v{}/request_relay".format(VERSION), methods=['POST'])
@flasgger.swag_from(swagger_specs.REQUEST_RELAY)
@webserver.validation.call(['escrow_pubkey', 'location'], require_auth=True)
def request_relay_handler(user_pubkey, escrow_pubkey, location, kwargs=None, photo=None):
    """
    Add `relay required` event to package
    ---
    :param user_pubkey:
    :param escrow_pubkey:
    :param location:
    :param photo:
    :param kwargs:
    :return:
    """
    db.request_delegation(user_pubkey, escrow_pubkey, location, kwargs=kwargs, photo=photo)
    return {'status': 200}


@BLUEPRINT.route("/v{}/my_packages".format(VERSION), methods=['POST'])
@flasgger.swag_from(swagger_specs.MY_PACKAGES)
@webserver.validation.call(require_auth=True)
def my_packages_handler(user_pubkey):
    """
    Get list of packages concerning the user.
    ---
    :param user_pubkey:
    :return:
    """
    return {'status': 200, 'packages': db.get_packages(user_pubkey)}


@BLUEPRINT.route("/v{}/package".format(VERSION), methods=['POST'])
@flasgger.swag_from(swagger_specs.PACKAGE)
@webserver.validation.call(['escrow_pubkey'])
def package_handler(escrow_pubkey, check_escrow=None):
    """
    Get a full info about a single package.
    ---
    :param escrow_pubkey:
    :param check_escrow:
    :return:
    """
    return {'status': 200, 'package': db.get_package(escrow_pubkey, bool(check_escrow))}


@BLUEPRINT.route("/v{}/package_photo".format(VERSION), methods=['POST'])
@flasgger.swag_from(swagger_specs.PACKAGE_PHOTO)
@webserver.validation.call(['escrow_pubkey'])
def package_photo_handler(escrow_pubkey):
    """
    Get package photo.
    ---
    :param escrow_pubkey:
    :return:
    """
    return {'status': 200, 'package_photo': db.get_package_photo(escrow_pubkey)}


@BLUEPRINT.route("/v{}/event_photo".format(VERSION), methods=['POST'])
@flasgger.swag_from(swagger_specs.EVENT_PHOTO)
@webserver.validation.call
def event_photo_handler(photo_id):
    """
    Get event photo by photo id.
    ---
    :param photo_id:
    :return:
    """
    return {'status': 200, 'event_photo': db.get_event_photo_by_id(photo_id)}


@BLUEPRINT.route("/v{}/add_event".format(VERSION), methods=['POST'])
@flasgger.swag_from(swagger_specs.ADD_EVENT)
@webserver.validation.call(['event_type', 'location'], require_auth=True)
def add_event_handler(user_pubkey, event_type, location, escrow_pubkey=None, kwargs=None, photo=None):
    """
    Add new event for package.
    ---
    :param user_pubkey:
    :param event_type:
    :param location:
    :param escrow_pubkey:
    :param kwargs:
    :param photo:
    :return:
    """
    db.add_event(user_pubkey, event_type, location, escrow_pubkey, kwargs, photo)
    return {'status': 200}


@BLUEPRINT.route("/v{}/changed_location".format(VERSION), methods=['POST'])
@flasgger.swag_from(swagger_specs.CHANGED_LOCATION)
@webserver.validation.call(['escrow_pubkey', 'location'], require_auth=True)
def changed_location_handler(user_pubkey, escrow_pubkey, location, kwargs=None, photo=None):
    """
    Add new `changed_location` event for package.
    ---
    :param user_pubkey:
    :param escrow_pubkey:
    :param location:
    :param kwargs:
    :param photo:
    :return:
    """
    db.changed_location(user_pubkey, location, escrow_pubkey, kwargs=kwargs, photo=photo)
    return {'status': 200}


# Debug routes.


@BLUEPRINT.route("/v{}/debug/create_mock_package".format(VERSION), methods=['POST'])
@flasgger.swag_from(swagger_specs.CREATE_MOCK_PACKAGE)
@webserver.validation.call(
    ['escrow_pubkey', 'launcher_pubkey', 'recipient_pubkey', 'launcher_phone_number', 'recipient_phone_number',
     'payment_buls', 'collateral_buls', 'deadline_timestamp'])
def create_mock_package_handler(
        escrow_pubkey, launcher_pubkey, recipient_pubkey, launcher_phone_number, recipient_phone_number, payment_buls,
        collateral_buls, deadline_timestamp, description='mock_description', from_location='mock_location',
        to_location='mock_location', from_address='mock_address', to_address='mock_address',
        event_location='mock_location', photo=None):
    """
    Create a mock package - for debug only.
    ---
    :param escrow_pubkey:
    :param launcher_pubkey:
    :param recipient_pubkey:
    :param launcher_phone_number:
    :param recipient_phone_number:
    :param payment_buls:
    :param collateral_buls:
    :param deadline_timestamp:
    :param description:
    :param from_location:
    :param to_location:
    :param from_address:
    :param to_address:
    :param event_location:
    :param photo:
    :return:
    """
    return {'status': 201, 'package': db.create_package(
        escrow_pubkey, launcher_pubkey, recipient_pubkey, launcher_phone_number, recipient_phone_number,
        payment_buls, collateral_buls, deadline_timestamp, description,
        from_location, to_location, from_address, to_address, event_location, photo)}


@BLUEPRINT.route("/v{}/debug/packages".format(VERSION), methods=['POST'])
@flasgger.swag_from(swagger_specs.PACKAGES)
@webserver.validation.call
def packages_handler():
    """
    Get list of packages - for debug only.
    ---
    :return:
    """
    return {'status': 200, 'packages': db.get_packages()}


@BLUEPRINT.route("/v{}/events".format(VERSION), methods=['POST'])
@flasgger.swag_from(swagger_specs.EVENTS)
@webserver.validation.call
def events_handler(max_events_num=100):
    """
    Get all events.
    ---
    :param max_events_num:
    :return:
    """
    events = db.get_events(max_events_num)
    package_events = [event for event in events if event['escrow_pubkey'] is not None]

    # Extra data to help client with indexing.
    package_index = {}
    package_event_types = {}
    for idx, event in enumerate(package_events):
        if event['escrow_pubkey'] not in package_index:
            package_index[event['escrow_pubkey']] = []
        if event['escrow_pubkey'] not in package_event_types:
            package_event_types[event['escrow_pubkey']] = []
        package_index[event['escrow_pubkey']].append(idx)
        package_event_types[event['escrow_pubkey']].append(event['event_type'])

    return {'status': 200, 'events': events, 'package_index': package_index, 'package_event_types': package_event_types}


@BLUEPRINT.route("/v{}/debug/log".format(VERSION), methods=['POST'])
@flasgger.swag_from(swagger_specs.LOG)
@webserver.validation.call
def view_log_handler(lines_num=10):
    """
    Get last lines of log - for debug only.
    Specify lines_num to get the x last lines.
    """
    with open(os.path.join(util.logger.LOG_DIR_NAME, util.logger.LOG_FILE_NAME)) as logfile:
        return {'status': 200, 'log': logfile.readlines()[:-1 - lines_num:-1]}
