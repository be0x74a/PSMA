#!/bin/bash

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
CWD=$(realpath "${1:-runtime}")

cd "$SCRIPT_DIR"/.. || exit 1

celery multi stop 1 --pidfile="$CWD"/celery/%n_dcs.pid --logfile="$CWD"/celery/%p_dcs.log
celery multi stop 1 --pidfile="$CWD"/celery/%n_dps.pid --logfile="$CWD"/celery/%p_dps.log
