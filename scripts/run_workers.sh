#!/bin/bash

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
CWD=$(realpath "${1:-runtime}")

cd "$SCRIPT_DIR"/.. || exit 1

export PSMA_CONFIG_FILE="$CWD"/.env
export DCS_CWD="$CWD"/dcs
export DPS_CWD="$CWD"/dps
export $(lockutils-wrapper env | grep OSLO_LOCK_PATH)

celery multi start 12 -A psma.workers.celery_worker -l INFO --pidfile="$CWD"/celery/%n_dcs.pid --logfile="$CWD"/celery/%p_dcs.log -Q dcs -c 1 --hostname=dcs.psma
celery multi start 1 -A psma.workers.celery_worker -l INFO --pidfile="$CWD"/celery/%n_dps.pid --logfile="$CWD"/celery/%p_dps.log -Q dps -c 1 --hostname=dps.psma

celery -A psma.workers.celery_worker control enable_events