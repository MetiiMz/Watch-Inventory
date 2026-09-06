# -*- coding: utf-8 -*-
"""TikoTime — سیستم مدیریت انبار فروشگاه ساعت (نسخه‌ی محلی).

اجرا:
    ./run.sh   (یا)   .venv/bin/python app.py
آدرس پیش‌فرض: http://127.0.0.1:5000  (با متغیر محیطی PORT قابل تغییر)
"""

import datetime
import os
import secrets

from flask import (
    Flask, jsonify, render_template, request, redirect, url_for,
    send_from_directory, send_file, abort,
)

import database as db_mod
from database import (
    init_db, get_db, get_setting, set_setting, get_brands, add_brand,
    delete_brand, backup_db, list_backups, restore_db, delete_backup,
    IMG_DIR, BACKUP_DIR,
)
from reports import get_dashboard_stats, get_monthly_activity, get_brand_breakdown
from excel_io import (
    export_products, export_repairs, export_tracking, export_payments,
    export_sales, import_products,
)
from jalali import (
    gregorian_to_jalali, jalali_to_gregorian, jalali_month_length,
    today_jalali, today_iso, fa_num, parse_jalali_date, MONTH_NAMES, WEEKDAY_NAMES,
)

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)

DATA_DIR = db_mod.DATA_DIR

ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif", ".svg"}
ICON_EXT = {".png", ".svg", ".ico", ".jpg", ".jpeg", ".webp"}

STATUS_FA = {
    "received": "دریافت شده",
    "in_progress": "در حال تعمیر",
    "waiting_parts": "انتظار قطعه",
    "done": "آماده تحویل",
    "delivered": "تحویل شده",
}
STATUS_COLOR = {
    "received": "blue",
    "in_progress": "amber",
    "waiting_parts": "purple",
    "done": "green",
    "delivered": "gray",
}

TRACKING_STATUS_FA = {
    "new": "جدید",
    "ordered": "سفارش داده شد",
    "found": "پیدا شد",
    "delivered": "تحویل شد",
    "cancelled": "لغو شد",
}
TRACKING_STATUS_COLOR = {
    "new": "blue",
    "ordered": "amber",
    "found": "green",
    "delivered": "gray",
    "cancelled": "red",
}

SALE_TYPE_FA = {"person": "حضوری", "online": "آنلاین"}
PAYMENT_TYPE_FA = {"cash": "نقدی", "card": "کارت به کارت", "deposit": "بیعانه"}

# مرتب‌سازی مجاز برای API محصولات
PRODUCT_SORT_MAP = {
    "office_code": "office_code COLLATE NOCASE",
    "website_code": "website_code COLLATE NOCASE",
    "name": "name COLLATE NOCASE",
    "brand": "brand COLLATE NOCASE",
    "supplier": "supplier COLLATE NOCASE",
    "purchase_date": "purchase_date",
    "purchase_price": "purchase_price",
    "sale_price": "sale_price",
    "available": "available",
    "created_at": "id",
}

app.config["MAX_CONTENT_LENGTH"] = 32 * 1024 * 1024


# ---------------------------------------------------------------- helpers

def fa_date(iso, with_weekday=False):
    if not iso:
        return ""
    try:
        y, m, d = (int(x) for x in str(iso)[:10].split("-"))
        datetime.date(y, m, d)
    except (ValueError, TypeError):
        return str(iso) if iso else ""
    jy, jm, jd = gregorian_to_jalali(y, m, d)
    if with_weekday:
        wd = WEEKDAY_NAMES[datetime.date(y, m, d).weekday()]
        return f"{wd} {fa_num(jd)} {MONTH_NAMES[jm - 1]} {fa_num(jy)}"
    return f"{fa_num(jy)}/{fa_num(f'{jm:02d}')}/{fa_num(f'{jd:02d}')}"


def fa_money(value):
    try:
        n = float(value or 0)
    except (TypeError, ValueError):
        n = 0
    s = f"{int(round(n)):,}".replace(",", "٬")
    return fa_num(s)


def to_int(value, default=0):
    try:
        return int(float(str(value).replace(",", "").replace("٬", "").strip() or default))
    except (TypeError, ValueError):
        return default


def to_float(value, default=0.0):
    try:
        return float(str(value).replace(",", "").replace("٬", "").strip() or default)
    except (TypeError, ValueError):
        return default


def product_dict(row):
    d = dict(row)
    d["purchase_date_fa"] = fa_date(d.get("purchase_date"))
    d["purchase_date_weekday"] = fa_date(d.get("purchase_date"), with_weekday=True)
    d["purchase_price_display"] = fa_money(d.get("purchase_price"))
    d["sale_price_display"] = fa_money(d.get("sale_price"))
    d["profit_per_unit"] = (d.get("sale_price") or 0) - (d.get("purchase_price") or 0)
    d["profit_per_unit_display"] = fa_money(d["profit_per_unit"])
    d["total_value"] = d.get("purchase_price") or 0
    d["total_value_display"] = fa_money(d["total_value"])
    d["total_sale_value"] = d.get("sale_price") or 0
    d["total_sale_value_display"] = fa_money(d["total_sale_value"])
    d["is_available"] = 1 if d.get("available") else 0
    d["availability_fa"] = "موجود" if d["is_available"] else "ناموجود"
    return d


def repair_dict(row):
    d = dict(row)
    d["delivery_date_fa"] = fa_date(d.get("delivery_date"))
    d["delivery_date_weekday"] = fa_date(d.get("delivery_date"), with_weekday=True)
    d["return_date_fa"] = fa_date(d.get("return_date"))
    d["repair_price_display"] = fa_money(d.get("repair_price"))
    d["status_fa"] = STATUS_FA.get(d.get("status"), d.get("status"))
    d["status_color"] = STATUS_COLOR.get(d.get("status"), "gray")
    d["is_warranty_fa"] = "بله" if d.get("is_warranty") else "خیر"
    return d


def tracking_dict(row):
    d = dict(row)
    d["status_fa"] = TRACKING_STATUS_FA.get(d.get("status"), d.get("status"))
    d["status_color"] = TRACKING_STATUS_COLOR.get(d.get("status"), "gray")
    d["price_display"] = fa_money(d.get("price"))
    d["customer_phone_fa"] = fa_num(d.get("customer_phone") or "")
    return d


def payment_dict(row):
    d = dict(row)
    d["pay_date_fa"] = fa_date(d.get("pay_date"))
    d["total_amount_display"] = fa_money(d.get("total_amount"))
    d["paid_amount_display"] = fa_money(d.get("paid_amount"))
    d["remaining"] = (d.get("total_amount") or 0) - (d.get("paid_amount") or 0)
    d["remaining_display"] = fa_money(d["remaining"])
    d["paid_percent"] = (
        round(100 * (d["paid_amount"] / d["total_amount"]))
        if d.get("total_amount") else 0
    )
    return d


def sale_dict(row):
    d = dict(row)
    d["sale_date_fa"] = fa_date(d.get("sale_date"))
    d["sale_date_weekday"] = fa_date(d.get("sale_date"), with_weekday=True)
    d["sale_price_display"] = fa_money(d.get("sale_price"))
    d["profit_display"] = fa_money(d.get("profit"))
    d["customer_phone_fa"] = fa_num(d.get("customer_phone") or "")
    d["sale_type_fa"] = SALE_TYPE_FA.get(d.get("sale_type"), "حضوری")
    d["payment_type_fa"] = PAYMENT_TYPE_FA.get(d.get("payment_type"), "نقدی")
    final = d.get("final_price") or d.get("sale_price") or 0
    d["final_price_display"] = fa_money(final)
    d["paid_cash"] = d.get("paid_cash") or 0
    d["paid_pos"] = d.get("paid_pos") or 0
    d["paid_card2card"] = d.get("paid_card2card") or 0
    d["paid_total"] = d["paid_cash"] + d["paid_pos"] + d["paid_card2card"]
    d["paid_total_display"] = fa_money(d["paid_total"])
    d["paid_breakdown_fa"] = " + ".join(filter(None, [
        f"نقدی {fa_money(d['paid_cash'])}" if d["paid_cash"] else "",
        f"کارت‌خوان {fa_money(d['paid_pos'])}" if d["paid_pos"] else "",
        f"کارت به کارت {fa_money(d['paid_card2card'])}" if d["paid_card2card"] else "",
    ]))
    d["purchase_price_display"] = fa_money(d.get("p_purchase_price") if "p_purchase_price" in d else d.get("purchase_price"))
    d["is_settled"] = 1 if d.get("is_settled") else 0
    return d


def clean(value):
    return str(value or "").strip()


def to_en_phone(value):
    """شماره تلفن: تبدیل ارقام فارسی به انگلیسی و حذف کاراکترهای اضافی."""
    return str(value or "").translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")).strip()


def to_en_digits(value):
    """تبدیل ارقام فارسی به انگلیسی (برای جستجو)."""
    return str(value or "").translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789"))


def _remove_image(fname):
    if not fname:
        return
    safe = os.path.basename(fname)
    p = os.path.join(IMG_DIR, safe)
    if os.path.isfile(p):
        try:
            os.remove(p)
        except OSError:
            pass


@app.context_processor
def inject_helpers():
    endpoint = (request.endpoint or "").split(".")[0]
    nav_map = {
        "dashboard": "dashboard", "products_page": "products",
        "calendar_page": "calendar", "repairs_page": "repairs",
        "sold_page": "sold", "tracking_page": "tracking",
        "payments_page": "payments", "settings_page": "settings",
    }
    active = nav_map.get(endpoint, "")
    site_icon = ""
    try:
        site_icon = get_setting("site_icon", "")
    except Exception:
        pass
    badges = {}
    if active:
        try:
            with get_db() as db:
                low = db.execute("SELECT COUNT(*) AS c FROM products WHERE available = 0").fetchone()["c"]
                reps = db.execute("SELECT COUNT(*) AS c FROM repairs WHERE status != 'delivered'").fetchone()["c"]
                unpaid = db.execute(
                    "SELECT COUNT(*) AS c FROM payments WHERE total_amount - paid_amount > 0.001"
                ).fetchone()["c"]
                tracking_open = db.execute(
                    "SELECT COUNT(*) AS c FROM tracking WHERE status NOT IN ('delivered','cancelled')"
                ).fetchone()["c"]
            badges = {
                "nav_badge_low": low or None,
                "nav_badge_repairs": reps or None,
                "nav_badge_unpaid": unpaid or None,
                "nav_badge_tracking": tracking_open or None,
            }
        except Exception:
            badges = {}
    return {
        "fa_date": fa_date,
        "fa_money": fa_money,
        "fa_num": fa_num,
        "MONTH_NAMES": MONTH_NAMES,
        "STATUS_FA": STATUS_FA,
        "TRACKING_STATUS_FA": TRACKING_STATUS_FA,
        "site_icon": site_icon,
        "active": active,
        **badges,
    }


# ---------------------------------------------------------------- pages

@app.route("/")
def index():
    return redirect(url_for("dashboard"))


@app.route("/dashboard")
def dashboard():
    init_db()
    stats = get_dashboard_stats()
    monthly = get_monthly_activity(12)
    brands = get_brand_breakdown()
    with get_db() as db:
        sales_rows = db.execute(
            """
            SELECT s.*, p.name AS product_name, p.image AS product_image
            FROM sales s LEFT JOIN products p ON p.id = s.product_id
            ORDER BY s.sale_date DESC, s.id DESC LIMIT 8
            """
        ).fetchall()
        purchase_rows = db.execute(
            "SELECT * FROM products WHERE purchase_date != '' "
            "ORDER BY purchase_date DESC, id DESC LIMIT 8"
        ).fetchall()
        low = db.execute(
            "SELECT * FROM products WHERE available = 0 ORDER BY name LIMIT 6"
        ).fetchall()
    return render_template(
        "dashboard.html", stats=stats, monthly=monthly, brands=brands,
        recent_sales=[sale_dict(x) for x in sales_rows],
        recent_purchases=[product_dict(x) for x in purchase_rows],
        low_stock=[product_dict(x) for x in low],
    )


@app.route("/products")
def products_page():
    init_db()
    return render_template("products.html")


@app.route("/calendar")
def calendar_page():
    init_db()
    return render_template("calendar.html")


@app.route("/repairs")
def repairs_page():
    init_db()
    return render_template("repairs.html")


@app.route("/sold")
def sold_page():
    init_db()
    return render_template("sold.html")


@app.route("/tracking")
def tracking_page():
    init_db()
    return render_template("tracking.html")


@app.route("/payments")
def payments_page():
    init_db()
    return render_template("payments.html")


@app.route("/settings")
def settings_page():
    init_db()
    return render_template("settings.html")


# ---------------------------------------------------------------- shared APIs

@app.route("/api/brands")
def api_brands():
    return jsonify({"brands": get_brands()})


@app.route("/api/brands", methods=["POST"])
def api_brands_add():
    payload = request.get_json(force=True, silent=True) or {}
    ok, err = add_brand(payload.get("name"))
    if not ok:
        return jsonify({"ok": False, "error": err}), 400
    return jsonify({"ok": True})


@app.route("/api/brands/delete", methods=["POST"])
def api_brands_delete():
    payload = request.get_json(force=True, silent=True) or {}
    ok, err = delete_brand(payload.get("name"))
    if not ok:
        return jsonify({"ok": False, "error": err}), 400
    return jsonify({"ok": True})


@app.route("/api/upload", methods=["POST"])
def api_upload():
    f = request.files.get("file")
    kind = request.form.get("kind", "image")
    if not f or not f.filename:
        return jsonify({"ok": False, "error": "فایلی انتخاب نشده است"}), 400
    ext = os.path.splitext(f.filename)[1].lower()
    allowed = ICON_EXT if kind == "icon" else ALLOWED_EXT
    if ext not in allowed:
        return jsonify({"ok": False, "error": "فرمت فایل پشتیبانی نمی‌شود"}), 400
    fname = ("icon_" if kind == "icon" else "img_") + \
        datetime.datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + secrets.token_hex(4) + ext
    os.makedirs(IMG_DIR, exist_ok=True)
    f.save(os.path.join(IMG_DIR, fname))
    return jsonify({"ok": True, "path": fname})


@app.route("/data/images/<path:fname>")
def serve_image(fname):
    return send_from_directory(IMG_DIR, fname)


# ---------------------------------------------------------------- products API

def _product_values(payload):
    """اعتبارسنجی و ساخت دیکشنری مقادیر محصول. خروجی: (values, error)"""
    name = clean(payload.get("name"))
    office_code = clean(payload.get("office_code"))
    website_code = clean(payload.get("website_code"))
    if not name:
        return None, "نام ساعت الزامی است"
    if not office_code:
        return None, "کد دفتر فروشگاه الزامی است"
    if not website_code:
        return None, "کد انبار سایت الزامی است"

    purchase_date = clean(payload.get("purchase_date"))
    if purchase_date:
        parsed = parse_jalali_date(purchase_date)
        if not parsed:
            return None, "تاریخ خرید معتبر نیست (نمونه: ۱۴۰۳/۰۵/۱۲)"
        purchase_date = parsed
    else:
        purchase_date = ""

    return {
        "name": name,
        "reference": clean(payload.get("reference")),
        "office_code": office_code,
        "website_code": website_code,
        "brand": clean(payload.get("brand")),
        "purchase_price": max(0.0, to_float(payload.get("purchase_price"))),
        "sale_price": max(0.0, to_float(payload.get("sale_price"))),
        # هر ردیف = یک دستگاه؛ با ثبت فروش ناموجود می‌شود
        "available": 1,
        "supplier": clean(payload.get("supplier")),
        "purchase_date": purchase_date,
        "notes": clean(payload.get("notes")),
        "image": clean(payload.get("image")),
    }, None


def _check_duplicate(db, office_code, website_code, exclude_id=None):
    q = ("SELECT id, name, office_code, website_code FROM products "
         "WHERE (office_code = ? COLLATE NOCASE OR website_code = ? COLLATE NOCASE)")
    params = [office_code, website_code]
    if exclude_id:
        q += " AND id != ?"
        params.append(exclude_id)
    dup = db.execute(q, params).fetchone()
    if not dup:
        return None
    if dup["office_code"].lower() == office_code.lower():
        return f"کد دفتر فروشگاه «{office_code}» قبلاً برای ساعت «{dup['name']}» ثبت شده است"
    return f"کد انبار سایت «{website_code}» قبلاً برای ساعت «{dup['name']}» ثبت شده است"


@app.route("/api/products")
def api_products():
    q = request.args.get("q", "").strip()
    brand = request.args.get("brand", "").strip()
    status = request.args.get("status", "").strip()
    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()
    sort = request.args.get("sort", "office_code").strip()
    direction = request.args.get("dir", "asc").strip().lower()

    sql = "SELECT * FROM products WHERE 1=1"
    params = []
    if q:
        like = f"%{q}%"
        sql += (" AND (name LIKE ? OR reference LIKE ? OR office_code LIKE ? "
                "OR website_code LIKE ? OR brand LIKE ? OR supplier LIKE ?)")
        params += [like] * 6
    if brand:
        sql += " AND brand = ?"
        params.append(brand)
    if status == "available":
        sql += " AND available = 1"
    elif status == "unavailable":
        sql += " AND available = 0"
    if date_from:
        parsed = parse_jalali_date(date_from)
        if parsed:
            sql += " AND purchase_date >= ?"
            params.append(parsed)
    if date_to:
        parsed = parse_jalali_date(date_to)
        if parsed:
            sql += " AND purchase_date <= ?"
            params.append(parsed)

    col = PRODUCT_SORT_MAP.get(sort, PRODUCT_SORT_MAP["office_code"])
    d = "DESC" if direction == "desc" else "ASC"
    sql += f" ORDER BY {col} {d}, id DESC"

    with get_db() as db:
        rows = db.execute(sql, params).fetchall()
    return jsonify([product_dict(r) for r in rows])


@app.route("/api/products/<int:pid>")
def api_product_get(pid):
    with get_db() as db:
        row = db.execute("SELECT * FROM products WHERE id = ?", (pid,)).fetchone()
    if not row:
        return jsonify({"ok": False, "error": "محصول یافت نشد"}), 404
    return jsonify(product_dict(row))


@app.route("/api/products", methods=["POST"])
def api_products_create():
    payload = request.get_json(force=True, silent=True) or {}
    values, err = _product_values(payload)
    if err:
        return jsonify({"ok": False, "error": err}), 400
    with get_db() as db:
        dup = _check_duplicate(db, values["office_code"], values["website_code"])
        if dup:
            return jsonify({"ok": False, "error": dup}), 400
        cols = ", ".join(values.keys())
        marks = ", ".join("?" for _ in values)
        cur = db.execute(
            f"INSERT INTO products({cols}) VALUES({marks})",
            tuple(values.values()),
        )
        pid = cur.lastrowid
        row = db.execute("SELECT * FROM products WHERE id = ?", (pid,)).fetchone()
    return jsonify({"ok": True, "product": product_dict(row)})


@app.route("/api/products/<int:pid>", methods=["PUT"])
def api_products_update(pid):
    payload = request.get_json(force=True, silent=True) or {}
    values, err = _product_values(payload)
    if err:
        return jsonify({"ok": False, "error": err}), 400
    with get_db() as db:
        old = db.execute("SELECT * FROM products WHERE id = ?", (pid,)).fetchone()
        if not old:
            return jsonify({"ok": False, "error": "محصول یافت نشد"}), 404
        dup = _check_duplicate(db, values["office_code"], values["website_code"], exclude_id=pid)
        if dup:
            return jsonify({"ok": False, "error": dup}), 400
        sets = ", ".join(f"{k} = ?" for k in values)
        db.execute(
            f"UPDATE products SET {sets}, updated_at = datetime('now', 'localtime') WHERE id = ?",
            (*values.values(), pid),
        )
        if old["image"] and old["image"] != values["image"]:
            _remove_image(old["image"])
        row = db.execute("SELECT * FROM products WHERE id = ?", (pid,)).fetchone()
    return jsonify({"ok": True, "product": product_dict(row)})


@app.route("/api/products/<int:pid>", methods=["DELETE"])
def api_products_delete(pid):
    with get_db() as db:
        old = db.execute("SELECT * FROM products WHERE id = ?", (pid,)).fetchone()
        if not old:
            return jsonify({"ok": False, "error": "محصول یافت نشد"}), 404
        db.execute("DELETE FROM products WHERE id = ?", (pid,))
    if old["image"]:
        _remove_image(old["image"])
    return jsonify({"ok": True})


@app.route("/api/products/bulk-delete", methods=["POST"])
def api_products_bulk_delete():
    payload = request.get_json(force=True, silent=True) or {}
    ids = payload.get("ids") or []
    ids = [to_int(i) for i in ids if to_int(i)]
    if not ids:
        return jsonify({"ok": False, "error": "موردی انتخاب نشده است"}), 400
    marks = ",".join("?" for _ in ids)
    with get_db() as db:
        images = [r["image"] for r in db.execute(
            f"SELECT image FROM products WHERE id IN ({marks})", ids).fetchall() if r["image"]]
        db.execute(f"DELETE FROM products WHERE id IN ({marks})", ids)
    for img in images:
        _remove_image(img)
    return jsonify({"ok": True, "deleted": len(ids)})


# ---------------------------------------------------------------- sales API

@app.route("/api/sales")
def api_sales():
    q = to_en_digits(request.args.get("q", "").strip())
    sale_type = request.args.get("sale_type", "").strip()
    pay_method = request.args.get("pay_method", "").strip()
    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()
    sort = request.args.get("sort", "date").strip()
    direction = request.args.get("dir", "desc").strip().lower()

    sql = """SELECT s.*, p.name AS product_name, p.image AS product_image,
                    p.website_code, p.office_code, p.reference, p.brand, p.supplier,
                    p.purchase_price AS p_purchase_price
             FROM sales s LEFT JOIN products p ON p.id = s.product_id
             WHERE s.is_settled = 1"""
    params = []
    if q:
        like = f"%{q}%"
        sql += (" AND (p.name LIKE ? OR s.customer LIKE ? OR s.customer_phone LIKE ? "
                "OR p.office_code LIKE ? OR p.website_code LIKE ? OR p.reference LIKE ?)")
        params += [like] * 6
    if sale_method := request.args.get("sale_type", "").strip():
        if sale_method in SALE_TYPE_FA:
            sql += " AND s.sale_type = ?"
            params.append(sale_method)
    if pay_method:
        # فیلتر روش پرداخت بر اساس ریز پرداخت‌ها
        col = {"cash": "paid_cash", "pos": "paid_pos", "card2card": "paid_card2card"}.get(pay_method)
        if col:
            sql += f" AND s.{col} > 0"
    if date_from:
        parsed = parse_jalali_date(date_from)
        if parsed:
            sql += " AND s.sale_date >= ?"
            params.append(parsed)
    if date_to:
        parsed = parse_jalali_date(date_to)
        if parsed:
            sql += " AND s.sale_date <= ?"
            params.append(parsed)

    sort_map = {
        "date": "s.sale_date", "name": "p.name COLLATE NOCASE",
        "final_price": "s.final_price", "profit": "s.profit",
        "office_code": "p.office_code COLLATE NOCASE",
        "customer": "s.customer COLLATE NOCASE",
    }
    col = sort_map.get(sort, "s.sale_date")
    d = "DESC" if direction == "desc" else "ASC"
    sql += f" ORDER BY {col} {d}, s.id DESC LIMIT 500"
    with get_db() as db:
        rows = db.execute(sql, params).fetchall()
    items = [sale_dict(r) for r in rows]
    summary = {
        "count": len(items),
        "total_final": sum(x.get("final_price") or 0 for x in items),
        "total_profit": sum(x.get("profit") or 0 for x in items),
    }
    return jsonify({"items": items, "summary": summary})


@app.route("/api/sales", methods=["POST"])
def api_sales_create():
    """ثبت فروش. دو حالت: cash (کامل) و deposit (بیعانه).
    ریز پرداخت: paid_cash / paid_pos / paid_card2card (اختیاری).
    """
    payload = request.get_json(force=True, silent=True) or {}
    pid = to_int(payload.get("product_id"))
    if not pid:
        return jsonify({"ok": False, "error": "محصول انتخاب نشده است"}), 400

    payment_kind = "deposit" if clean(payload.get("payment_type")) == "deposit" else "cash"

    with get_db() as db:
        p = db.execute("SELECT * FROM products WHERE id = ?", (pid,)).fetchone()
        if not p:
            return jsonify({"ok": False, "error": "محصول یافت نشد"}), 404

        sale_price = to_float(payload.get("sale_price"), p["sale_price"])
        discount = to_float(payload.get("discount_price"), 0)
        final_price = discount if discount > 0 else sale_price
        if final_price > sale_price:
            return jsonify({"ok": False, "error":
                            "قیمت نهایی نمی‌تواند از قیمت فروش بیشتر باشد"}), 400

        paid_cash = max(0.0, to_float(payload.get("paid_cash")))
        paid_pos = max(0.0, to_float(payload.get("paid_pos")))
        paid_card2card = max(0.0, to_float(payload.get("paid_card2card")))
        paid_now = paid_cash + paid_pos + paid_card2card

        sale_date = clean(payload.get("sale_date"))
        if sale_date:
            parsed = parse_jalali_date(sale_date)
            if not parsed:
                return jsonify({"ok": False, "error": "تاریخ فروش معتبر نیست"}), 400
        else:
            parsed = today_iso()
        sale_type = clean(payload.get("sale_type")) or "person"
        if sale_type not in SALE_TYPE_FA:
            sale_type = "person"
        customer_phone = to_en_phone(clean(payload.get("customer_phone")))
        customer = clean(payload.get("customer"))

        if payment_kind == "deposit":
            if paid_now <= 0:
                return jsonify({"ok": False, "error":
                                "برای فروش بیعانه، دست‌کم مبلغ بیعانه را وارد کنید"}), 400
            if paid_now > final_price + 0.001:
                return jsonify({"ok": False, "error":
                                f"جمع پرداخت‌ها نمی‌تواند از قیمت نهایی بیشتر باشد ({fa_money(final_price)} تومان)"}), 400
            is_settled = 0
        else:
            if paid_now > final_price + 0.001:
                return jsonify({"ok": False, "error":
                                f"جمع پرداخت‌ها نمی‌تواند از قیمت نهایی بیشتر باشد ({fa_money(final_price)} تومان)"}), 400
            # فروش نقدی کامل است؛ اگر ریز پرداخت وارد نشده باشد، همه نقدی در نظر گرفته می‌شود
            if paid_now <= 0:
                paid_cash, paid_pos, paid_card2card = final_price, 0.0, 0.0
            payment_kind = "cash"
            is_settled = 1

        profit = final_price - (p["purchase_price"] or 0)

        cur = db.execute(
            "INSERT INTO sales(product_id, sale_price, purchase_price, profit, sale_date,"
            " customer, customer_phone, sale_type, payment_type, final_price,"
            " paid_cash, paid_pos, paid_card2card, is_settled, notes)"
            " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (pid, sale_price, p["purchase_price"], profit, parsed,
             customer, customer_phone, sale_type, payment_kind,
             final_price, paid_cash, paid_pos, paid_card2card, is_settled,
             clean(payload.get("notes"))),
        )
        sid = cur.lastrowid

        if payment_kind == "deposit":
            db.execute(
                "INSERT INTO payments(product_id, product_name, customer_name, customer_phone,"
                " total_amount, paid_amount, pay_date, notes, sale_id) VALUES(?,?,?,?,?,?,?,?,?)",
                (pid, p["name"], customer, customer_phone,
                 final_price, paid_now, parsed,
                 f"بیعانه فروش #{sid} — مانده: {fa_money(final_price - paid_now)} تومان",
                 sid),
            )

        # این ساعت فروخته شد — ناموجود می‌شود
        db.execute(
            "UPDATE products SET available = 0, updated_at = datetime('now', 'localtime') WHERE id = ?",
            (pid,),
        )

        row = db.execute(
            """SELECT s.*, p.name AS product_name, p.image AS product_image,
                      p.website_code, p.office_code, p.reference, p.brand, p.supplier
               FROM sales s LEFT JOIN products p ON p.id = s.product_id WHERE s.id = ?""",
            (sid,),
        ).fetchone()
    return jsonify({"ok": True, "sale": sale_dict(row)})


@app.route("/api/sales/<int:sid>", methods=["PUT"])
def api_sales_update(sid):
    """ویرایش فروش تسویه‌شده (قیمت، خریدار، روش‌ها، یادداشت)."""
    payload = request.get_json(force=True, silent=True) or {}
    with get_db() as db:
        s = db.execute("SELECT * FROM sales WHERE id = ?", (sid,)).fetchone()
        if not s:
            return jsonify({"ok": False, "error": "فروش یافت نشد"}), 404
        p = db.execute("SELECT * FROM products WHERE id = ?", (s["product_id"],)).fetchone()

        sale_price = to_float(payload.get("sale_price"), s["sale_price"])
        payment_kind = clean(payload.get("payment_type")) or s["payment_type"]
        if payment_kind not in ("cash", "deposit"):
            payment_kind = "cash"
        if payment_kind == "deposit":
            final_price = to_float(payload.get("discount_price"), s["final_price"] or sale_price)
        else:
            discount = to_float(payload.get("discount_price"), 0)
            final_price = discount if discount > 0 else sale_price
        if final_price > sale_price:
            return jsonify({"ok": False, "error":
                            "قیمت نهایی نمی‌تواند از قیمت فروش بیشتر باشد"}), 400

        paid_cash = max(0.0, to_float(payload.get("paid_cash"), s["paid_cash"]))
        paid_pos = max(0.0, to_float(payload.get("paid_pos"), s["paid_pos"]))
        paid_card2card = max(0.0, to_float(payload.get("paid_card2card"), s["paid_card2card"]))
        paid_now = paid_cash + paid_pos + paid_card2card
        if paid_now > final_price + 0.001:
            return jsonify({"ok": False, "error":
                            f"جمع پرداخت‌ها نمی‌تواند از قیمت نهایی بیشتر باشد ({fa_money(final_price)} تومان)"}), 400
        if paid_now <= 0 and payment_kind == "cash":
            paid_cash, paid_pos, paid_card2card = final_price, 0.0, 0.0

        purchase_price = to_float(payload.get("purchase_price"), p["purchase_price"] if p else 0)
        profit = final_price - purchase_price

        sale_date = clean(payload.get("sale_date")) or s["sale_date"]
        parsed = parse_jalali_date(sale_date)
        if not parsed:
            return jsonify({"ok": False, "error": "تاریخ فروش معتبر نیست"}), 400
        sale_type = clean(payload.get("sale_type")) or s["sale_type"]
        if sale_type not in SALE_TYPE_FA:
            sale_type = "person"

        db.execute(
            "UPDATE sales SET sale_price = ?, final_price = ?, profit = ?, sale_date = ?,"
            " customer = ?, customer_phone = ?, sale_type = ?, payment_type = ?,"
            " paid_cash = ?, paid_pos = ?, paid_card2card = ?, notes = ? WHERE id = ?",
            (sale_price, final_price, profit, parsed,
             clean(payload.get("customer")), to_en_phone(clean(payload.get("customer_phone"))),
             sale_type, payment_kind,
             paid_cash, paid_pos, paid_card2card,
             clean(payload.get("notes")), sid),
        )
        row = db.execute(
            """SELECT s.*, p.name AS product_name, p.image AS product_image,
                      p.website_code, p.office_code, p.reference, p.brand, p.supplier
               FROM sales s LEFT JOIN products p ON p.id = s.product_id WHERE s.id = ?""",
            (sid,),
        ).fetchone()
    return jsonify({"ok": True, "sale": sale_dict(row)})


@app.route("/api/sales/bulk-delete", methods=["POST"])
def api_sales_bulk_delete():
    payload = request.get_json(force=True, silent=True) or {}
    ids = [to_int(i) for i in (payload.get("ids") or []) if to_int(i)]
    if not ids:
        return jsonify({"ok": False, "error": "موردی انتخاب نشده است"}), 400
    marks = ",".join("?" for _ in ids)
    with get_db() as db:
        # ساعت‌های این فروش‌ها دوباره موجود می‌شوند
        db.execute(
            f"UPDATE products SET available = 1, updated_at = datetime('now', 'localtime')"
            f" WHERE id IN (SELECT product_id FROM sales WHERE id IN ({marks}))", ids)
        db.execute(f"DELETE FROM sales WHERE id IN ({marks})", ids)
        db.execute(f"DELETE FROM payments WHERE sale_id IN ({marks}) AND paid_amount < total_amount", ids)
    return jsonify({"ok": True, "deleted": len(ids)})


@app.route("/api/sales/<int:sid>", methods=["DELETE"])
def api_sales_delete(sid):
    """حذف فروش — ساعت دوباره موجود می‌شود."""
    with get_db() as db:
        s = db.execute("SELECT * FROM sales WHERE id = ?", (sid,)).fetchone()
        if not s:
            return jsonify({"ok": False, "error": "فروش یافت نشد"}), 404
        db.execute("DELETE FROM sales WHERE id = ?", (sid,))
        db.execute("DELETE FROM payments WHERE sale_id = ?", (sid,))
        if s["product_id"]:
            db.execute(
                "UPDATE products SET available = 1, updated_at = datetime('now', 'localtime')"
                " WHERE id = ?",
                (s["product_id"],),
            )
    return jsonify({"ok": True})


# ---------------------------------------------------------------- repairs API

def _repair_values(payload):
    watch_name = clean(payload.get("watch_name"))
    if not watch_name:
        return None, "نام ساعت الزامی است"
    customer_phone = clean(payload.get("customer_phone"))
    if customer_phone and not customer_phone.replace("+", "").replace(" ", "").isdigit():
        return None, "شماره تماس معتبر نیست"
    delivery_date = clean(payload.get("delivery_date"))
    if delivery_date:
        parsed = parse_jalali_date(delivery_date)
        if not parsed:
            return None, "تاریخ تحویل معتبر نیست"
        delivery_date = parsed
    else:
        delivery_date = today_iso()
    return_date = clean(payload.get("return_date"))
    if return_date:
        parsed = parse_jalali_date(return_date)
        if not parsed:
            return None, "تاریخ بازگشت معتبر نیست"
        return_date = parsed
    else:
        return_date = ""
    status = clean(payload.get("status")) or "received"
    if status not in STATUS_FA:
        status = "received"
    return {
        "watch_name": watch_name,
        "watch_code": clean(payload.get("watch_code")),
        "issue": clean(payload.get("issue")),
        "delivery_date": delivery_date,
        "return_date": return_date,
        "customer_name": clean(payload.get("customer_name")),
        "customer_phone": customer_phone,
        "is_warranty": 1 if payload.get("is_warranty") else 0,
        "status": status,
        "repair_price": max(0.0, to_float(payload.get("repair_price"))),
        "image": clean(payload.get("image")),
        "notes": clean(payload.get("notes")),
    }, None


@app.route("/api/repairs")
def api_repairs():
    status = request.args.get("status", "").strip()
    q = request.args.get("q", "").strip()
    sql = "SELECT * FROM repairs WHERE 1=1"
    params = []
    if status:
        sql += " AND status = ?"
        params.append(status)
    if q:
        like = f"%{q}%"
        sql += " AND (watch_name LIKE ? OR watch_code LIKE ? OR customer_name LIKE ? OR customer_phone LIKE ?)"
        params += [like] * 4
    sql += " ORDER BY id DESC"
    with get_db() as db:
        rows = db.execute(sql, params).fetchall()
    return jsonify([repair_dict(r) for r in rows])


@app.route("/api/repairs", methods=["POST"])
def api_repairs_create():
    payload = request.get_json(force=True, silent=True) or {}
    values, err = _repair_values(payload)
    if err:
        return jsonify({"ok": False, "error": err}), 400
    with get_db() as db:
        cols = ", ".join(values.keys())
        marks = ", ".join("?" for _ in values)
        cur = db.execute(f"INSERT INTO repairs({cols}) VALUES({marks})", tuple(values.values()))
        rid = cur.lastrowid
        row = db.execute("SELECT * FROM repairs WHERE id = ?", (rid,)).fetchone()
    return jsonify({"ok": True, "repair": repair_dict(row)})


@app.route("/api/repairs/<int:rid>", methods=["PUT"])
def api_repairs_update(rid):
    payload = request.get_json(force=True, silent=True) or {}
    values, err = _repair_values(payload)
    if err:
        return jsonify({"ok": False, "error": err}), 400
    with get_db() as db:
        old = db.execute("SELECT * FROM repairs WHERE id = ?", (rid,)).fetchone()
        if not old:
            return jsonify({"ok": False, "error": "ساعت تعمیری یافت نشد"}), 404
        sets = ", ".join(f"{k} = ?" for k in values)
        db.execute(
            f"UPDATE repairs SET {sets}, updated_at = datetime('now', 'localtime') WHERE id = ?",
            (*values.values(), rid),
        )
        if old["image"] and old["image"] != values["image"]:
            _remove_image(old["image"])
        row = db.execute("SELECT * FROM repairs WHERE id = ?", (rid,)).fetchone()
    return jsonify({"ok": True, "repair": repair_dict(row)})


@app.route("/api/repairs/<int:rid>", methods=["DELETE"])
def api_repairs_delete(rid):
    with get_db() as db:
        old = db.execute("SELECT * FROM repairs WHERE id = ?", (rid,)).fetchone()
        if not old:
            return jsonify({"ok": False, "error": "یافت نشد"}), 404
        db.execute("DELETE FROM repairs WHERE id = ?", (rid,))
    if old["image"]:
        _remove_image(old["image"])
    return jsonify({"ok": True})


@app.route("/api/repairs/bulk-delete", methods=["POST"])
def api_repairs_bulk_delete():
    payload = request.get_json(force=True, silent=True) or {}
    ids = [to_int(i) for i in (payload.get("ids") or []) if to_int(i)]
    if not ids:
        return jsonify({"ok": False, "error": "موردی انتخاب نشده است"}), 400
    marks = ",".join("?" for _ in ids)
    with get_db() as db:
        images = [r["image"] for r in db.execute(
            f"SELECT image FROM repairs WHERE id IN ({marks})", ids).fetchall() if r["image"]]
        db.execute(f"DELETE FROM repairs WHERE id IN ({marks})", ids)
    for img in images:
        _remove_image(img)
    return jsonify({"ok": True, "deleted": len(ids)})


@app.route("/api/repairs/<int:rid>/status", methods=["POST"])
def api_repairs_status(rid):
    payload = request.get_json(force=True, silent=True) or {}
    status = clean(payload.get("status"))
    if status not in STATUS_FA:
        return jsonify({"ok": False, "error": "وضعیت نامعتبر است"}), 400
    return_date = clean(payload.get("return_date"))
    parsed = ""
    if return_date:
        parsed = parse_jalali_date(return_date)
        if not parsed:
            return jsonify({"ok": False, "error": "تاریخ بازگشت معتبر نیست"}), 400
    with get_db() as db:
        if status == "delivered" and not parsed:
            parsed = today_iso()
        if parsed:
            db.execute(
                "UPDATE repairs SET status = ?, return_date = ?, "
                "updated_at = datetime('now', 'localtime') WHERE id = ?",
                (status, parsed, rid),
            )
        else:
            db.execute(
                "UPDATE repairs SET status = ?, updated_at = datetime('now', 'localtime') WHERE id = ?",
                (status, rid),
            )
        row = db.execute("SELECT * FROM repairs WHERE id = ?", (rid,)).fetchone()
    if not row:
        return jsonify({"ok": False, "error": "یافت نشد"}), 404
    return jsonify({"ok": True, "repair": repair_dict(row)})


# ---------------------------------------------------------------- tracking API

def _tracking_values(payload):
    item_name = clean(payload.get("item_name"))
    if not item_name:
        return None, "نام ساعت یا قطعه الزامی است"
    status = clean(payload.get("status")) or "new"
    if status not in TRACKING_STATUS_FA:
        status = "new"
    return {
        "item_name": item_name,
        "item_code": clean(payload.get("item_code")),
        "customer_name": clean(payload.get("customer_name")),
        "customer_phone": clean(payload.get("customer_phone")),
        "price": max(0.0, to_float(payload.get("price"))),
        "status": status,
        "notes": clean(payload.get("notes")),
        "image": clean(payload.get("image")),
    }, None


@app.route("/api/tracking")
def api_tracking():
    status = request.args.get("status", "").strip()
    q = request.args.get("q", "").strip()
    sql = "SELECT * FROM tracking WHERE 1=1"
    params = []
    if status:
        sql += " AND status = ?"
        params.append(status)
    if q:
        like = f"%{q}%"
        sql += " AND (item_name LIKE ? OR item_code LIKE ? OR customer_name LIKE ? OR customer_phone LIKE ?)"
        params += [like] * 4
    sql += " ORDER BY id DESC"
    with get_db() as db:
        rows = db.execute(sql, params).fetchall()
    return jsonify([tracking_dict(r) for r in rows])


@app.route("/api/tracking", methods=["POST"])
def api_tracking_create():
    payload = request.get_json(force=True, silent=True) or {}
    values, err = _tracking_values(payload)
    if err:
        return jsonify({"ok": False, "error": err}), 400
    with get_db() as db:
        cols = ", ".join(values.keys())
        marks = ", ".join("?" for _ in values)
        cur = db.execute(f"INSERT INTO tracking({cols}) VALUES({marks})", tuple(values.values()))
        tid = cur.lastrowid
        row = db.execute("SELECT * FROM tracking WHERE id = ?", (tid,)).fetchone()
    return jsonify({"ok": True, "tracking": tracking_dict(row)})


@app.route("/api/tracking/<int:tid>", methods=["PUT"])
def api_tracking_update(tid):
    payload = request.get_json(force=True, silent=True) or {}
    values, err = _tracking_values(payload)
    if err:
        return jsonify({"ok": False, "error": err}), 400
    with get_db() as db:
        old = db.execute("SELECT * FROM tracking WHERE id = ?", (tid,)).fetchone()
        if not old:
            return jsonify({"ok": False, "error": "یافت نشد"}), 404
        sets = ", ".join(f"{k} = ?" for k in values)
        db.execute(
            f"UPDATE tracking SET {sets}, updated_at = datetime('now', 'localtime') WHERE id = ?",
            (*values.values(), tid),
        )
        if old["image"] and old["image"] != values["image"]:
            _remove_image(old["image"])
        row = db.execute("SELECT * FROM tracking WHERE id = ?", (tid,)).fetchone()
    return jsonify({"ok": True, "tracking": tracking_dict(row)})


@app.route("/api/tracking/<int:tid>", methods=["DELETE"])
def api_tracking_delete(tid):
    with get_db() as db:
        old = db.execute("SELECT * FROM tracking WHERE id = ?", (tid,)).fetchone()
        if not old:
            return jsonify({"ok": False, "error": "یافت نشد"}), 404
        db.execute("DELETE FROM tracking WHERE id = ?", (tid,))
    if old["image"]:
        _remove_image(old["image"])
    return jsonify({"ok": True})


@app.route("/api/tracking/bulk-delete", methods=["POST"])
def api_tracking_bulk_delete():
    payload = request.get_json(force=True, silent=True) or {}
    ids = [to_int(i) for i in (payload.get("ids") or []) if to_int(i)]
    if not ids:
        return jsonify({"ok": False, "error": "موردی انتخاب نشده است"}), 400
    marks = ",".join("?" for _ in ids)
    with get_db() as db:
        images = [r["image"] for r in db.execute(
            f"SELECT image FROM tracking WHERE id IN ({marks})", ids).fetchall() if r["image"]]
        db.execute(f"DELETE FROM tracking WHERE id IN ({marks})", ids)
    for img in images:
        _remove_image(img)
    return jsonify({"ok": True, "deleted": len(ids)})


# ---------------------------------------------------------------- payments API

@app.route("/api/payments")
def api_payments():
    status = request.args.get("status", "").strip()  # all | unpaid | paid
    q = request.args.get("q", "").strip()
    sql = "SELECT * FROM payments WHERE 1=1"
    params = []
    if status == "unpaid":
        sql += " AND total_amount - paid_amount > 0.001"
    elif status == "paid":
        sql += " AND total_amount - paid_amount <= 0.001"
    if q:
        like = f"%{q}%"
        sql += " AND (product_name LIKE ? OR customer_name LIKE ? OR customer_phone LIKE ?)"
        params += [like] * 3
    sql += " ORDER BY id DESC"
    with get_db() as db:
        rows = db.execute(sql, params).fetchall()
    items = [payment_dict(r) for r in rows]
    summary = {
        "count": len(items),
        "total": sum(i["total_amount"] for i in items),
        "paid": sum(i["paid_amount"] for i in items),
        "remaining": sum(i["remaining"] for i in items),
    }
    return jsonify({"items": items, "summary": summary})


@app.route("/api/payments", methods=["POST"])
def api_payments_create():
    payload = request.get_json(force=True, silent=True) or {}
    pid = to_int(payload.get("product_id")) or None
    product_name = clean(payload.get("product_name"))
    if pid:
        with get_db() as db:
            p = db.execute("SELECT name FROM products WHERE id = ?", (pid,)).fetchone()
        if not p:
            return jsonify({"ok": False, "error": "محصول انتخاب‌شده یافت نشد"}), 400
        product_name = p["name"]
    if not product_name:
        return jsonify({"ok": False, "error": "نام محصول را وارد یا از انبار انتخاب کنید"}), 400
    total = max(0.0, to_float(payload.get("total_amount")))
    paid = max(0.0, to_float(payload.get("paid_amount")))
    if total <= 0:
        return jsonify({"ok": False, "error": "مبلغ کل باید بیشتر از صفر باشد"}), 400
    if paid > total:
        return jsonify({"ok": False, "error": "مبلغ پرداخت‌شده نمی‌تواند از مبلغ کل بیشتر باشد"}), 400
    pay_date = clean(payload.get("pay_date"))
    if pay_date:
        parsed = parse_jalali_date(pay_date)
        if not parsed:
            return jsonify({"ok": False, "error": "تاریخ معتبر نیست"}), 400
        pay_date = parsed
    else:
        pay_date = today_iso()
    with get_db() as db:
        cur = db.execute(
            "INSERT INTO payments(product_id, product_name, customer_name, customer_phone,"
            " total_amount, paid_amount, pay_date, notes) VALUES(?,?,?,?,?,?,?,?)",
            (pid, product_name, clean(payload.get("customer_name")),
             clean(payload.get("customer_phone")), total, paid, pay_date,
             clean(payload.get("notes"))),
        )
        row = db.execute("SELECT * FROM payments WHERE id = ?", (cur.lastrowid,)).fetchone()
    return jsonify({"ok": True, "payment": payment_dict(row)})


@app.route("/api/payments/<int:payid>", methods=["PUT"])
def api_payments_update(payid):
    payload = request.get_json(force=True, silent=True) or {}
    with get_db() as db:
        old = db.execute("SELECT * FROM payments WHERE id = ?", (payid,)).fetchone()
        if not old:
            return jsonify({"ok": False, "error": "یافت نشد"}), 404
    total = max(0.0, to_float(payload.get("total_amount"), old["total_amount"]))
    paid = max(0.0, to_float(payload.get("paid_amount"), old["paid_amount"]))
    if total <= 0:
        return jsonify({"ok": False, "error": "مبلغ کل باید بیشتر از صفر باشد"}), 400
    if paid > total:
        return jsonify({"ok": False, "error": "مبلغ پرداخت‌شده نمی‌تواند از مبلغ کل بیشتر باشد"}), 400
    pay_date = clean(payload.get("pay_date")) or old["pay_date"]
    if pay_date:
        parsed = parse_jalali_date(pay_date)
        if not parsed:
            return jsonify({"ok": False, "error": "تاریخ معتبر نیست"}), 400
        pay_date = parsed
    with get_db() as db:
        db.execute(
            "UPDATE payments SET product_name = ?, customer_name = ?, customer_phone = ?,"
            " total_amount = ?, paid_amount = ?, pay_date = ?, notes = ?,"
            " updated_at = datetime('now', 'localtime') WHERE id = ?",
            (clean(payload.get("product_name")) or old["product_name"],
             clean(payload.get("customer_name")), clean(payload.get("customer_phone")),
             total, paid, pay_date, clean(payload.get("notes")), payid),
        )
        row = db.execute("SELECT * FROM payments WHERE id = ?", (payid,)).fetchone()
    return jsonify({"ok": True, "payment": payment_dict(row)})


@app.route("/api/payments/<int:payid>/add", methods=["POST"])
def api_payments_add(payid):
    """افزودن پرداخت جدید به فقره‌ی موجود."""
    payload = request.get_json(force=True, silent=True) or {}
    amount = to_float(payload.get("amount"))
    if amount <= 0:
        return jsonify({"ok": False, "error": "مبلغ باید بیشتر از صفر باشد"}), 400
    with get_db() as db:
        p = db.execute("SELECT * FROM payments WHERE id = ?", (payid,)).fetchone()
        if not p:
            return jsonify({"ok": False, "error": "یافت نشد"}), 404
        remaining = p["total_amount"] - p["paid_amount"]
        if amount > remaining + 0.001:
            return jsonify({"ok": False, "error":
                            f"بیشتر از مانده‌ی فقره است (مانده: {fa_money(remaining)} تومان)"}), 400
        db.execute(
            "UPDATE payments SET paid_amount = paid_amount + ?,"
            " updated_at = datetime('now', 'localtime') WHERE id = ?",
            (amount, payid),
        )
        # تسویه‌ی کامل شد؟ فروش بیعانه‌ی متصل را تسویه‌شده کن
        row = db.execute("SELECT * FROM payments WHERE id = ?", (payid,)).fetchone()
        if row["sale_id"] and row["total_amount"] - row["paid_amount"] <= 0.001:
            db.execute("UPDATE sales SET is_settled = 1 WHERE id = ?", (p["sale_id"],))
    return jsonify({"ok": True, "payment": payment_dict(row)})


@app.route("/api/payments/<int:payid>/settle-full", methods=["POST"])
def api_payments_settle_full(payid):
    """تسویه‌ی کامل فقره بدون ورود مبلغ — کل مانده یکجا پرداخت می‌شود."""
    with get_db() as db:
        p = db.execute("SELECT * FROM payments WHERE id = ?", (payid,)).fetchone()
        if not p:
            return jsonify({"ok": False, "error": "یافت نشد"}), 404
        remaining = p["total_amount"] - p["paid_amount"]
        if remaining <= 0.001:
            return jsonify({"ok": False, "error": "این فقره قبلاً تسویه شده است"}), 400
        db.execute(
            "UPDATE payments SET paid_amount = ?,"
            " updated_at = datetime('now', 'localtime') WHERE id = ?",
            (p["total_amount"], payid),
        )
        if p["sale_id"]:
            # مانده به‌عنوان پرداخت نقدی به فروش اضافه می‌شود
            db.execute(
                "UPDATE sales SET is_settled = 1, paid_cash = paid_cash + ? WHERE id = ?",
                (remaining, p["sale_id"]),
            )
    return jsonify({"ok": True})


@app.route("/api/payments/<int:payid>", methods=["DELETE"])
def api_payments_delete(payid):
    with get_db() as db:
        old = db.execute("SELECT * FROM payments WHERE id = ?", (payid,)).fetchone()
        if not old:
            return jsonify({"ok": False, "error": "یافت نشد"}), 404
        db.execute("DELETE FROM payments WHERE id = ?", (payid,))
    return jsonify({"ok": True})


@app.route("/api/payments/bulk-delete", methods=["POST"])
def api_payments_bulk_delete():
    payload = request.get_json(force=True, silent=True) or {}
    ids = [to_int(i) for i in (payload.get("ids") or []) if to_int(i)]
    if not ids:
        return jsonify({"ok": False, "error": "موردی انتخاب نشده است"}), 400
    marks = ",".join("?" for _ in ids)
    with get_db() as db:
        db.execute(f"DELETE FROM payments WHERE id IN ({','.join('?' * len(ids))})", ids)
    return jsonify({"ok": True, "deleted": len(ids)})


# ---------------------------------------------------------------- calendar API

@app.route("/api/calendar")
def api_calendar():
    """رویدادهای یک ماه شمسی. پارامترها: jy, jm"""
    jy = to_int(request.args.get("jy"), 0)
    jm = to_int(request.args.get("jm"), 0)
    if not jy or not jm or jm < 1 or jm > 12:
        jy, jm, _ = today_jalali()
    gy1, gm1, gd1 = jalali_to_gregorian(jy, jm, 1)
    last = jalali_month_length(jy, jm)
    gy2, gm2, gd2 = jalali_to_gregorian(jy, jm, last)
    start = datetime.date(gy1, gm1, gd1).isoformat()
    end = datetime.date(gy2, gm2, gd2).isoformat()

    days = {}
    with get_db() as db:
        purchases = db.execute(
            "SELECT id, name, image, office_code, website_code, purchase_price, purchase_date "
            "FROM products WHERE purchase_date >= ? AND purchase_date <= ? ORDER BY purchase_date",
            (start, end),
        ).fetchall()
        for p in purchases:
            d = days.setdefault(p["purchase_date"], {"purchases": [], "sales": [], "repairs_in": [], "repairs_out": []})
            d["purchases"].append({
                "type": "purchase", "id": p["id"], "name": p["name"], "image": p["image"],
                "office_code": p["office_code"],
                "website_code": p["website_code"],
                "price_display": fa_money(p["purchase_price"]),
            })
        sales = db.execute(
            """SELECT s.id, s.sale_date, s.sale_price, s.final_price, s.profit, s.customer,
                      s.customer_phone, s.sale_type, p.name, p.image
               FROM sales s LEFT JOIN products p ON p.id = s.product_id
               WHERE s.sale_date >= ? AND s.sale_date <= ? ORDER BY s.sale_date""",
            (start, end),
        ).fetchall()
        for s in sales:
            d = days.setdefault(s["sale_date"], {"purchases": [], "sales": [], "repairs_in": [], "repairs_out": []})
            d["sales"].append({
                "type": "sale", "id": s["id"], "name": s["name"] or "محصول حذف‌شده", "image": s["image"],
                "customer": s["customer"],
                "customer_phone": s["customer_phone"] or "",
                "customer_phone_fa": fa_num(s["customer_phone"] or ""),
                "sale_type_fa": SALE_TYPE_FA.get(s["sale_type"], "حضوری"),
                "price_display": fa_money(s["final_price"] or s["sale_price"]),
                "profit_display": fa_money(s["profit"]),
            })
        # تعمیرات: تاریخ تحویل به فروشگاه و تاریخ بازگشت به مشتری
        for col, key in (("delivery_date", "repairs_in"), ("return_date", "repairs_out")):
            repairs = db.execute(
                f"""SELECT id, watch_name, watch_code, customer_name, {col} AS d, repair_price, image
                    FROM repairs WHERE {col} != '' AND {col} >= ? AND {col} <= ? ORDER BY {col}""",
                (start, end),
            ).fetchall()
            for r in repairs:
                d = days.setdefault(r["d"], {"purchases": [], "sales": [], "repairs_in": [], "repairs_out": []})
                d[key].append({
                    "type": key, "id": r["id"], "name": r["watch_name"], "image": r["image"],
                    "customer": r["customer_name"], "code": r["watch_code"],
                    "price_display": fa_money(r["repair_price"]),
                })

    first_weekday = datetime.date(gy1, gm1, gd1).weekday()
    weekday_index = (first_weekday + 2) % 7  # شنبه = اول هفته

    cells = []
    for _ in range(weekday_index):
        cells.append(None)
    for day in range(1, last + 1):
        gy, gm, gd = jalali_to_gregorian(jy, jm, day)
        iso = datetime.date(gy, gm, gd).isoformat()
        info = days.get(iso)
        cells.append({
            "day": day,
            "iso": iso,
            "is_today": iso == today_iso(),
            "purchases": info["purchases"] if info else [],
            "sales": info["sales"] if info else [],
            "repairs_in": info["repairs_in"] if info else [],
            "repairs_out": info["repairs_out"] if info else [],
        })
    while len(cells) % 7 != 0:
        cells.append(None)

    return jsonify({
        "jy": jy, "jm": jm,
        "month_name": MONTH_NAMES[jm - 1],
        "cells": cells,
    })


@app.route("/api/calendar/day")
def api_calendar_day():
    """جزئیات یک روز. پارامتر: date (ISO میلادی)"""
    iso = clean(request.args.get("date"))
    if not iso:
        return jsonify({"ok": False, "error": "تاریخ مشخص نشده"}), 400
    with get_db() as db:
        purchases = db.execute(
            "SELECT * FROM products WHERE purchase_date = ? ORDER BY id", (iso,)
        ).fetchall()
        sales = db.execute(
            """SELECT s.*, p.name AS product_name, p.image AS product_image
               FROM sales s LEFT JOIN products p ON p.id = s.product_id
               WHERE s.sale_date = ? ORDER BY s.id""",
            (iso,),
        ).fetchall()
        repairs_in = db.execute(
            "SELECT * FROM repairs WHERE delivery_date = ? ORDER BY id", (iso,)
        ).fetchall()
        repairs_out = db.execute(
            "SELECT * FROM repairs WHERE return_date = ? ORDER BY id", (iso,)
        ).fetchall()
    return jsonify({
        "date_iso": iso,
        "date_fa": fa_date(iso, with_weekday=True),
        "purchases": [product_dict(p) for p in purchases],
        "sales": [sale_dict(s) for s in sales],
        "repairs_in": [repair_dict(r) for r in repairs_in],
        "repairs_out": [repair_dict(r) for r in repairs_out],
    })


# ---------------------------------------------------------------- export / import

EXPORT_DIR = os.path.join(DATA_DIR, "exports")

EXPORT_KINDS = {
    "products": export_products,
    "repairs": export_repairs,
    "tracking": export_tracking,
    "payments": export_payments,
    "sales": export_sales,
}


def _export_file(kind, fmt):
    os.makedirs(EXPORT_DIR, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y-%m-%d_%H%M")
    name = f"{kind}_{stamp}.{fmt}"
    path = os.path.join(EXPORT_DIR, name)
    EXPORT_KINDS[kind](path, fmt)
    return path, name


@app.route("/export/<kind>.<fmt>")
def export_route(kind, fmt):
    if fmt not in ("xlsx", "csv") or kind not in EXPORT_KINDS:
        abort(404)
    path, name = _export_file(kind, fmt)
    mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" if fmt == "xlsx" else "text/csv"
    return send_file(path, as_attachment=True, download_name=name, mimetype=mime)


@app.route("/api/import/products", methods=["POST"])
def api_import_products():
    f = request.files.get("file")
    if not f or not f.filename:
        return jsonify({"ok": False, "error": "فایلی انتخاب نشده است"}), 400
    ext = os.path.splitext(f.filename)[1].lower()
    if ext not in (".csv", ".xlsx", ".xlsm"):
        return jsonify({"ok": False, "error": "فقط فایل csv یا xlsx پذیرفته می‌شود"}), 400
    os.makedirs(EXPORT_DIR, exist_ok=True)
    tmp_path = os.path.join(EXPORT_DIR, "import_tmp" + ext)
    f.save(tmp_path)
    update_existing = request.form.get("update_existing") == "1"
    try:
        ok, stats, errors = import_products(tmp_path, update_existing=update_existing)
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass
    if not ok:
        return jsonify({"ok": False, "error": errors}), 400
    return jsonify({"ok": True, "stats": stats, "errors": errors[:30]})


@app.route("/api/import/template")
def api_import_template():
    path, name = _export_file("products", "xlsx")
    return send_file(
        path, as_attachment=True, download_name="قالب_ورود_اطلاعات.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


# ---------------------------------------------------------------- backup API

@app.route("/api/backups")
def api_backups():
    return jsonify({"backups": list_backups()})


@app.route("/api/backups/create", methods=["POST"])
def api_backup_create():
    target = backup_db()
    return jsonify({"ok": True, "name": os.path.basename(target)})


@app.route("/api/backups/upload", methods=["POST"])
def api_backup_upload():
    """آپلود فایل بکاپ از بیرون (برای انتقال به سرور یا بازیابی از فلش)."""
    f = request.files.get("file")
    if not f or not f.filename:
        return jsonify({"ok": False, "error": "فایلی انتخاب نشده است"}), 400
    fname = os.path.basename(f.filename)
    if not fname.endswith(".db"):
        fname += ".db"
    os.makedirs(BACKUP_DIR, exist_ok=True)
    target = os.path.join(BACKUP_DIR, fname)
    f.save(target)
    # اعتبارسنجی: فایل باید یک SQLite معتبر با جدول products باشد
    import sqlite3
    try:
        conn = sqlite3.connect(target)
        conn.execute("SELECT COUNT(*) FROM products")
        conn.close()
    except sqlite3.Error:
        os.remove(target)
        return jsonify({"ok": False, "error": "فایل انتخاب‌شده یک نسخه‌ی پشتیبان معتبر TikoTime نیست"}), 400
    return jsonify({"ok": True, "name": fname})


@app.route("/api/backups/download/<path:fname>")
def api_backup_download(fname):
    safe = os.path.basename(fname)
    p = os.path.join(BACKUP_DIR, safe)
    if not os.path.isfile(p):
        abort(404)
    return send_file(p, as_attachment=True, download_name=safe)


@app.route("/api/backups/restore", methods=["POST"])
def api_backup_restore():
    payload = request.get_json(force=True, silent=True) or {}
    ok, err = restore_db(payload.get("name"))
    if not ok:
        return jsonify({"ok": False, "error": err}), 400
    return jsonify({"ok": True})


@app.route("/api/backups/delete", methods=["POST"])
def api_backup_delete():
    payload = request.get_json(force=True, silent=True) or {}
    ok, err = delete_backup(payload.get("name"))
    if not ok:
        return jsonify({"ok": False, "error": err}), 400
    return jsonify({"ok": True})


# ---------------------------------------------------------------- settings API

@app.route("/api/settings")
def api_settings():
    return jsonify({
        "store_name": get_setting("store_name", ""),
        "store_phone": get_setting("store_phone", ""),
        "store_address": get_setting("store_address", ""),
        "currency": get_setting("currency", "تومان"),
        "site_icon": get_setting("site_icon", ""),
    })


@app.route("/api/settings", methods=["POST"])
def api_settings_save():
    payload = request.get_json(force=True, silent=True) or {}
    for key in ("store_name", "store_phone", "store_address", "currency"):
        if key in payload:
            set_setting(key, clean(payload.get(key)))
    return jsonify({"ok": True})


@app.route("/api/settings/site-icon", methods=["POST"])
def api_settings_site_icon():
    payload = request.get_json(force=True, silent=True) or {}
    icon = clean(payload.get("icon"))
    old = get_setting("site_icon", "")
    if icon and icon != old:
        _remove_image(old)
    set_setting("site_icon", icon)
    return jsonify({"ok": True, "icon": icon})


# ---------------------------------------------------------------- error handlers

@app.errorhandler(404)
def not_found(e):
    if request.path.startswith("/api/") or request.path.startswith("/export/"):
        return jsonify({"ok": False, "error": "یافت نشد"}), 404
    return redirect(url_for("dashboard"))


@app.errorhandler(413)
def too_large(e):
    return jsonify({"ok": False, "error": "حجم فایل بیش از حد مجاز است (حداکثر ۳۲ مگابایت)"}), 413


if __name__ == "__main__":
    init_db()
    from waitress import serve
    port = int(os.environ.get("PORT", "5000"))
    print("\n  ⌚ TikoTime — سیستم مدیریت انبار فروشگاه ساعت")
    print(f"  آدرس: http://127.0.0.1:{port}\n")
    serve(app, host="127.0.0.1", port=port, threads=8)
