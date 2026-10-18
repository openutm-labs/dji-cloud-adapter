#!/bin/sh
set -eu
umask 077
cp /bootstrap/config/mosquitto.conf /mosquitto/config/mosquitto.conf
cp /bootstrap/config/acl /mosquitto/config/acl
cp /bootstrap/config/passwords.input /mosquitto/config/passwords
# Input stays in the private bootstrap mount; the running broker reads PBKDF2 hashes.
mosquitto_passwd -U /mosquitto/config/passwords
chown -R mosquitto:mosquitto /mosquitto/config /mosquitto/data
chmod 600 /mosquitto/config/passwords /mosquitto/config/acl
exec /docker-entrypoint.sh /usr/sbin/mosquitto -c /mosquitto/config/mosquitto.conf
