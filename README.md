PaKeT API Server
================

The PaKeT API Server is a centralized server which provides a bridge between mobile and Web apps and the Stellar network, in addition to some very basic routing capabilities.

To Run the Server
-----------------

1. Clone the repository:

```
git clone git@github.com:paket-core/api.git
```

2. Optionally, create and / or activate a python virtual environment:

```
python3 -m venv venv
. venv/bin/activate
```

3. Upgrade pip and install requirements:

```
pip install --upgrade pip
pip install -r requirements.txt
```

4. Make sure your `paket.env` contains all desired variables. Available values are:
  * `PAKET_HORIZON_SERVER` - to specify your horizon server.
  * `PAKET_USER_ISSUER` - to specify the issuer seed.
  * `PAKET_DEBUG` - to run the api server in debug mode, with debug calls and no signature checking.
  * `FLASK_DEBUG` - to run the web server in debug mode with auto reloading.
  * `PAKET_USER_XXX` - to specify seeds for builtin prefunded users.

5. Run the deploy script to start the server with the following commands:
  * `s|shell` - to run python interactive shell and import main modules.
  * `d|create-db` - to remove existing DBs and recreate them.
  * `t|test` - to run tests.
  * `r|run-server` - to run the server.

7. Access the swagger Web interface from a browser at: http://localhost:8000
