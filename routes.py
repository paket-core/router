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
def accept_package_handler(user_pubkey, escrow_pubkey, location, leg_price=None, photo=None):
    """
    Accept a package.
    If the package requires collateral, commit it.
    If user is the package's recipient, release all funds from the escrow.
    ---
    :param user_pubkey:
    :param escrow_pubkey:
    :param location:
    :param leg_price:
    :param photo:
    :return:
    """
    db.accept_package(user_pubkey, escrow_pubkey, location, leg_price, photo)
    return {'status': 200}


@BLUEPRINT.route("/v{}/confirm_couriering".format(VERSION), methods=['POST'])
@flasgger.swag_from(swagger_specs.CONFIRM_COURIERING)
@webserver.validation.call(['escrow_pubkey'], require_auth=True)
def confirm_couriering_handler(user_pubkey, escrow_pubkey, location, photo=None):
    """
    Add event to package, which indicates that user became courier.
    ---
    :param user_pubkey:
    :param escrow_pubkey:
    :param location:
    :param photo:
    :return:
    """
    db.confirm_couriering(user_pubkey, escrow_pubkey, location, photo)
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
    db.assign_xdrs(escrow_pubkey, user_pubkey, location, kwargs, photo)
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


@BLUEPRINT.route("/v{}/request_delegation".format(VERSION), methods=['POST'])
@flasgger.swag_from(swagger_specs.REQUEST_DELEGATION)
@webserver.validation.call(['escrow_pubkey', 'location'], require_auth=True)
def request_delegation_handler(user_pubkey, escrow_pubkey, location, kwargs=None, photo=None):
    """
    Add `delegate required` event to package
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
def events_handler(max_events_num=100, mock=None):
    """
    Get all events.
    ---
    :param max_events_num:
    :param mock:
    :return:
    """
    if not bool(mock):
        events = db.get_events(max_events_num)
        # Mock data. Temporary.
    else:
        events = {
            'packages_events': [{
                'timestamp': '2018-08-03 14:29:18.116482',
                'escrow_pubkey': 'GB5SUIN2OEJXG2GDYG6EGB544DQLUVZX35SJJVLHWCEZ4FYWRWW236FB',
                'user_pubkey': 'GBUPZ63WK2ZLOCXPCUOMM7XRUGXOVJC3RIBL7KBTUSHLKFRKVHUB757L',
                'event_type': 'launched', 'location': '51.4983407,-0.173709'
            }, {
                'timestamp': '2018-08-03 14:35:05.958315',
                'escrow_pubkey': 'GB5SUIN2OEJXG2GDYG6EGB544DQLUVZX35SJJVLHWCEZ4FYWRWW236FB',
                'user_pubkey': 'GCBKJ3QLHCBK5WBF4UZ5K2LOVDI63WG2SKLIWIMREPRLCTIHD6B5QR65',
                'event_type': 'couriered', 'location': '51.4983407,-0.173709'
            }, {
                'timestamp': '2018-08-04 17:02:55.138572',
                'escrow_pubkey': 'GB5SUIN2OEJXG2GDYG6EGB544DQLUVZX35SJJVLHWCEZ4FYWRWW236FB',
                'user_pubkey': 'GDRGF2BU7CV4QU4E54B72BJEL4CWFMTTVSVJMKWESK32HLTYD4ZEWJOR',
                'event_type': 'received', 'location': '53.3979468,-2.932953'
            }, {
                'timestamp': '2018-08-03 06:35:17.169421',
                'escrow_pubkey': 'GBMU5SWBUNBCDRUMIZNCDOTMIRGLBFY5DEPIE4OTBAUOFK4V3HOENAGT',
                'user_pubkey': 'GANEU37FIEBICW6352CVIUD7GYOV5H7W5YUE5ECDH5PJNF7R5ISYJR3K',
                'event_type': 'launched', 'location': '31.2373787,34.7889161'
            }, {
                'timestamp': '2018-08-03 07:01:17.192375',
                'escrow_pubkey': 'GBMU5SWBUNBCDRUMIZNCDOTMIRGLBFY5DEPIE4OTBAUOFK4V3HOENAGT',
                'user_pubkey': 'GBL4FZ6HCA6SQATD5UYHQYMVWASBEZCKGL2P7PEU6VNLONVFZY6DPV3R',
                'event_type': 'couriered', 'location': '31.2373787,34.7889161'
            }, {
                'timestamp': '2018-08-05 22:05:53.162485',
                'escrow_pubkey': 'GBMU5SWBUNBCDRUMIZNCDOTMIRGLBFY5DEPIE4OTBAUOFK4V3HOENAGT',
                'user_pubkey': 'GBYYI24HZ75OYBAHZOUVAAQNS5YHMN32VLCDBZFXHAAJKRRSCZICBIDJ',
                'event_type': 'received', 'location': '32.8266712,34.9774087'
            }, {
                'timestamp': '2018-08-07 05:55:15.168276',
                'escrow_pubkey': 'GALIFYZ6GDHXWDH2QZLRJY2XS77A6WXILDFSRH6ZZM3IYOIH2XEK3TAK',
                'user_pubkey': 'GAZ2UUQUEYY2LHAQMP4M737DXXX3TM7L6BE5JT7LYWS5GYL6VXQ6HASR',
                'event_type': 'launched', 'location': '12.926039,77.5056131'
            }, {
                'timestamp': '2018-08-07 09:14:18.137124',
                'escrow_pubkey': 'GALIFYZ6GDHXWDH2QZLRJY2XS77A6WXILDFSRH6ZZM3IYOIH2XEK3TAK',
                'user_pubkey': 'GBQR3QGZOS2K4MQPPJDKRMJ6MIEACCG4BRO23UE33TDFRZOM57VL5O5J',
                'event_type': 'couriered', 'location': '12.926039,77.5056131'
            }, {
                'timestamp': '2018-08-09 14:27:16.143762',
                'escrow_pubkey': 'GALIFYZ6GDHXWDH2QZLRJY2XS77A6WXILDFSRH6ZZM3IYOIH2XEK3TAK',
                'user_pubkey': 'GAYOZB7SZBD7O4UPLLQNXFN5ZZCQJSXBKERNIY4MIWL7DVXF7DBF7OU6',
                'event_type': 'received', 'location': '28.7050581,77.1419526'}],
            'user_events': [{
                'timestamp': '2018-08-01 17:46:18.169723',
                'escrow_pubkey': None,
                'user_pubkey': 'GBUPZ63WK2ZLOCXPCUOMM7XRUGXOVJC3RIBL7KBTUSHLKFRKVHUB757L',
                'event_type': 'installed app', 'location': '51.5482912,-0.3048464'
            }, {
                'timestamp': '2018-07-22 19:36:18.123142',
                'escrow_pubkey': None,
                'user_pubkey': 'GCCYNSN3WETV2FBASFVXKAJ54OX4NUTP4ZUJFGXTX47A2GRQYQ52QQBK',
                'event_type': 'installed app', 'location': '50.2443519,28.6989147'
            }, {
                'timestamp': '2018-07-22 19:58:38.164237',
                'escrow_pubkey': None,
                'user_pubkey': 'GCCYNSN3WETV2FBASFVXKAJ54OX4NUTP4ZUJFGXTX47A2GRQYQ52QQBK',
                'event_type': 'passed kyc', 'location': '50.2443519,28.6989147'
            }, {
                'timestamp': '2018-07-28 05:34:21.134562',
                'escrow_pubkey': None,
                'user_pubkey': 'GBOTDKM6ZJNV54QLXKTU5WSYFXJZDZZSGKTYHDNWDDVAEVB73DPLSP4H',
                'event_type': 'funded account', 'location': '22.9272893,113.3443182'
            }, {
                'timestamp': '2018-07-30 22:12:21.136421',
                'escrow_pubkey': None,
                'user_pubkey': 'GAUHIJXEV2D46G375FJNCUBGVUKXRF7C3VC7U3HUPCBIZUYHJKP4N6XA',
                'event_type': 'funded account', 'location': '-16.2658233,-47.9159335'
            }, {
                'timestamp': '2018-08-03 17:35:14.136415',
                'escrow_pubkey': None,
                'user_pubkey': 'GAL54ATIHYBWMKYUNQSM3QAGZGCUBJGF6KEFFSQTEV7JOOA72UEJP4UL',
                'event_type': 'funded account', 'location': '51.0465554,-114.0752757'}]}
    return {'status': 200, 'events': events}


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
