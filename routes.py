"""Routes for Routing Server API."""
import datetime
import os

import flasgger
import flask

import util.logger
import util.conversion
import webserver.validation

import db
import swagger_specs

LOGGER = util.logger.logging.getLogger('pkt.router.routes')
VERSION = swagger_specs.VERSION
PORT = os.environ.get('PAKET_ROUTER_PORT', 8000)
BLUEPRINT = flask.Blueprint('router', __name__)


# Input validators and fixers.
webserver.validation.KWARGS_CHECKERS_AND_FIXERS['_timestamp'] = webserver.validation.check_and_fix_natural
webserver.validation.KWARGS_CHECKERS_AND_FIXERS['_buls'] = webserver.validation.check_and_fix_natural
webserver.validation.KWARGS_CHECKERS_AND_FIXERS['_num'] = webserver.validation.check_and_fix_natural
# temporary disable checker for pacjage_id
# webserver.validation.KWARGS_CHECKERS_AND_FIXERS['_id'] = webserver.validation.check_and_fix_natural
webserver.validation.CUSTOM_EXCEPTION_STATUSES[db.UnknownPackage] = 404


# Internal error codes
webserver.validation.INTERNAL_ERROR_CODES[db.util.geodecoding.GeodecodingError] = 110
webserver.validation.INTERNAL_ERROR_CODES[db.paket_stellar.NotOnTestnet] = 120
webserver.validation.INTERNAL_ERROR_CODES[db.paket_stellar.StellarTransactionFailed] = 200
webserver.validation.INTERNAL_ERROR_CODES[db.paket_stellar.TrustError] = 202
webserver.validation.INTERNAL_ERROR_CODES[db.UnknownPackage] = 400


# Package routes.


# pylint: disable=too-many-locals
@BLUEPRINT.route("/v{}/create_package".format(VERSION), methods=['POST'])
@flasgger.swag_from(swagger_specs.CREATE_PACKAGE)
@webserver.validation.call(
    ['recipient_pubkey', 'launcher_phone_number', 'recipient_phone_number',
     'payment_buls', 'collateral_buls', 'deadline_timestamp', 'description',
     'from_location', 'to_location', 'from_address', 'to_address', 'event_location'],
    require_auth=True)
def create_package_handler(
        user_pubkey, recipient_pubkey, launcher_phone_number, recipient_phone_number,
        payment_buls, collateral_buls, deadline_timestamp, description, from_location, to_location,
        from_address, to_address, event_location, package_id=None, escrow_pubkey=None, photo=None):
    """
    Create a package.
    Use this call to create a new package for delivery.
    ---
    :param user_pubkey:
    :param package_id:
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
    # optional both package_id and escrow_pubkey args is temporary measure
    if not package_id and not escrow_pubkey:
        raise AssertionError('specify at least one of package_id or escrow_pubkey')
    elif package_id and escrow_pubkey:
        warning = {}
    else:
        # pylint: disable=unused-variable
        arg_name, arg, missed_arg_name, missed_arg = (
            'package_id', package_id, 'escrow_pubkey', escrow_pubkey) if package_id else (
                'escrow_pubkey', escrow_pubkey, 'package_id', package_id)
        # used only for its side effect
        missed_arg = arg
        # pylint: enable=unused-variable
        warning_message = "{} missed and replaced with {} value: {}".format(missed_arg_name, arg_name, arg)
        LOGGER.warning(warning_message)
        warning = {'warning': warning_message}

    package_details = db.create_package(
        package_id, escrow_pubkey, user_pubkey, recipient_pubkey, launcher_phone_number, recipient_phone_number,
        payment_buls, collateral_buls, deadline_timestamp, description,
        from_location, to_location, from_address, to_address, event_location, photo)
    response = {'status': 201, 'package': package_details}
    if warning:
        response.update(warning)
    return response
# pylint: enable=too-many-locals


@BLUEPRINT.route("/v{}/accept_package".format(VERSION), methods=['POST'])
@flasgger.swag_from(swagger_specs.ACCEPT_PACKAGE)
@webserver.validation.call(['package_id', 'location'], require_auth=True)
def accept_package_handler(user_pubkey, package_id, location, kwargs=None, photo=None):
    """
    Accept a package.
    If the package requires collateral, commit it.
    If user is the package's recipient, release all funds from the escrow.
    ---
    :param user_pubkey:
    :param package_id:
    :param location:
    :param kwargs:
    :param photo:
    :return:
    """
    db.accept_package(user_pubkey, package_id, location, kwargs=kwargs, photo=photo)
    return {'status': 200}


@BLUEPRINT.route("/v{}/confirm_couriering".format(VERSION), methods=['POST'])
@flasgger.swag_from(swagger_specs.CONFIRM_COURIERING)
@webserver.validation.call(['package_id'], require_auth=True)
def confirm_couriering_handler(user_pubkey, package_id, location, kwargs=None, photo=None):
    """
    Add event to package, which indicates that user became courier.
    ---
    :param user_pubkey:
    :param package_id:
    :param location:
    :param kwargs:
    :param photo:
    :return:
    """
    db.confirm_couriering(user_pubkey, package_id, location, kwargs=kwargs, photo=photo)
    return {'status': 200, 'package': db.get_package(package_id)}


@BLUEPRINT.route("/v{}/assign_xdrs".format(VERSION), methods=['POST'])
@flasgger.swag_from(swagger_specs.ASSIGN_XDRS)
@webserver.validation.call(['package_id', 'location', 'kwargs'], require_auth=True)
def assign_xdrs_handler(user_pubkey, package_id, location, kwargs, photo=None):
    """
    Assign XDRs transaction to package.
    ---
    :param user_pubkey:
    :param package_id:
    :param location:
    :param kwargs:
    :param photo:
    :return:
    """
    db.assign_xdrs(package_id, user_pubkey, location, kwargs=kwargs, photo=photo)
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
@webserver.validation.call(['package_id', 'location'], require_auth=True)
def request_relay_handler(user_pubkey, package_id, location, kwargs=None, photo=None):
    """
    Add `relay required` event to package
    ---
    :param user_pubkey:
    :param package_id:
    :param location:
    :param photo:
    :param kwargs:
    :return:
    """
    db.request_relay(user_pubkey, package_id, location, kwargs=kwargs, photo=photo)
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
@webserver.validation.call(['package_id'])
def package_handler(package_id, check_escrow=None):
    """
    Get a full info about a single package.
    ---
    :param package_id:
    :param check_escrow:
    :return:
    """
    return {'status': 200, 'package': db.get_package(package_id, bool(check_escrow))}


@BLUEPRINT.route("/v{}/package_photo".format(VERSION), methods=['POST'])
@flasgger.swag_from(swagger_specs.PACKAGE_PHOTO)
@webserver.validation.call(['package_id'])
def package_photo_handler(package_id):
    """
    Get package photo.
    ---
    :param package_id:
    :return:
    """
    return {'status': 200, 'package_photo': db.get_package_photo(package_id)}


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
def add_event_handler(user_pubkey, event_type, location, package_id=None, kwargs=None, photo=None):
    """
    Add new event for package.
    ---
    :param user_pubkey:
    :param event_type:
    :param location:
    :param package_id:
    :param kwargs:
    :param photo:
    :return:
    """
    db.add_event(user_pubkey, event_type, location, package_id, kwargs, photo)
    return {'status': 200}


@BLUEPRINT.route("/v{}/changed_location".format(VERSION), methods=['POST'])
@flasgger.swag_from(swagger_specs.CHANGED_LOCATION)
@webserver.validation.call(['package_id', 'location'], require_auth=True)
def changed_location_handler(user_pubkey, package_id, location, kwargs=None, photo=None):
    """
    Add new `changed_location` event for package.
    ---
    :param user_pubkey:
    :param package_id:
    :param location:
    :param kwargs:
    :param photo:
    :return:
    """
    db.changed_location(user_pubkey, location, package_id, kwargs=kwargs, photo=photo)
    return {'status': 200}


@BLUEPRINT.route("/v{}/set_notification_token".format(VERSION), methods=['POST'])
@flasgger.swag_from(swagger_specs.SET_NOTIFICATION_TOKEN)
@webserver.validation.call(['notification_token'], require_auth=True)
def set_notification_token_handler(user_pubkey, notification_token):
    """
    Set notification token.
    """
    db.set_notification_token(user_pubkey, notification_token)
    return {'status': 200}


@BLUEPRINT.route("/v{}/remove_notification_token".format(VERSION), methods=['POST'])
@flasgger.swag_from(swagger_specs.REMOVE_NOTIFICATION_TOKEN)
@webserver.validation.call(['notification_token'], require_auth=True)
def remove_notification_token_handler(user_pubkey, notification_token):
    """
    Remove notification token.
    """
    db.remove_notification_token(user_pubkey, notification_token)
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
        escrow_pubkey, escrow_pubkey, launcher_pubkey, recipient_pubkey, launcher_phone_number, recipient_phone_number,
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
def events_handler(from_timestamp=None, till_timestamp=None):
    """
    Get all events.
    ---
    :param from_timestamp:
    :param till_timestamp:
    :return:
    """
    events = db.get_events(from_timestamp or 0, till_timestamp or datetime.datetime.now().timestamp())
    package_events = [event for event in events if event['package_id'] is not None]

    # Extra data to help client with indexing.
    event_indexes_by_package = {}
    event_types_by_package = {}
    for idx, event in enumerate(package_events):
        if event['package_id'] not in event_indexes_by_package:
            event_indexes_by_package[event['package_id']] = []
        if event['package_id'] not in event_types_by_package:
            event_types_by_package[event['package_id']] = []
        event_indexes_by_package[event['package_id']].append(idx)
        event_types_by_package[event['package_id']].append(event['event_type'])

    return {
        'status': 200, 'events': events,
        'event_indexes_by_package': event_indexes_by_package,
        'event_types_by_package': event_types_by_package}


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
