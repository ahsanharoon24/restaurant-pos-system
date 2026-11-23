"""Touch POS E2E test: tap tile -> order panel updates -> place order -> paid -> receipt."""
from playwright.sync_api import sync_playwright
import time
import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

with sync_playwright() as pw:
    b = pw.chromium.launch()
    p = b.new_page(viewport={'width': 1440, 'height': 900})
    p.goto('http://localhost:5001/login', wait_until='networkidle')
    p.fill('input[name=username]', 'admin')
    p.fill('input[name=password]', 'admin123')
    p.click('form button')
    p.wait_for_load_state('networkidle')
    print('logged in:', p.url)

    p.goto('http://localhost:5001/orders/new', wait_until='networkidle')
    time.sleep(0.6)
    tiles = p.query_selector_all('.pos-tile')
    print('tile count:', len(tiles))
    # tap first tile twice
    tiles[0].click()
    tiles[0].click()
    time.sleep(0.4)
    # order panel should show 1 item with qty 2
    items = p.query_selector_all('.o-item')
    qty = p.query_selector('.o-qty')
    total = p.query_selector('#t_total').inner_text()
    print('order items in panel:', len(items), '| qty:', qty.inner_text() if qty else None, '| total:', total)
    # tap second tile once
    tiles[1].click()
    time.sleep(0.4)
    items = p.query_selector_all('.o-item')
    print('order items after 2nd tap:', len(items))
    # place order
    p.click('#place_btn')
    p.wait_for_load_state('networkidle')
    time.sleep(0.5)
    print('after place order:', p.url)
    # mark paid
    pay_btn = p.query_selector('form[action*="checkout"] button')
    if pay_btn:
        pay_btn.click()
        p.wait_for_load_state('networkidle')
        time.sleep(0.5)
    print('after payment:', p.url)
    body = p.inner_text('body')
    print('receipt has order no:', 'R-' in body, '| has TOTAL:', 'TOTAL' in body)
    b.close()
print('E2E DONE')
