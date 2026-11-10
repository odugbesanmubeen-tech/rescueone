# Emergency Response & Incident Management System

Django + Channels + Leaflet, vanilla JavaScript. Local development uses SQLite
(no database server needed). Locations are stored as latitude/longitude numbers.

## Setup (Windows PowerShell)

    py -m venv venv
    Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
    venv\Scripts\Activate.ps1
    pip install -r requirements.txt
    copy .env.example .env
    py manage.py check
    py manage.py makemigrations accounts audit stations vehicles citizens responders locations incidents dispatch notifications dashboard
    py manage.py migrate
    py manage.py test
    py manage.py createsuperuser
    py manage.py runserver

Sign in at http://127.0.0.1:8000/login/

## Later, for production

Switch DATABASES to PostgreSQL (optionally with PostGIS) and set REDIS_URL so
WebSockets and the cache are shared between workers.

## Citizen app (installable PWA)

Open http://127.0.0.1:8000/app/ and register a citizen account.
Browsers allow location access only on HTTPS or localhost, so testing on a phone
over your Wi-Fi needs an HTTPS tunnel (for example cloudflared or ngrok).
