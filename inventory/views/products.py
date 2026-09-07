# -*- coding: utf-8 -*-
"""API محصولات — همان رفتار، همان پیام‌های خطا."""

from django.db import transaction
from django.db.models import Q
from django.db.models.functions import Lower
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from inventory.jalali import parse_jalali_date
from inventory.models import Product
from inventory.utils import clean, product_dict, remove_image, to_float, to_int

from .common import fail, get_payload, ok

PRODUCT_SORT = {
    "office_code": "office_code", "website_code": "website_code", "name": "name",
    "brand": "brand", "supplier": "supplier", "purchase_date": "purchase_date",
    "purchase_price": "purchase_price", "sale_price": "sale_price",
    "available": "available", "created_at": "id",
}
_CASE_INSENSITIVE = {"office_code", "website_code", "name", "brand", "supplier"}


def _order(sort, direction):
    """مرتب‌سازی — COLLATE NOCASE قدیمی با Lower معادل شد."""
    col = PRODUCT_SORT.get(sort, "office_code")
    desc = direction == "desc"
    if col in _CASE_INSENSITIVE:
        f = Lower(col)
        return [f.desc() if desc else f.asc()]
    return ["-" + col if desc else col]
def _check_duplicate(office_code, website_code, exclude_id=None):
    q = Q(office_code__iexact=office_code) | Q(website_code__iexact=website_code)
    if exclude_id:
        q &= ~Q(id=exclude_id)
    dup = Product.objects.filter(q).first()
    if not dup:
        return None
    if dup.office_code.lower() == office_code.lower():
        return f"کد دفتر فروشگاه «{office_code}» قبلاً برای ساعت «{dup.name}» ثبت شده است"
    return f"کد انبار سایت «{website_code}» قبلاً برای ساعت «{dup.name}» ثبت شده است"


def _product_values(payload):
    """اعتبارسنجی و ساخت مقادیر محصول. خروجی: (values, error)"""
    name = clean(payload.get("name"))
    office_code = clean(payload.get("office_code"))
    website_code = clean(payload.get("website_code"))
    if not name:
        return None, "نام ساعت الزامی است"
    if not office_code:
        return None, "کد دفتر فروشگاه الزامی است"
    if not website_code:
        return None, "کد انبار سایت الزامی است"

    purchase_date = clean(payload.get("purchase_date"))
    if purchase_date:
        parsed = parse_jalali_date(purchase_date)
        if not parsed:
            return None, "تاریخ خرید معتبر نیست (نمونه: ۱۴۰۳/۰۵/۱۲)"
        purchase_date = parsed
    else:
        purchase_date = ""

    return {
        "name": name,
        "reference": clean(payload.get("reference")),
        "office_code": office_code,
        "website_code": website_code,
        "brand": clean(payload.get("brand")),
        "purchase_price": max(0.0, to_float(payload.get("purchase_price"))),
        "sale_price": max(0.0, to_float(payload.get("sale_price"))),
        # هر ردیف = یک دستگاه؛ با ثبت فروش ناموجود می‌شود
        "available": True,
        "supplier": clean(payload.get("supplier")),
        "purchase_date": purchase_date,
        "notes": clean(payload.get("notes")),
        "image": clean(payload.get("image")),
    }, None


def api_products(request):
    """GET: فهرست با فیلتر/مرتب‌سازی — POST: ثبت محصول جدید."""
    if request.method == "POST":
        return _create(request)

    q = request.GET.get("q", "").strip()
    brand = request.GET.get("brand", "").strip()
    status = request.GET.get("status", "").strip()
    date_from = request.GET.get("date_from", "").strip()
    date_to = request.GET.get("date_to", "").strip()
    sort = request.GET.get("sort", "office_code").strip()
    direction = request.GET.get("dir", "asc").strip().lower()

    qs = Product.objects.all()
    if q:
        qs = qs.filter(
            Q(name__icontains=q) | Q(reference__icontains=q)
            | Q(office_code__icontains=q) | Q(website_code__icontains=q)
            | Q(brand__icontains=q) | Q(supplier__icontains=q)
        )
    if brand:
        qs = qs.filter(brand=brand)
    if status == "available":
        qs = qs.filter(available=True)
    elif status == "unavailable":
        qs = qs.filter(available=False)
    if date_from:
        parsed = parse_jalali_date(date_from)
        if parsed:
            qs = qs.filter(purchase_date__gte=parsed)
    if date_to:
        parsed = parse_jalali_date(date_to)
        if parsed:
            qs = qs.filter(purchase_date__lte=parsed)

    rows = qs.order_by(*_order(sort, direction), "-id")
    return JsonResponse([product_dict(r) for r in rows], safe=False)


def _create(request):
    payload = get_payload(request)
    values, err = _product_values(payload)
    if err:
        return fail(err)
    dup = _check_duplicate(values["office_code"], values["website_code"])
    if dup:
        return fail(dup)
    with transaction.atomic():
        row = Product.objects.create(**values)
    return ok(product=product_dict(row))


def api_product_detail(request, pid):
    product = Product.objects.filter(id=pid).first()
    if product is None:
        return fail("محصول یافت نشد", 404)
    if request.method == "GET":
        return JsonResponse(product_dict(product), safe=False)
    if request.method == "PUT":
        return _update(request, product)
    return _delete(product)


def _update(request, product):
    payload = get_payload(request)
    values, err = _product_values(payload)
    if err:
        return fail(err)
    dup = _check_duplicate(values["office_code"], values["website_code"],
                           exclude_id=product.id)
    if dup:
        return fail(dup)
    # ویرایش نباید وضعیتِ موجودیِ ناشی از فروش را بازنشانی کند
    # (باگ قدیمی: ویرایشِ ساعت فروخته‌شده آن را دوباره «موجود» می‌کرد)
    values.pop("available", None)
    old_image = product.image
    for k, v in values.items():
        setattr(product, k, v)
    product.save()
    if old_image and old_image != values["image"]:
        remove_image(old_image)
    return ok(product=product_dict(product))


def _delete(product):
    with transaction.atomic():
        product.delete()
    if product.image:
        remove_image(product.image)
    return ok()


@require_POST
def api_products_bulk_delete(request):
    payload = get_payload(request)
    ids = [to_int(i) for i in (payload.get("ids") or []) if to_int(i)]
    if not ids:
        return fail("موردی انتخاب نشده است")
    images = list(
        Product.objects.filter(id__in=ids)
        .exclude(image="").values_list("image", flat=True)
    )
    with transaction.atomic():
        Product.objects.filter(id__in=ids).delete()
    for img in images:
        remove_image(img)
    return ok(deleted=len(ids))