"""Run the PaKeT router server."""
import router
router.APP.run('0.0.0.0', router.routes.PORT, router.webserver.validation.DEBUG)
