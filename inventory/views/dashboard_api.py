# -*- coding: utf-8 -*-
"""APIهای داشبورد — داده‌ی نمودار فعالیت ماهانه به تفکیک سال جلالی."""
from inventory.reports import get_monthly_activity

from .common import fail, ok


def api_monthly_activity(request):
    """GET /api/reports/monthly-activity?year=1404 — ۱۲ ماه آن سال جلالی.

    بدون پارامتر، سال جاری برمی‌گردد. خروجی:
    {ok, year, months: [{jy, jm, label, revenue, profit, count,
                         purchase_value, future}]}
    """
    year = request.GET.get("year")
    if year is None or str(year).strip() == "":
        months = get_monthly_activity()
        return ok(year=months[0]["jy"], months=months)
    try:
        jy = int(str(year).strip())
    except (TypeError, ValueError):
        return fail("سال نامعتبر است")
    if not 1300 <= jy <= 1600:
        return fail("سال خارج از بازه‌ی مجاز است")
    months = get_monthly_activity(jy)
    return ok(year=jy, months=months)
