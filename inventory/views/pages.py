# -*- coding: utf-8 -*-
"""صفحات HTML — همان مسیرها و نام‌های endpoint نسخه‌ی Flask."""
from django.http import JsonResponse
from django.shortcuts import redirect, render

from inventory.models import Product, Sale
from inventory.reports import (
    get_brand_breakdown, get_dashboard_stats, get_monthly_activity,
)
from inventory.utils import product_dict, sale_dict

from .common import page_ctx


def index(request):
    return redirect("/dashboard")


def dashboard(request):
    stats = get_dashboard_stats()
    monthly = get_monthly_activity()
    brands = get_brand_breakdown()
    sales_rows = (
        Sale.objects.select_related("product")
        .order_by("-sale_date", "-id")[:8]
    )
    purchase_rows = (
        Product.objects.exclude(purchase_date="")
        .order_by("-purchase_date", "-id")[:8]
    )
    low = Product.objects.filter(available=False).order_by("name")[:6]
    ctx = page_ctx(request, "dashboard")
    ctx.update(
        stats=stats, monthly=monthly, brands=brands,
        recent_sales=[sale_dict(s) for s in sales_rows],
        recent_purchases=[product_dict(p) for p in purchase_rows],
        low_stock=[product_dict(p) for p in low],
    )
    return render(request, "dashboard.html", ctx)


def products_page(request):
    return render(request, "products.html", page_ctx(request, "products"))


def calendar_page(request):
    return render(request, "calendar.html", page_ctx(request, "calendar"))


def repairs_page(request):
    return render(request, "repairs.html", page_ctx(request, "repairs"))


def sold_page(request):
    return render(request, "sold.html", page_ctx(request, "sold"))


def tracking_page(request):
    return render(request, "tracking.html", page_ctx(request, "tracking"))


def payments_page(request):
    return render(request, "payments.html", page_ctx(request, "payments"))


def settings_page(request):
    return render(request, "settings.html", page_ctx(request, "settings"))


def handler404(request, exception=None):
    """همان رفتار قدیمی: خطای API به‌صورت JSON، بقیه ریدایرکت به داشبورد."""
    if request.path.startswith("/api/") or request.path.startswith("/export/"):
        return JsonResponse({"ok": False, "error": "یافت نشد"}, status=404)
    return redirect("/dashboard")