#!/bin/bash
# Deploy a PaKeT server.

if ! [ "$VIRTUAL_ENV" ]; then
    echo "refusing to install outside of virtual env"
    return 2 2>/dev/null
    exit 4
fi

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

# Requires python3.
if ! which python3 > /dev/null; then
    echo 'python3 not found'
    return 1 2>/dev/null
    exit 1
fi

# Requires python packages (as specified in requirements.txt).
set -e
installed_packages="$(pip freeze)"
local_packages=()
while read package; do
    # Make sure local packages exist and are up to date.
    if [ ${package:0:3} = '../' ]; then
        local_packages+=("$package")
        if ! [ -d "$package" ]; then
            set -e
            q='n'; read -n 1 -p "Missing local package $package - try to fetch from github? [y|N] " q < /dev/tty; echo
            if [ y = "$q" ]; then
                pushd .. > /dev/null
                git clone "git@github.com:paket-core/${package:3}.git"
                popd > /dev/null
            else
                echo "Can't continue without $package"
                return 1 2>/dev/null
                exit 1
            fi
        else
            q='n'; read -n 1 -p "Update local package $package? [y|N] " q < /dev/tty; echo
            if [ y = "$q" ]; then
                pushd "$package" > /dev/null
                git pull
                popd > /dev/null
            fi
        fi
    fi
done < requirements.txt
pip install -r requirements.txt
set +e

# Make sure horizon server is reachable.
if ! curl -m 2 "$PAKET_HORIZON_SERVER" > /dev/null; then
    echo "Can't connect to horizon server $PAKET_HORIZON_SERVER"
    q='n'; read -n 1 -p 'Continue anyway? [y|N] ' q; echo
    if ! [ y = "$q" ]; then
        return 1 2>/dev/null
        exit 2
    fi
    echo
fi

if [ "$create_db" ]; then
    rm -i *.db
    python -c "import db; db.init_db()"
fi

if [ "$_test" ]; then
    original_db_name="$PAKET_DB_NAME"
    PAKET_DB_NAME=test
    export PAKET_DB_NAME
    for package in "${local_packages[@]}"; do
        pushd "$package" > /dev/null
        echo
        pwd
        echo ---
        which pycodestyle > /dev/null && echo pycodestyle had $(pycodestyle --max-line-length=120 **/*.py 2>&1 | wc -l) issues
        which pylint > /dev/null && pylint **/*.py 2>&1 | tail -2 | head -1
        python -m unittest 2>&1 | tail -3 | head -1
        popd > /dev/null
    done
    echo
    pwd
    echo ---
    which pycodestyle > /dev/null && echo pycodestyle had $(pycodestyle --max-line-length=120 *.py **/*.py 2>&1 | wc -l) issues
    which pylint > /dev/null && pylint *.py **/*.py | tail -2 | head -1
    python -m unittest
    PAKET_DB_NAME="$original_db_name"
fi

[ "$shell" ] && python -ic 'import util.logger; util.logger.setup(); import routes; import db'

[ "$run" ] && python ./routes.py

return 0 2>/dev/null
exit 0
