# -*- coding: utf-8 -*-
"""API تعمیرات."""

from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from inventory.jalali import parse_jalali_date, today_iso
from inventory.models import Repair
from inventory.utils import STATUS_FA, clean, repair_dict, remove_image, to_float, to_int

from .common import fail, get_payload, ok


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


def api_repairs(request):
    """GET: فهرست تعمیرات — POST: ثبت تعمیر جدید."""
    if request.method == "POST":
        payload = get_payload(request)
        values, err = _repair_values(payload)
        if err:
            return fail(err)
        with transaction.atomic():
            row = Repair.objects.create(**values)
        return ok(repair=repair_dict(row))

    status = request.GET.get("status", "").strip()
    q = request.GET.get("q", "").strip()
    qs = Repair.objects.all()
    if status:
        qs = qs.filter(status=status)
    if q:
        qs = qs.filter(
            Q(watch_name__icontains=q) | Q(watch_code__icontains=q)
            | Q(customer_name__icontains=q) | Q(customer_phone__icontains=q)
        )
    rows = qs.order_by("-id")
    return JsonResponse([repair_dict(r) for r in rows], safe=False)


def api_repair_detail(request, rid):
    row = Repair.objects.filter(id=rid).first()
    if row is None:
        return fail("یافت نشد", 404)
    if request.method == "GET":
        return JsonResponse(repair_dict(row), safe=False)
    if request.method == "PUT":
        payload = get_payload(request)
        values, err = _repair_values(payload)
        if err:
            return fail(err)
        old_image = row.image
        for k, v in values.items():
            setattr(row, k, v)
        row.save()
        if old_image and old_image != values["image"]:
            remove_image(old_image)
        return ok(repair=repair_dict(row))
    with transaction.atomic():
        row.delete()
    if row.image:
        remove_image(row.image)
    return ok()


@require_POST
def api_repairs_bulk_delete(request):
    payload = get_payload(request)
    ids = [to_int(i) for i in (payload.get("ids") or []) if to_int(i)]
    if not ids:
        return fail("موردی انتخاب نشده است")
    images = list(
        Repair.objects.filter(id__in=ids)
        .exclude(image="").values_list("image", flat=True)
    )
    with transaction.atomic():
        Repair.objects.filter(id__in=ids).delete()
    for img in images:
        remove_image(img)
    return ok(deleted=len(ids))


@require_POST
def api_repair_status(request, rid):
    payload = get_payload(request)
    status = clean(payload.get("status"))
    if status not in STATUS_FA:
        return fail("وضعیت نامعتبر است")
    return_date = clean(payload.get("return_date"))
    parsed = ""
    if return_date:
        parsed = parse_jalali_date(return_date)
        if not parsed:
            return fail("تاریخ بازگشت معتبر نیست")
    if status == "delivered" and not parsed:
        parsed = today_iso()
    row = Repair.objects.filter(id=rid).first()
    if row is None:
        return fail("یافت نشد", 404)
    if parsed:
        row.status = status
        row.return_date = parsed
    else:
        row.status = status
    row.save()
    return ok(repair=repair_dict(row))