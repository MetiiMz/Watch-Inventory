# -*- coding: utf-8 -*-
"""گزارش‌های نمایه (Dashboard) — آمار کلی انبار، فروش ماهانه، پرداخت‌ها."""

from database import get_db


def get_dashboard_stats():
    with get_db() as db:
        row = db.execute(
            """
            SELECT
                COALESCE(SUM(purchase_price), 0) AS total_purchase_value,
                COALESCE(SUM(sale_price), 0)     AS total_sale_value,
                COALESCE(SUM(sale_price - purchase_price), 0) AS total_profit_value,
                COALESCE(SUM(CASE WHEN available = 1 THEN 1 ELSE 0 END), 0) AS available_count,
                COUNT(*) AS product_count
            FROM products
            """
        ).fetchone()

        sales_row = db.execute(
            """
            SELECT
                COUNT(*)                              AS sold_count,
                COALESCE(SUM(profit), 0)              AS sold_profit,
                COALESCE(SUM(COALESCE(final_price, sale_price)), 0) AS sold_revenue
            FROM sales
            """
        ).fetchone()

        repairs = db.execute(
            "SELECT COUNT(*) AS c FROM repairs WHERE status != 'delivered'"
        ).fetchone()["c"]

        tracking = db.execute(
            "SELECT COUNT(*) AS c FROM tracking WHERE status NOT IN ('delivered','cancelled')"
        ).fetchone()["c"]

        payments = db.execute(
            """
            SELECT
                COUNT(*) AS cnt,
                COALESCE(SUM(total_amount - paid_amount), 0) AS total_remaining
            FROM payments WHERE total_amount - paid_amount > 0.001
            """
        ).fetchone()

        unavailable = db.execute(
            "SELECT COUNT(*) AS c FROM products WHERE available = 0"
        ).fetchone()["c"]

    return {
        "total_purchase_value": row["total_purchase_value"] or 0,
        "total_sale_value": row["total_sale_value"] or 0,
        "total_profit_value": row["total_profit_value"] or 0,
        "available_count": row["available_count"] or 0,
        "product_count": row["product_count"] or 0,
        "sold_count": sales_row["sold_count"] or 0,
        "sold_profit": sales_row["sold_profit"] or 0,
        "sold_revenue": sales_row["sold_revenue"] or 0,
        "open_repairs": repairs,
        "open_tracking": tracking,
        "unpaid_count": payments["cnt"] or 0,
        "unpaid_total": payments["total_remaining"] or 0,
        "unavailable_count": unavailable,
    }


def get_monthly_activity(months=12):
    """فعالیت ۱۲ ماه اخیر (شامل ماه جاری) برای نمودار خطی.
    خروجی: [{'jy','jm','label','revenue','profit','count','purchase_value'}]
    """
    import datetime
    from jalali import gregorian_to_jalali, jalali_month_length, MONTH_NAMES

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

    out = []
    with get_db() as db:
        for jy, jm in months_list:
            gy1, gm1, gd1 = _j2g(jy, jm, 1)
            last = jalali_month_length(jy, jm)
            gy2, gm2, gd2 = _j2g(jy, jm, last)
            start = datetime.date(gy1, gm1, gd1).isoformat()
            end = datetime.date(gy2, gm2, gd2).isoformat()

            srow = db.execute(
                """
                SELECT COALESCE(SUM(COALESCE(final_price, sale_price)), 0) AS revenue,
                       COALESCE(SUM(profit), 0) AS profit,
                       COUNT(*) AS cnt
                FROM sales WHERE sale_date >= ? AND sale_date <= ?
                """,
                (start, end),
            ).fetchone()
            prow = db.execute(
                """
                SELECT COALESCE(SUM(purchase_price), 0) AS pvalue
                FROM products WHERE purchase_date >= ? AND purchase_date <= ?
                """,
                (start, end),
            ).fetchone()

            out.append({
                "jy": jy, "jm": jm,
                "label": MONTH_NAMES[jm - 1],
                "revenue": srow["revenue"] or 0,
                "profit": srow["profit"] or 0,
                "count": srow["cnt"] or 0,
                "purchase_value": prow["pvalue"] or 0,
            })
    return out


def _j2g(jy, jm, jd):
    from jalali import jalali_to_gregorian
    return jalali_to_gregorian(jy, jm, jd)


def get_brand_breakdown():
    with get_db() as db:
        rows = db.execute(
            """
            SELECT brand,
                   COUNT(*) AS count,
                   COALESCE(SUM(purchase_price), 0) AS value
            FROM products
            GROUP BY brand
            ORDER BY value DESC
            """
        ).fetchall()
    return [dict(r) for r in rows]
