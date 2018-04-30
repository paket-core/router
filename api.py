"""JSON swagger API to PaKeT."""
import logging
import os

import flask
import flasgger

import webserver.validation

import db
import paket
import swagger_specs

VERSION = swagger_specs.VERSION
LOGGER = logging.getLogger('pkt.api')
BLUEPRINT = flask.Blueprint('api', __name__)

# pylint: disable=missing-docstring
# See documentation in swagfiles.


# Wallet routes.


@BLUEPRINT.route("/v{}/submit_transaction".format(VERSION), methods=['POST'])
@flasgger.swag_from(swagger_specs.TEST)
@webserver.validation.call(['transaction'])
def submit_transaction_handler(user_pubkey, transaction):
    return {'status': 200, 'transaction': paket.submit_transaction_envelope(user_pubkey, transaction)}


@BLUEPRINT.route("/v{}/bul_account".format(VERSION), methods=['GET'])
@flasgger.swag_from(swagger_specs.TEST)
@webserver.validation.call(['queried_pubkey'])
def bul_account_handler(queried_pubkey):
    return dict(status=200, **paket.get_bul_account(queried_pubkey))


@BLUEPRINT.route("/v{}/send_buls".format(VERSION), methods=['POST'])
@flasgger.swag_from(swagger_specs.TEST)
@webserver.validation.call(['to_pubkey', 'amount_buls'], require_auth=True)
def send_buls_handler(user_pubkey, to_pubkey, amount_buls):
    return {'status': 201, 'transaction': paket.send_buls(user_pubkey, to_pubkey, amount_buls)}


@BLUEPRINT.route("/v{}/prepare_send_buls".format(VERSION), methods=['GET'])
@flasgger.swag_from(swagger_specs.TEST)
@webserver.validation.call(['from_pubkey', 'to_pubkey', 'amount_buls'])
def prepare_send_buls_handler(from_pubkey, to_pubkey, amount_buls):
    return {'status': 200, 'transaction': paket.prepare_send_buls(from_pubkey, to_pubkey, amount_buls)}


@BLUEPRINT.route("/v{}/price".format(VERSION), methods=['GET'])
@flasgger.swag_from(swagger_specs.TEST)
def price_handler():
    return flask.jsonify({'status': 200, 'buy_price': 1, 'sell_price': 1})


# Package routes.


@BLUEPRINT.route("/v{}/launch_package".format(VERSION), methods=['POST'])
@flasgger.swag_from(swagger_specs.TEST)
@webserver.validation.call(
    ['recipient_pubkey', 'courier_pubkey', 'deadline_timestamp', 'payment_buls', 'collateral_buls'], require_auth=True)
def launch_package_handler(
        user_pubkey, recipient_pubkey, courier_pubkey, deadline_timestamp, payment_buls, collateral_buls
):
    escrow_address, refund_transaction, payment_transaction = paket.launch_paket(
        user_pubkey, recipient_pubkey, courier_pubkey, deadline_timestamp, payment_buls, collateral_buls
    )
    return {
        'status': 200, 'escrow_address': escrow_address,
        'refund_transaction': refund_transaction, 'payment_transaction': payment_transaction}


@BLUEPRINT.route("/v{}/accept_package".format(VERSION), methods=['POST'])
@flasgger.swag_from(swagger_specs.TEST)
@webserver.validation.call(['paket_id'], require_auth=True)
def accept_package_handler(user_pubkey, paket_id, payment_transaction=None):
    paket.accept_package(user_pubkey, paket_id, payment_transaction)
    return {'status': 200}


@BLUEPRINT.route("/v{}/relay_package".format(VERSION), methods=['POST'])
@flasgger.swag_from(swagger_specs.TEST)
@webserver.validation.call(['paket_id', 'courier_pubkey', 'payment_buls'], require_auth=True)
def relay_package_handler(user_pubkey, paket_id, courier_pubkey, payment_buls):
    return {'status': 200, 'transaction': paket.relay_payment(user_pubkey, paket_id, courier_pubkey, payment_buls)}


@BLUEPRINT.route("/v{}/refund_package".format(VERSION), methods=['POST'])
@flasgger.swag_from(swagger_specs.TEST)
@webserver.validation.call(['paket_id', 'refund_transaction'], require_auth=True)
# pylint: disable=unused-argument
# user_pubkey is used in decorator.
def refund_package_handler(user_pubkey, paket_id, refund_transaction):
    # pylint: enable=unused-argument
    return {'status': 200, 'transaction': paket.refund(paket_id, refund_transaction)}


# pylint: disable=unused-argument
# This function does not yet implement the filters.
@BLUEPRINT.route("/v{}/my_packages".format(VERSION), methods=['GET'])
@flasgger.swag_from(swagger_specs.TEST)
@webserver.validation.call(require_auth=True)
def my_packages_handler(user_pubkey, show_inactive=False, from_date=None, role_in_delivery=None):
    return {'status': 200, 'packages': db.get_packages()}
# pylint: enable=unused-argument


@BLUEPRINT.route("/v{}/package".format(VERSION), methods=['GET'])
@flasgger.swag_from(swagger_specs.TEST)
@webserver.validation.call(['paket_id'])
def package_handler(paket_id):
    return {'status': 200, 'package': db.get_package(paket_id)}


# User routes.


@BLUEPRINT.route("/v{}/register_user".format(VERSION), methods=['POST'])
@flasgger.swag_from(swagger_specs.TEST)
@webserver.validation.call(['full_name', 'phone_number', 'paket_user'], require_auth=True)
# Note that pubkey is different from user_pubkey in that it does not yet exist in the system.
def register_user_handler(pubkey, full_name, phone_number, paket_user):
    try:
        paket.stellar_base.keypair.Keypair.from_address(str(pubkey))
        db.create_user(pubkey, paket_user)

    # For debug purposes, we generate a pubkey if no valid key is found.
    except paket.stellar_base.utils.DecodeError:
        if not webserver.validation.DEBUG:
            raise
        keypair = paket.get_keypair()
        pubkey, seed = keypair.address().decode(), keypair.seed().decode()
        db.create_user(pubkey, paket_user, seed)
        paket.new_account(pubkey)
        paket.trust(keypair)

    return {'status': 201, 'user_details': db.update_user_details(pubkey, full_name, phone_number)}


@BLUEPRINT.route("/v{}/recover_user".format(VERSION), methods=['POST'])
@flasgger.swag_from(swagger_specs.TEST)
@webserver.validation.call(require_auth=True)
def recover_user_handler(user_pubkey):
    return {'status': 200, 'user_details': db.get_user(user_pubkey)}


# Debug routes.


@BLUEPRINT.route("/v{}/debug/users".format(VERSION), methods=['GET'])
@flasgger.swag_from(swagger_specs.TEST)
@webserver.validation.call
def users_handler():
    return {'status': 200, 'users': {
        pubkey: dict(user, bul_account=paket.get_bul_account(pubkey)) for pubkey, user in db.get_users().items()}}


@BLUEPRINT.route("/v{}/debug/packages".format(VERSION), methods=['GET'])
@flasgger.swag_from(swagger_specs.TEST)
@webserver.validation.call
def packages_handler():
    return {'status': 200, 'packages': db.get_packages()}


# Sandbox setup.


def create_db_user(paket_user, pubkey, seed):
    """Create a new user in the DB."""
    LOGGER.debug("Creating user %s", paket_user)
    try:
        db.create_user(pubkey, paket_user, seed)
        db.update_user_details(pubkey, paket_user, '123-456')
    except db.DuplicateUser:
        LOGGER.debug("User %s already exists", paket_user)


def create_stellar_account(pubkey, keypair):
    """Create a stellar account."""
    LOGGER.debug("Creating account %s", pubkey)
    try:
        paket.new_account(pubkey)
    except paket.StellarTransactionFailed:
        LOGGER.warning("address %s already exists", pubkey)
    paket.trust(keypair)


def fund_stellar_account(pubkey):
    """Fund a stellar account."""
    if pubkey == paket.ISSUER.address().decode():
        return
    try:
        balance = paket.get_bul_account(pubkey)['balance']
    except paket.stellar_base.utils.AccountNotExistError:
        LOGGER.error("address %s does not exist", pubkey)
        return
    if balance < 100:
        LOGGER.warning("address %s has only %s BUL", pubkey, balance)
        paket.send_buls(paket.ISSUER.address().decode(), pubkey, 1000 - balance)


def init_sandbox(create_db=None, create_stellar=None, fund_stellar=None):
    """Initialize database with debug values and fund users. For debug only."""
    if create_db is None and bool(os.environ.get('PAKET_CREATE_DB')):
        create_db = True
    if create_stellar is None and bool(os.environ.get('PAKET_CREATE_STELLAR')):
        create_stellar = True
    if fund_stellar is None and bool(os.environ.get('PAKET_FUND_STELLAR')):
        fund_stellar = True

    if create_db:
        webserver.validation.init_nonce_db()
        db.init_db()
    for paket_user, seed in [
            (key.split('PAKET_USER_', 1)[1], value)
            for key, value in os.environ.items()
            if key.startswith('PAKET_USER_')
    ]:
        keypair = paket.get_keypair(seed)
        pubkey, seed = keypair.address().decode(), keypair.seed().decode()
        if create_db:
            create_db_user(paket_user, pubkey, seed)
        if create_stellar:
            create_stellar_account(pubkey, keypair)
        if fund_stellar:
            fund_stellar_account(pubkey)


if __name__ == '__main__':
    webserver.run(BLUEPRINT, swagger_specs.CONFIG)
