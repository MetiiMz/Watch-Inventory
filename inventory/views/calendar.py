# -*- coding: utf-8 -*-
"""API تقویم شمسی — پورت از app.py قدیمی."""
import datetime

from inventory.jalali import (
    MONTH_NAMES, jalali_month_length, jalali_to_gregorian, today_jalali,
)
from inventory.models import Product, Repair, Sale
from inventory.utils import clean, fa_date, fa_money, fa_num, product_dict, repair_dict, sale_dict, to_int

from .common import fail, ok


def _empty_day():
    return {"purchases": [], "sales": [], "repairs_in": [], "repairs_out": []}


def api_calendar(request):
    """رویدادهای یک ماه شمسی. پارامترها: jy, jm"""
    jy = to_int(request.GET.get("jy"), 0)
    jm = to_int(request.GET.get("jm"), 0)
    if not jy or not jm or jm < 1 or jm > 12:
        jy, jm, _ = today_jalali()
    gy1, gm1, gd1 = jalali_to_gregorian(jy, jm, 1)
    last = jalali_month_length(jy, jm)
    gy2, gm2, gd2 = jalali_to_gregorian(jy, jm, last)
    start = datetime.date(gy1, gm1, gd1).isoformat()
    end = datetime.date(gy2, gm2, gd2).isoformat()

    days = {}
    purchases = Product.objects.filter(
        purchase_date__gte=start, purchase_date__lte=end).order_by("purchase_date")
    for p in purchases:
        d = days.setdefault(p.purchase_date, _empty_day())
        d["purchases"].append({
            "type": "purchase", "id": p.id, "name": p.name, "image": p.image,
            "office_code": p.office_code,
            "website_code": p.website_code,
            "price_display": fa_money(p.purchase_price),
        })
    sales = Sale.objects.select_related("product").filter(
        sale_date__gte=start, sale_date__lte=end).order_by("sale_date")
    for s in sales:
        d = days.setdefault(s.sale_date, _empty_day())
        d["sales"].append({
            "type": "sale", "id": s.id,
            "name": s.product.name if s.product else "محصول حذف‌شده",
            "image": s.product.image if s.product else "",
            "customer": s.customer,
            "customer_phone": s.customer_phone or "",
            "customer_phone_fa": fa_num(s.customer_phone or ""),
            "price_display": fa_money(s.final_price or s.sale_price),
        })
    repairs_in = Repair.objects.filter(
        delivery_date__gte=start, delivery_date__lte=end).order_by("delivery_date")
    for r in repairs_in:
        d = days.setdefault(r.delivery_date, _empty_day())
        d["repairs_in"].append(_repair_cell(r, "repairs_in"))
    repairs_out = Repair.objects.filter(
        return_date__gte=start, return_date__lte=end).order_by("return_date")
    for r in repairs_out:
        d = days.setdefault(r.return_date, _empty_day())
        d["repairs_out"].append(_repair_cell(r, "repairs_out"))

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
            "is_today": iso == datetime.date.today().isoformat(),
            "purchases": info["purchases"] if info else [],
            "sales": info["sales"] if info else [],
            "repairs_in": info["repairs_in"] if info else [],
            "repairs_out": info["repairs_out"] if info else [],
        })
    while len(cells) % 7 != 0:
        cells.append(None)

    return ok(jy=jy, jm=jm, month_name=MONTH_NAMES[jm - 1], cells=cells)


def _repair_cell(r, key):
    return {
        "type": key, "id": r.id, "name": r.watch_name, "image": r.image,
        "customer": r.customer_name, "code": r.watch_code,
        "price_display": fa_money(r.repair_price),
    }


def api_calendar_day(request):
    """جزئیات یک روز. پارامتر: date (ISO میلادی)"""
    iso = clean(request.GET.get("date"))
    if not iso:
        return fail("تاریخ مشخص نشده")
    purchases = Product.objects.filter(purchase_date=iso).order_by("id")
    sales = Sale.objects.select_related("product").filter(sale_date=iso).order_by("id")
    repairs_in = Repair.objects.filter(delivery_date=iso).order_by("id")
    repairs_out = Repair.objects.filter(return_date=iso).order_by("id")
    return ok(
        date_iso=iso,
        date_fa=fa_date(iso, with_weekday=True),
        purchases=[product_dict(p) for p in purchases],
        sales=[
            {**sale_dict(s),
             "name": s.product.name if s.product else "محصول حذف‌شده",
             "image": s.product.image if s.product else ""}
            for s in sales
        ],
        repairs_in=[repair_dict(r) for r in repairs_in],
        repairs_out=[repair_dict(r) for r in repairs_out],
    )