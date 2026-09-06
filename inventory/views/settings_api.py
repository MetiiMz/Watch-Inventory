# -*- coding: utf-8 -*-
"""API تنظیمات فروشگاه — پورت از app.py قدیمی."""
from inventory.dbhelpers import get_setting, set_setting
from inventory.utils import clean, remove_image

from .common import get_payload, ok


def api_settings(request):
    """GET: خواندن — POST: ذخیره."""
    if request.method == "POST":
        payload = get_payload(request)
        for key in ("store_name", "store_phone", "store_address", "currency"):
            if key in payload:
                set_setting(key, clean(payload.get(key)))
        return ok()
    return ok(
        store_name=get_setting("store_name", "") or "Tick O Time",
        store_phone=get_setting("store_phone", ""),
        store_address=get_setting("store_address", ""),
        currency=get_setting("currency", "تومان"),
        site_icon=get_setting("site_icon", ""),
    )


def api_settings_site_icon(request):
    payload = get_payload(request)
    icon = clean(payload.get("icon"))
    old = get_setting("site_icon", "")
    if icon and icon != old:
        remove_image(old)
    set_setting("site_icon", icon)
    return ok(icon=icon)