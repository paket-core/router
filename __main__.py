"""Run the PaKeT router server."""
import sys
import os.path

import util.logger
import webserver

import router.routes

# Python imports are silly.
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
# pylint: disable=wrong-import-position
import router.swagger_specs
# pylint: enable=wrong-import-position

util.logger.setup()

webserver.run(router.routes.BLUEPRINT, router.swagger_specs.CONFIG, router.routes.PORT)
