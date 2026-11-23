# -*- coding: utf-8 -*-
"""Seed demo data for the MULTI-TENANT build: central pos.db (users) + tenants/u<id>.db."""
import os
import sqlite3

from werkzeug.security import generate_password_hash

BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE, 'pos.db')
TENANTS = os.path.join(BASE, 'tenants')
SCHEMA = open(os.path.join(BASE, 'schema.sql'), encoding='utf-8').read()

USERS_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    full_name     TEXT NOT NULL DEFAULT '',
    role          TEXT NOT NULL DEFAULT 'user' CHECK (role IN ('user', 'admin')),
    created_at    TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);
"""

MENUS = {
    1: ('Tandoori House', 'Admin Demo Restaurant', [
        ('Chicken Biryani', 'Main Course', 450), ('Mutton Karahi', 'Main Course', 1200),
        ('Chicken Karahi', 'Main Course', 950), ('Seekh Kabab (6 pcs)', 'BBQ', 550),
        ('Chicken Tikka', 'BBQ', 480), ('Garlic Naan', 'Breads', 120),
        ('Tandoori Roti', 'Breads', 40), ('Raita', 'Sides', 80),
        ('Green Salad', 'Sides', 100), ('Soft Drink 500ml', 'Drinks', 120),
    ]),
    2: ('KFC Restaurant', 'KFC - Karachi', [
        ('Zinger Burger', 'Burgers', 550), ('Zinger Tower', 'Burgers', 750),
        ('Hot Wings (6 pcs)', 'Chicken', 480), ('Chicken Piece', 'Chicken', 320),
        ('French Fries', 'Sides', 250), ('Coleslaw', 'Sides', 120),
        ('Pepsi 500ml', 'Drinks', 130), ('Chicken Bucket (8 pcs)', 'Buckets', 1950),
    ]),
    3: ('Pizza Point', 'Pizza Point - Lahore', [
        ('Chicken Fajita Pizza (Medium)', 'Pizza', 1250), ('Pepperoni Pizza (Medium)', 'Pizza', 1450),
        ('Chicken Tikka Pizza (Small)', 'Pizza', 850), ('Garlic Bread', 'Sides', 320),
        ('Pasta Alfredo', 'Pasta', 690), ('Chicken Wings (6 pcs)', 'Sides', 520),
        ('Choco Lava Cake', 'Desserts', 350), ('Soft Drink 1L', 'Drinks', 180),
    ]),
}

TABLES = {1: 8, 2: 6, 3: 4}

os.makedirs(TENANTS, exist_ok=True)
if os.path.exists(DB):
    os.remove(DB)

central = sqlite3.connect(DB)
central.executescript(USERS_SCHEMA)
accounts = [
    ('admin', 'admin123', 'Administrator', 'admin'),
    ('kfc', 'kfc123', 'KFC Manager', 'user'),
    ('pizza', 'pizza123', 'Pizza Point Manager', 'user'),
]
for username, pw, full, role in accounts:
    central.execute('INSERT INTO users (username, password_hash, full_name, role) VALUES (?, ?, ?, ?)',
                    (username, generate_password_hash(pw), full, role))
central.commit()
users = central.execute('SELECT id, username, role FROM users ORDER BY id').fetchall()
print('central users:', users)
central.close()

for uid, (name, address, items) in MENUS.items():
    path = os.path.join(TENANTS, f'u{uid}.db')
    if os.path.exists(path):
        os.remove(path)
    con = sqlite3.connect(path)
    con.executescript(SCHEMA)
    con.execute('INSERT OR REPLACE INTO restaurant_settings (id, restaurant_name, address, phone, '
                'receipt_footer, gst_percent) VALUES (1, ?, ?, ?, ?, ?)',
                (name, address, '+92 300 0000000', 'Thank you! Please visit again.', 0))
    for i in range(1, TABLES[uid] + 1):
        con.execute('INSERT INTO tables (name, seats) VALUES (?, 4)', (f'T{i}',))
    for item, cat, price in items:
        con.execute('INSERT INTO menu_items (name, category, price) VALUES (?, ?, ?)', (item, cat, price))
    con.commit()
    n_items = con.execute('SELECT COUNT(*) FROM menu_items').fetchone()[0]
    n_tables = con.execute('SELECT COUNT(*) FROM tables').fetchone()[0]
    con.close()
    print(f'tenant u{uid} ({name}): {n_items} items, {n_tables} tables -> {path}')

print('DONE')
