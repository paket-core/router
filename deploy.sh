#!/bin/bash
# Deploy a PaKeT server.

# Parse options
usage() { echo 'Usage: ./deploy.sh [d|create-db] [t|test] [s|shell] [r|run-server]'; }
if ! [ "$1" ]; then
    if [ "$BASH_SOURCE" == "$0" ]; then
        usage
        return 0 2>/dev/null
        exit 0
    fi
fi
while [ "$1" ]; do
    case "$1" in
        d|create-db)
            create_db=1;;
        t|test)
            _test=1;;
        s|shell)
            shell=1;;
        r|run-server)
            run=1;;
        *)
            usage
            return 0 2>/dev/null
            exit 0;;
    esac
    shift
done

# Export environment variables.
set -o allexport
. paket.env
set +o allexport

# Requires python3 and python packages (as specified in requirements.txt).
if ! which python3; then
    echo 'python3 not found'
    return 1 2>/dev/null
    exit 1
fi

missing_packages="$(comm -23 <(sed 's|^../||' requirements.txt | sort) <(pip freeze | grep -v '0.0.0' | sort))"
if [ "$missing_packages" ]; then
    echo "The following packages are missing: $missing_packages"
    return 1 2>/dev/null
    exit 1
fi

# Make sure horizon server is reachable.
if ! curl -m 2 "$PAKET_HORIZON_SERVER" | tail -5; then
    echo "Can't connect to horizon server $PAKET_HORIZON_SERVER"
    read -n 1 -p 'Continue anyway? [y|N] ' c
    if ! [ y = "$c" ]; then
        return 1 2>/dev/null
        exit 1
    fi
    echo
fi

if [ "$create_db" ]; then
    rm -i *.db
    python -c "import db; db.init_db()"
fi

if [ "$_test" ]; then
    python -m unittest test
    which pycodestyle && pycodestyle --max-line-length=120 *.py logger webserver
    which pylint && pylint *.py logger webserver

fi

[ "$shell" ] && python -ic 'import logger; logger.setup(); import api; import db; import paket; p = paket'

[ "$run" ] && python ./api.py

return 0 2>/dev/null
exit 0
