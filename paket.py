"""Use PaKeT smart contract."""
import logging
import os
import time

import requests
import stellar_base.address
import stellar_base.asset
import stellar_base.builder
import stellar_base.keypair

import db

LOGGER = logging.getLogger('pkt.paket')

HORIZON = os.environ['PAKET_HORIZON_SERVER']


class StellarTransactionFailed(Exception):
    """A stellar transaction failed."""


def get_keypair(seed=None):
    """Get a keypair from seed (default to random)."""
    keypair = stellar_base.keypair.Keypair.from_seed(
        seed if seed else stellar_base.keypair.Keypair.random().seed())
    keypair.__class__ = type('DisplayKeypair', (stellar_base.keypair.Keypair,), {
        '__repr__': lambda self: "KeyPair ({})".format(self.address())})
    return keypair


def new_account(address):
    """Create a new account and fund it with lumens."""
    LOGGER.info("creating and funding account %s", address)
    request = requests.get("https://friendbot.stellar.org/?addr={}".format(address))
    if request.status_code != 200:
        LOGGER.error("Request to friendbot failed: %s", request.json())
        raise StellarTransactionFailed("unable to create account {}".format(address))


def get_bul_account(address):
    """Get address details."""
    try:
        details = stellar_base.address.Address(address, horizon=HORIZON)
        details.get()
    except stellar_base.utils.AccountNotExistError:
        return None
    for balance in details.balances:
        if balance.get('asset_code') == 'BUL' and balance.get('asset_issuer') == ISSUER.address().decode():
            return {
                'balance': float(balance['balance']), 'sequence': details.sequence,
                'signers': details.signers, 'thresholds': details.thresholds}
    return None


ISSUER = get_keypair(os.environ['PAKET_USER_ISSUER'])


def submit(builder):
    """Submit a transaction and raise an exception if it fails."""
    response = builder.submit()
    if 'status' in response and response['status'] >= 300:
        raise StellarTransactionFailed(response)
    return response


def add_memo(builder, memo):
    """Add a memo with limited length."""
    if len(memo) > 28:
        LOGGER.warning("memo length too long: %s>28. Memo truncated!", len(memo))
        memo = memo[:28]
    builder.add_text_memo(memo)


def submit_transaction_envelope(envelope):
    """Submit a transaction from an XDR of the envelope."""
    builder = stellar_base.builder.Builder(horizon=HORIZON, address='')
    builder.import_from_xdr(envelope)
    return submit(builder)


def trust(keypair):
    """Trust BUL from account."""
    LOGGER.debug("adding trust to %s", keypair.address().decode())
    builder = stellar_base.builder.Builder(horizon=HORIZON, secret=keypair.seed())
    builder.append_trust_op(ISSUER.address().decode(), 'BUL')
    builder.sign()
    return submit(builder)


def send_buls(from_address, to_address, amount):
    """Transfer BULs."""
    LOGGER.info("sending %s BUL from %s to %s", amount, from_address, to_address)
    source = get_keypair(db.get_user(from_address)['seed'])
    builder = stellar_base.builder.Builder(horizon=HORIZON, secret=source.seed())
    builder.append_payment_op(to_address, amount, 'BUL', ISSUER.address().decode())
    add_memo(builder, "send {} BULs".format(amount))
    builder.sign()
    return submit(builder)


def prepare_send_buls(from_address, to_address, amount):
    """Transfer BULs."""
    builder = stellar_base.builder.Builder(horizon=HORIZON, address=from_address)
    builder.append_payment_op(to_address, amount, 'BUL', ISSUER.address().decode())
    return builder.gen_te().xdr().decode()


def launch_paket(launcher, recipient, courier, deadline, payment, collateral):
    """Launch a paket."""
    escrow = get_keypair()
    builder = stellar_base.builder.Builder(horizon=HORIZON, secret=db.get_user(launcher)['seed'])
    builder.append_create_account_op(destination=escrow.address().decode(), starting_balance=5)
    add_memo(builder, "launch {} / {}".format(payment, collateral))
    builder.sign()
    submit(builder)
    trust(escrow)

    sequence = int(get_bul_account(escrow.address().decode())['sequence']) + 1

    # Create refund transaction.
    builder = stellar_base.builder.Builder(horizon=HORIZON, secret=escrow.seed(), sequence=sequence)
    builder.append_payment_op(
        launcher, payment + collateral,
        'BUL', ISSUER.address().decode(),
        escrow.address().decode())
    add_memo(builder, "refund minTime: {} maxTime: 0".format(deadline))
    refund_envelope = builder.gen_te()

    # Create payment transaction.
    builder = stellar_base.builder.Builder(horizon=HORIZON, secret=escrow.seed(), sequence=sequence)
    builder.append_payment_op(
        courier, payment + collateral,
        'BUL', ISSUER.address().decode(),
        escrow.address().decode())
    add_memo(builder, "payment {} BULs".format(payment + collateral))
    payment_envelope = builder.gen_te()

    # Set transactions and recipient as only signers.
    builder = stellar_base.builder.Builder(horizon=HORIZON, secret=escrow.seed())
    builder.append_set_options_op(
        signer_address=refund_envelope.hash_meta(),
        signer_type='preAuthTx',
        signer_weight=2)
    builder.append_set_options_op(
        signer_address=payment_envelope.hash_meta(),
        signer_type='preAuthTx',
        signer_weight=1)
    builder.append_set_options_op(
        signer_address=recipient,
        signer_type='ed25519PublicKey',
        signer_weight=1)
    builder.append_set_options_op(
        master_weight=0, low_threshold=1, med_threshold=2, high_threshold=3)
    builder.sign()
    submit(builder)

    package_details = dict(
        paket_id=escrow.address().decode(),
        launcher_pubkey=launcher, recipient_pubkey=recipient, deadline=deadline, payment=payment, collateral=collateral,
        refund_transaction=refund_envelope.xdr().decode(), payment_transaction=payment_envelope.xdr().decode())
    db.create_package(**package_details)
    return package_details


def confirm_receipt(recipient_pubkey, payment_envelope):
    """Confirm the receipt of a package by signing and submitting the payment transaction."""
    recipient_seed = db.get_user(recipient_pubkey)['seed']
    builder = stellar_base.builder.Builder(horizon=HORIZON, secret=recipient_seed)
    builder.import_from_xdr(payment_envelope)
    builder.sign()
    return submit(builder)


def accept_package(user_pubkey, paket_id, payment_envelope=None):
    """Accept a package - confirm delivery if recipient."""
    db.update_custodian(paket_id, user_pubkey)
    paket = db.get_package(paket_id)
    if paket['recipient_pubkey'] == user_pubkey:
        return confirm_receipt(user_pubkey, payment_envelope)
    return paket


def relay_payment(*_, **__):
    """Relay payment to another courier."""
    raise NotImplementedError('Relay payment not yet implemented.')


def refund(paket_id, refund_envelope):
    """Claim a refund if deadline has passed."""
    now = time.time()
    builder = stellar_base.builder.Builder(horizon=HORIZON, address=paket_id)
    builder.import_from_xdr(refund_envelope)
    add_memo(builder, "refund")
    for time_bound in builder.time_bounds:
        if time_bound.minTime > 0 and time_bound.minTime > now:
            raise StellarTransactionFailed(
                "transaction can't be sent before {} and it's {}".format(time_bound.minTime, now))
        if 0 < time_bound.maxTime < now:
            raise StellarTransactionFailed(
                "transaction can't be sent after {} and it's {}".format(time_bound.maxTime, now))
    return submit(builder)
