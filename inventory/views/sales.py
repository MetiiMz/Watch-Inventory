# -*- coding: utf-8 -*-
"""API فروش‌ها.

رفع باگ صفحه‌ی فروش: لیست، همه‌ی فروش‌ها را برمی‌گرداند — حتی بیعانه‌های
تسویه‌نشده (is_settled=0). نسخه‌ی قدیمی `WHERE is_settled = 1` داشت و
فروش‌های بیعانه از لیست حذف می‌شدند. نشان «بیعانه» مطابق قبل حفظ شده است.
"""
import json

from django.db import transaction
from django.db.models import Q
from django.db.models.functions import Lower
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from inventory.jalali import parse_jalali_date, today_iso
from inventory.models import Payment, Product, Sale
from inventory.utils import (
    SALE_TYPE_FA, clean, fa_money, sale_dict, to_en_digits, to_en_phone,
    to_float, to_int,
)

from .common import fail, get_payload, ok

SALE_SORT = {
    "date": "sale_date", "name": "product__name", "final_price": "final_price",
    "profit": "profit", "office_code": "product__office_code",
    "customer": "customer",
}
_SALE_NOCASE = {"product__name", "product__office_code", "customer"}


def _order(sort, direction):
    col = SALE_SORT.get(sort, "sale_date")
    desc = direction == "desc"
    if col in _SALE_NOCASE:
        f = Lower(col)
        return [f.desc() if desc else f.asc()]
    return ["-" + col if desc else col]


def api_sales(request):
    """GET: فهرست فروش‌ها + خلاصه — POST: ثبت فروش (نقدی یا بیعانه)."""
    if request.method == "POST":
        return _create(request)

    q = to_en_digits(request.GET.get("q", "").strip())
    sale_type = request.GET.get("sale_type", "").strip()
    pay_method = request.GET.get("pay_method", "").strip()
    date_from = request.GET.get("date_from", "").strip()
    date_to = request.GET.get("date_to", "").strip()
    sort = request.GET.get("sort", "date").strip()
    direction = request.GET.get("dir", "desc").strip().lower()

    # ✦ رفع باگ: بدون فیلتر is_settled — بیعانه‌ها هم در لیست‌اند
    qs = Sale.objects.select_related("product").all()
    if q:
        qs = qs.filter(
            Q(product__name__icontains=q) | Q(customer__icontains=q)
            | Q(customer_phone__icontains=q) | Q(product__office_code__icontains=q)
            | Q(product__website_code__icontains=q) | Q(product__reference__icontains=q)
        )
    if sale_type in SALE_TYPE_FA:
        qs = qs.filter(sale_type=sale_type)
    col = {"cash": "paid_cash", "pos": "paid_pos", "card2card": "paid_card2card"}.get(pay_method)
    if col:
        qs = qs.filter(**{col + "__gt": 0})
    if date_from:
        parsed = parse_jalali_date(date_from)
        if parsed:
            qs = qs.filter(sale_date__gte=parsed)
    if date_to:
        parsed = parse_jalali_date(date_to)
        if parsed:
            qs = qs.filter(sale_date__lte=parsed)

    rows = list(qs.order_by(*_order(sort, direction), "-id")[:500])
    items = [sale_dict(s) for s in rows]
    summary = {
        "count": len(items),
        "total_final": sum(x.get("final_price") or 0 for x in items),
        "total_profit": sum(x.get("profit") or 0 for x in items),
    }
    return JsonResponse({"items": items, "summary": summary})


def _create(request):
    """ثبت فروش. دو حالت: cash (کامل) و deposit (بیعانه)."""
    payload = get_payload(request)
    pid = to_int(payload.get("product_id"))
    if not pid:
        return fail("محصول انتخاب نشده است")

    payment_kind = "deposit" if clean(payload.get("payment_type")) == "deposit" else "cash"

    p = Product.objects.filter(id=pid).first()
    if p is None:
        return fail("محصول یافت نشد", 404)

    sale_price = to_float(payload.get("sale_price"), p.sale_price)
    discount = to_float(payload.get("discount_price"), 0)
    final_price = discount if discount > 0 else sale_price
    if final_price > sale_price:
        return fail("قیمت نهایی نمی‌تواند از قیمت فروش بیشتر باشد")

    paid_cash = max(0.0, to_float(payload.get("paid_cash")))
    paid_pos = max(0.0, to_float(payload.get("paid_pos")))
    paid_card2card = max(0.0, to_float(payload.get("paid_card2card")))
    paid_now = paid_cash + paid_pos + paid_card2card

    sale_date = clean(payload.get("sale_date"))
    if sale_date:
        parsed = parse_jalali_date(sale_date)
        if not parsed:
            return fail("تاریخ فروش معتبر نیست")
    else:
        parsed = today_iso()
    sale_type = clean(payload.get("sale_type")) or "person"
    if sale_type not in SALE_TYPE_FA:
        sale_type = "person"
    customer_phone = to_en_phone(clean(payload.get("customer_phone")))
    customer = clean(payload.get("customer"))

    if payment_kind == "deposit":
        if paid_now <= 0:
            return fail("برای فروش بیعانه، دست‌کم مبلغ بیعانه را وارد کنید")
        if paid_now > final_price + 0.001:
            return fail("جمع پرداخت‌ها نمی‌تواند از قیمت نهایی بیشتر باشد "
                        f"({fa_money(final_price)} تومان)")
        is_settled = False
    else:
        if paid_now > final_price + 0.001:
            return fail("جمع پرداخت‌ها نمی‌تواند از قیمت نهایی بیشتر باشد "
                        f"({fa_money(final_price)} تومان)")
        # فروش نقدی کامل است؛ اگر ریز پرداخت وارد نشده باشد، همه نقدی در نظر گرفته می‌شود
        if paid_now <= 0:
            paid_cash, paid_pos, paid_card2card = final_price, 0.0, 0.0
        payment_kind = "cash"
        is_settled = True

    profit = final_price - (p.purchase_price or 0)

    with transaction.atomic():
        s = Sale.objects.create(
            product=p, sale_price=sale_price, purchase_price=p.purchase_price,
            profit=profit, sale_date=parsed, customer=customer,
            customer_phone=customer_phone, sale_type=sale_type,
            payment_type=payment_kind, final_price=final_price,
            paid_cash=paid_cash, paid_pos=paid_pos, paid_card2card=paid_card2card,
            is_settled=is_settled, notes=clean(payload.get("notes")),
        )
        if payment_kind == "deposit":
            Payment.objects.create(
                sale=s, product=p, product_name=p.name,
                customer_name=customer, customer_phone=customer_phone,
                total_amount=final_price, paid_amount=paid_now,
                pay_date=parsed,
                notes=f"بیعانه فروش #{s.id} — مانده: "
                      f"{fa_money(final_price - paid_now)} تومان",
            )
        # این ساعت فروخته شد — ناموجود می‌شود
        Product.objects.filter(id=pid).update(available=False)

    return ok(sale=sale_dict(s, p))


def api_sale_detail(request, sid):
    s = Sale.objects.filter(id=sid).select_related("product").first()
    if s is None:
        return fail("فروش یافت نشد", 404)
    if request.method == "GET":
        return JsonResponse({"ok": True, "sale": sale_dict(s)})
    if request.method == "PUT":
        return _update(request, s)
    return _delete(s)


def _update(request, s):
    """ویرایش فروش (قیمت، خریدار، روش‌ها، یادداشت)."""
    payload = get_payload(request)
    p = s.product

    sale_price = to_float(payload.get("sale_price"), s.sale_price)
    payment_kind = clean(payload.get("payment_type")) or s.payment_type
    if payment_kind not in ("cash", "deposit"):
        payment_kind = "cash"
    if payment_kind == "deposit":
        final_price = to_float(payload.get("discount_price"), s.final_price or sale_price)
    else:
        discount = to_float(payload.get("discount_price"), 0)
        final_price = discount if discount > 0 else sale_price
    if final_price > sale_price:
        return fail("قیمت نهایی نمی‌تواند از قیمت فروش بیشتر باشد")

    paid_cash = max(0.0, to_float(payload.get("paid_cash"), s.paid_cash))
    paid_pos = max(0.0, to_float(payload.get("paid_pos"), s.paid_pos))
    paid_card2card = max(0.0, to_float(payload.get("paid_card2card"), s.paid_card2card))
    paid_now = paid_cash + paid_pos + paid_card2card
    if paid_now > final_price + 0.001:
        return fail(f"جمع پرداخت‌ها نمی‌تواند از قیمت نهایی بیشتر باشد "
                    f"({fa_money(final_price)} تومان)")
    if paid_now <= 0 and payment_kind == "cash":
        paid_cash, paid_pos, paid_card2card = final_price, 0.0, 0.0

    purchase_price = to_float(payload.get("purchase_price"), p.purchase_price if p else 0)
    profit = final_price - purchase_price

    sale_date = clean(payload.get("sale_date")) or s.sale_date
    parsed = parse_jalali_date(sale_date)
    if not parsed:
        return fail("تاریخ فروش معتبر نیست")
    sale_type = clean(payload.get("sale_type")) or s.sale_type
    if sale_type not in SALE_TYPE_FA:
        sale_type = "person"

    s.sale_price = sale_price
    s.final_price = final_price
    s.profit = profit
    s.sale_date = parsed
    s.customer = clean(payload.get("customer"))
    s.customer_phone = to_en_phone(clean(payload.get("customer_phone")))
    s.sale_type = sale_type
    s.payment_type = payment_kind
    s.paid_cash = paid_cash
    s.paid_pos = paid_pos
    s.paid_card2card = paid_card2card
    s.notes = clean(payload.get("notes"))
    s.save()
    return ok(sale=sale_dict(s, p))


def _delete(s):
    """حذف فروش — ساعت دوباره موجود می‌شود (پرداخت‌ها با FK حذف می‌شوند)."""
    pid = s.product_id
    with transaction.atomic():
        s.delete()
        if pid:
            Product.objects.filter(id=pid).update(available=True)
    return ok()


@require_POST
def api_sales_bulk_delete(request):
    payload = get_payload(request)
    ids = [to_int(i) for i in (payload.get("ids") or []) if to_int(i)]
    if not ids:
        return fail("موردی انتخاب نشده است")
    with transaction.atomic():
        # ساعت‌های این فروش‌ها دوباره موجود می‌شوند
        Product.objects.filter(
            id__in=Sale.objects.filter(id__in=ids).values("product_id")
        ).update(available=True)
        Sale.objects.filter(id__in=ids).delete()
    return ok(deleted=len(ids))