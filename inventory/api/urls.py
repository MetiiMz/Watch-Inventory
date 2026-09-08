# -*- coding: utf-8 -*-
"""مسیرهای API نسخه‌ی ۱ — زیر /api/v1/ (Router DRF).

بدون اسلش انتهایی (trailing_slash=False) تا با قرارداد API فعلی برنامه و
fetch های فرانت‌اند یکی باشد و ریدایرکت ۳۰۱ (که بدنه‌ی POST را خراب می‌کند)
رخ ندهد.
"""
from django.urls import path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter(trailing_slash=False)
router.register("products", views.ProductViewSet, basename="v1-products")
router.register("sales", views.SaleViewSet, basename="v1-sales")
router.register("payments", views.PaymentViewSet, basename="v1-payments")
router.register("repairs", views.RepairViewSet, basename="v1-repairs")
router.register("tracking", views.TrackingViewSet, basename="v1-tracking")

urlpatterns = [
    # برندها
    path("brands", views.BrandsView.as_view()),
    path("brands/delete", views.BrandsDeleteView.as_view()),

    # تنظیمات
    path("settings", views.SettingsView.as_view()),
    path("settings/site-icon", views.SiteIconView.as_view()),

    # بکاپ و پاک‌سازی
    path("backups", views.BackupsView.as_view()),
    path("backups/create", views.BackupCreateView.as_view()),
    path("backups/upload", views.BackupUploadView.as_view()),
    path("backups/restore", views.BackupRestoreView.as_view()),
    path("backups/delete", views.BackupDeleteView.as_view()),
    path("backups/download/<path:fname>", views.BackupDownloadView.as_view()),
    path("database/info", views.DatabaseInfoView.as_view()),
    path("database/clear", views.DatabaseClearView.as_view()),

    # تقویم و گزارش
    path("calendar", views.CalendarView.as_view()),
    path("calendar/day", views.CalendarDayView.as_view()),
    path("reports/monthly-activity", views.MonthlyActivityView.as_view()),

    # آپلود و ورودی/خروجی
    path("upload", views.UploadView.as_view()),
    path("import/products", views.ImportProductsView.as_view()),
    path("import/template", views.ImportTemplateView.as_view()),
    path("export/<str:kind>.<str:fmt>", views.ExportView.as_view()),
] + router.urls
