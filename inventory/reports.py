# -*- coding: utf-8 -*-
"""گزارش‌های نمایه (Dashboard) — پورت ORM از نسخه‌ی Flask."""
import datetime

from django.db.models import (
    Count, F, Q, Sum, Value, FloatField,
)
from django.db.models.functions import Coalesce

from inventory.jalali import MONTH_NAMES, gregorian_to_jalali, jalali_month_length, jalali_to_gregorian
from inventory.models import Payment, Product, Repair, Sale, Tracking


def get_dashboard_stats():
    prod = Product.objects.aggregate(
        total_purchase_value=Coalesce(Sum("purchase_price"), Value(0.0), output_field=FloatField()),
        total_sale_value=Coalesce(Sum("sale_price"), Value(0.0), output_field=FloatField()),
        total_profit_value=Coalesce(
            Sum(F("sale_price") - F("purchase_price")), Value(0.0), output_field=FloatField()),
        available_count=Count("id", filter=Q(available=True)),
        product_count=Count("id"),
    )
    sales = Sale.objects.aggregate(
        sold_count=Count("id"),
        sold_profit=Coalesce(Sum("profit"), Value(0.0), output_field=FloatField()),
        sold_revenue=Coalesce(Sum("final_price"), Value(0.0), output_field=FloatField()),
    )
    payments = Payment.objects.filter(total_amount__gt=F("paid_amount") + 0.001).aggregate(
        cnt=Count("id"),
        total_remaining=Coalesce(
            Sum(F("total_amount") - F("paid_amount")), Value(0.0), output_field=FloatField()),
    )
    return {
        "total_purchase_value": prod["total_purchase_value"] or 0,
        "total_sale_value": prod["total_sale_value"] or 0,
        "total_profit_value": prod["total_profit_value"] or 0,
        "available_count": prod["available_count"] or 0,
        "product_count": prod["product_count"] or 0,
        "sold_count": sales["sold_count"] or 0,
        "sold_profit": sales["sold_profit"] or 0,
        "sold_revenue": sales["sold_revenue"] or 0,
        "open_repairs": Repair.objects.exclude(status="delivered").count(),
        "open_tracking": Tracking.objects.exclude(status__in=["delivered", "cancelled"]).count(),
        "unpaid_count": payments["cnt"] or 0,
        "unpaid_total": payments["total_remaining"] or 0,
        "unavailable_count": Product.objects.filter(available=False).count(),
    }


def get_monthly_activity(months=12):
    """فعالیت ۱۲ ماه اخیر برای نمودار خطی — با ۲ کوئری به‌جای ۲۴."""
    today = datetime.date.today()
    jy_now, jm_now, _ = gregorian_to_jalali(today.year, today.month, today.day)

    months_list = []
    jy, jm = jy_now, jm_now
    for _ in range(months):
        months_list.append((jy, jm))
        jm -= 1
        if jm == 0:
            jm = 12
            jy -= 1
    months_list.reverse()

    ranges = []
    for jy, jm in months_list:
        gy1, gm1, gd1 = jalali_to_gregorian(jy, jm, 1)
        last = jalali_month_length(jy, jm)
        gy2, gm2, gd2 = jalali_to_gregorian(jy, jm, last)
        ranges.append((
            (jy, jm),
            datetime.date(gy1, gm1, gd1).isoformat(),
            datetime.date(gy2, gm2, gd2).isoformat(),
        ))

    # سرعت: کل بازه را یک‌باره می‌خوانیم و در پایتون دسته‌بندی می‌کنیم
    sales_rows = Sale.objects.values_list("sale_date", "final_price", "profit")
    prod_rows = Product.objects.exclude(purchase_date="").values_list("purchase_date", "purchase_price")

    def month_of(iso):
        # ISO میلادی → (jy, jm)
        y, m, d = (int(x) for x in iso[:10].split("-"))
        return gregorian_to_jalali(y, m, d)[:2]

    sales_by_month = {}
    for sdate, final_price, profit in sales_rows:
        if not sdate:
            continue
        key = month_of(sdate)
        agg = sales_by_month.setdefault(key, [0.0, 0.0, 0])
        agg[0] += final_price or 0
        agg[1] += profit or 0
        agg[2] += 1

    prod_by_month = {}
    for pdate, pprice in prod_rows:
        key = month_of(pdate)
        prod_by_month[key] = prod_by_month.get(key, 0.0) + (pprice or 0)

    out = []
    for (jy, jm), start, end in ranges:
        s = sales_by_month.get((jy, jm), [0.0, 0.0, 0])
        out.append({
            "jy": jy, "jm": jm,
            "label": MONTH_NAMES[jm - 1],
            "revenue": s[0], "profit": s[1], "count": s[2],
            "purchase_value": prod_by_month.get((jy, jm), 0.0),
        })
    return out


def get_brand_breakdown():
    rows = (
        Product.objects.values("brand")
        .annotate(
            count=Count("id"),
            value=Coalesce(Sum("purchase_price"), Value(0.0), output_field=FloatField()),
            sale_value=Coalesce(Sum("sale_price"), Value(0.0), output_field=FloatField()),
        )
        .order_by("-value")
    )
    return [
        {"brand": r["brand"], "count": r["count"],
         "value": r["value"], "sale_value": r["sale_value"]}
        for r in rows
    ]
