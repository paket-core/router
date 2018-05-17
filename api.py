"""JSON swagger API to PaKeT."""
import logging
import os

import flasgger
import flask

import db
import paket
import swagger_specs
import webserver.validation

VERSION = swagger_specs.VERSION
PORT = os.environ.get('PAKET_API_PORT', 8000)
LOGGER = logging.getLogger('pkt.api')
BLUEPRINT = flask.Blueprint('api', __name__)


# Wallet routes.


@BLUEPRINT.route("/v{}/submit_transaction".format(VERSION), methods=['POST'])
@flasgger.swag_from(swagger_specs.SUBMIT_TRANSACTION)
@webserver.validation.call(['transaction'])
def submit_transaction_handler(transaction):
    """
    Submit a signed transaction. This call is used to submit signed
    transactions. Signed transactions can be obtained by signing unsigned
    transactions returned by other calls. You can use the
    [laboratory](https://www.stellar.org/laboratory/#txsigner?network=test) to
    sign the transaction with your private key.
    ---
    :param transaction:
    :return:
    """
    return {'status': 200, 'response': paket.submit_transaction_envelope(transaction)}


@BLUEPRINT.route("/v{}/bul_account".format(VERSION), methods=['POST'])
@flasgger.swag_from(swagger_specs.BUL_ACCOUNT)
@webserver.validation.call(['queried_pubkey'])
def bul_account_handler(queried_pubkey):
    """
    Get the details of a Stellar BUL account.
    ---
    :param queried_pubkey:
    :return:
    """
    return dict(status=200, **paket.get_bul_account(queried_pubkey))


@BLUEPRINT.route("/v{}/prepare_create_account".format(VERSION), methods=['POST'])
@flasgger.swag_from(swagger_specs.PREPARE_CREATE_ACCOUNT)
@webserver.validation.call(['from_pubkey', 'new_pubkey'])
def prepare_create_account_handler(from_pubkey, new_pubkey, starting_balance=5):
    """
    Prepare a create account transaction.
    ---
    :param from_pubkey:
    :param new_pubkey:
    :param starting_balance:
    :return:
    """
    return {'status': 200, 'transaction': paket.prepare_create_account(from_pubkey, new_pubkey, starting_balance)}


@BLUEPRINT.route("/v{}/prepare_trust".format(VERSION), methods=['POST'])
@flasgger.swag_from(swagger_specs.PREPARE_TRUST)
@webserver.validation.call(['from_pubkey'])
def prepare_trust_handler(from_pubkey, limit=None):
    """
    Prepare an add trust transaction.
    ---
    :param from_pubkey:
    :return:
    """
    return {'status': 200, 'transaction': paket.prepare_trust(from_pubkey, limit)}


@BLUEPRINT.route("/v{}/prepare_send_buls".format(VERSION), methods=['POST'])
@flasgger.swag_from(swagger_specs.PREPARE_SEND_BULS)
@webserver.validation.call(['from_pubkey', 'to_pubkey', 'amount_buls'])
def prepare_send_buls_handler(from_pubkey, to_pubkey, amount_buls):
    """
    Prepare a BUL transfer transaction.
    ---
    :param from_pubkey:
    :param to_pubkey:
    :param amount_buls:
    :return:
    """
    return {'status': 200, 'transaction': paket.prepare_send_buls(from_pubkey, to_pubkey, amount_buls)}


# Package routes.


@BLUEPRINT.route("/v{}/prepare_escrow".format(VERSION), methods=['POST'])
@flasgger.swag_from(swagger_specs.PREPARE_ESCROW)
@webserver.validation.call(
    ['launcher_pubkey', 'recipient_pubkey', 'courier_pubkey', 'deadline_timestamp', 'payment_buls', 'collateral_buls'],
    require_auth=True)
def prepare_escrow_handler(
        user_pubkey, launcher_pubkey, courier_pubkey, recipient_pubkey,
        payment_buls, collateral_buls, deadline_timestamp
    ):
    """
    Launch a package.
    Use this call to create a new package for delivery.
    ---
    :param user_pubkey: the escrow pubkey
    :param launcher_pubkey:
    :param courier_pubkey:
    :param recipient_pubkey:
    :param payment_buls:
    :param collateral_buls:
    :param deadline_timestamp:
    :return:
    """
    return dict(status=201, **paket.prepare_escrow(
        user_pubkey, launcher_pubkey, courier_pubkey, recipient_pubkey,
        payment_buls, collateral_buls, deadline_timestamp
    ))


@BLUEPRINT.route("/v{}/accept_package".format(VERSION), methods=['POST'])
@flasgger.swag_from(swagger_specs.ACCEPT_PACKAGE)
@webserver.validation.call(['escrow_pubkey'], require_auth=True)
def accept_package_handler(user_pubkey, escrow_pubkey):
    """
    Accept a package.
    If the package requires collateral, commit it.
    If user is the package's recipient, release all funds from the escrow.
    ---
    :param user_pubkey:
    :param escrow_pubkey:
    :param payment_transaction:
    :return:
    """
    db.update_custodian(escrow_pubkey, user_pubkey)
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
def package_handler(escrow_pubkey):
    """
    Get a full info about a single package.
    ---
    :param escrow_pubkey:
    :return:
    """
    return {'status': 200, 'package': db.get_package(escrow_pubkey)}


# Debug routes.


@BLUEPRINT.route("/v{}/debug/fund".format(VERSION), methods=['POST'])
@flasgger.swag_from(swagger_specs.FUND_FROM_ISSUER)
@webserver.validation.call(['funded_pubkey'])
def fund_handler(funded_pubkey, funded_buls=1000):
    """
    Give an account BULs - for debug only.
    ---
    :return:
    """
    return {'status': 200, 'response': paket.fund_from_issuer(funded_pubkey, funded_buls)}


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


if __name__ == '__main__':
    webserver.run(BLUEPRINT, swagger_specs.CONFIG, PORT)
