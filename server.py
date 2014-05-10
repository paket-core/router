#!/usr/bin/python3
from router import Router

# A Parcel has info about the physical package and an unlimited number of attribute.
class Parcel(object):
    def __init__(self, encumbrance=0):
        self.encumbrance = encumbrance
        # Place holder
        self.attributes = {}

"""Location in the world. soon to rely on the routing module.(?)
latlng - geo pos tuple
accuracy - Accuracy indicator in meters. None if unknown.
FIXME Do we really need to separate Location from Address?
NOFIX yes, a location is logical - a person, or a Hub may be a location. In 
addition, a location is more granular - it has floor, a specific person to sign maybe?
We should give it more thought. Besides, I think location should be a hirarchical structure
but that's a separate discussion.
"""
class Location(object):
    def __init__(self, latlng, acc=None):
        self.latlng = latlng
        self.accuracy = acc
    def __str__(self, *args, **kwargs):
        return "<Location in %s>" % (self.latlng,)
    def distance(self, latlng):
        return sum((self.latlng[i] - latlng[i]) ** 2 for i in (0, 1)) ** .5
    def routeDistance(self, location):
        print("calc route distance from %s to %s" % (self, location))
        r = Router(self.latlng,location.latlng, 'motorcar')
        return r.getDistance() 
    def routeTimeMin(self, location):
        print("calc route time from %s to %s" % (self.latlng, location))
        r = Router(self.latlng,location.latlng, 'motorcar')
        return r.getTravelTimeMin() 


# An Address is a fixed Location with a helpful description on how to get to it.
class Address(Location):
    def __init__(self, latlng, desc=''):
        Location.__init__(self, latlng, acc=1)
        self.desc = desc

# A Delivery is the taking of a Parcel from one Address to another.
class Delivery(object):
    STATUSES = {
        'CREATED': 'created',
        'OPEN': 'open',
        'COMMITTED': 'committed',
        'ENROUTE': 'enroute',
        'RECEIVED': 'received'
    }
    def __init__(self, parcel, source, destination):
        self.parcel = parcel
        self.source = source
        self.destination = destination
        self.status = self.STATUSES['CREATED']
    def open(self, pickup):
        self.pickup = pickup
        self.status = self.STATUSES['OPEN']
        return self
    def commit(self, courier):
        self.courier = courier
        self.status = self.STATUSES['COMMITTED']
        return self
    def pickup(self, deposit):
        self.deposit = deposit
        self.status = self.STATUSES['ENROUTE']
        return self
    def receive(self):
        self.status = self.STATUSES['RECEIVED']
        return self
    
    def getRouteTimeMin(self):
        return round(self.source.routeTimeMin(self.destination), 1)
    
    
# Generate deliveries
from random import uniform
from time import time
deliveries = {
        str(i): Delivery(
            Parcel(),
            Location((uniform(31.95, 32.15), uniform(34.70, 34.90))),
            Location((uniform(31.95, 32.15), uniform(34.70, 34.90))),
        ).open(None) for i in range(200)
}

# Get deliveries for pickup in a radius around a center.
def getdeliveries_sourceinrange(center, radius):
    return [key for key, delivery in deliveries.items() if delivery.source.distance(center) < radius]

# Our jsonp delivering handler
from http.server import SimpleHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs
from json import dumps
class Handler(SimpleHTTPRequestHandler):
    def do_GET(self):

        # Parse query string, make sure we have a callback.
        url = urlparse(self.path)
        if '.jsonp' != url.path[-6:]: return SimpleHTTPRequestHandler.do_GET(self)
        query = parse_qs(url.query)
        if 'callback' not in query: raise Exception('No callback specified')
        callback = query['callback'][-1]

        # Get data for different calls
        try:
            if '/delivery.jsonp' == url.path: data = deliveries[query['id'][0]].source.latlng + (deliveries[query['id'][0]].getRouteTimeMin(),)
            elif '/deliveriesinrange.jsonp' == url.path:
                data = getdeliveries_sourceinrange(
                    [float(i) for i in query['center'][0].split(':')],
                    float(query['radius'][0])
                )
            else: data = {'error': 'Did not understand ' + url.path}
        except (KeyError, ValueError): data = {'error': 'Wrong parameters', 'query': query}

        # Send the reply as jsonp
        self.send_response(200)
        self.send_header('Content-type', 'application/javascript')
        self.end_headers()
        self.wfile.write(bytes(callback + '(' + dumps(data) + ');', 'UTF-8'))

# Run the server on port 8080 till keyboard interrupt.
if __name__ == '__main__':
    server = HTTPServer(('192.168.1.100', 8080), Handler) #yeah! fixit! yeah!
    sockname = server.socket.getsockname()
    try:
        print("\nServing HTTP on", sockname[0], "port", sockname[1], "...")
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nKeyboard interrupt received, exiting.")
        server.server_close()
        from sys import exit
        exit(0)
