# -*- coding: utf-8 -*-
"""APIهای مشترک: برندها، آپلود تصویر و سرو تصاویر."""
import datetime
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


def api_upload(request):
    f = request.FILES.get("file")
    kind = clean(request.POST.get("kind")) or "image"
    if not f or not f.name:
        return fail("فایلی انتخاب نشده است")
    ext = os.path.splitext(f.name)[1].lower()
    allowed = ICON_EXT if kind == "icon" else ALLOWED_EXT
    if ext not in allowed:
        return fail("فرمت فایل پشتیبانی نمی‌شود")
    fname = ("icon_" if kind == "icon" else "img_") + \
        datetime.datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + \
        secrets.token_hex(4) + ext
    os.makedirs(settings.IMG_DIR, exist_ok=True)
    with open(os.path.join(settings.IMG_DIR, fname), "wb") as out:
        for chunk in f.chunks():
            out.write(chunk)
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