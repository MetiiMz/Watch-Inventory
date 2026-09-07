# -*- coding: utf-8 -*-
"""API پیگیری سفارش‌ها."""

from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from inventory.models import Tracking
from inventory.utils import TRACKING_STATUS_FA, clean, to_float, to_int, tracking_dict

from .common import fail, get_payload, ok


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


def api_tracking(request):
    """GET: فهرست — POST: ثبت جدید."""
    if request.method == "POST":
        payload = get_payload(request)
        values, err = _tracking_values(payload)
        if err:
            return fail(err)
        with transaction.atomic():
            row = Tracking.objects.create(**values)
        return ok(tracking=tracking_dict(row))

    status = request.GET.get("status", "").strip()
    q = request.GET.get("q", "").strip()
    qs = Tracking.objects.all()
    if status:
        qs = qs.filter(status=status)
    if q:
        qs = qs.filter(
            Q(item_name__icontains=q) | Q(item_code__icontains=q)
            | Q(customer_name__icontains=q) | Q(customer_phone__icontains=q)
        )
    rows = qs.order_by("-id")
    return JsonResponse([tracking_dict(r) for r in rows], safe=False)


def api_tracking_detail(request, tid):
    row = Tracking.objects.filter(id=tid).first()
    if row is None:
        return fail("یافت نشد", 404)
    if request.method == "GET":
        return JsonResponse(tracking_dict(row), safe=False)
    if request.method == "PUT":
        payload = get_payload(request)
        values, err = _tracking_values(payload)
        if err:
            return fail(err)
        old_image = row.image
        for k, v in values.items():
            setattr(row, k, v)
        row.save()
        if old_image and old_image != values["image"]:
            remove_image(old_image)
        return ok(tracking=tracking_dict(row))
    with transaction.atomic():
        row.delete()
    if row.image:
        remove_image(row.image)
    return ok()


@require_POST
def api_tracking_bulk_delete(request):
    payload = get_payload(request)
    ids = [to_int(i) for i in (payload.get("ids") or []) if to_int(i)]
    if not ids:
        return fail("موردی انتخاب نشده است")
    images = list(
        Tracking.objects.filter(id__in=ids)
        .exclude(image="").values_list("image", flat=True)
    )
    with transaction.atomic():
        Tracking.objects.filter(id__in=ids).delete()
    for img in images:
        remove_image(img)
    return ok(deleted=len(ids))