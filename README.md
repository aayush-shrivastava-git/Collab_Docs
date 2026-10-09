# CollabDocs

API-only collaborative document backend built with Django REST Framework and PostgreSQL.

## Features

- UUID primary keys for the eight domain models.
- Workspace membership with role choices and a unique `(workspace, user)` constraint.
- Documents, version history, threaded comments, tags, and audit logs.
- Custom request timing middleware.
- Document `post_save` audit signal.
- Transactional workspace creation and document/version saves.
- Filtering, aggregation, and related-object query optimization.

## Requirements

- Python 3.11+ (use the Python version installed in your environment)
- Docker Desktop with Docker Compose
- Dependencies listed in `requirements.txt`

## Setup (Windows PowerShell)

1. Create and activate a virtual environment:

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

2. Install dependencies:

   ```powershell
   pip install -r requirements.txt
   ```

3. Copy `env.example` to `.env` and set the local database credentials to match your configuration:

   ```powershell
   Copy-Item env.example .env
   ```

4. Start PostgreSQL:

   ```powershell
   docker compose up -d
   docker compose ps
   ```

5. Apply migrations and check the project:

   ```powershell
   python manage.py migrate
   python manage.py check
   ```

6. Start the development server:

   ```powershell
   python manage.py runserver
   ```

API base URL: `http://127.0.0.1:8000/api/`

## PostgreSQL and pgAdmin

Use these values when registering the Docker database in pgAdmin:

- **Host:** `localhost`
- **Port:** `5434`
- **Maintenance database:** value of `DB_NAME` in `.env`
- **Username:** value of `DB_USER` in `.env`
- **Password:** value of `DB_PASSWORD` in `.env`

## Postman

Import `CollabDocs_API_postman_collection.json` into Postman. Set the collection variables `user_id`, `workspace_id`, `document_id`, and `tag_id` to UUIDs returned from successful create requests. Create a second user and use that user's real UUID when testing **Add workspace member**.

The collection contains 17 requests across Users, Workspaces, Documents, Comments, Tags, and Audit Logs. Some requests depend on IDs returned by earlier requests.

## Transaction rollback demonstration

Run the following after the local database is configured and the required user/workspace data is available:

```powershell
python test_rollback.py
```

The script deliberately raises an exception inside an atomic transaction and checks that the document, version, and signal-generated audit entry are absent afterward.

## Demo video

The demo video is submitted separately through the assignment submission portal.

## Security notes

- Do not commit `.env`; commit `env.example` only.
- Use local/example credentials only and never publish real passwords or secrets.
- The current API uses `AllowAny` to keep the assignment's Postman flow simple. Add authentication and object-level permissions before using it in production.
