"""One-time migration: legacy shared app data (central pos.db) -> admin tenant u1.db.

Multi-tenant refactor ke baad central pos.db me SIRF users table rehna hai.
Ye script (deploy-time, ek dafa):
  1. central ke app tables (settings/menu/orders...) ka data tenants/u1.db (admin) me copy karta hai
  2. central se wo app tables drop kar deta hai (ab data tenant files me hai)
  3. naya koi bhi client (KFC etc) KHALI tenant file pe start hota hai — migration sirf admin ko deta hai
"""
import os
import sqlite3

BASE = '/opt/restaurant-pos'
CENTRAL = os.path.join(BASE, 'pos.db')
APP_TABLES = ['restaurant_settings', 'tables', 'menu_items',
              'orders', 'order_items', 'receipt_sequences']

src = sqlite3.connect(CENTRAL)
src.row_factory = sqlite3.Row
has_legacy = bool(src.execute(
    "SELECT 1 FROM sqlite_master WHERE type='table' AND name='menu_items'").fetchone())

if not has_legacy:
    print('no legacy app tables in central — already migrated or fresh')
    src.close()
    raise SystemExit(0)

dst = sqlite3.connect(os.path.join(BASE, 'tenants', 'u1.db'))

# settings: tenant file me pehle se default row (id=1) hai -> update, insert nahi
row = src.execute('SELECT * FROM restaurant_settings WHERE id=1').fetchone()
if row:
    dst.execute(
        'UPDATE restaurant_settings SET restaurant_name=?, address=?, phone=?, '
        'receipt_footer=?, gst_percent=? WHERE id=1',
        (row['restaurant_name'], row['address'], row['phone'],
         row['receipt_footer'], row['gst_percent']))
    print('settings copied -> u1 (admin)')

for t in APP_TABLES:
    if t == 'restaurant_settings':
        continue
    rows = src.execute(f'SELECT * FROM {t}').fetchall()
    if not rows:
        continue
    cols = [d[0] for d in src.execute(f'SELECT * FROM {t}').description]
    marks = ','.join('?' * len(cols))
    dst.executemany(f'INSERT INTO {t} ({",".join(cols)}) VALUES ({marks})',
                    [tuple(r) for r in rows])
    print(f'{t}: {len(rows)} rows copied -> u1 (admin)')

# autoincrement continuity
for t in ('tables', 'menu_items', 'orders', 'order_items'):
    row = src.execute('SELECT seq FROM sqlite_sequence WHERE name=?', (t,)).fetchone()
    if row:
        dst.execute('INSERT OR REPLACE INTO sqlite_sequence (name, seq) VALUES (?, ?)',
                    (t, row['seq']))
dst.commit()
dst.close()

# ab central se app tables hatao — sirf users rehna chahiye
for t in APP_TABLES:
    src.execute(f'DROP TABLE IF EXISTS {t}')
try:
    src.execute("DELETE FROM sqlite_sequence WHERE name IN ('restaurant_settings','tables','menu_items','orders','order_items','receipt_sequences')")
except sqlite3.OperationalError:
    pass
src.commit()
left = [r[0] for r in src.execute(
    "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
print('central tables now:', left)
src.close()
print('MIGRATION DONE')
