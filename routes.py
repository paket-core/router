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


# Package routes.


@BLUEPRINT.route("/v{}/create_package".format(VERSION), methods=['POST'])
@flasgger.swag_from(swagger_specs.CREATE_PACKAGE)
@webserver.validation.call(
    ['escrow_pubkey', 'recipient_pubkey', 'payment_buls', 'collateral_buls', 'deadline_timestamp',
     'set_options_transaction', 'refund_transaction', 'payment_transaction', 'merge_transaction'],
    require_auth=True)
def create_package_handler(
        user_pubkey, escrow_pubkey, recipient_pubkey, payment_buls, collateral_buls, deadline_timestamp,
        set_options_transaction, refund_transaction, merge_transaction, payment_transaction, location=None):
    """
    Create a package.
    Use this call to create a new package for delivery.
    ---
    :param user_pubkey:
    :param escrow_pubkey:
    :param recipient_pubkey:
    :param payment_buls:
    :param collateral_buls:
    :param deadline_timestamp:
    :param set_options_transaction:
    :param refund_transaction:
    :param merge_transaction:
    :param payment_transaction:
    :param location:
    :return:
    """
    package_details = db.create_package(
        escrow_pubkey, user_pubkey, recipient_pubkey, payment_buls, collateral_buls, deadline_timestamp,
        set_options_transaction, refund_transaction, merge_transaction, payment_transaction, location)
    return dict(status=201, package=package_details)


@BLUEPRINT.route("/v{}/accept_package".format(VERSION), methods=['POST'])
@flasgger.swag_from(swagger_specs.ACCEPT_PACKAGE)
@webserver.validation.call(['escrow_pubkey'], require_auth=True)
def accept_package_handler(user_pubkey, escrow_pubkey, location=None):
    """
    Accept a package.
    If the package requires collateral, commit it.
    If user is the package's recipient, release all funds from the escrow.
    ---
    :param user_pubkey:
    :param escrow_pubkey:
    :param location:
    :return:
    """
    package = db.get_package(escrow_pubkey)
    event_type = 'received' if package['recipient_pubkey'] == user_pubkey else 'couriered'
    db.add_event(escrow_pubkey, user_pubkey, event_type, location)
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
    packages = db.get_packages(user_pubkey)
    return {'status': 200, 'packages': packages}


@BLUEPRINT.route("/v{}/package".format(VERSION), methods=['POST'])
@flasgger.swag_from(swagger_specs.PACKAGE)
@webserver.validation.call(['escrow_pubkey'])
def package_handler(escrow_pubkey):
    """
    Get a full info about a single package.
    ---
    :param escrow_pubkey:
    :return:
    """
    package = db.get_package(escrow_pubkey)
    return {'status': 200, 'package': package}


@BLUEPRINT.route("/v{}/add_event".format(VERSION), methods=['POST'])
@flasgger.swag_from(swagger_specs.ADD_EVENT)
@webserver.validation.call(['escrow_pubkey', 'event_type', 'location'], require_auth=True)
def add_event_handler(user_pubkey, escrow_pubkey, event_type, location):
    """
    Add new event for package.
    ---
    :param user_pubkey:
    :param escrow_pubkey:
    :param event_type:
    :param location:
    :return:
    """
    db.add_event(escrow_pubkey, user_pubkey, event_type, location)
    return {'status': 200}


@BLUEPRINT.route("/v{}/changed_location".format(VERSION), methods=['POST'])
@flasgger.swag_from(swagger_specs.CHANGED_LOCATION)
@webserver.validation.call(['escrow_pubkey', 'location'], require_auth=True)
def changed_location_handler(user_pubkey, escrow_pubkey, location):
    """
    Add new `changed_location` event for package.
    ---
    :param user_pubkey:
    :param escrow_pubkey:
    :param location:
    :return:
    """
    db.add_event(escrow_pubkey, user_pubkey, 'changed location', location)
    return {'status': 200}


# Debug routes.


@BLUEPRINT.route("/v{}/debug/create_mock_package".format(VERSION), methods=['POST'])
@flasgger.swag_from(swagger_specs.CREATE_MOCK_PACKAGE)
@webserver.validation.call(
    ['escrow_pubkey', 'launcher_pubkey', 'recipient_pubkey', 'payment_buls', 'collateral_buls', 'deadline_timestamp'])
def create_mock_package_handler(
        escrow_pubkey, launcher_pubkey, recipient_pubkey,
        payment_buls, collateral_buls, deadline_timestamp):
    """
    Create a mock package - for debug only.
    ---
    :return:
    """
    return {'status': 201, 'package': db.create_package(
        escrow_pubkey, launcher_pubkey, recipient_pubkey, payment_buls, collateral_buls, deadline_timestamp,
        'mock_setopts', 'mock_refund', 'mock merge', 'mock payment')}


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
