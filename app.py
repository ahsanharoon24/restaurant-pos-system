"""Restaurant POS — menu, tables, orders, receipts, sales report.

Single-file Flask app (portfolio demo). Run: run.bat
Login: admin / admin123
"""
import os
import sqlite3
from datetime import datetime
from uuid import uuid4

from flask import (Flask, abort, flash, redirect, render_template,
                   request, session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'pos.db')
# --- Serverless (Vercel) support: only /tmp is writable -----------------
if os.environ.get('VERCEL'):
    import shutil as _shutil
    DB_PATH = '/tmp/pos.db'
    _src = os.path.join(BASE_DIR, 'pos.db')
    if not os.path.exists(DB_PATH) and os.path.exists(_src):
        _shutil.copyfile(_src, DB_PATH)


app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'pos-demo-secret-change-me')
app.config['MAX_CONTENT_LENGTH'] = 8 * 1024 * 1024  # 8 MB max photo upload

UPLOAD_DIR = ('/tmp/uploads/menu' if os.environ.get('VERCEL') else os.path.join(BASE_DIR, 'static', 'uploads', 'menu'))
os.makedirs(UPLOAD_DIR, exist_ok=True)
ALLOWED_IMG = {'png', 'jpg', 'jpeg', 'gif', 'webp'}


# ==================================================================
# DB helpers
# ==================================================================
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    return conn


def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.executescript(open(os.path.join(BASE_DIR, 'schema.sql'),
                                encoding='utf-8').read())
        # migration: purane DBs mein image_path column add karo
        try:
            conn.execute("ALTER TABLE menu_items ADD COLUMN image_path TEXT NOT NULL DEFAULT ''")
            conn.commit()
        except sqlite3.OperationalError:
            pass


def save_item_image(file_storage):
    """Uploaded dish photo save karo; relative path ya '' return karo."""
    if not file_storage or not file_storage.filename:
        return ''
    fname = file_storage.filename
    ext = fname.rsplit('.', 1)[-1].lower() if '.' in fname else ''
    if ext not in ALLOWED_IMG:
        return ''
    safe = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid4().hex[:6]}.{ext}"
    file_storage.save(os.path.join(UPLOAD_DIR, safe))
    return f'uploads/menu/{safe}'


def delete_item_image(image_path):
    if image_path:
        # UPLOAD_DIR se basename join karo — test redirects bhi respect hote hain
        p = os.path.join(UPLOAD_DIR, os.path.basename(image_path))
        if os.path.isfile(p):
            try:
                os.remove(p)
            except OSError:
                pass


def settings_row():
    with get_db() as conn:
        row = conn.execute('SELECT * FROM restaurant_settings WHERE id = 1').fetchone()
        return dict(row) if row else {}


# ==================================================================
# Auth
# ==================================================================
@app.context_processor
def inject_globals():
    return dict(settings=settings_row(), logged_in='user' in session)


def login_required(fn):
    from functools import wraps
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('login', next=request.path))
        return fn(*args, **kwargs)
    return wrapper


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user, pw = request.form.get('username', '').strip(), request.form.get('password', '')
        with get_db() as conn:
            row = conn.execute('SELECT * FROM users WHERE username = ?', (user,)).fetchone()
        if row and check_password_hash(row['password_hash'], pw):
            session['user'] = dict(row)
            return redirect(request.args.get('next') or url_for('dashboard'))
        flash('Wrong username or password.', 'error')
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


# ==================================================================
# Dashboard
# ==================================================================
@app.route('/')
@login_required
def dashboard():
    today = datetime.now().strftime('%Y-%m-%d')
    with get_db() as conn:
        sales = conn.execute(
            "SELECT COALESCE(SUM(total), 0) s, COUNT(*) c FROM orders "
            "WHERE status = 'paid' AND paid_at LIKE ?", (today + '%',)).fetchone()
        open_orders = conn.execute(
            "SELECT COUNT(*) c FROM orders WHERE status = 'open'").fetchone()['c']
        tables = conn.execute('SELECT * FROM tables WHERE is_active = 1 ORDER BY name').fetchall()
        free = conn.execute(
            "SELECT COUNT(*) c FROM tables t WHERE t.is_active = 1 "
            "AND NOT EXISTS (SELECT 1 FROM orders o WHERE o.table_id = t.id AND o.status = 'open')"
        ).fetchone()['c']
        top = conn.execute(
            "SELECT item_name, SUM(qty) q, SUM(amount) a FROM order_items oi "
            "JOIN orders o ON o.id = oi.order_id "
            "WHERE o.status = 'paid' AND o.paid_at LIKE ? "
            "GROUP BY item_name ORDER BY q DESC LIMIT 5", (today + '%',)).fetchall()
        recent = conn.execute(
            "SELECT * FROM orders WHERE status != 'cancelled' "
            "ORDER BY id DESC LIMIT 8").fetchall()
        open_map = {r['table_id']: r for r in conn.execute(
            "SELECT o.id oid, o.table_id, o.total t FROM orders o JOIN "
            "(SELECT table_id, MAX(id) mid FROM orders WHERE status = 'open' "
            "GROUP BY table_id) x ON x.mid = o.id").fetchall()}
    return render_template('dashboard.html', sales=sales['s'], orders_today=sales['c'],
                           open_orders=open_orders, tables=tables,
                           free_tables=free, total_tables=len(tables),
                           top=top, recent=recent, today=today, open_map=open_map)


# ==================================================================
# Tables
# ==================================================================
@app.route('/tables', methods=['GET', 'POST'])
@login_required
def tables_page():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        seats = request.form.get('seats', 2)
        if not name:
            flash('Table name required.', 'error')
        else:
            try:
                with get_db() as conn:
                    conn.execute('INSERT INTO tables (name, seats) VALUES (?, ?)', (name, seats))
                flash('Table added.', 'success')
            except sqlite3.IntegrityError:
                flash('Table name already exists.', 'error')
        return redirect(url_for('tables_page'))
    with get_db() as conn:
        tables = conn.execute('SELECT * FROM tables ORDER BY name').fetchall()
        open_map = {r['table_id']: r for r in conn.execute(
            "SELECT o.id oid, o.table_id, o.total t FROM orders o JOIN "
            "(SELECT table_id, MAX(id) mid FROM orders WHERE status = 'open' "
            "GROUP BY table_id) x ON x.mid = o.id").fetchall()}
    return render_template('tables.html', tables=tables, open_map=open_map)


@app.route('/tables/<int:tid>/toggle', methods=['POST'])
@login_required
def table_toggle(tid):
    with get_db() as conn:
        conn.execute('UPDATE tables SET is_active = 1 - is_active WHERE id = ?', (tid,))
    return redirect(url_for('tables_page'))


# ==================================================================
# Menu
# ==================================================================
@app.route('/menu', methods=['GET', 'POST'])
@login_required
def menu_page():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        cat = request.form.get('category', 'General').strip()
        try:
            price = float(request.form.get('price', '0') or 0)
        except ValueError:
            price = 0
        if not name:
            flash('Item name required.', 'error')
        else:
            image_path = save_item_image(request.files.get('image'))
            with get_db() as conn:
                conn.execute('INSERT INTO menu_items (name, category, price, image_path) '
                             'VALUES (?, ?, ?, ?)', (name, cat, price, image_path))
            flash(f'"{name}" added to menu.', 'success')
        return redirect(url_for('menu_page'))
    cat = request.args.get('cat', '')
    with get_db() as conn:
        cats = [r['category'] for r in conn.execute(
            'SELECT DISTINCT category FROM menu_items ORDER BY category').fetchall()]
        if cat:
            items = conn.execute(
                'SELECT * FROM menu_items WHERE category = ? ORDER BY name', (cat,)).fetchall()
        else:
            items = conn.execute('SELECT * FROM menu_items ORDER BY category, name').fetchall()
    return render_template('menu.html', items=items, cats=cats, cat=cat)


@app.route('/menu/<int:mid>/edit', methods=['GET', 'POST'])
@login_required
def menu_edit(mid):
    with get_db() as conn:
        item = conn.execute('SELECT * FROM menu_items WHERE id = ?', (mid,)).fetchone()
        if not item:
            abort(404)
        if request.method == 'POST':
            name = request.form.get('name', '').strip()
            cat = request.form.get('category', 'General').strip()
            try:
                price = float(request.form.get('price', '0') or 0)
            except ValueError:
                price = 0
            if not name:
                flash('Item name required.', 'error')
                return redirect(url_for('menu_edit', mid=mid))
            # photo: nayi upload → purani delete; ya sirf remove
            new_img = save_item_image(request.files.get('image'))
            if new_img:
                delete_item_image(item['image_path'])
                conn.execute('UPDATE menu_items SET image_path = ? WHERE id = ?',
                             (new_img, mid))
            elif request.form.get('image_action') == 'remove':
                delete_item_image(item['image_path'])
                conn.execute("UPDATE menu_items SET image_path = '' WHERE id = ?", (mid,))
            conn.execute('UPDATE menu_items SET name = ?, category = ?, price = ? WHERE id = ?',
                         (name, cat, price, mid))
            flash(f'"{name}" updated.', 'success')
            return redirect(url_for('menu_page'))
    return render_template('menu_edit.html', item=item)


@app.route('/menu/<int:mid>/toggle', methods=['POST'])
@login_required
def menu_toggle(mid):
    with get_db() as conn:
        conn.execute('UPDATE menu_items SET is_available = 1 - is_available WHERE id = ?', (mid,))
    return redirect(request.referrer or url_for('menu_page'))


@app.route('/menu/<int:mid>/delete', methods=['POST'])
@login_required
def menu_delete(mid):
    with get_db() as conn:
        row = conn.execute('SELECT image_path FROM menu_items WHERE id = ?', (mid,)).fetchone()
        conn.execute('DELETE FROM menu_items WHERE id = ?', (mid,))
    if row:
        delete_item_image(row['image_path'])
    flash('Item deleted.', 'success')
    return redirect(url_for('menu_page'))


# ==================================================================
# Orders
# ==================================================================
def next_order_number(conn, now):
    day = now.strftime('%Y-%m-%d')
    row = conn.execute('SELECT * FROM receipt_sequences WHERE id = 1').fetchone()
    n = (row['last_number'] + 1) if row and row['date'] == day else 1
    conn.execute(
        'INSERT INTO receipt_sequences (id, date, last_number) VALUES (1, ?, ?) '
        'ON CONFLICT(id) DO UPDATE SET date = excluded.date, last_number = excluded.last_number',
        (day, n))
    return f"R-{now.strftime('%y%m%d')}-{n:04d}"


@app.route('/orders')
@login_required
def order_list():
    status = request.args.get('status', '')
    day = request.args.get('day', '')
    q = "SELECT * FROM orders WHERE 1=1"
    args = []
    if status in ('open', 'paid', 'cancelled'):
        q += ' AND status = ?'
        args.append(status)
    if day:
        q += ' AND created_at LIKE ?'
        args.append(day + '%')
    q += ' ORDER BY id DESC LIMIT 200'
    with get_db() as conn:
        orders = conn.execute(q, args).fetchall()
        tables = {r['id']: r['name'] for r in conn.execute('SELECT * FROM tables').fetchall()}
    return render_template('orders/list.html', orders=orders, tables=tables,
                           status=status, day=day)


@app.route('/orders/new', methods=['GET', 'POST'])
@login_required
def order_new():
    if request.method == 'POST':
        table_id = request.form.get('table_id') or None
        discount = float(request.form.get('discount', '0') or 0)
        gst = settings_row().get('gst_percent', 0) or 0
        qty_map = {}
        for key, val in request.form.items():
            if key.startswith('qty_'):
                iid = key[4:]
                try:
                    qty = float(val or 0)
                except ValueError:
                    qty = 0
                if qty > 0:
                    qty_map[iid] = qty
        if not qty_map:
            flash('No items selected — quantity is 0.', 'error')
            return redirect(url_for('order_new'))
        try:
            with get_db() as conn:
                conn.execute('BEGIN IMMEDIATE')
                number = next_order_number(conn, datetime.now())
                cur = conn.execute(
                    'INSERT INTO orders (order_number, table_id, status) VALUES (?, ?, ?)',
                    (number, table_id, 'open'))
                oid = cur.lastrowid
                subtotal = 0.0
                for iid, qty in qty_map.items():
                    row = conn.execute('SELECT * FROM menu_items WHERE id = ?', (iid,)).fetchone()
                    if not row or not row['is_available']:
                        continue
                    amount = round(row['price'] * qty, 2)
                    subtotal += amount
                    conn.execute(
                        'INSERT INTO order_items (order_id, item_name, price, qty, amount) '
                        'VALUES (?, ?, ?, ?, ?)', (oid, row['name'], row['price'], qty, amount))
                gst_amt = round(subtotal * gst / 100, 2)
                total = round(subtotal + gst_amt - discount, 2)
                if total < 0:  # discount se total kabhi negative nahi ho sakta
                    total = 0.0
                conn.execute(
                    'UPDATE orders SET subtotal = ?, gst_percent = ?, gst_amount = ?, '
                    'discount = ?, total = ? WHERE id = ?',
                    (subtotal, gst, gst_amt, discount, total, oid))
                conn.commit()
            flash(f'Order {number} created — total Rs. {total:,.2f}', 'success')
            return redirect(url_for('order_view', oid=oid))
        except sqlite3.IntegrityError:
            conn.rollback()
            flash('Order number collision — please try again.', 'error')
            return redirect(url_for('order_new'))
    with get_db() as conn:
        tables = conn.execute('SELECT * FROM tables WHERE is_active = 1 ORDER BY name').fetchall()
        menu = conn.execute('SELECT * FROM menu_items WHERE is_available = 1 '
                            'ORDER BY category, name').fetchall()
        cats = [r['category'] for r in conn.execute(
            'SELECT DISTINCT category FROM menu_items WHERE is_available = 1 '
            'ORDER BY category').fetchall()]
    return render_template('orders/new.html', tables=tables, menu=menu, cats=cats,
                           gst=settings_row().get('gst_percent', 0) or 0)


@app.route('/orders/<int:oid>')
@login_required
def order_view(oid):
    with get_db() as conn:
        order = conn.execute('SELECT * FROM orders WHERE id = ?', (oid,)).fetchone()
        if not order:
            abort(404)
        items = conn.execute('SELECT * FROM order_items WHERE order_id = ?', (oid,)).fetchall()
        table = conn.execute('SELECT * FROM tables WHERE id = ?', (order['table_id'],)).fetchone()
    return render_template('orders/view.html', order=order, items=items, table=table)


@app.route('/orders/<int:oid>/checkout', methods=['POST'])
@login_required
def order_checkout(oid):
    method = request.form.get('method', 'cash')
    if method not in ('cash', 'card', 'online'):
        method = 'cash'
    with get_db() as conn:
        order = conn.execute('SELECT * FROM orders WHERE id = ?', (oid,)).fetchone()
        if not order or order['status'] != 'open':
            flash('Order already closed.', 'error')
        else:
            conn.execute('UPDATE orders SET status = ?, payment_method = ?, paid_at = ? '
                         'WHERE id = ?', ('paid', method, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), oid))
            flash(f'Order paid — Rs. {order["total"]:,.2f} via {method}. Print the slip below.',
                  'success')
    return redirect(url_for('order_receipt', oid=oid))


@app.route('/orders/<int:oid>/cancel', methods=['POST'])
@login_required
def order_cancel(oid):
    with get_db() as conn:
        conn.execute("UPDATE orders SET status = 'cancelled' WHERE id = ? AND status = 'open'",
                     (oid,))
    flash('Order cancelled.', 'success')
    return redirect(url_for('order_list'))


@app.route('/orders/<int:oid>/receipt')
@login_required
def order_receipt(oid):
    with get_db() as conn:
        order = conn.execute('SELECT * FROM orders WHERE id = ?', (oid,)).fetchone()
        if not order:
            abort(404)
        items = conn.execute('SELECT * FROM order_items WHERE order_id = ?', (oid,)).fetchall()
        table = conn.execute('SELECT * FROM tables WHERE id = ?', (order['table_id'],)).fetchone()
    return render_template('orders/receipt.html', order=order, items=items,
                           table=table, settings=settings_row())


# ==================================================================
# Sales report
# ==================================================================
@app.route('/sales')
@login_required
def sales():
    frm = request.args.get('from', datetime.now().strftime('%Y-%m-01'))
    to = request.args.get('to', datetime.now().strftime('%Y-%m-%d'))
    with get_db() as conn:
        rows = conn.execute(
            "SELECT date(paid_at) d, COUNT(*) orders, SUM(total) sales FROM orders "
            "WHERE status = 'paid' AND date(paid_at) BETWEEN ? AND ? "
            "GROUP BY date(paid_at) ORDER BY d", (frm, to)).fetchall()
        by_method = conn.execute(
            "SELECT payment_method, COUNT(*) c, SUM(total) s FROM orders "
            "WHERE status = 'paid' AND date(paid_at) BETWEEN ? AND ? "
            "GROUP BY payment_method", (frm, to)).fetchall()
        by_cat = conn.execute(
            "SELECT m.category, SUM(oi.amount) s FROM order_items oi "
            "JOIN orders o ON o.id = oi.order_id "
            "JOIN menu_items m ON m.name = oi.item_name "
            "WHERE o.status = 'paid' AND date(o.paid_at) BETWEEN ? AND ? "
            "GROUP BY m.category ORDER BY s DESC", (frm, to)).fetchall()
        total = sum(r['sales'] for r in rows)
    return render_template('sales.html', rows=rows, by_method=by_method,
                           by_cat=by_cat, total=total, frm=frm, to=to)


# ==================================================================
# Settings
# ==================================================================
@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings_page():
    if request.method == 'POST':
        data = {k: request.form.get(k, '') for k in
                ('restaurant_name', 'address', 'phone', 'receipt_footer')}
        try:
            data['gst_percent'] = float(request.form.get('gst_percent', '0') or 0)
        except ValueError:
            data['gst_percent'] = 0
        with get_db() as conn:
            conn.execute(
                'UPDATE restaurant_settings SET restaurant_name = ?, address = ?, '
                'phone = ?, receipt_footer = ?, gst_percent = ? WHERE id = 1',
                (data['restaurant_name'], data['address'], data['phone'],
                 data['receipt_footer'], data['gst_percent']))
        flash('Settings saved.', 'success')
        return redirect(url_for('settings_page'))
    return render_template('settings.html', s=settings_row())


@app.route('/password', methods=['GET', 'POST'])
@login_required
def password():
    if request.method == 'POST':
        old, new, confirm = (request.form.get('old_password', ''),
                             request.form.get('new_password', ''),
                             request.form.get('confirm_password', ''))
        with get_db() as conn:
            row = conn.execute('SELECT * FROM users WHERE id = ?',
                               (session['user']['id'],)).fetchone()
        if not check_password_hash(row['password_hash'], old):
            flash('Old password wrong.', 'error')
        elif len(new) < 6:
            flash('New password must be at least 6 characters.', 'error')
        elif new != confirm:
            flash('Passwords do not match.', 'error')
        else:
            with get_db() as conn:
                conn.execute('UPDATE users SET password_hash = ? WHERE id = ?',
                             (generate_password_hash(new), session['user']['id']))
            flash('Password changed.', 'success')
            return redirect(url_for('dashboard'))
    return render_template('password.html')


def seed_admin():
    with get_db() as conn:
        if not conn.execute('SELECT 1 FROM users LIMIT 1').fetchone():
            conn.execute('INSERT INTO users (username, password_hash, full_name) VALUES (?, ?, ?)',
                         ('admin', generate_password_hash('admin123'), 'Administrator'))
            print('=' * 56)
            print('  DEFAULT LOGIN: admin / admin123')
            print('=' * 56)


if __name__ == '__main__':
    init_db()
    seed_admin()
    app.run(host='0.0.0.0', port=5001, debug=False)
