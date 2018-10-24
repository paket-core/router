"""Handle notifications process."""
import logging
import os

import firebase_admin
from firebase_admin import messaging

LOGGER = logging.getLogger('pkt.notification')
PATH_TO_CERT = os.environ.get('PAKET_PATH_TO_CERT')


CREDENTIALS = firebase_admin.credentials.Certificate(PATH_TO_CERT)
FIREBASE_APP = firebase_admin.initialize_app(CREDENTIALS)


# internal notification codes
NOTIFICATION_CODES = {}


def send_notifications(tokens, title, body, notification_code, short_package_id):
    """Send notification to all devices which tokens was provided."""
    for token in tokens:
        notification = messaging.Notification(title=title, body=body)
        data = {
            'notification_code': str(notification_code),
            'short_package_id': str(short_package_id)}
        message = messaging.Message(data=data, notification=notification, token=token)
        try:
            response = messaging.send(message, app=FIREBASE_APP)
            LOGGER.info(response)
        except messaging.ApiCallError as exc:
            LOGGER.error(str(exc))
