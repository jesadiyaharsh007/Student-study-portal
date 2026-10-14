#!/bin/bash
python3 -m pip install -r requirements.txt --break-system-packages 2>/dev/null || python3 -m pip install -r requirements.txt || pip install -r requirements.txt
python3 manage.py collectstatic --noinput --clear
# Create/upgrade tables (e.g. the admin console's sessions). Non-fatal so a build never fails on a database hiccup.
python3 manage.py migrate --noinput || echo "WARNING: migrate did not finish. Run 'python manage.py migrate' against the production database."
