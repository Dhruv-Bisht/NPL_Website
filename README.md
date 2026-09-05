# NPL Website

An interactive National Premier League-style cricket auction platform built with Flask, SQLAlchemy and a modern responsive UI.

## Features

- Player registration
- Player photo upload stored as database data, so the app does not depend on a writable server filesystem
- View/search/filter all registered players
- Individual player profiles
- Teams page
- Individual team pages showing every sold player in that team
- Admin team creation
- Live-style auction dashboard
- Sell players to teams with purse validation
- Mark players unsold
- Auction history
- Dashboard statistics
- PostgreSQL support for production
- SQLite support for local development
- Vercel serverless entrypoint

## Local setup

```bash
python -m venv venv
# Windows
venv\Scripts\activate

pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:5000

Default local admin password:

```text
npladmin
```

Change it with the `ADMIN_PASSWORD` environment variable.

## Vercel deployment

For a real deployment, create a PostgreSQL database (Neon, Supabase, Railway PostgreSQL, etc.) and add these Vercel environment variables:

```text
DATABASE_URL=your-postgresql-connection-string
SECRET_KEY=a-long-random-secret
ADMIN_PASSWORD=a-strong-admin-password
```

Then import the GitHub repository into Vercel.

The app creates its tables automatically on startup.

### Important

Vercel's filesystem is ephemeral. This project intentionally stores uploaded player/team images as base64 data in the database instead of writing them to `static/uploads/`. Use PostgreSQL for production rather than relying on SQLite.

For a larger production system, move images to object storage such as Vercel Blob, Cloudinary or S3.

## Admin

Go to `/admin/login`.

Admin can:

- create teams
- conduct the auction
- sell a player to a team
- mark a player unsold
- see recent auction activity

## Project structure

```text
NPL_Website/
├── api/
│   └── index.py
├── templates/
├── static/
│   ├── css/
│   └── js/
├── app.py
├── requirements.txt
├── vercel.json
├── Procfile
└── README.md
```
