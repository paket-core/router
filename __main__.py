"""Run the PAKET routing server."""
import router
router.APP.run('0.0.0.0', router.routes.PORT, router.webserver.validation.DEBUG)
