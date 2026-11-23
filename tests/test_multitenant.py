# -*- coding: utf-8 -*-
"""Multi-tenant POS tests — admin panel, client workspaces, data isolation.

Run: py -3.12 -m unittest discover -s tests -v
"""
import os
import shutil
import sqlite3
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import app as pos  # noqa: E402


class MultiTenantTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix='pos-test-')
        pos.DB_PATH = os.path.join(cls.tmp, 'pos.db')
        pos.TENANT_DIR = os.path.join(cls.tmp, 'tenants')
        pos.UPLOAD_DIR = os.path.join(cls.tmp, 'uploads')
        os.makedirs(pos.UPLOAD_DIR, exist_ok=True)
        pos.app.config.update(TESTING=True)
        pos.init_db()
        pos.seed_admin()

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def setUp(self):
        self.c = pos.app.test_client()

    # -- helpers -------------------------------------------------------
    def login(self, username, password):
        return self.c.post('/login', data={'username': username, 'password': password})

    def admin(self):
        self.login('admin', 'admin123')

    def uid(self, username):
        con = sqlite3.connect(pos.DB_PATH)
        con.row_factory = sqlite3.Row
        try:
            row = con.execute('SELECT id FROM users WHERE username = ?', (username,)).fetchone()
            return row['id'] if row else None
        finally:
            con.close()

    def seed_item(self, tenant_uid, name):
        con = sqlite3.connect(pos.tenant_path(tenant_uid))
        try:
            con.execute('INSERT INTO menu_items (name, category, price) VALUES (?, ?, ?)',
                        (name, 'Test', 100))
            con.commit()
        finally:
            con.close()

    # -- tests ---------------------------------------------------------
    def test_01_admin_login_redirects(self):
        self.assertEqual(self.login('admin', 'admin123').status_code, 302)

    def test_02_wrong_password_stays_on_login(self):
        r = self.login('admin', 'nope')
        self.assertEqual(r.status_code, 200)
        self.assertIn(b'Wrong username or password', r.data)

    def test_03_admin_sees_users_page(self):
        self.admin()
        r = self.c.get('/users')
        self.assertEqual(r.status_code, 200)
        self.assertIn(b'Users', r.data)

    def test_04_create_client_creates_workspace(self):
        self.admin()
        r = self.c.post('/users/add', data={'username': 'client1', 'password': 'client123',
                                            'full_name': 'Client One', 'role': 'user'})
        self.assertEqual(r.status_code, 302)
        self.assertIsNotNone(self.uid('client1'))
        self.assertTrue(os.path.exists(pos.tenant_path(self.uid('client1'))))

    def test_05_client_cannot_open_admin_panel(self):
        c = pos.app.test_client()
        c.post('/login', data={'username': 'client1', 'password': 'client123'})
        self.assertEqual(c.get('/users').status_code, 302)  # redirected away

    def test_06_client_data_is_isolated(self):
        admin_uid = self.uid('admin')
        client_uid = self.uid('client1')
        self.seed_item(admin_uid, 'Admin Special Dish')
        self.seed_item(client_uid, 'Client Only Dish')

        # impersonate the client and read its menu
        self.admin()
        self.c.post(f'/users/{client_uid}/open')
        menu = self.c.get('/menu').get_data(as_text=True)
        self.assertIn('Client Only Dish', menu)
        self.assertNotIn('Admin Special Dish', menu)

        # back to admin view
        self.c.get('/back-to-account')
        admin_menu = self.c.get('/menu').get_data(as_text=True)
        self.assertIn('Admin Special Dish', admin_menu)
        self.assertNotIn('Client Only Dish', admin_menu)

    def test_07_admin_cannot_delete_self(self):
        self.admin()
        admin_uid = self.uid('admin')
        self.c.post(f'/users/{admin_uid}/delete')
        self.assertIsNotNone(self.uid('admin'))

    def test_08_delete_client_removes_account_and_db(self):
        self.admin()
        self.c.post('/users/add', data={'username': 'throwaway', 'password': 'temp1234'})
        uid = self.uid('throwaway')
        path = pos.tenant_path(uid)
        self.assertTrue(os.path.exists(path))
        self.c.post(f'/users/{uid}/delete')
        self.assertIsNone(self.uid('throwaway'))
        self.assertFalse(os.path.exists(path))

    def test_09_duplicate_username_rejected(self):
        self.admin()
        self.c.post('/users/add', data={'username': 'client1', 'password': 'client123'})
        con = sqlite3.connect(pos.DB_PATH)
        try:
            count = con.execute("SELECT COUNT(*) FROM users WHERE username = 'client1'").fetchone()[0]
        finally:
            con.close()
        self.assertEqual(count, 1)


if __name__ == '__main__':
    unittest.main(verbosity=2)
