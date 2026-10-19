#!/bin/sh
set -eu
umask 077
cp /bootstrap/config/mosquitto.conf /mosquitto/config/mosquitto.conf
if [ -f /bootstrap/config/dynamic-security.json ] && grep -q '^plugin ' /bootstrap/config/mosquitto.conf; then
    # The persisted broker file is authoritative after first bootstrap.
    if [ ! -f /mosquitto/data/dynamic-security.json ]; then
        cp /bootstrap/config/dynamic-security.json /mosquitto/data/dynamic-security.json
    fi
    chown -R mosquitto:mosquitto /mosquitto/config /mosquitto/data
    chmod 600 /mosquitto/data/dynamic-security.json
    exec /docker-entrypoint.sh /usr/sbin/mosquitto -c /mosquitto/config/mosquitto.conf
fi
cp /bootstrap/config/acl /mosquitto/config/acl
cp /bootstrap/config/passwords.input /mosquitto/config/passwords
# Input stays in the private bootstrap mount; the running broker reads PBKDF2 hashes.
mosquitto_passwd -U /mosquitto/config/passwords
chown -R mosquitto:mosquitto /mosquitto/config /mosquitto/data
chmod 600 /mosquitto/config/passwords /mosquitto/config/acl
exec /docker-entrypoint.sh /usr/sbin/mosquitto -c /mosquitto/config/mosquitto.conf
