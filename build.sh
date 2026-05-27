#!/usr/bin/env bash
# build.sh — Render.com build script
# Set as the "Build Command" in your Render Web Service settings.
set -o errexit

pip install -r requirements.txt
python manage.py collectstatic --noinput
python manage.py migrate
