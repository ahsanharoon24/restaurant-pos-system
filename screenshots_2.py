"""Sample 2 fresh screenshots (new touch POS UI). Run: python screenshots_2.py"""
from playwright.sync_api import sync_playwright
import shutil
import time
import os

BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, 'screenshots')
shutil.rmtree(OUT, ignore_errors=True)
os.makedirs(OUT, exist_ok=True)

with sync_playwright() as pw:
    b = pw.chromium.launch()
    p = b.new_page(viewport={'width': 1440, 'height': 900}, device_scale_factor=1.5)
    p.goto('http://localhost:5001/login', wait_until='networkidle')
    p.fill('input[name=username]', 'admin')
    p.fill('input[name=password]', 'admin123')
    p.click('form button')
    p.wait_for_load_state('networkidle')
    time.sleep(0.8)
    # 1: new order screen (tap tiles so panel shows items)
    p.goto('http://localhost:5001/orders/new', wait_until='networkidle')
    time.sleep(0.6)
    tiles = p.query_selector_all('.pos-tile')
    tiles[3].click(); tiles[3].click(); tiles[8].click(); tiles[15].click()
    time.sleep(0.5)
    p.screenshot(path=os.path.join(OUT, '02_new_order.png'))
    # 2: menu manager
    p.goto('http://localhost:5001/menu', wait_until='networkidle')
    time.sleep(0.5)
    p.screenshot(path=os.path.join(OUT, '04_menu.png'))
    # 3: dashboard
    p.goto('http://localhost:5001/', wait_until='networkidle')
    time.sleep(0.5)
    p.screenshot(path=os.path.join(OUT, '01_dashboard.png'))
    # 4: latest receipt (order 6 just paid) — print view
    p.goto('http://localhost:5001/orders/6/receipt', wait_until='networkidle')
    time.sleep(0.5)
    p.screenshot(path=os.path.join(OUT, '03_order_receipt.png'))
    # 5: sales
    p.goto('http://localhost:5001/sales', wait_until='networkidle')
    time.sleep(0.5)
    p.screenshot(path=os.path.join(OUT, '05_sales.png'))
    # mobile view of POS order screen
    m = b.new_page(viewport={'width': 390, 'height': 844}, device_scale_factor=2)
    m.goto('http://localhost:5001/login', wait_until='networkidle')
    m.fill('input[name=username]', 'admin')
    m.fill('input[name=password]', 'admin123')
    m.click('form button')
    m.wait_for_load_state('networkidle')
    m.goto('http://localhost:5001/orders/new', wait_until='networkidle')
    time.sleep(0.6)
    m.screenshot(path=os.path.join(OUT, '06_mobile_pos.png'))
    b.close()
print('sample 2 screenshots:', len(os.listdir(OUT)))
