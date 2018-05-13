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

BUL_TOKEN_CODE = 'BUL'
ISSUER = os.environ['PAKET_USER_ISSUER']
ISSUER_SEED = os.environ.get('PAKET_SEED_ISSUER')
HORIZON = os.environ['PAKET_HORIZON_SERVER']

LOGGER = logging.getLogger('pkt.paket')

class StellarTransactionFailed(Exception):
    """A stellar transaction failed."""


def get_keypair(pubkey=None, seed=None):
    """Get a keypair from pubkey or seed (default to random) with a decent string representation."""
    if pubkey is None:
        if seed is None:
            keypair = stellar_base.keypair.Keypair.random()
        else:
            keypair = stellar_base.keypair.Keypair.from_seed(seed)
            keypair.__class__ = type('DisplayUnlockedKeypair', (stellar_base.keypair.Keypair,), {
                '__repr__': lambda self: "KeyPair {} ({})".format(self.address(), self.seed())})
    else:
        keypair = stellar_base.keypair.Keypair.from_address(pubkey)
        keypair.__class__ = type('DisplayKeypair', (stellar_base.keypair.Keypair,), {
            '__repr__': lambda self: "KeyPair ({})".format(self.address())})
    return keypair


def get_bul_account(pubkey, accept_untrusted=False):
    """Get account details."""
    try:
        details = stellar_base.address.Address(pubkey, horizon=HORIZON)
        details.get()
    except stellar_base.utils.AccountNotExistError:
        raise AssertionError("no account found for {}".format(pubkey))
    account = {'sequence': details.sequence, 'signers': details.signers, 'thresholds': details.thresholds}
    for balance in details.balances:
        if balance.get('asset_type') == 'native':
            account['XLM balance'] = float(balance['balance'])
        if balance.get('asset_code') == BUL_TOKEN_CODE and balance.get('asset_issuer') == ISSUER:
            account['BUL balance'] = float(balance['balance'])
    if 'BUL balance' not in account and not accept_untrusted:
        raise AssertionError("account {} does not trust {} from {}".format(pubkey, BUL_TOKEN_CODE, ISSUER))
    return account


def add_memo(builder, memo):
    """Add a memo with limited length."""
    return LOGGER.error("Not using memos ATM because of bug.")
    # pylint: disable=unreachable
    max_byte_length = 28
    utf8 = memo.encode('utf8')
    if len(utf8) > max_byte_length:
        LOGGER.warning("memo too long (%s > 28), truncating", len(memo))
        cursor = max_byte_length
        while cursor > 0 and not (utf8[cursor] & 0xC0) == 0x80:
            cursor -= 1
            memo = utf8[:cursor].decode()
    builder.add_text_memo(memo)
    return builder
    # pylint: enable=unreachable


def gen_builder(pubkey='', sequence_delta=None):
    """Create a builder."""
    if sequence_delta:
        sequence = int(get_bul_account(pubkey, accept_untrusted=True)['sequence']) + sequence_delta
        builder = stellar_base.builder.Builder(horizon=HORIZON, address=pubkey, sequence=sequence)
    else:
        builder = stellar_base.builder.Builder(horizon=HORIZON, address=pubkey)
    return builder


def submit(builder):
    """Submit a transaction and raise an exception if it fails."""
    response = builder.submit()
    if 'status' in response and response['status'] >= 300:
        raise StellarTransactionFailed(response)
    return response


def submit_transaction_envelope(envelope):
    """Submit a transaction from an XDR of the envelope."""
    builder = stellar_base.builder.Builder(horizon=HORIZON, address='')
    builder.import_from_xdr(envelope)
    return submit(builder)


def prepare_create_account(from_pubkey, new_pubkey, starting_balance=1):
    """Prepare account creation transaction."""
    builder = gen_builder(from_pubkey)
    builder.append_create_account_op(destination=new_pubkey, starting_balance=starting_balance)
    add_memo(builder, 'create escrow')
    return builder.gen_te().xdr().decode()


def prepare_trust(from_pubkey):
    """Prepare trust transaction from account."""
    builder = gen_builder(from_pubkey)
    builder.append_trust_op(ISSUER, BUL_TOKEN_CODE)
    add_memo(builder, "trust BUL {}".format(ISSUER))
    return builder.gen_te().xdr().decode()


def prepare_send_buls(from_pubkey, to_pubkey, amount):
    """Prepare BUL transfer."""
    builder = gen_builder(from_pubkey)
    builder.append_payment_op(to_pubkey, amount, BUL_TOKEN_CODE, ISSUER)
    add_memo(builder, "send {} BUL".format(amount))
    return builder.gen_te().xdr().decode()


def prepare_escrow_transactions(
        escrow_pubkey, launcher_pubkey, courier_pubkey, recipient_pubkey, payment, collateral, deadline):
    """Prepare timelocked refund transaction."""
    # Refund transaction, in case of failed delivery, timelocked.
    builder = gen_builder(escrow_pubkey, sequence_delta=1)
    builder.append_payment_op(launcher_pubkey, payment + collateral, BUL_TOKEN_CODE, ISSUER)
    builder.add_time_bounds(type('TimeBound', (), {'minTime': deadline, 'maxTime': 0})())
    add_memo(builder, 'refund')
    refund_envelope = builder.gen_te()

    # Payment transaction, in case of successful delivery, requires recipient signature.
    builder = gen_builder(escrow_pubkey, sequence_delta=1)
    builder.append_payment_op(courier_pubkey, payment + collateral, BUL_TOKEN_CODE, ISSUER)
    add_memo(builder, 'payment')
    payment_envelope = builder.gen_te()

    # Merge transaction, to drain the remaining XLM from the account, timelocked.
    builder = gen_builder(escrow_pubkey, sequence_delta=2)
    builder.append_account_merge_op(launcher_pubkey)
    builder.add_time_bounds(type('TimeBound', (), {'minTime': deadline, 'maxTime': 0})())
    merge_envelope = builder.gen_te()

    # Set transactions and recipient as only signers.
    builder = gen_builder(escrow_pubkey)
    builder.append_set_options_op(
        signer_address=refund_envelope.hash_meta(),
        signer_type='preAuthTx',
        signer_weight=2)
    builder.append_set_options_op(
        signer_address=payment_envelope.hash_meta(),
        signer_type='preAuthTx',
        signer_weight=1)
    builder.append_set_options_op(
        signer_address=merge_envelope.hash_meta(),
        signer_type='preAuthTx',
        signer_weight=2)
    builder.append_set_options_op(
        signer_address=recipient_pubkey,
        signer_type='ed25519PublicKey',
        signer_weight=1)
    builder.append_set_options_op(
        master_weight=0, low_threshold=1, med_threshold=2, high_threshold=3)
    add_memo(builder, 'freeze')
    set_options_envelope = builder.gen_te()

    package_details = dict(
        paket_id=escrow_pubkey, launcher_pubkey=launcher_pubkey, recipient_pubkey=recipient_pubkey,
        payment=payment, collateral=collateral, deadline=deadline,
        set_options_transaction=set_options_envelope.xdr().decode(),
        refund_transaction=refund_envelope.xdr().decode(),
        payment_transaction=payment_envelope.xdr().decode(),
        merge_transaction=merge_envelope.xdr().decode())
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


def new_account(pubkey):
    """Create a new account and fund it with lumens. Debug only."""
    LOGGER.info("creating and funding account %s", pubkey)
    request = requests.get("https://friendbot.stellar.org/?addr={}".format(pubkey))
    if request.status_code != 200:
        LOGGER.error("Request to friendbot failed: %s", request.json())
        raise StellarTransactionFailed("unable to create account {}".format(pubkey))


def fund_from_issuer(pubkey, amount):
    """Fund an account directly from issuer. Debug only."""
    builder = stellar_base.builder.Builder(horizon=HORIZON, secret=ISSUER_SEED)
    builder.append_payment_op(pubkey, amount, BUL_TOKEN_CODE, ISSUER)
    add_memo(builder, 'fund')
    builder.sign()
    return submit(builder)
