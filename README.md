# Restaurant POS & Billing System

Point-of-sale and billing for restaurants, cafés, dhabas, fast food outlets and cloud kitchens — menu management, table status, fast order taking, receipt printing and daily sales reporting on any device.

**[Live demo](https://ahsan-restaurant-pos.vercel.app)** · Login: `admin` / `admin123`

![Dashboard](screenshots/01_dashboard.png)

## Features

**Menu**
- Categories with ordering, item name, price, photo and availability toggle
- Quick add / edit / hide items during service

**Orders & tables**
- Table grid with free / occupied status (auto-detected from open orders)
- Order screen optimised for touch: pick table or walk-in, tap items, live total
- Quantity editing, line notes, discounts (amount or %), GST
- Held and completed orders

**Receipts & sales**
- Clean receipt layout with restaurant name, GST number and footer
- Print or save as PDF, daily auto-incrementing receipt numbers
- Daily sales report: totals, payment methods, category breakdown, best sellers

**Operations**
- Staff login, restaurant settings, automatic daily backups
- Mobile-friendly layout with off-canvas navigation

## Tech stack

Python 3 · Flask · SQLite · Jinja2 · HTML/CSS/JS · Gunicorn + Nginx (VPS) · Vercel (serverless)

## Run locally

```bash
python -m venv venv
venv\Scripts\activate        # Windows
pip install -r requirements.txt
python app.py
```

Open <http://localhost:5001> and sign in with `admin` / `admin123`.
Demo data (8 tables, 18 menu items, sample orders) is included. Reset: `python seed_demo.py`.

## Deploy

- **Vercel:** `vercel --prod` — `api/index.py` + `vercel.json` included. Serverless mode uses `/tmp` for the SQLite copy, so data resets on redeploy.
- **VPS (production):** Gunicorn + Nginx + systemd. This app is also available in a multi-tenant build where every restaurant gets its own isolated database.

## Project structure

```
app.py            Flask application and routes
schema.sql        Database schema
templates/        Jinja2 templates
static/           CSS, JS, icons
seed_demo.py      Demo menu, tables and orders
verify.py         End-to-end smoke checks
```

## Notes

Demo credentials and `SECRET_KEY` are for evaluation only — change both before serving real customers.

## License

MIT © 2026 Ahsan Haroon
