# -*- coding: utf-8 -*-
"""API نسخه‌های پشتیبان — پورت از app.py قدیمی."""
import os
import sqlite3

from django.conf import settings
from django.db import close_old_connections
from django.http import FileResponse
from django.views.decorators.http import require_POST

from inventory.dbhelpers import backup_db, delete_backup, list_backups, restore_db

from .common import fail, get_payload, ok


@require_POST
def api_backups_create(request):
    close_old_connections()
    target = backup_db()
    return ok(name=os.path.basename(target))


@require_POST
def api_backups_upload(request):
    """آپلود فایل بکاپ از بیرون (برای انتقال به سرور یا بازیابی از فلش)."""
    f = request.FILES.get("file")
    if not f or not f.name:
        return fail("فایلی انتخاب نشده است")
    fname = os.path.basename(f.name)
    if not fname.endswith(".db"):
        fname += ".db"
    os.makedirs(settings.BACKUP_DIR, exist_ok=True)
    target = os.path.join(str(settings.BACKUP_DIR), fname)
    with open(target, "wb") as out:
        for chunk in f.chunks():
            out.write(chunk)
    # اعتبارسنجی: فایل باید یک SQLite معتبر با جدول products باشد
    try:
        conn = sqlite3.connect(target)
        conn.execute("SELECT COUNT(*) FROM products")
        conn.close()
    except sqlite3.Error:
        os.remove(target)
        return fail("فایل انتخاب‌شده یک نسخه‌ی پشتیبان معتبر TikoTime نیست")
    return ok(name=fname)


def api_backups_download(request, fname):
    safe = os.path.basename(fname)
    p = os.path.join(str(settings.BACKUP_DIR), safe)
    if not os.path.isfile(p):
        return fail("یافت نشد", 404)
    resp = FileResponse(open(p, "rb"), content_type="application/octet-stream")
    resp["Content-Disposition"] = f'attachment; filename="{safe}"'
    return resp


@require_POST
def api_backups_restore(request):
    payload = get_payload(request)
    close_old_connections()
    good, err = restore_db(payload.get("name"))
    if not good:
        return fail(err)
    return ok()


@require_POST
def api_backups_delete(request):
    payload = get_payload(request)
    good, err = delete_backup(payload.get("name"))
    if not good:
        return fail(err)
    return ok()


def api_backups(request):
    return ok(backups=list_backups())