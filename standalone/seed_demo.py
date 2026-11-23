"""seed_demo.py — Restaurant POS demo data (menu, tables, sample orders).

Run:  venv\\Scripts\\python seed_demo.py
Login: admin / admin123
"""
import os
import sys
from datetime import datetime, timedelta

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)
sys.path.insert(0, BASE_DIR)

from app import app, init_db, seed_admin
from app import get_db


def menu_item_by_name(name):
    with get_db() as conn:
        return conn.execute('SELECT * FROM menu_items WHERE name = ?', (name,)).fetchone()

MENU = [
    # (name, category, price)
    ('Chicken Biryani',     'Main Course', 450),
    ('Mutton Karahi',       'Main Course', 1200),
    ('Chicken Karahi',      'Main Course', 900),
    ('Daal Makhani',        'Main Course', 350),
    ('Mixed Vegetables',    'Main Course', 300),
    ('Garlic Naan',         'Breads',      80),
    ('Roghni Naan',         'Breads',      90),
    ('Plain Naan',          'Breads',      50),
    ('Vegetable Biryani',   'Rice',        320),
    ('Special Pulao',       'Rice',        380),
    ('Chicken Tikka (4pc)', 'BBQ',         600),
    ('Seekh Kebab (4pc)',   'BBQ',         550),
    ('Chicken Malai Boti',  'BBQ',         650),
    ('Coke 500ml',          'Drinks',      120),
    ('Mineral Water',       'Drinks',      80),
    ('Fresh Lime Soda',     'Drinks',      150),
    ('Kheer',               'Desserts',    180),
    ('Gulab Jamun (2pc)',   'Desserts',    150),
]

TABLES = ['T1', 'T2', 'T3', 'T4', 'T5', 'Table 6', 'Table 7', 'Table 8']


def main():
    init_db()
    seed_admin()

    with get_db() as conn:
        # Restaurant settings
        conn.execute(
            "UPDATE restaurant_settings SET restaurant_name = 'Tandoori House', "
            "address = 'Main Market, Gulberg II, Lahore', phone = '+92 42 3575 1234', "
            "gst_percent = 0 WHERE id = 1")
        # Tables
        for name in TABLES:
            conn.execute('INSERT OR IGNORE INTO tables (name, seats) VALUES (?, ?)',
                         (name, 4 if name.startswith('Table') else 2))
        # Menu
        for name, cat, price in MENU:
            conn.execute('INSERT INTO menu_items (name, category, price) VALUES (?, ?, ?)',
                         (name, cat, price))

    client = app.test_client()
    r = client.post('/login', data={'username': 'admin', 'password': 'admin123'})
    assert r.status_code == 302, 'login failed'

    # --- Sample orders: aaj ke 4 paid orders + 1 open order ---
    sample_orders = [
        (1, [('Chicken Biryani', 2), ('Garlic Naan', 2), ('Coke 500ml', 2)]),      # T1
        (3, [('Mutton Karahi', 1), ('Roghni Naan', 3), ('Mineral Water', 1)]),     # T3
        (None, [('Chicken Tikka (4pc)', 1), ('Seekh Kebab (4pc)', 1)]),            # walk-in
        (5, [('Vegetable Biryani', 1), ('Fresh Lime Soda', 2), ('Gulab Jamun (2pc)', 1)]),
    ]
    for table_id, items in sample_orders:
        data = {'table_id': str(table_id) if table_id else '', 'discount': '0'}
        for name, qty in items:
            row = menu_item_by_name(name)
            data[f'qty_{row["id"]}'] = str(qty)
        r = client.post('/orders/new', data=data, follow_redirects=False)
        assert r.status_code == 302, f'order failed: {items}'
        oid = int(r.headers['Location'].rstrip('/').split('/')[-1])
        r = client.post(f'/orders/{oid}/checkout', data={'method': 'cash'})
        assert r.status_code == 302, f'checkout failed: {oid}'
        # order ko aaj ka din dikhao (created_at pehle se default = abhi)

    # Ek open order (T2) — dashboard par occupied table dikhe
    data = {'table_id': '2', 'discount': '0'}
    for name, qty in [('Chicken Karahi', 1), ('Plain Naan', 4), ('Coke 500ml', 1)]:
        row = menu_item_by_name(name)
        data[f'qty_{row["id"]}'] = str(qty)
    r = client.post('/orders/new', data=data, follow_redirects=False)
    assert r.status_code == 302, 'open order failed'

    print('=' * 56)
    print('  Restaurant POS demo data ready!')
    print('  Login: admin / admin123')
    print('  8 tables, 18 menu items, 4 paid orders + 1 open order')
    print('  Run:  run.bat  →  http://localhost:5001')
    print('=' * 56)


if __name__ == '__main__':
    main()
