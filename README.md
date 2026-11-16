# QueueLess

A queue management app: customers book a token, staff call the next in line, and everyone sees the live status. Built with Django REST Framework on the backend and React + Vite on the frontend.

## Features

- Book tokens (General, Priority, Support) with an auto-incrementing number starting at 101
- Live queue status: now serving, waiting list, and estimated wait time (5 min per token)
- Staff controls to call the next token, cancel a waiting token, or reset the queue
- Responsive React UI with polling for real-time updates

## Tech stack

| Layer    | Tech                                              |
| -------- | ------------------------------------------------- |
| Backend  | Python, Django 5.2, Django REST Framework, django-cors-headers |
| Frontend | React 19, Vite 8, oxlint                          |
| Database | SQLite (development)                              |

## Project structure

```
queueless/
├── config/          # Django project settings and root URLs
├── queueapp/        # Queue models, serializers, views, API routes
├── frontend/        # React + Vite client
├── manage.py
└── requirements.txt
```

## Getting started

### Backend

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
source .venv/bin/activate     # macOS / Linux

pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

The API is served at `http://127.0.0.1:8000/`.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Vite runs at `http://localhost:5173/` and talks to the backend at `http://127.0.0.1:8000` by default. Override with an environment variable:

```bash
VITE_API_URL=http://your-api-host npm run dev
```

## API reference

Base path: `/api/`

| Method | Endpoint                  | Description                                       |
| ------ | ------------------------- | ------------------------------------------------- |
| GET    | `/status/`                | Current queue: now serving, waiting list, ETA      |
| POST   | `/book/`                  | Book a token — body: `{ "customer_name", "service_type" }` |
| POST   | `/next/`                  | Complete the current token and call the next one   |
| POST   | `/cancel/<token_number>/` | Cancel a waiting token                             |
| POST   | `/reset/`                 | Delete all tokens and reset the queue              |

`service_type` must be one of `General`, `Priority`, or `Support`.

### Example

```bash
curl -X POST http://127.0.0.1:8000/api/book/ \
  -H "Content-Type: application/json" \
  -d '{"customer_name": "Alice", "service_type": "General"}'
```

## Notes

- `db.sqlite3`, `node_modules/`, and build output are ignored — the database is created on first `migrate`.
- `DEBUG` is on and `SECRET_KEY` is committed for local development only. Replace both before deploying.

## License

MIT
