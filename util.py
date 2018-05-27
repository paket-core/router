"""General PaKeT utilities."""
import json
import logging

import requests

COUNTLY_URL = 'http://c.paket.global/i'
LOGGER = logging.getLogger('pkt.util')


def send_countly_event(key, count, begin_session=None, end_session=None, **kwargs):
    """
    Sends an event to countly.
    If the kwargs dict contains any of the following listed arguments, they are entered directly as part of the event.
        amount (Double)
        dur (Double)
        timestamp (Integer)
        hour (hour of the day, Integer)
        dow (day of week, Integer)
    Any unknown kwargs are inserted into the segmentation dict.
    ---
    :param key: Mandatory, String
    :param count: Mandatory, Integer
    :param begin_session: Optional, Integer
    :param end_session: Optional, Integer
    :return:
    """
    event = {'key': key, 'count': int(str(count)), 'segmentation': {}}
    known_event_keys = ['dur', 'timestamp', 'hour', 'dow']
    for event_key, value in kwargs.items():
        if event_key in known_event_keys:
            event[event_key] = value
        else:
            event['segmentation'][event_key] = value
    payload = {
        'app_key': 'e9c76edc986ea951ece1d4ae1cf4081686142dd4',
        'device_id': 'None',
        'begin_session': begin_session,
        'end_session': end_session,
        'events': json.dumps([event])
    }
    # pylint: disable=broad-except
    try:
        response = requests.get(COUNTLY_URL, params=payload)
        LOGGER.debug("response: %s", response)
        LOGGER.debug("URI: %s", response.url)
        LOGGER.debug("text: %s", response.text)
    except Exception as exception:
        LOGGER.error('failed request to countly: %s', str(exception))
    # pylint: enable=broad-except


if __name__ == '__main__':
    send_countly_event('main test', 1)
