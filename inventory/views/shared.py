# -*- coding: utf-8 -*-
"""APIهای مشترک: برندها، آپلود تصویر و سرو تصاویر."""
import base64
import datetime
import json
import mimetypes
import os
import secrets

from django.conf import settings
from django.http import FileResponse

from inventory.dbhelpers import add_brand, delete_brand, get_brands
from inventory.utils import clean

from .common import fail, get_payload, ok

ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif", ".svg"}
ICON_EXT = {".png", ".svg", ".ico", ".jpg", ".jpeg", ".webp"}


def api_brands(request):
    """GET: فهرست برندها — POST: افزودن برند (مثل Flask)."""
    if request.method == "POST":
        payload = get_payload(request)
        good, err = add_brand(payload.get("name"))
        if not good:
            return fail(err)
        return ok()
    return ok(brands=get_brands())


def api_brands_delete(request):
    payload = get_payload(request)
    good, err = delete_brand(payload.get("name"))
    if not good:
        return fail(err)
    return ok()


def _save_uploaded(kind, ext, content):
    """ذخیره‌ی محتوای آپلودی (بایت‌ها) با نام یکتا — برای multipart و JSON."""
    allowed = ICON_EXT if kind == "icon" else ALLOWED_EXT
    if ext not in allowed:
        return None, "فرمت فایل پشتیبانی نمی‌شود"
    fname = ("icon_" if kind == "icon" else "img_") + \
        datetime.datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + \
        secrets.token_hex(4) + ext
    os.makedirs(settings.IMG_DIR, exist_ok=True)
    with open(os.path.join(settings.IMG_DIR, fname), "wb") as out:
        out.write(content)
    return fname, None


def api_upload(request):
    if request.content_type and "application/json" in request.content_type:
        # مسیر پایدار: فایل به‌صورت base64 داخل JSON (مثل بقیه‌ی APIها)
        try:
            payload = json.loads(request.body or b"{}")
        except Exception:
            return fail("بدنه‌ی درخواست نامعتبر است")
        kind = clean(payload.get("kind")) or "image"
        name = clean(payload.get("name")) or "file"
        data = payload.get("data") or ""
        if isinstance(data, str) and data.startswith("data:"):
            _, _, data = data.partition(",")
        try:
            content = base64.b64decode(data)
        except Exception:
            return fail("محتوای فایل قابل خواندن نیست")
        if not content:
            return fail("فایلی انتخاب نشده است")
        if len(content) > 2 * 1024 * 1024:
            return fail("حجم فایل باید کمتر از ۲ مگابایت باشد")
        fname, err = _save_uploaded(kind, os.path.splitext(name)[1].lower(), content)
        if err:
            return fail(err)
        return ok(path=fname)

    f = request.FILES.get("file")
    kind = clean(request.POST.get("kind")) or "image"
    if not f or not f.name:
        return fail("فایلی انتخاب نشده است")
    fname, err = _save_uploaded(kind, os.path.splitext(f.name)[1].lower(), b"".join(f.chunks()))
    if err:
        return fail(err)
    return ok(path=fname)


def serve_image(request, fname):
    """سرو تصاویر /data/images/<name> — مثل send_from_directory Flask."""
    safe = os.path.basename(fname)
    path = os.path.join(settings.IMG_DIR, safe)
    if not os.path.isfile(path):
        return fail("یافت نشد", 404)
    ctype = mimetypes.guess_type(path)[0] or "application/octet-stream"
    resp = FileResponse(open(path, "rb"), content_type=ctype)
    resp["Cache-Control"] = "public, max-age=604800"
    return resp