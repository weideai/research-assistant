#!/bin/sh
set -eu

flask --app run.py db upgrade
exec "$@"

