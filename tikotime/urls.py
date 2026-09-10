# -*- coding: utf-8 -*-
"""URL configuration.

Three kinds of routes:

* ``/dashboard``, ``/products`` … — HTML page shells (``inventory.views.pages``);
* ``/api/v1/`` — the main DRF API (versioned, the backend's core contract);
* ``/api/*``, ``/export/*``, ``/data/images/*`` — legacy-shape endpoints
  (``inventory.api.compat``) that the current frontend calls; they share
  the same service layer and will keep working until the frontend moves
  to ``/api/v1/``.
"""
from django.urls import include, path

from inventory.api import compat
from inventory import views

urlpatterns = [
    # ------------------------------------------------- pages (HTML shells)
    path("", views.index, name="index"),
    path("dashboard", views.dashboard, name="dashboard"),
    path("products", views.products_page, name="products"),
    path("calendar", views.calendar_page, name="calendar"),
    path("repairs", views.repairs_page, name="repairs"),
    path("sold", views.sold_page, name="sold"),
    path("tracking", views.tracking_page, name="tracking"),
    path("payments", views.payments_page, name="payments"),
    path("settings", views.settings_page, name="settings"),

    # --------------------------------- legacy-shape API (frontend contract)
    # brands / upload / images
    path("api/brands", compat.api_brands),
    path("api/brands/delete", compat.api_brands_delete),
    path("api/upload", compat.api_upload),
    path("data/images/<path:fname>", compat.serve_image),

    # products
    path("api/products", compat.api_products),
    path("api/products/bulk-delete", compat.api_products_bulk_delete),
    path("api/products/<int:pid>", compat.api_product_detail),

    # sales
    path("api/sales", compat.api_sales),
    path("api/sales/bulk-delete", compat.api_sales_bulk_delete),
    path("api/sales/<int:sid>", compat.api_sale_detail),

    # repairs
    path("api/repairs", compat.api_repairs),
    path("api/repairs/bulk-delete", compat.api_repairs_bulk_delete),
    path("api/repairs/<int:rid>", compat.api_repair_detail),
    path("api/repairs/<int:rid>/status", compat.api_repair_status),

    # tracking
    path("api/tracking", compat.api_tracking),
    path("api/tracking/bulk-delete", compat.api_tracking_bulk_delete),
    path("api/tracking/<int:tid>", compat.api_tracking_detail),

    # payments
    path("api/payments", compat.api_payments),
    path("api/payments/bulk-delete", compat.api_payments_bulk_delete),
    path("api/payments/<int:payid>", compat.api_payment_detail),
    path("api/payments/<int:payid>/add", compat.api_payment_add),
    path("api/payments/<int:payid>/settle-full", compat.api_payment_settle_full),

    # calendar
    path("api/calendar", compat.api_calendar),
    path("api/calendar/day", compat.api_calendar_day),

    # dashboard chart
    path("api/reports/monthly-activity", compat.api_monthly_activity),

    # export / import
    path("export/<kind>.<fmt>", compat.export_file),
    path("api/import/products", compat.api_import_products),
    path("api/import/template", compat.api_import_template),

    # backups
    path("api/backups", compat.api_backups),
    path("api/backups/create", compat.api_backups_create),
    path("api/backups/upload", compat.api_backups_upload),
    path("api/backups/download/<path:fname>", compat.api_backups_download),
    path("api/backups/restore", compat.api_backups_restore),
    path("api/backups/delete", compat.api_backups_delete),

    # database clear — new-period reset
    path("api/database/info", compat.api_database_info),
    path("api/database/clear", compat.api_database_clear),

    # settings
    path("api/settings", compat.api_settings),
    path("api/settings/site-icon", compat.api_settings_site_icon),

    # ------------------------------------------------- versioned DRF API
    path("api/v1/", include("inventory.api.urls")),
]
