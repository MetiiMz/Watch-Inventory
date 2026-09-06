# -*- coding: utf-8 -*-
"""لایه‌ی پایگاه‌داده — SQLite با مهاجرت خودکار نسخه‌ها و بکاپ امن."""

import os
import sqlite3
from contextlib import contextmanager

from jalali import parse_jalali_date

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
IMG_DIR = os.path.join(DATA_DIR, "images")
BACKUP_DIR = os.path.join(DATA_DIR, "backups")
# مسیر دیتابیس را می‌توان با متغیر محیطی TIKOTIME_DB تغییر داد (برای سرور/تست)
DB_PATH = os.environ.get("TIKOTIME_DB") or os.path.join(DATA_DIR, "watch_inventory.db")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(IMG_DIR, exist_ok=True)
os.makedirs(BACKUP_DIR, exist_ok=True)


@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


SCHEMA = """
CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    reference TEXT NOT NULL DEFAULT '',
    office_code TEXT NOT NULL,
    website_code TEXT NOT NULL,
    brand TEXT NOT NULL DEFAULT '',
    purchase_price REAL NOT NULL DEFAULT 0,
    sale_price REAL NOT NULL DEFAULT 0,
    available INTEGER NOT NULL DEFAULT 1,
    supplier TEXT NOT NULL DEFAULT '',
    purchase_date TEXT NOT NULL DEFAULT '',
    purchase_type TEXT NOT NULL DEFAULT 'person',
    notes TEXT NOT NULL DEFAULT '',
    image TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_products_office_code ON products(office_code COLLATE NOCASE);
CREATE UNIQUE INDEX IF NOT EXISTS idx_products_website_code ON products(website_code COLLATE NOCASE);
CREATE INDEX IF NOT EXISTS idx_products_name ON products(name);
CREATE INDEX IF NOT EXISTS idx_products_brand ON products(brand);

CREATE TABLE IF NOT EXISTS sales (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    sale_price REAL NOT NULL DEFAULT 0,
    purchase_price REAL NOT NULL DEFAULT 0,
    profit REAL NOT NULL DEFAULT 0,
    sale_date TEXT NOT NULL,
    customer TEXT NOT NULL DEFAULT '',
    customer_phone TEXT NOT NULL DEFAULT '',
    sale_type TEXT NOT NULL DEFAULT 'person',
    payment_type TEXT NOT NULL DEFAULT 'cash',
    final_price REAL NOT NULL DEFAULT 0,
    paid_cash REAL NOT NULL DEFAULT 0,
    paid_pos REAL NOT NULL DEFAULT 0,
    paid_card2card REAL NOT NULL DEFAULT 0,
    is_settled INTEGER NOT NULL DEFAULT 1,
    notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);
CREATE INDEX IF NOT EXISTS idx_sales_date ON sales(sale_date);

CREATE TABLE IF NOT EXISTS repairs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    watch_name TEXT NOT NULL,
    watch_code TEXT NOT NULL DEFAULT '',
    issue TEXT NOT NULL DEFAULT '',
    delivery_date TEXT NOT NULL DEFAULT '',
    customer_name TEXT NOT NULL DEFAULT '',
    customer_phone TEXT NOT NULL DEFAULT '',
    is_warranty INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'received',
    repair_price REAL NOT NULL DEFAULT 0,
    return_date TEXT NOT NULL DEFAULT '',
    image TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);
CREATE INDEX IF NOT EXISTS idx_repairs_phone ON repairs(customer_phone);

CREATE TABLE IF NOT EXISTS tracking (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_name TEXT NOT NULL,
    item_code TEXT NOT NULL DEFAULT '',
    customer_name TEXT NOT NULL DEFAULT '',
    customer_phone TEXT NOT NULL DEFAULT '',
    price REAL NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'new',
    notes TEXT NOT NULL DEFAULT '',
    image TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);
CREATE INDEX IF NOT EXISTS idx_tracking_status ON tracking(status);

CREATE TABLE IF NOT EXISTS payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sale_id INTEGER REFERENCES sales(id) ON DELETE CASCADE,
    product_id INTEGER REFERENCES products(id) ON DELETE SET NULL,
    product_name TEXT NOT NULL DEFAULT '',
    customer_name TEXT NOT NULL DEFAULT '',
    customer_phone TEXT NOT NULL DEFAULT '',
    total_amount REAL NOT NULL DEFAULT 0,
    paid_amount REAL NOT NULL DEFAULT 0,
    pay_date TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);
CREATE INDEX IF NOT EXISTS idx_payments_date ON payments(pay_date);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL DEFAULT ''
);
"""

DEFAULT_BRANDS = [
    "رولکس", "امگا", "اپل", "سامسونگ", "سیکو", "تیسوت", "لانژین",
    "کاسیو", "سویچ", "فسیل", "مایکل کورس", "ارمیتاج", "بولووا",
    "راپو", "گیلارد پروند", "سایر",
]


def _table_exists(db, name):
    return db.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone() is not None


def _add_column(db, table, column, decl):
    cols = {r[1] for r in db.execute(f"PRAGMA table_info({table})")}
    if column not in cols:
        db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")


def _table_cols(db, name):
    return {r[1] for r in db.execute(f"PRAGMA table_info({name})")}


def _migrate(db):
    """مهاجرت‌های افزایشی — هر بار اجرا امن است."""
    # هنگام بازسازی جدول‌ها، کلیدهای خارجی باید موقتاً خاموش باشند
    # وگرنه DROP TABLE والد، ردیف‌های جدول‌های فرزند را حذف می‌کند
    db.execute("PRAGMA foreign_keys = OFF")
    try:
        _migrate_inner(db)
    finally:
        db.execute("PRAGMA foreign_keys = ON")


def _migrate_inner(db):
    """مهاجرت‌های افزایشی — هر بار اجرا امن است."""
    # حذف ستون «تعداد» از انبار — مدل موجود/ناموجود
    if _table_exists(db, "products"):
        cols = _table_cols(db, "products")
        if "quantity" in cols:
            has_available = "available" in cols
            expr = (
                "CASE WHEN COALESCE(quantity, 1) > 0 THEN 1 ELSE 0 END"
                if has_available else
                "CASE WHEN COALESCE(quantity, 1) > 0 THEN 1 ELSE 0 END AS available"
            )
            tmp = "products__rebuild"
            db.execute(f"DROP TABLE IF EXISTS {tmp}")
            # نکته: CREATE TABLE AS SELECT کلید اصلی و ایندکس‌ها را حفظ نمی‌کند؛
            # برای سالم ماندن FKهای جدول‌های دیگر، DDL کامل اینجا تکرار می‌شود
            db.execute(f"""
                CREATE TABLE {tmp} (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    reference TEXT NOT NULL DEFAULT '',
                    office_code TEXT NOT NULL,
                    website_code TEXT NOT NULL,
                    brand TEXT NOT NULL DEFAULT '',
                    purchase_price REAL NOT NULL DEFAULT 0,
                    sale_price REAL NOT NULL DEFAULT 0,
                    available INTEGER NOT NULL DEFAULT 1,
                    supplier TEXT NOT NULL DEFAULT '',
                    purchase_date TEXT NOT NULL DEFAULT '',
                    purchase_type TEXT NOT NULL DEFAULT 'person',
                    notes TEXT NOT NULL DEFAULT '',
                    image TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
                    updated_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
                )
            """)
            db.execute(
                f"INSERT INTO {tmp}(id, name, reference, office_code, website_code, brand,"
                " purchase_price, sale_price, available, supplier, purchase_date, purchase_type,"
                " notes, image, created_at, updated_at)"
                f" SELECT id, name, reference, office_code, website_code, brand,"
                " purchase_price, sale_price,"
                f" CASE WHEN COALESCE(quantity, 1) > 0 THEN 1 ELSE 0 END,"
                " supplier, purchase_date, purchase_type, notes, image, created_at, updated_at"
                " FROM products"
            )
            db.execute("DROP TABLE products")
            db.execute(f"ALTER TABLE {tmp} RENAME TO products")
            db.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_products_office_code ON products(office_code COLLATE NOCASE)")
            db.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_products_website_code ON products(website_code COLLATE NOCASE)")

    # sales: حذف «تعداد» و ستون‌های تحویل؛ افزودن ریز پرداخت‌ها
    if _table_exists(db, "sales"):
        cols = _table_cols(db, "sales")
        # اول همه‌ی ستون‌های لازم را اضافه کن (برای دیتابیس‌های خیلی قدیمی)
        for c, d in (
            ("customer_phone", "TEXT NOT NULL DEFAULT ''"),
            ("sale_type", "TEXT NOT NULL DEFAULT 'person'"),
            ("payment_type", "TEXT NOT NULL DEFAULT 'cash'"),
            ("final_price", "REAL NOT NULL DEFAULT 0"),
            ("paid_cash", "REAL NOT NULL DEFAULT 0"),
            ("paid_pos", "REAL NOT NULL DEFAULT 0"),
            ("paid_card2card", "REAL NOT NULL DEFAULT 0"),
            ("is_settled", "INTEGER NOT NULL DEFAULT 1"),
        ):
            _add_column(db, "sales", c, d)
        # بعد اگر ستون‌های قدیمی مانده، جدول را بدون آن‌ها بازسازی کن
        legacy = {"quantity", "delivered", "delivered_at"}
        if legacy & cols:
            db.execute("DROP TABLE IF EXISTS sales__rebuild")
            # DDL کامل — حفظ PRIMARY KEY و FK (CREATE TABLE AS SELECT قیدها را می‌بُرد)
            db.execute("""
                CREATE TABLE sales__rebuild (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
                    sale_price REAL NOT NULL DEFAULT 0,
                    purchase_price REAL NOT NULL DEFAULT 0,
                    profit REAL NOT NULL DEFAULT 0,
                    sale_date TEXT NOT NULL,
                    customer TEXT NOT NULL DEFAULT '',
                    customer_phone TEXT NOT NULL DEFAULT '',
                    sale_type TEXT NOT NULL DEFAULT 'person',
                    payment_type TEXT NOT NULL DEFAULT 'cash',
                    final_price REAL NOT NULL DEFAULT 0,
                    paid_cash REAL NOT NULL DEFAULT 0,
                    paid_pos REAL NOT NULL DEFAULT 0,
                    paid_card2card REAL NOT NULL DEFAULT 0,
                    is_settled INTEGER NOT NULL DEFAULT 1,
                    notes TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
                )
            """)
            db.execute(
                "INSERT INTO sales__rebuild(id, product_id, sale_price, purchase_price, profit,"
                " sale_date, customer, customer_phone, sale_type, payment_type, final_price,"
                " paid_cash, paid_pos, paid_card2card, is_settled, notes, created_at)"
                " SELECT id, product_id, sale_price, purchase_price, profit, sale_date,"
                " customer, customer_phone, sale_type, payment_type, final_price,"
                " COALESCE(paid_cash,0), COALESCE(paid_pos,0), COALESCE(paid_card2card,0),"
                " COALESCE(is_settled,1), notes, created_at FROM sales"
            )
            db.execute("DROP TABLE sales")
            db.execute("ALTER TABLE sales__rebuild RENAME TO sales")
        db.execute("UPDATE sales SET payment_type = 'cash' WHERE payment_type = 'card'")
        if _table_exists(db, "payments"):
            db.execute(
                "UPDATE sales SET is_settled = 0 WHERE id IN ("
                " SELECT CAST(SUBSTR(notes, 13) AS INTEGER) FROM payments WHERE notes LIKE 'بیعانه فروش #%')"
            )

    # payments: اتصال فقره به فروش بیعانه
    if _table_exists(db, "payments"):
        cols = _table_cols(db, "payments")
        if "sale_id" not in cols:
            # ستون sale_id را با بازسازی جدول اضافه می‌کنیم تا FK صحیح به sales داشته باشد
            # (ALTER TABLE ADD COLUMN نمی‌تواند FK تعریف کند و FK ناقص باعث
            #  خطای «foreign key mismatch» هنگام INSERT می‌شود)
            db.execute("DROP TABLE IF EXISTS payments__rebuild")
            db.execute(
                "CREATE TABLE payments__rebuild ("
                " id INTEGER PRIMARY KEY AUTOINCREMENT,"
                " sale_id INTEGER REFERENCES sales(id) ON DELETE CASCADE,"
                " product_id INTEGER REFERENCES products(id) ON DELETE SET NULL,"
                " product_name TEXT NOT NULL DEFAULT '',"
                " customer_name TEXT NOT NULL DEFAULT '',"
                " customer_phone TEXT NOT NULL DEFAULT '',"
                " total_amount REAL NOT NULL DEFAULT 0,"
                " paid_amount REAL NOT NULL DEFAULT 0,"
                " pay_date TEXT NOT NULL DEFAULT '',"
                " notes TEXT NOT NULL DEFAULT '',"
                " created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),"
                " updated_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))"
                ")"
            )
            db.execute(
                "INSERT INTO payments__rebuild(id, product_id, product_name, customer_name,"
                " customer_phone, total_amount, paid_amount, pay_date, notes, created_at, updated_at)"
                " SELECT id, product_id, product_name, customer_name, customer_phone,"
                " total_amount, paid_amount, pay_date, notes, created_at, updated_at FROM payments"
            )
            db.execute("DROP TABLE payments")
            db.execute("ALTER TABLE payments__rebuild RENAME TO payments")
        # پیوند فقره‌های بیعانه‌ی قدیمی به فروش مربوطه
        for row in db.execute(
            "SELECT id, notes FROM payments WHERE sale_id IS NULL AND notes LIKE 'بیعانه فروش #%'"
        ).fetchall():
            try:
                sid = int(str(row["notes"]).split("#")[1].split(" ")[0])
                exists = db.execute("SELECT 1 FROM sales WHERE id = ?", (sid,)).fetchone()
                if exists:
                    db.execute("UPDATE payments SET sale_id = ? WHERE id = ?", (sid, row["id"]))
            except (ValueError, TypeError):
                pass

    # repairs: تاریخ بازگشت به مشتری
    if _table_exists(db, "repairs"):
        _add_column(db, "repairs", "return_date", "TEXT NOT NULL DEFAULT ''")

    # listings (نسخه‌ی قدیمی) → tracking
    if _table_exists(db, "listings") and not _table_exists(db, "tracking"):
        db.execute("""
            CREATE TABLE tracking (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_name TEXT NOT NULL,
                item_code TEXT NOT NULL DEFAULT '',
                customer_name TEXT NOT NULL DEFAULT '',
                customer_phone TEXT NOT NULL DEFAULT '',
                price REAL NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'new',
                notes TEXT NOT NULL DEFAULT '',
                image TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
            )
        """)
        status_map = {"open": "new", "done": "delivered", "cancelled": "cancelled"}
        rows = db.execute("SELECT * FROM listings").fetchall()
        for r in rows:
            old_kind = {"buy": "خرید از مشتری", "sell": "فروش به مشتری"}.get(r["kind"], "")
            notes = r["notes"] or ""
            if old_kind:
                notes = (notes + " | " if notes else "") + f"نوع قبلی: {old_kind}"
            db.execute(
                "INSERT INTO tracking(id, item_name, item_code, customer_name, customer_phone,"
                " price, status, notes, image, created_at, updated_at)"
                " VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (r["id"], r["watch_name"], r["reference"], r["customer_name"],
                 r["customer_phone"], r["target_price"],
                 status_map.get(r["status"], "new"), notes, r["image"],
                 r["created_at"], r["updated_at"]),
            )
        db.execute("DROP TABLE listings")

    # products/sales: ترمیم ساختار خرابِ جداول — هر بار اجرا امن است
    # در پایگاه‌های داده‌ی ساخته‌شده با نسخه‌های قدیمی، ستون id به‌جای
    # «INTEGER PRIMARY KEY» فقط «INT» است؛ در نتیجه:
    #  - حذف محصول، فروش‌هایش را پاک نمی‌کند و ردیف فروشِ «محصول حذف‌شده»
    #    برای همیشه در تقویم و فروش‌ها باقی می‌ماند
    #  - ردیف‌هایی با شناسه‌ی NULL ساخته می‌شود که هیچ‌وقت قابل حذف/ویرایش نیستند
    # اینجا هر دو جدول با DDL کامل (PK و FK) بازسازی می‌شوند.

    def _needs_pk_rebuild(table):
        for r in db.execute(f"PRAGMA table_info({table})").fetchall():
            if r[1] == "id":
                return not (str(r[2]).upper() == "INTEGER" and r[5] == 1)
        return True

    def _fix_null_ids(table):
        used = {r[0] for r in db.execute(
            f"SELECT id FROM {table} WHERE id IS NOT NULL").fetchall()}
        nxt = (max(used) if used else 0) + 1
        for r in db.execute(
            f"SELECT rowid FROM {table} WHERE id IS NULL ORDER BY rowid"
        ).fetchall():
            while nxt in used:
                nxt += 1
            db.execute(f"UPDATE {table} SET id = ? WHERE rowid = ?", (nxt, r[0]))
            used.add(nxt)

    if _table_exists(db, "products") and _needs_pk_rebuild("products"):
        # هر ستونی که در SCHEMA هست ولی در جدول قدیمی نیست اضافه شود
        for c, d in (
            ("reference", "TEXT NOT NULL DEFAULT ''"),
            ("brand", "TEXT NOT NULL DEFAULT ''"),
            ("available", "INTEGER NOT NULL DEFAULT 1"),
            ("supplier", "TEXT NOT NULL DEFAULT ''"),
            ("purchase_date", "TEXT NOT NULL DEFAULT ''"),
            ("purchase_type", "TEXT NOT NULL DEFAULT 'person'"),
            ("notes", "TEXT NOT NULL DEFAULT ''"),
            ("image", "TEXT NOT NULL DEFAULT ''"),
            ("created_at", "TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))"),
            ("updated_at", "TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))"),
        ):
            _add_column(db, "products", c, d)
        _fix_null_ids("products")
        db.execute("DROP TABLE IF EXISTS products__pkfix")
        db.execute("""
            CREATE TABLE products__pkfix (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                reference TEXT NOT NULL DEFAULT '',
                office_code TEXT NOT NULL,
                website_code TEXT NOT NULL,
                brand TEXT NOT NULL DEFAULT '',
                purchase_price REAL NOT NULL DEFAULT 0,
                sale_price REAL NOT NULL DEFAULT 0,
                available INTEGER NOT NULL DEFAULT 1,
                supplier TEXT NOT NULL DEFAULT '',
                purchase_date TEXT NOT NULL DEFAULT '',
                purchase_type TEXT NOT NULL DEFAULT 'person',
                notes TEXT NOT NULL DEFAULT '',
                image TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
            )
        """)
        db.execute("""
            INSERT INTO products__pkfix(id, name, reference, office_code, website_code,
                brand, purchase_price, sale_price, available, supplier, purchase_date,
                purchase_type, notes, image, created_at, updated_at)
            SELECT id, name, reference, office_code, website_code,
                brand, purchase_price, sale_price, COALESCE(available, 1), supplier,
                COALESCE(purchase_date, ''), COALESCE(purchase_type, 'person'),
                notes, image, created_at, updated_at
            FROM products
        """)
        db.execute("DROP TABLE products")
        db.execute("ALTER TABLE products__pkfix RENAME TO products")

    if _table_exists(db, "sales") and _needs_pk_rebuild("sales"):
        _add_column(
            db, "sales", "created_at",
            "TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))",
        )
        _fix_null_ids("sales")
        db.execute("DROP TABLE IF EXISTS sales__pkfix")
        db.execute("""
            CREATE TABLE sales__pkfix (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
                sale_price REAL NOT NULL DEFAULT 0,
                purchase_price REAL NOT NULL DEFAULT 0,
                profit REAL NOT NULL DEFAULT 0,
                sale_date TEXT NOT NULL DEFAULT '',
                customer TEXT NOT NULL DEFAULT '',
                customer_phone TEXT NOT NULL DEFAULT '',
                sale_type TEXT NOT NULL DEFAULT 'person',
                payment_type TEXT NOT NULL DEFAULT 'cash',
                final_price REAL NOT NULL DEFAULT 0,
                paid_cash REAL NOT NULL DEFAULT 0,
                paid_pos REAL NOT NULL DEFAULT 0,
                paid_card2card REAL NOT NULL DEFAULT 0,
                is_settled INTEGER NOT NULL DEFAULT 1,
                notes TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
            )
        """)
        db.execute("""
            INSERT INTO sales__pkfix(id, product_id, sale_price, purchase_price, profit,
                sale_date, customer, customer_phone, sale_type, payment_type, final_price,
                paid_cash, paid_pos, paid_card2card, is_settled, notes, created_at)
            SELECT id, product_id, sale_price, purchase_price, profit,
                COALESCE(sale_date, ''), customer, customer_phone, sale_type, payment_type,
                final_price, COALESCE(paid_cash, 0), COALESCE(paid_pos, 0),
                COALESCE(paid_card2card, 0), COALESCE(is_settled, 1), notes,
                COALESCE(created_at, datetime('now', 'localtime'))
            FROM sales
        """)
        db.execute("DROP TABLE sales")
        db.execute("ALTER TABLE sales__pkfix RENAME TO sales")

    # sales: ترمیم داده‌ی خراب — تاریخ‌های غیر ISO به ISO تبدیل می‌شوند
    # (تاریخ شمسیِ خام در مقایسه‌های تاریخ کار نمی‌کند؛ فروش در تقویم،
    #  مرتب‌سازی و آمار دیده نمی‌شود و حذف/نمایشش ناسازگار می‌شود)
    if _table_exists(db, "sales"):
        for row in db.execute("SELECT rowid, sale_date FROM sales").fetchall():
            rid, d = row[0], (row[1] or "").strip()
            if d and not (len(d) == 10 and d[4] == "-" and d[7] == "-"):
                parsed = parse_jalali_date(d)
                if parsed:
                    db.execute("UPDATE sales SET sale_date = ? WHERE rowid = ?", (parsed, rid))

    # توالی AUTOINCREMENT را همگام کن تا شناسه‌ی تکراری تولید نشود
    # (در پایگاه‌های خیلی قدیمی بدون جدول AUTOINCREMENT، sqlite_sequence وجود ندارد)
    has_sequence = db.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='sqlite_sequence'"
    ).fetchone() is not None
    if has_sequence:
        for t in ("products", "sales"):
            if _table_exists(db, t):
                db.execute(
                    "INSERT INTO sqlite_sequence(name, seq)"
                    f" SELECT '{t}', COALESCE((SELECT MAX(id) FROM {t}), 0)"
                    " WHERE NOT EXISTS (SELECT 1 FROM sqlite_sequence WHERE name = ?)",
                    (t,),
                )
                db.execute(
                    "UPDATE sqlite_sequence SET seq = (SELECT COALESCE(MAX(id), 0) FROM"
                    f" {t}) WHERE name = ?",
                    (t,),
                )



def init_db():
    with get_db() as db:
        # اول مهاجرت‌ها (بازسازی جدول‌ها) و بعد اسکیمای کامل با ایندکس‌ها
        _migrate(db)
        db.executescript(SCHEMA)
        for brand in DEFAULT_BRANDS:
            db.execute(
                "INSERT OR IGNORE INTO settings(key, value) VALUES(?, ?)",
                ("brand:" + brand, brand),
            )
        for key, val in (("theme", "light"), ("site_icon", ""), ("currency", "تومان")):
            db.execute("INSERT OR IGNORE INTO settings(key, value) VALUES(?, ?)", (key, val))


def get_setting(key, default=""):
    with get_db() as db:
        row = db.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else default


def set_setting(key, value):
    with get_db() as db:
        db.execute(
            "INSERT INTO settings(key, value) VALUES(?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )


def get_brands():
    with get_db() as db:
        rows = db.execute(
            "SELECT value FROM settings WHERE key LIKE 'brand:%' ORDER BY value"
        ).fetchall()
        return [r["value"] for r in rows]


def add_brand(name):
    name = (name or "").strip()
    if not name:
        return False, "نام برند خالی است"
    with get_db() as db:
        exists = db.execute(
            "SELECT 1 FROM settings WHERE key = ?", ("brand:" + name,)
        ).fetchone()
        if exists:
            return False, "این برند قبلاً ثبت شده است"
        db.execute(
            "INSERT INTO settings(key, value) VALUES(?, ?)", ("brand:" + name, name)
        )
    return True, ""


def delete_brand(name):
    with get_db() as db:
        db.execute("DELETE FROM settings WHERE key = ?", ("brand:" + name,))
    return True, ""


def _stamp():
    import datetime
    return datetime.datetime.now().strftime("%Y%m%d_%H%M%S")


def backup_db(filename=None):
    """ایجاد نسخه‌ی پشتیبان امن (شامل فایل‌های WAL) از پایگاه‌داده."""
    os.makedirs(BACKUP_DIR, exist_ok=True)
    fname = filename or ("backup_" + _stamp() + ".db")
    if not fname.endswith(".db"):
        fname += ".db"
    target = os.path.join(BACKUP_DIR, os.path.basename(fname))
    src = sqlite3.connect(DB_PATH)
    dst = sqlite3.connect(target)
    with dst:
        src.backup(dst)
    dst.close()
    src.close()
    return target


def list_backups():
    os.makedirs(BACKUP_DIR, exist_ok=True)
    out = []
    for f in sorted(os.listdir(BACKUP_DIR), reverse=True):
        if f.endswith(".db"):
            p = os.path.join(BACKUP_DIR, f)
            out.append({
                "name": f,
                "size": os.path.getsize(p),
                "modified": os.path.getmtime(p),
            })
    return out


def restore_db(filename):
    """بازگردانی نسخه‌ی پشتیبان. ابتدا از وضعیت فعلی یک بکاپ می‌گیرد."""
    safe = os.path.basename(filename)
    target = os.path.join(BACKUP_DIR, safe)
    if not os.path.isfile(target):
        return False, "فایل نسخه‌ی پشتیبان یافت نشد"
    backup_db("pre_restore_" + _stamp() + ".db")
    src = sqlite3.connect(target)
    dst = sqlite3.connect(DB_PATH)
    with dst:
        src.backup(dst)
    dst.close()
    src.close()
    init_db()
    return True, ""


def delete_backup(filename):
    safe = os.path.basename(filename)
    p = os.path.join(BACKUP_DIR, safe)
    if os.path.isfile(p):
        os.remove(p)
        return True, ""
    return False, "فایل یافت نشد"


def db_stats():
    with get_db() as db:
        p = db.execute("SELECT COUNT(*) AS c FROM products").fetchone()["c"]
        s = db.execute("SELECT COUNT(*) AS c FROM sales").fetchone()["c"]
        r = db.execute("SELECT COUNT(*) AS c FROM repairs").fetchone()["c"]
        t = db.execute("SELECT COUNT(*) AS c FROM tracking").fetchone()["c"]
        pay = db.execute("SELECT COUNT(*) AS c FROM payments").fetchone()["c"]
    return {"products": p, "sales": s, "repairs": r, "tracking": t, "payments": pay}
