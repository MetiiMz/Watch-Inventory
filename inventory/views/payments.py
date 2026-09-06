# -*- coding: utf-8 -*-
"""API فقره‌های پرداخت (بیعانه/اقساط) — پورت از app.py قدیمی."""
from django.db.models import F, Q
from django.db import transaction
from django.views.decorators.http import require_POST

from inventory.jalali import parse_jalali_date, today_iso
from inventory.models import Payment, Product, Sale
from inventory.utils import fa_money, payment_dict, clean, to_float, to_int

from .common import fail, get_payload, ok


def api_payments(request):
    """GET: فهرست + خلاصه — POST: ایجاد فقره‌ی جدید."""
    if request.method == "POST":
        return _create(request)

    status = clean(request.GET.get("status"))  # all | unpaid | paid
    q = clean(request.GET.get("q"))
    qs = Payment.objects.select_related("product").all()
    if status == "unpaid":
        qs = qs.filter(total_amount__gt=F("paid_amount") + 0.001)
    elif status == "paid":
        qs = qs.filter(total_amount__lte=F("paid_amount") + 0.001)
    if q:
        qs = qs.filter(
            Q(product_name__icontains=q) | Q(customer_name__icontains=q)
            | Q(customer_phone__icontains=q))
    qs = qs.order_by("-id")

    items = [payment_dict(p) for p in qs]
    summary = {
        "count": len(items),
        "total": sum(i["total_amount"] for i in items),
        "paid": sum(i["paid_amount"] for i in items),
        "remaining": sum(i["remaining"] for i in items),
    }
    return ok(items=items, summary=summary)


def _create(request):
    payload = get_payload(request)
    pid = to_float(payload.get("product_id")) or None
    pid = int(pid) if pid else None
    product_name = clean(payload.get("product_name"))
    if pid:
        p = Product.objects.filter(id=pid).values_list("name", flat=True).first()
        if not p:
            return fail("محصول انتخاب‌شده یافت نشد")
        product_name = p
    if not product_name:
        return fail("نام محصول را وارد یا از انبار انتخاب کنید")
    total = max(0.0, to_float(payload.get("total_amount")))
    paid = max(0.0, to_float(payload.get("paid_amount")))
    if total <= 0:
        return fail("مبلغ کل باید بیشتر از صفر باشد")
    if paid > total:
        return fail("مبلغ پرداخت‌شده نمی‌تواند از مبلغ کل بیشتر باشد")
    pay_date = clean(payload.get("pay_date"))
    if pay_date:
        parsed = parse_jalali_date(pay_date)
        if not parsed:
            return fail("تاریخ معتبر نیست")
        pay_date = parsed
    else:
        pay_date = today_iso()
    payment = Payment.objects.create(
        product_id=pid, product_name=product_name,
        customer_name=clean(payload.get("customer_name")),
        customer_phone=clean(payload.get("customer_phone")),
        total_amount=total, paid_amount=paid, pay_date=pay_date,
        notes=clean(payload.get("notes")),
    )
    return ok(payment=payment_dict(payment))


def api_payment_detail(request, payid):
    """PUT: ویرایش — DELETE: حذف."""
    payment = Payment.objects.filter(id=payid).first()
    if not payment:
        return fail("یافت نشد", 404)

    if request.method == "PUT":
        return _update(request, payment)
    if request.method == "DELETE":
        payment.delete()
        return ok()
    return fail("متد پشتیبانی نمی‌شود", 405)


def _update(request, payment):
    payload = get_payload(request)
    total = max(0.0, to_float(payload.get("total_amount"), payment.total_amount))
    paid = max(0.0, to_float(payload.get("paid_amount"), payment.paid_amount))
    if total <= 0:
        return fail("مبلغ کل باید بیشتر از صفر باشد")
    if paid > total:
        return fail("مبلغ پرداخت‌شده نمی‌تواند از مبلغ کل بیشتر باشد")
    pay_date = clean(payload.get("pay_date")) or payment.pay_date
    if pay_date:
        parsed = parse_jalali_date(pay_date)
        if not parsed:
            return fail("تاریخ معتبر نیست")
        pay_date = parsed
    payment.product_name = clean(payload.get("product_name")) or payment.product_name
    payment.customer_name = clean(payload.get("customer_name"))
    payment.customer_phone = clean(payload.get("customer_phone"))
    payment.total_amount = total
    payment.paid_amount = paid
    payment.pay_date = pay_date
    # وضعیت تسویه — اگر با ویرایش کامل/ناقص شد، تاریخ تسویه ثبت/پاک می‌شود
    now_settled = total - paid <= 0.001
    if now_settled and not payment.settled_at:
        payment.settled_at = today_iso()
    elif not now_settled:
        payment.settled_at = ""
    if payment.sale_id:
        Sale.objects.filter(id=payment.sale_id).update(
            is_settled=now_settled, settled_at=payment.settled_at)
    payment.notes = clean(payload.get("notes"))
    payment.save(update_fields=[
        "product_name", "customer_name", "customer_phone",
        "total_amount", "paid_amount", "pay_date", "settled_at", "notes", "updated_at"])
    return ok(payment=payment_dict(payment))


@require_POST
def api_payment_add(request, payid):
    """افزودن پرداخت جدید به فقره‌ی موجود."""
    payload = get_payload(request)
    amount = to_float(payload.get("amount"))
    if amount <= 0:
        return fail("مبلغ باید بیشتر از صفر باشد")
    with transaction.atomic():
        payment = Payment.objects.select_for_update().filter(id=payid).first()
        if not payment:
            return fail("یافت نشد", 404)
        remaining = payment.total_amount - payment.paid_amount
        if amount > remaining + 0.001:
            return fail(
                f"بیشتر از مانده‌ی فقره است (مانده: {fa_money(remaining)} تومان)")
        payment.paid_amount = payment.paid_amount + amount
        now_settled = payment.total_amount - payment.paid_amount <= 0.001
        if now_settled and not payment.settled_at:
            payment.settled_at = today_iso()
        payment.save(update_fields=["paid_amount", "settled_at", "updated_at"])
        # تسویه‌ی کامل شد؟ فروش بیعانه‌ی متصل را تسویه‌شده کن
        if payment.sale_id and now_settled:
            Sale.objects.filter(id=payment.sale_id).update(
                is_settled=True, settled_at=payment.settled_at)
    return ok(payment=payment_dict(payment))


@require_POST
def api_payment_settle_full(request, payid):
    """تسویه‌ی کامل فقره بدون ورود مبلغ — کل مانده یکجا پرداخت می‌شود."""
    with transaction.atomic():
        payment = Payment.objects.select_for_update().filter(id=payid).first()
        if not payment:
            return fail("یافت نشد", 404)
        remaining = payment.total_amount - payment.paid_amount
        if remaining <= 0.001:
            return fail("این فقره قبلاً تسویه شده است")
        payment.paid_amount = payment.total_amount
        if not payment.settled_at:
            payment.settled_at = today_iso()
        payment.save(update_fields=["paid_amount", "settled_at", "updated_at"])
        if payment.sale_id:
            # مانده به‌عنوان پرداخت نقدی به فروش اضافه می‌شود
            Sale.objects.filter(id=payment.sale_id).update(
                is_settled=True, paid_cash=F("paid_cash") + remaining,
                settled_at=payment.settled_at)
    return ok()


@require_POST
def api_payments_bulk_delete(request):
    payload = get_payload(request)
    ids = [to_int(i) for i in (payload.get("ids") or []) if to_int(i)]
    if not ids:
        return fail("موردی انتخاب نشده است")
    deleted, _ = Payment.objects.filter(id__in=ids).delete()
    return ok(deleted=len(ids))
