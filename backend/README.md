# Subbayya Gari Hotel — Separate Frontend & Backend

## Structure
- `frontend/` — customer UI, admin UI, CSS, JavaScript, logo and frontend assets
- `backend/` — Flask API, SQLite database, uploads and Python dependencies

## Run
1. Open the **backend** folder in VS Code.
2. Terminal: `pip install -r requirements.txt`
3. Run: `python app.py`
4. Customer site: `http://127.0.0.1:5000`
5. Menu: `http://127.0.0.1:5000/menu`
6. Admin (direct URL): `http://127.0.0.1:5000/admin`

The Admin link is intentionally hidden from the customer-facing navigation. Admin access remains protected by the login password.
