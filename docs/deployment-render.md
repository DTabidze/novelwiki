# Render Deployment

This project can be deployed as two Render services:

- Backend: Flask web service from `backend/`
- Frontend: Vite static site from `frontend/`

This guide keeps deployment simple and uses SQLite. For real production traffic, move to a managed Postgres database and proper migrations later.

## Backend Web Service

Create a Render **Web Service** from the repository.

Settings:

| Setting | Value |
| --- | --- |
| Root Directory | `backend` |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `gunicorn run:app` |

Environment variables:

| Variable | Example |
| --- | --- |
| `FLASK_ENV` | `production` |
| `SECRET_KEY` | Generate a long random value |
| `DATABASE_URL` | `sqlite:////var/data/novelwiki.db` |
| `UPLOAD_FOLDER` | `/var/data/uploads` |
| `FRONTEND_ORIGINS` | `https://your-frontend.onrender.com` |
| `SESSION_COOKIE_SAMESITE` | `None` |
| `SESSION_COOKIE_SECURE` | `true` |
| `OPENAI_API_KEY` | Your OpenAI API key |
| `OPENAI_MODEL` | `gpt-4o-mini` or the model you want |

Add a Render persistent disk mounted at:

```text
/var/data
```

Without a persistent disk, SQLite data and uploaded files can disappear after redeploys/restarts.

## Frontend Static Site

Create a Render **Static Site** from the same repository.

Settings:

| Setting | Value |
| --- | --- |
| Root Directory | `frontend` |
| Build Command | `npm ci && npm run build` |
| Publish Directory | `dist` |

Environment variables:

| Variable | Example |
| --- | --- |
| `VITE_API_BASE_URL` | `https://your-backend.onrender.com/api` |

After the frontend URL is known, copy it into the backend `FRONTEND_ORIGINS` env var.

## Create The First Superadmin

After the backend service is deployed and the database exists, open a Render shell for the backend service and run:

```bash
SUPERADMIN_USERNAME="Your Name" \
SUPERADMIN_EMAIL="you@example.com" \
SUPERADMIN_PASSWORD="change-this-long-password" \
flask --app run.py create-superadmin
```

The command is idempotent:

- If the user does not exist, it creates a superadmin.
- If a user with that username or email exists, it promotes/updates that user to superadmin and resets the password.

Do not keep `SUPERADMIN_PASSWORD` stored in Render env vars after the account is created unless you intentionally want to reuse it.

## Quick Health Check

Backend:

```text
https://your-backend.onrender.com/api/health
```

Frontend:

```text
https://your-frontend.onrender.com/wiki/novels
```

## Common Problems

- Login works locally but not on Render:
  - Ensure backend `FRONTEND_ORIGINS` exactly matches the frontend URL.
  - Ensure `SESSION_COOKIE_SAMESITE=None`.
  - Ensure `SESSION_COOKIE_SECURE=true`.
  - Ensure frontend `VITE_API_BASE_URL` points to the backend `/api`.

- Database resets after redeploy:
  - Add a persistent disk and use `DATABASE_URL=sqlite:////var/data/novelwiki.db`.

- No admin account exists:
  - Run the `flask --app run.py create-superadmin` command from the backend Render shell.
