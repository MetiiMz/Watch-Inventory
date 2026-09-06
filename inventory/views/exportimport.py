# -*- coding: utf-8 -*-
"""خروجی گرفتن (Excel/CSV) و ورود اطلاعات — پورت از app.py قدیمی."""
import datetime
import os
from urllib.parse import quote

from django.conf import settings
from django.http import FileResponse
from django.views.decorators.http import require_POST

from inventory.excel_io import (
    export_payments, export_products, export_repairs, export_sales,
    export_tracking, import_products,
)

from .common import fail, ok


def _export_file(kind, fmt):
    export_dir = os.path.join(str(settings.DATA_DIR), "exports")
    os.makedirs(export_dir, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y-%m-%d_%H%M")
    name = f"{kind}_{stamp}.{fmt}"
    path = os.path.join(export_dir, name)
    EXPORT_FUNCS[kind](path, fmt)
    return path, name


EXPORT_FUNCS = {
    "products": export_products,
    "repairs": export_repairs,
    "tracking": export_tracking,
    "payments": export_payments,
    "sales": export_sales,
}


def _attachment(path, name, mimetype):
    resp = FileResponse(open(path, "rb"), content_type=mimetype)
    quoted = quote(name)
    resp["Content-Disposition"] = (
        f"attachment; filename=\"{quoted}\"; filename*=UTF-8''{quoted}")
    return resp


def export_file(request, kind, fmt):
    if fmt not in ("xlsx", "csv") or kind not in EXPORT_FUNCS:
        return fail("یافت نشد", 404)
    path, name = _export_file(kind, fmt)
    mime = ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            if fmt == "xlsx" else "text/csv")
    return _attachment(path, name, mime)


@require_POST
def api_import_products(request):
    f = request.FILES.get("file")
    if not f or not f.name:
        return fail("فایلی انتخاب نشده است")
    ext = os.path.splitext(f.name)[1].lower()
    if ext not in (".csv", ".xlsx", ".xlsm"):
        return fail("فقط فایل csv یا xlsx پذیرفته می‌شود")
    export_dir = os.path.join(str(settings.DATA_DIR), "exports")
    os.makedirs(export_dir, exist_ok=True)
    tmp_path = os.path.join(export_dir, "import_tmp" + ext)
    with open(tmp_path, "wb") as out:
        for chunk in f.chunks():
            out.write(chunk)
    update_existing = request.POST.get("update_existing") == "1"
    try:
        good, stats, errors = import_products(tmp_path, update_existing=update_existing)
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass
    if not good:
        return fail(errors)
    return ok(stats=stats, errors=errors[:30])


def api_import_template(request):
    path, name = _export_file("products", "xlsx")
    return _attachment(
        path, "قالب_ورود_اطلاعات.xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")