"""URL configuration — routes identical to the legacy Flask app."""
from django.urls import path

from inventory import views

urlpatterns = [
    path("", views.index, name="index"),
    path("dashboard", views.dashboard, name="dashboard"),
    path("products", views.products_page, name="products"),
    path("calendar", views.calendar_page, name="calendar"),
    path("repairs", views.repairs_page, name="repairs"),
    path("sold", views.sold_page, name="sold"),
    path("tracking", views.tracking_page, name="tracking"),
    path("payments", views.payments_page, name="payments"),
    path("settings", views.settings_page, name="settings"),

    # brands / upload / images
    path("api/brands", views.api_brands),
    path("api/brands/delete", views.api_brands_delete),
    path("api/upload", views.api_upload),
    path("data/images/<path:fname>", views.serve_image),

    # products
    path("api/products", views.api_products),
    path("api/products/bulk-delete", views.api_products_bulk_delete),
    path("api/products/<int:pid>", views.api_product_detail),

    # sales
    path("api/sales", views.api_sales),
    path("api/sales/bulk-delete", views.api_sales_bulk_delete),
    path("api/sales/<int:sid>", views.api_sale_detail),

    # repairs
    path("api/repairs", views.api_repairs),
    path("api/repairs/bulk-delete", views.api_repairs_bulk_delete),
    path("api/repairs/<int:rid>", views.api_repair_detail),
    path("api/repairs/<int:rid>/status", views.api_repair_status),

    # tracking
    path("api/tracking", views.api_tracking),
    path("api/tracking/bulk-delete", views.api_tracking_bulk_delete),
    path("api/tracking/<int:tid>", views.api_tracking_detail),

    # payments
    path("api/payments", views.api_payments),
    path("api/payments/bulk-delete", views.api_payments_bulk_delete),
    path("api/payments/<int:payid>", views.api_payment_detail),
    path("api/payments/<int:payid>/add", views.api_payment_add),
    path("api/payments/<int:payid>/settle-full", views.api_payment_settle_full),

    # calendar
    path("api/calendar", views.api_calendar),
    path("api/calendar/day", views.api_calendar_day),

    # export / import
    path("export/<kind>.<fmt>", views.export_file),
    path("api/import/products", views.api_import_products),
    path("api/import/template", views.api_import_template),

    # backups
    path("api/backups", views.api_backups),
    path("api/backups/create", views.api_backups_create),
    path("api/backups/upload", views.api_backups_upload),
    path("api/backups/download/<path:fname>", views.api_backups_download),
    path("api/backups/restore", views.api_backups_restore),
    path("api/backups/delete", views.api_backups_delete),

    # settings
    path("api/settings", views.api_settings),
    path("api/settings/site-icon", views.api_settings_site_icon),
]
