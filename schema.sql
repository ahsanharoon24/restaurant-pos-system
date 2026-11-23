-- Restaurant POS — TENANT schema (har client ki apni DB file: tenants/u<id>.db)
-- users table is file me NAHI hoti — wo central pos.db me hai (logins/admin).

PRAGMA foreign_keys = ON;

-- ============================================================
-- RESTAURANT SETTINGS (single row, id = 1)
-- ============================================================
CREATE TABLE IF NOT EXISTS restaurant_settings (
    id             INTEGER PRIMARY KEY CHECK (id = 1),
    restaurant_name TEXT NOT NULL DEFAULT 'My Restaurant',
    address        TEXT NOT NULL DEFAULT '',
    phone          TEXT NOT NULL DEFAULT '',
    receipt_footer TEXT NOT NULL DEFAULT 'Thank you! Please visit again.',
    gst_percent    REAL NOT NULL DEFAULT 0,
    updated_at     TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

-- ============================================================
-- TABLES
-- ============================================================
CREATE TABLE IF NOT EXISTS tables (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    name     TEXT NOT NULL UNIQUE,          -- e.g. "T1", "Table 5"
    seats    INTEGER NOT NULL DEFAULT 2,
    is_active INTEGER NOT NULL DEFAULT 1
);

-- ============================================================
-- MENU ITEMS
-- ============================================================
CREATE TABLE IF NOT EXISTS menu_items (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT NOT NULL,
    category     TEXT NOT NULL DEFAULT 'General',
    price        REAL NOT NULL CHECK (price >= 0),
    image_path   TEXT NOT NULL DEFAULT '',        -- dish photo (uploads/menu/...)
    is_available INTEGER NOT NULL DEFAULT 1,
    created_at   TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);
CREATE INDEX IF NOT EXISTS idx_menu_category ON menu_items(category);

-- ============================================================
-- ORDERS
-- ============================================================
CREATE TABLE IF NOT EXISTS orders (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    order_number    TEXT NOT NULL UNIQUE,   -- R-2026-0001
    table_id        INTEGER REFERENCES tables(id),
    status          TEXT NOT NULL DEFAULT 'open'
                    CHECK (status IN ('open', 'paid', 'cancelled')),
    subtotal        REAL NOT NULL DEFAULT 0,
    gst_percent     REAL NOT NULL DEFAULT 0,
    gst_amount      REAL NOT NULL DEFAULT 0,
    discount        REAL NOT NULL DEFAULT 0,
    total           REAL NOT NULL DEFAULT 0,
    payment_method  TEXT NOT NULL DEFAULT '' CHECK (payment_method IN ('', 'cash', 'card', 'online')),
    created_at      TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    paid_at         TEXT
);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
CREATE INDEX IF NOT EXISTS idx_orders_created ON orders(created_at);

-- ============================================================
-- ORDER ITEMS (line-level with price snapshot)
-- ============================================================
CREATE TABLE IF NOT EXISTS order_items (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id    INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    item_name   TEXT NOT NULL,              -- snapshot: menu edit se old orders nahi badalte
    price       REAL NOT NULL DEFAULT 0,    -- snapshot
    qty         REAL NOT NULL DEFAULT 1,
    amount      REAL NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_oi_order ON order_items(order_id);

-- ============================================================
-- RECEIPT NUMBER SEQUENCE (transaction-safe, har roz 1 se)
-- ============================================================
CREATE TABLE IF NOT EXISTS receipt_sequences (
    id          INTEGER PRIMARY KEY CHECK (id = 1),
    date        TEXT NOT NULL,              -- 'YYYY-MM-DD'
    last_number INTEGER NOT NULL DEFAULT 0
);

-- ============================================================
-- SEED
-- ============================================================
INSERT OR IGNORE INTO restaurant_settings (id, restaurant_name, receipt_footer)
VALUES (1, 'My Restaurant', 'Thank you! Please visit again.');
