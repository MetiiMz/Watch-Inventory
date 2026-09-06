# -*- coding: utf-8 -*-
"""Integration test: sales must appear/disappear in the Calendar consistently,
and deleting a sale must remove it from the Calendar at the same time.

Run: .venv/bin/python /tmp/test_calendar_sale_deletion.py
"""
import os
import sys
import tempfile

os.environ["TIKOTIME_DB"] = os.path.join(tempfile.mkdtemp(prefix="tikotime_test_"), "test.db")

sys.path.insert(0, "/media/MyShit/Works/Tick O Time/DB/Watch Inventory")
import sqlite3  # noqa: E402
import datetime  # noqa: E402
import app as app_module  # noqa: E402
from database import init_db, get_db, DB_PATH  # noqa: E402
from jalali import gregorian_to_jalali  # noqa: E402

client = app_module.app.test_client()
app_module.app.config["TESTING"] = True

passed, failed = [], []


def check(name, cond, extra=""):
    (passed if cond else failed).append(name)
    print(("PASS  " if cond else "FAIL  ") + name + (f"  -> {extra}" if extra and not cond else ""))


# ---- 0) simulate a LEGACY database exactly like the production one was:
#         products/sales with `id INT` (no PK, no FK), a NULL-id sale row with
#         a raw Jalali date — invisible in calendar, undeletable from UI
import sqlite3 as _sq
_con = _sq.connect(DB_PATH)
_con.executescript("""
    CREATE TABLE products (
        id INT, name TEXT, reference TEXT, office_code TEXT, website_code TEXT,
        brand TEXT, purchase_price REAL, sale_price REAL, available,
        supplier TEXT, purchase_date TEXT, purchase_type TEXT, notes TEXT,
        image TEXT, created_at TEXT, updated_at TEXT
    );
    CREATE TABLE sales (
        id INT, product_id INT, sale_price REAL, purchase_price REAL, profit REAL,
        sale_date TEXT, customer TEXT, customer_phone TEXT, sale_type TEXT,
        payment_type TEXT, final_price REAL, notes TEXT, created_at TEXT,
        paid_cash, paid_pos, paid_card2card, is_settled
    );
    INSERT INTO products VALUES(1, 'Legacy Watch', 'R1', 'OF-1', 'WS-1', 'رولکس',
        18000000, 23000000, 0, '', '2026-08-29', 'person', '', '', '2026-08-29', '2026-08-29');
    INSERT INTO sales VALUES(NULL, 1, 23000000, 18000000, 5000000, '1405/06/07',
        'علی', '', 'person', 'cash', 23000000, '', NULL, 0, 10000000, 0, 1);
    INSERT INTO sales VALUES(2, 1, 23000000, 18000000, 5000000, '2026-08-28',
        'رضا', '', 'person', 'cash', 23000000, '', '2026-08-28', 23000000, 0, 0, 1);
""")
_con.commit()
_con.close()

# repair runs on every init
init_db()
with get_db() as db:
    corrupt = db.execute("SELECT COUNT(*) FROM sales WHERE id IS NULL").fetchone()[0]
    bad_dates = db.execute(
        "SELECT COUNT(*) FROM sales WHERE sale_date != ''"
        " AND (length(sale_date) != 10 OR substr(sale_date,5,1) != '-')"
    ).fetchone()[0]
    fixed = db.execute(
        "SELECT id, sale_date FROM sales WHERE customer = 'علی'"
    ).fetchone()
    legacy = db.execute("SELECT id FROM sales WHERE customer = 'رضا'").fetchone()
    pk_info = [(r[2], r[5]) for r in db.execute("PRAGMA table_info(sales)") if r[1] == "id"][0]
    seq = db.execute("SELECT seq FROM sqlite_sequence WHERE name = 'sales'").fetchone()
check("migration: no NULL-id sales left", corrupt == 0, str(corrupt))
check("migration: raw Jalali dates normalized to ISO", bad_dates == 0, str(bad_dates))
check("migration: repaired row got an id", fixed is not None and fixed["id"] is not None)
check("migration: repaired date is ISO", fixed is not None and fixed["sale_date"] == "2026-08-29",
      str(dict(fixed) if fixed else None))
check("migration: existing ids preserved", legacy is not None and legacy["id"] == 2)
check("migration: sales PK is now INTEGER PRIMARY KEY",
      str(pk_info[0]).upper() == "INTEGER" and pk_info[1] == 1, f"type={pk_info[0]} pk={pk_info[1]}")
check("migration: sqlite_sequence synced", seq is not None and seq["seq"] >= 2, str(seq))

# next insert must not collide with the repaired id
with get_db() as db:
    db.execute(
        "INSERT INTO sales(product_id, sale_price, purchase_price, profit, sale_date, final_price)"
        " VALUES(1, 1, 1, 0, '2026-09-01', 1)"
    )
    nxt = db.execute("SELECT MAX(id) FROM sales").fetchone()[0]
check("no id collision after repair", nxt > (fixed["id"] if fixed else 0))

# ---- 1) create a product
r = client.post("/api/products", json={
    "name": "Test Rolex", "office_code": "OF-10", "website_code": "WS-10",
    "purchase_price": "100", "sale_price": "200",
})
check("create product", r.status_code == 200 and r.get_json().get("ok"), r.get_data(as_text=True)[:200])
pid = r.get_json()["product"]["id"]

today = datetime.date.today()
jy, jm, _ = gregorian_to_jalali(today.year, today.month, today.day)
today_iso = today.isoformat()


def cal_sale_ids():
    data = client.get(f"/api/calendar?jy={jy}&jm={jm}").get_json()
    ids = []
    for cell in data["cells"]:
        if cell:
            ids.extend(s["id"] for s in cell["sales"])
    return ids


def day_sale_ids():
    data = client.get(f"/api/calendar/day?date={today_iso}").get_json()
    return [s["id"] for s in data["sales"]]


# ---- 2) sale with UI-style JALALI date must be visible in the calendar
r = client.post("/api/sales", json={"product_id": pid, "payment_type": "cash",
                                    "sale_date": "۱۴۰۵/۰۶/۱۲"})
check("create sale with Jalali date", r.status_code == 200 and r.get_json().get("ok"),
      r.get_data(as_text=True)[:200])
sale1 = r.get_json()["sale"]["id"]
with get_db() as db:
    stored = db.execute("SELECT sale_date FROM sales WHERE id = ?", (sale1,)).fetchone()[0]
check("Jalali input stored as ISO", stored == "2026-09-03", str(stored))
check("Jalali-date sale visible in month view", sale1 in cal_sale_ids(), str(cal_sale_ids()))
check("Jalali-date sale visible in day view", sale1 in day_sale_ids(), str(day_sale_ids()))

# ---- 3) sale with NO date defaults to today and is visible
r = client.post("/api/products", json={
    "name": "Test Omega", "office_code": "OF-20", "website_code": "WS-20",
    "purchase_price": "100", "sale_price": "200",
})
pid2 = r.get_json()["product"]["id"]
r = client.post("/api/sales", json={"product_id": pid2, "payment_type": "cash"})
check("create sale without date", r.status_code == 200 and r.get_json().get("ok"),
      r.get_data(as_text=True)[:200])
sale2 = r.get_json()["sale"]["id"]
check("no-date sale visible in month view", sale2 in cal_sale_ids(), str(cal_sale_ids()))
check("no-date sale visible in day view", sale2 in day_sale_ids(), str(day_sale_ids()))


# ---- 4) delete sale1 -> must vanish from BOTH calendar views immediately
r = client.delete(f"/api/sales/{sale1}")
check("delete single sale", r.status_code == 200 and r.get_json().get("ok"), r.get_data(as_text=True)[:200])
check("deleted sale gone from month view", sale1 not in cal_sale_ids(), str(cal_sale_ids()))
check("deleted sale gone from day view", sale1 not in day_sale_ids(), str(day_sale_ids()))
with get_db() as db:
    avail = db.execute("SELECT available FROM products WHERE id = ?", (pid,)).fetchone()[0]
check("product available again after sale delete", avail == 1)

# ---- 5) deposit sale + bulk delete -> gone from calendar, receipt cascade-removed
r = client.post("/api/sales", json={"product_id": pid2, "payment_type": "deposit", "paid_cash": "50"})
check("create deposit sale", r.status_code == 200 and r.get_json().get("ok"), r.get_data(as_text=True)[:200])
sale3 = r.get_json()["sale"]["id"]
r = client.get("/api/payments").get_json()
check("deposit receipt auto-created", len([p for p in r["items"] if p.get("sale_id") == sale3]) == 1)
check("deposit sale visible in month view", sale3 in cal_sale_ids(), str(cal_sale_ids()))

r = client.post("/api/sales/bulk-delete", json={"ids": [sale3]})
check("bulk delete sale", r.status_code == 200 and r.get_json().get("ok"), r.get_data(as_text=True)[:200])
check("bulk-deleted sale gone from month view", sale3 not in cal_sale_ids(), str(cal_sale_ids()))
check("bulk-deleted sale gone from day view", sale3 not in day_sale_ids(), str(day_sale_ids()))
r = client.get("/api/payments").get_json()
check("deposit receipt cascade-removed", len([p for p in r["items"] if p.get("sale_id") == sale3]) == 0)

# ---- 6) repaired legacy sales are now visible in calendar AND product-delete cascades
with get_db() as db:
    legacy_id = db.execute("SELECT id FROM sales WHERE customer = 'علی'").fetchone()[0]
day = client.get("/api/calendar/day?date=2026-08-29").get_json()
check("repaired legacy sale visible in day view", legacy_id in [s["id"] for s in day["sales"]],
      str([s["id"] for s in day["sales"]]))

# the KEY requirement: deleting a PRODUCT removes its sales from the calendar too
r = client.post("/api/products", json={
    "name": "Cascade Test", "office_code": "OF-30", "website_code": "WS-30",
    "purchase_price": "100", "sale_price": "200",
})
pid3 = r.get_json()["product"]["id"]
r = client.post("/api/sales", json={"product_id": pid3, "payment_type": "cash"})
check("create sale for cascade test", r.status_code == 200 and r.get_json().get("ok"),
      r.get_data(as_text=True)[:200])
sale4 = r.get_json()["sale"]["id"]
check("cascade-test sale visible in month view", sale4 in cal_sale_ids(), str(cal_sale_ids()))

r = client.delete(f"/api/products/{pid3}")
check("delete product", r.status_code == 200 and r.get_json().get("ok"), r.get_data(as_text=True)[:200])
check("product-delete removed sale from month view", sale4 not in cal_sale_ids(), str(cal_sale_ids()))
check("product-delete removed sale from day view", sale4 not in day_sale_ids(), str(day_sale_ids()))

# and the legacy undeletable row can now be removed from the UI as well
r = client.delete(f"/api/sales/{legacy_id}")
check("legacy corrupt row now deletable", r.status_code == 200 and r.get_json().get("ok"),
      r.get_data(as_text=True)[:200])
with get_db() as db:
    gone = db.execute("SELECT COUNT(*) FROM sales WHERE customer = 'علی'").fetchone()[0]
check("legacy corrupt row removed", gone == 0)

# ---- 7) no orphans in DB
db = sqlite3.connect(DB_PATH)
orphan_sales = db.execute(
    "SELECT COUNT(*) FROM sales s LEFT JOIN products p ON p.id = s.product_id WHERE p.id IS NULL"
).fetchone()[0]
orphan_payments = db.execute(
    "SELECT COUNT(*) FROM payments pm LEFT JOIN sales s ON s.id = pm.sale_id"
    " WHERE pm.sale_id IS NOT NULL AND s.id IS NULL"
).fetchone()[0]
db.close()
check("no orphan sales after deletions", orphan_sales == 0, str(orphan_sales))
check("no orphan payments after deletions", orphan_payments == 0, str(orphan_payments))

print()
print(f"RESULT: {len(passed)} passed, {len(failed)} failed")
sys.exit(1 if failed else 0)

