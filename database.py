import sqlite3
import os
from datetime import datetime

DB_FILE = 'inventory.db'


def get_connection():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row  # 让结果可以用列名访问
    return conn


def init_db():
    """初始化数据库，创建表如果不存在"""
    conn = get_connection()
    c = conn.cursor()

    # 创建库存表
    c.execute('''
        CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            brand TEXT NOT NULL,
            name TEXT NOT NULL,
            category TEXT,
            warehouse TEXT NOT NULL,
            location TEXT,
            quantity INTEGER DEFAULT 0,
            min_stock INTEGER DEFAULT 5,
            unit_price REAL,
            image_path TEXT,
            batch_no TEXT,
            expiry_date TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 创建出入库记录表 (审计日志)
    c.execute('''
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id INTEGER,
            action TEXT, -- 'IN', 'OUT', 'ADJUST', 'TRANSFER'
            quantity_change INTEGER,
            reason TEXT,
            operator TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    conn.commit()
    conn.close()


def get_all_items():
    conn = get_connection()
    c = conn.cursor()
    c.execute('SELECT * FROM items ORDER BY warehouse, brand, name')
    rows = c.fetchall()
    conn.close()
    return rows


def add_item(brand, name, category, warehouse, location, quantity, min_stock, unit_price, batch_no, expiry_date):
    conn = get_connection()
    c = conn.cursor()
    c.execute('''
        INSERT INTO items (brand, name, category, warehouse, location, quantity, min_stock, unit_price, batch_no, expiry_date)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (brand, name, category, warehouse, location, quantity, min_stock, unit_price, batch_no, expiry_date))

    # 记录日志
    item_id = c.lastrowid
    c.execute('''
        INSERT INTO logs (item_id, action, quantity_change, reason, operator)
        VALUES (?, 'INIT', ?, 'Initial stock entry', 'System')
    ''', (item_id, quantity))

    conn.commit()
    conn.close()
    return True


def update_item(item_id, brand, name, category, warehouse, location, quantity, min_stock, unit_price, batch_no,
                expiry_date):
    conn = get_connection()
    c = conn.cursor()

    # 获取旧数量以记录日志
    c.execute('SELECT quantity FROM items WHERE id = ?', (item_id,))
    old_qty = c.fetchone()[0]

    c.execute('''
        UPDATE items 
        SET brand=?, name=?, category=?, warehouse=?, location=?, quantity=?, min_stock=?, unit_price=?, batch_no=?, expiry_date=?, updated_at=?
        WHERE id=?
    ''', (
    brand, name, category, warehouse, location, quantity, min_stock, unit_price, batch_no, expiry_date, datetime.now(),
    item_id))

    # 记录数量变动日志
    if quantity != old_qty:
        diff = quantity - old_qty
        action = 'IN' if diff > 0 else 'OUT'
        c.execute('''
            INSERT INTO logs (item_id, action, quantity_change, reason, operator)
            VALUES (?, ?, ?, 'Manual adjustment', 'User')
        ''', (item_id, action, diff))

    conn.commit()
    conn.close()
    return True


def delete_item(item_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute('DELETE FROM items WHERE id = ?', (item_id,))
    conn.commit()
    conn.close()
    return True


# 初始化数据库 (每次导入时运行一次)
init_db()