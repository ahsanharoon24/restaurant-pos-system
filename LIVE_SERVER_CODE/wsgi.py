"""Production entry point — gunicorn isko import karta hai (wsgi:app).

app.py me DB init sirf `python app.py` (dev) pe chalta tha. Yahan import
time pe init_db() + seed_admin() chala kar pakka karte hain ke server par
bhi tables ban jayen aur admin/admin123 login maujood ho.

Schema.sql IF NOT EXISTS / INSERT OR IGNORE use karta hai, to har worker
ke import pe repeat karna safe hai.
"""
from app import app, init_db, seed_admin

init_db()
seed_admin()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=False)
