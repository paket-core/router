#!/bin/bash
# Deploy a PaKeT server.

# Export environment variables.
set -o allexport
. paket.env
set +o allexport

# Exit if sourced.
[ "$BASH_SOURCE" == "$0" ] || return 0

# Parse options
usage() { echo 'Usage: ./deploy.sh [i|install] [d|create-db] [t|test] [s|shell] [r|run-server]'; }
if ! [ "$1" ]; then
    usage
    exit 0
fi
while [ "$1" ]; do
    case "$1" in
        i|install)
            install=1;;
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
            exit 0;;
    esac
    shift
done

# Requires python3.
if ! which python3 > /dev/null; then
    echo 'python3 not found'
    exit 1
fi

# Requires python packages (as specified in requirements.txt).
set -e
installed_packages="$(pip freeze)"
local_packages=()
while read package; do
    if [ ${package:0:3} = '../' ]; then
        local_packages+=("$package")
        if ! [ -d "$package" ]; then
            echo "$package not found"
            exit 1
        else
            package="$(grep -Po "(?<=name=.).*(?=')" "$package/setup.py")=="
        fi
    fi
    if ! grep "$package" > /dev/null <<<"$installed_packages"; then
        echo "$package not found"
        exit 1
    fi
done < requirements.txt
set +e

if [ "$install" ]; then
    if ! [ "$VIRTUAL_ENV" ]; then
        echo "refusing to install outside of virtual env"
        exit 2
    fi
    set -e
    for package in "${local_packages[@]}"; do
        # Make sure local packages exist and are up to date.
        if ! [ -d "$package" ]; then
            pushd .. > /dev/null
            git clone "git@github.com:paket-core/${package:3}.git"
            popd > /dev/null
        else
            q='n'; read -n 1 -p "Update local package $package? [y|N] " q < /dev/tty; echo
            if [ y = "$q" ]; then
                pushd "$package" > /dev/null
                git pull
                popd > /dev/null
            fi
        fi
    done
    pip install -r requirements.txt
    set +e
fi

if [ "$create_db" ]; then
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

[ "$shell" ] && python -ic 'import util.logger; util.logger.setup(); import db; import routes'

[ "$run" ] && python ./routes.py

exit 0
