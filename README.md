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
- PostgreSQL container from `docker-compose.yml`
- Dependencies from `requirements.txt`

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

3. Copy `.env.example` to `.env` and set a local password.

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

- Host: `localhost`
- Port: `5434`
- Maintenance database: value of `DB_NAME`
- Username: value of `DB_USER`
- Password: value of `DB_PASSWORD`

## Postman

Import `CollabDocs.postman_collection.json` into Postman. Set the collection variables `user_id`, `workspace_id`, `document_id`, and `tag_id` using UUIDs returned from successful create requests. Create a second user before testing **Add workspace member**.

Recommended order:
1. Create user
2. Create workspace
3. List workspace members and workspace summary
4. Create a tag
5. Create and update a document
6. Assign tag, view versions and stats
7. Create/list comments
8. Inspect audit logs

The collection includes 17 requests across the folders Users, Workspaces, Documents, Comments, Tags, and Audit Logs. Some requests depend on IDs returned by earlier requests.

## Transaction rollback demonstration

Run `python test_rollback.py` after creating a user and workspace. It deliberately raises an exception inside an atomic block and checks that the document, version, and signal-generated audit entry are absent afterward.

For the demo video, show the script, run it in the terminal, and explain that the intentional exception causes the database transaction to roll back.

## Demo video

Record a 5–10 minute walkthrough with audio showing:
- Creating a user and workspace, and the owner membership.
- Creating/updating a document and checking version history.
- Audit log entries created by the document signal.
- Workspace/document aggregation endpoints.
- Request timing logs in the Django console.
- The rollback demonstration.

After recording, upload the video to Loom or Google Drive and replace this line with the share link:

**Demo video:** TODO — add Loom/Google Drive URL.

## Security and submission notes

- Do not commit `.env`; commit `.env.example` only.
- Change example passwords before using the project outside local development.
- The current API uses `AllowAny` to keep this assignment's Postman flow simple; it is not suitable for production without authentication and object-level permissions.
