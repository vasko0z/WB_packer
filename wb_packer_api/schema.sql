-- WB Packer Database Schema (production-aligned)

CREATE TABLE IF NOT EXISTS sku (
    barcode TEXT NOT NULL PRIMARY KEY,
    name TEXT DEFAULT '',
    article TEXT DEFAULT '',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS stock_cache (
    barcode TEXT NOT NULL PRIMARY KEY,
    quantity INTEGER DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS shipments (
    id SERIAL PRIMARY KEY,
    destination_name TEXT NOT NULL,
    font_size INTEGER DEFAULT 10,
    label_font_size INTEGER DEFAULT 20,
    theme TEXT DEFAULT 'Светлая',
    removed_items TEXT DEFAULT '{}',
    parent_group TEXT DEFAULT '',
    properties TEXT DEFAULT '{}',
    archived BOOLEAN DEFAULT FALSE,
    archived_date TIMESTAMP,
    archived_by TEXT,
    version INTEGER DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    wb_shipment_number VARCHAR(255),
    wb_metadata JSONB
);

CREATE TABLE IF NOT EXISTS shipment_items (
    id SERIAL PRIMARY KEY,
    shipment_id INTEGER NOT NULL REFERENCES shipments(id) ON DELETE CASCADE,
    barcode TEXT NOT NULL,
    sku TEXT NOT NULL,
    total_qty INTEGER NOT NULL,
    allocated_qty INTEGER DEFAULT 0,
    version INTEGER DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS boxes (
    id SERIAL PRIMARY KEY,
    shipment_id INTEGER NOT NULL REFERENCES shipments(id) ON DELETE CASCADE,
    box_id TEXT NOT NULL,
    is_current BOOLEAN DEFAULT FALSE,
    version INTEGER DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS box_items (
    id SERIAL PRIMARY KEY,
    box_id INTEGER NOT NULL REFERENCES boxes(id) ON DELETE CASCADE,
    barcode TEXT NOT NULL,
    qty INTEGER NOT NULL,
    version INTEGER DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS packer_users (
    id SERIAL PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    current_shipment TEXT,
    font_size INTEGER DEFAULT 10,
    label_font_size INTEGER DEFAULT 20,
    current_theme TEXT DEFAULT 'macOS',
    ok_sound TEXT DEFAULT 'ok.wav',
    error_sound TEXT DEFAULT 'error.wav',
    tone_sound BOOLEAN DEFAULT FALSE,
    sound_volume INTEGER DEFAULT 100,
    colored_buttons BOOLEAN DEFAULT TRUE,
    show_sku BOOLEAN DEFAULT TRUE,
    show_name BOOLEAN DEFAULT FALSE,
    show_total BOOLEAN DEFAULT TRUE,
    show_stock BOOLEAN DEFAULT FALSE,
    hide_completed BOOLEAN DEFAULT FALSE,
    shipment_columns_width TEXT,
    box_columns_width TEXT,
    main_splitter_sizes TEXT,
    window_width INTEGER DEFAULT 1300,
    window_height INTEGER DEFAULT 800,
    window_x INTEGER DEFAULT 0,
    window_y INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS app_settings (
    key TEXT NOT NULL PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS window_state (
    key TEXT NOT NULL PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS user_sessions (
    id SERIAL PRIMARY KEY,
    shipment_name TEXT NOT NULL,
    username TEXT NOT NULL,
    last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(shipment_name, username)
);

CREATE TABLE IF NOT EXISTS item_locks (
    barcode TEXT NOT NULL,
    shipment_id INTEGER NOT NULL REFERENCES shipments(id) ON DELETE CASCADE,
    username TEXT NOT NULL,
    locked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL,
    PRIMARY KEY (barcode, shipment_id)
);

CREATE TABLE IF NOT EXISTS cache_invalidation (
    id SERIAL PRIMARY KEY,
    shipment_id INTEGER NOT NULL REFERENCES shipments(id) ON DELETE CASCADE,
    tables_changed TEXT NOT NULL,
    invalidated_by TEXT,
    invalidated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_user_sessions_shipment_username ON user_sessions(shipment_name, username);
CREATE INDEX IF NOT EXISTS idx_sku_barcode ON sku(barcode);
CREATE INDEX IF NOT EXISTS idx_stock_cache_barcode ON stock_cache(barcode);
CREATE INDEX IF NOT EXISTS idx_shipment_items_shipment ON shipment_items(shipment_id);
CREATE INDEX IF NOT EXISTS idx_boxes_shipment ON boxes(shipment_id);
CREATE INDEX IF NOT EXISTS idx_box_items_box ON box_items(box_id);
CREATE INDEX IF NOT EXISTS idx_user_sessions_shipment ON user_sessions(shipment_name);
CREATE INDEX IF NOT EXISTS idx_cache_invalidation_shipment ON cache_invalidation(shipment_id);
