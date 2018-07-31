"""Run the PaKeT funding server."""
import sys
import os.path

import webserver

import api.routes

# Python imports are silly.
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
# pylint: disable=wrong-import-position
import api.swagger_specs
# pylint: enable=wrong-import-position

webserver.run(api.routes.BLUEPRINT, api.swagger_specs.CONFIG, api.routes.PORT)
