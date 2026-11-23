"""verify.py — Restaurant POS end-to-end verification (throwaway temp DB).

Run:  venv\\Scripts\\python verify.py        (exit 0 = sab pass)
Real data file (pos.db) kabhi touch nahi hota.
"""
import os
import sys
import sqlite3
import tempfile

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
os.chdir(BASE)

import app as m

fd, tmp = tempfile.mkstemp(suffix='.db')
os.close(fd)
m.DB_PATH = tmp

fails = []


def check(name, cond, extra=''):
    print(('PASS' if cond else 'FAIL'), '|', name, extra)
    if not cond:
        fails.append(name)


def q(sql, args=()):
    conn = sqlite3.connect(tmp)
    conn.row_factory = sqlite3.Row
    r = conn.execute(sql, args).fetchall()
    conn.close()
    return r


def main():
    m.init_db()
    m.seed_admin()
    c = m.app.test_client()

    r = c.post('/login', data={'username': 'admin', 'password': 'admin123'})
    check('login', r.status_code == 302)

    with m.get_db() as conn:
        conn.execute("INSERT INTO tables (name, seats) VALUES ('T1', 2)")
        for name, price in [('Biryani', 450), ('Naan', 80), ('Cola', 120)]:
            conn.execute("INSERT INTO menu_items (name, category, price) "
                         "VALUES (?, 'X', ?)", (name, price))

    # --- order: 2x Biryani + 1x Naan = 980 ---
    r = c.post('/orders/new', data={'table_id': '1', 'discount': '0',
                                    'qty_1': '2', 'qty_2': '1', 'qty_3': '0'},
               follow_redirects=False)
    check('order created', r.status_code == 302 and '/orders/' in r.headers['Location'])
    oid = int(r.headers['Location'].rstrip('/').split('/')[-1])
    o = q('SELECT * FROM orders WHERE id = ?', (oid,))[0]
    check('number format R-YYMMDD-0001', o['order_number'].startswith('R-'), o['order_number'])
    check('subtotal 2*450+80 = 980', o['subtotal'] == 980, f"sub={o['subtotal']}")
    check('total = 980', o['total'] == 980, f"tot={o['total']}")
    check('2 item rows', len(q('SELECT * FROM order_items WHERE order_id = ?', (oid,))) == 2)

    # --- discount order: 450 - 50 = 400 ---
    r = c.post('/orders/new', data={'table_id': '', 'discount': '50',
                                    'qty_1': '1', 'qty_2': '0', 'qty_3': '0'},
               follow_redirects=False)
    oid2 = int(r.headers['Location'].rstrip('/').split('/')[-1])
    o2 = q('SELECT * FROM orders WHERE id = ?', (oid2,))[0]
    check('discount total 450-50 = 400', o2['total'] == 400, f"tot={o2['total']}")

    # --- discount > subtotal -> clamp to 0 ---
    r = c.post('/orders/new', data={'table_id': '1', 'discount': '9999', 'qty_3': '1'},
               follow_redirects=False)
    oid3 = int(r.headers['Location'].rstrip('/').split('/')[-1])
    o3 = q('SELECT * FROM orders WHERE id = ?', (oid3,))[0]
    check('discount clamp -> total 0', o3['total'] == 0, f"tot={o3['total']}")

    # --- dashboard shows occupied table ---
    r = c.get('/')
    check('dashboard shows T1 Occupied', b'Occupied' in r.data and b'T1' in r.data)

    # --- checkout + cancel protection ---
    r = c.post(f'/orders/{oid}/checkout', data={'method': 'card'})
    st = q('SELECT status, payment_method FROM orders WHERE id = ?', (oid,))[0]
    check('checkout -> paid/card', st['status'] == 'paid' and st['payment_method'] == 'card')
    c.post(f'/orders/{oid}/cancel')
    st = q('SELECT status FROM orders WHERE id = ?', (oid,))[0]
    check('paid order not cancellable', st['status'] == 'paid')

    # --- sales sums ---
    c.post(f'/orders/{oid2}/checkout', data={'method': 'cash'})
    c.post(f'/orders/{oid3}/checkout', data={'method': 'cash'})
    t = q("SELECT SUM(total) t, COUNT(*) c FROM orders WHERE status = 'paid'")[0]
    check('sales 980 + 400 + 0 = 1380, 3 orders', t['t'] == 1380 and t['c'] == 3,
          f"t={t['t']} c={t['c']}")

    # --- menu add / toggle / delete ---
    r = c.post('/menu', data={'name': 'Kheer', 'category': 'Dessert', 'price': '180'},
               follow_redirects=True)
    check('menu add', b'Kheer' in r.data)
    kid = q("SELECT id FROM menu_items WHERE name = 'Kheer'")[0]['id']
    c.post(f'/menu/{kid}/toggle')
    check('menu toggle -> unavailable', q('SELECT is_available a FROM menu_items WHERE id = ?',
                                          (kid,))[0]['a'] == 0)
    c.post(f'/menu/{kid}/delete')
    check('menu delete', len(q('SELECT * FROM menu_items WHERE id = ?', (kid,))) == 0)

    # --- tables add/toggle ---
    c.post('/tables', data={'name': 'T9', 'seats': '6'})
    check('table add', len(q("SELECT * FROM tables WHERE name = 'T9'")) == 1)

    # --- regression: /tables render with an OPEN order (was 500: oid missing) ---
    r = c.post('/orders/new', data={'table_id': '1', 'discount': '0', 'qty_3': '1'},
               follow_redirects=False)
    oid_open = int(r.headers['Location'].rstrip('/').split('/')[-1])
    r = c.get('/tables')
    check('/tables 200 with open order', r.status_code == 200, str(r.status_code))
    check('/tables shows Occupied link', b'Occupied' in r.data and b'Order #' in r.data)
    r = c.get('/')
    check('dashboard 200 with open order', r.status_code == 200)

    # --- menu with photo upload ---
    import tempfile as _tf, io as _io
    _td = _tf.mkdtemp()
    m.UPLOAD_DIR = _td  # test uploads go to temp dir, real uploads folder untouched
    import base64
    png = base64.b64decode(
        'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==')
    r = c.post('/menu', data={'name': 'Chicken Roll', 'category': 'Fast Food',
                              'price': '250',
                              'image': (_io.BytesIO(png), 'roll.png')},
               content_type='multipart/form-data', follow_redirects=False)
    check('menu add with image', r.status_code == 302)
    roll = q("SELECT * FROM menu_items WHERE name = 'Chicken Roll'")[0]
    check('image_path saved', roll['image_path'].startswith('uploads/menu/'), roll['image_path'])
    check('image file on disk', os.path.isfile(os.path.join(_td, os.path.basename(roll['image_path']))))
    rid = roll['id']
    # edit name + price (no new image)
    r = c.post(f'/menu/{rid}/edit', data={'name': 'Chicken Roll (Spicy)', 'category': 'Fast Food',
                                          'price': '275', 'image_action': 'keep'},
               follow_redirects=False)
    check('menu edit', r.status_code == 302)
    check('edit applied', q('SELECT name n, price p FROM menu_items WHERE id = ?',
                            (rid,))[0]['n'] == 'Chicken Roll (Spicy)')
    # edit: remove image
    c.post(f'/menu/{rid}/edit', data={'name': 'Chicken Roll (Spicy)', 'category': 'Fast Food',
                                      'price': '275', 'image_action': 'remove'})
    check('image removed on edit', q('SELECT image_path p FROM menu_items WHERE id = ?',
                                     (rid,))[0]['p'] == '')
    check('image file deleted from disk',
          not os.path.isfile(os.path.join(_td, os.path.basename(roll['image_path']))))
    # POS new-order page markup
    r = c.get('/orders/new')
    check('POS page has tiles', b'pos-tile' in r.data and b'data-price' in r.data)
    check('POS page has order panel', b'order-panel' in r.data)
    # delete cleans row
    c.post(f'/menu/{rid}/delete')
    check('menu delete', len(q('SELECT * FROM menu_items WHERE id = ?', (rid,))) == 0)

    # --- all pages 200 ---
    for p in ['/', '/orders', '/orders/new', '/menu', '/tables', '/sales',
              '/settings', '/password', f'/orders/{oid}', f'/orders/{oid}/receipt',
              '/orders?status=paid', '/orders?status=open']:
        r = c.get(p)
        check(f'page {p}', r.status_code == 200, str(r.status_code))

    print(f'==== {59 - len(fails)} passed, {len(fails)} failed (of 59) ====')
    sys.exit(1 if fails else 0)


if __name__ == '__main__':
    main()
