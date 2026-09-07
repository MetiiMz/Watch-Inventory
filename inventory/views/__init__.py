# -*- coding: utf-8 -*-
"""همه‌ی ویوها — urls.py از همین‌جا import می‌کند (مثل inventory.views.api_products)."""
from .pages import (  # noqa: F401
    calendar_page, dashboard, handler404, index, payments_page,
    products_page, repairs_page, settings_page, sold_page, tracking_page,
)
from .shared import (  # noqa: F401
    api_brands, api_brands_delete, api_upload, serve_image,
)
from .products import (  # noqa: F401
    api_product_detail, api_products, api_products_bulk_delete,
)
from .sales import (  # noqa: F401
    api_sale_detail, api_sales, api_sales_bulk_delete,
)
from .repairs import (  # noqa: F401
    api_repair_detail, api_repairs, api_repairs_bulk_delete, api_repair_status,
)
from .tracking import (  # noqa: F401
    api_tracking, api_tracking_bulk_delete, api_tracking_detail,
)
from .payments import (  # noqa: F401
    api_payment_add, api_payment_detail, api_payment_settle_full,
    api_payments, api_payments_bulk_delete,
)
from .calendar import api_calendar, api_calendar_day  # noqa: F401
from .dashboard_api import api_monthly_activity  # noqa: F401
from .exportimport import (  # noqa: F401
    api_import_products, api_import_template, export_file,
)
from .backups import (  # noqa: F401
    api_backups, api_backups_create, api_backups_delete, api_backups_download,
    api_backups_restore, api_backups_upload, api_database_clear, api_database_info,
)
from .settings_api import api_settings, api_settings_site_icon  # noqa: F401
