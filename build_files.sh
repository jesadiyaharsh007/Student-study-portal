#!/bin/bash
python3 -m pip install -r requirements.txt --break-system-packages 2>/dev/null || python3 -m pip install -r requirements.txt || pip install -r requirements.txt
python3 manage.py collectstatic --noinput --clear
