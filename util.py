import json

import requests


def send_countly_event(key, count, begin_session=1, end_session=1, sum=None, dur=None, segmentation=None,
                       timestamp=None, hour=None, dow=None):
    """
    key (Mandatory, String)
    count (Mandatory, Integer)
    sum (Optional, Double)
    dur (Optional, Double)
    segmentation (Optional, Dictionary Object)
    timestamp (Optional)
    hour (Optional)
    dow (Optional)

    """
    countly_url = 'http://c.paket.global/i'
    try:
        event = {'key': key, 'count': int(count)}
        if sum:
            event['sum'] = sum
        if dur:
            event['dur'] = dur
        if segmentation:
            event['segmentation'] = segmentation
        if timestamp:
            event['timestamp'] = timestamp
        if hour:
            event['hour'] = hour
        if dow:
            event['dow'] = dow

        event_payload = json.dumps([event], separators=(',', ':'))
        print('event_payload: %s' % event_payload)
        payload = {
            'app_key': 'e9c76edc986ea951ece1d4ae1cf4081686142dd4',
            'device_id': 'None',
            'begin_session': begin_session,
            'end_session': end_session,
            'events': json.dumps([event], separators=(',', ':'))
        }
    except ValueError as v:
        print("ValueError: " + str(v))
        return
    try:
        resp = requests.get(countly_url, params=payload)
        print(resp)
        print(resp.url)
        print(resp.text)
    except Exception as e:
        print("Error: " + str(e))


if __name__ == '__main__':
    send_countly_event('main test', 1)
