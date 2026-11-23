"""Vercel serverless entry point (WSGI) — Restaurant POS."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app import app, init_db, seed_admin  # noqa: E402

try:
    init_db()
    seed_admin()
except Exception as exc:  # pragma: no cover
    print('startup init warning:', exc)

handler = app
