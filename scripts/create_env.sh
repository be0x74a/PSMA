#!/bin/bash

FILE=$1/.env
if [ ! -f "$FILE" ]; then
    echo "SFTP_PASS=\"$(cat /dev/urandom | tr -dc 'a-zA-Z0-9' | fold -w 32 | head -n 1)\"" >> "$FILE"
    echo "PSQL_PASS=\"$(cat /dev/urandom | tr -dc 'a-zA-Z0-9' | fold -w 32 | head -n 1)\"" >> "$FILE"
    echo "REDIS_PASS=\"$(cat /dev/urandom | tr -dc 'a-zA-Z0-9' | fold -w 32 | head -n 1)\"" >> "$FILE"
    echo "SFTP_HOST=\"localhost\"" >> "$FILE"
    echo "SFTP_PORT=\"2222\"" >> "$FILE"
    echo "PSQL_HOST=\"localhost\"" >> "$FILE"
    echo "REDIS_HOST=\"localhost\"" >> "$FILE"
fi
