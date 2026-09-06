# -*- coding: utf-8 -*-
"""ابزار مشترک ویوها — پاسخ JSON و متغیرهای پایه‌ی قالب."""
import json

from django.db.models import F
from django.http import JsonResponse

from inventory.dbhelpers import get_setting
from inventory.models import Payment, Product, Repair, Tracking


def get_payload(request):
    """بدنه‌ی JSON درخواست — در بدترین حالت دیکشنری خالی."""
    try:
        return json.loads(request.body.decode("utf-8") or "{}")
    except (ValueError, UnicodeDecodeError):
        return {}


def ok(**data):
    data.setdefault("ok", True)
    return JsonResponse(data)


def fail(error, status=400):
    return JsonResponse({"ok": False, "error": error}, status=status)


def page_ctx(request, active):
    """متغیرهای پایه‌ی base.html — همان context_processor نسخه‌ی Flask."""
    ctx = {
        "site_icon": get_setting("site_icon", ""),
        "store_name": get_setting("store_name", "") or "TikoTime",
        "active": active,
    }
    if active:
        low = Product.objects.filter(available=False).count()
        reps = Repair.objects.exclude(status="delivered").count()
        unpaid = Payment.objects.filter(total_amount__gt=F("paid_amount") + 0.001).count()
        tracking_open = Tracking.objects.exclude(
            status__in=["delivered", "cancelled"]).count()
        ctx.update(
            nav_badge_low=low or None,
            nav_badge_repairs=reps or None,
            nav_badge_unpaid=unpaid or None,
            nav_badge_tracking=tracking_open or None,
        )
    return ctx