# -*- coding: utf-8 -*-
"""Versioned API views — Django REST Framework under ``/api/v1/``.

Architecture (the backend's main core):

* **Reads** go straight through the QuerySets built in
  :mod:`inventory.api.services` and are serialized with DRF serializers.
* **Writes** call the transactional service functions so business rules
  (deposit receipts, stock flips, settlement sync, cascade deletes,
  invoice codes) exist in exactly one place.
* :class:`ApiError` raised by a service is rendered as a standard DRF
  error — ``{"error": "<persian message>"}`` with the original status
  code — which is also the shape ``static/js/app.js`` displays.
* Legacy-shape endpoints (same JSON as the old function-based views) are
  thin adapters in :mod:`inventory.api.compat`; they call the very same
  service functions.
"""
import os
import sqlite3
from urllib.parse import quote

from django.db import close_old_connections
from django.db.models import Count, Q
from django.http import FileResponse
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from inventory.api import services
from inventory.api.serializers import (
    PaymentSerializer, ProductSerializer, RepairSerializer, SaleSerializer,
    TrackingSerializer,
)
from inventory.dbhelpers import (
    backup_db, clear_database, count_records, delete_backup, list_backups,
    restore_db,
)
from inventory.models import Product


class DefaultPagination(PageNumberPagination):
    """Page-number pagination (``?page`` / ``?page_size``, default 100)."""

    page_size = 100
    page_size_query_param = "page_size"
    max_page_size = 1000


# ---------------------------------------------------------------- products
class ProductViewSet(viewsets.ModelViewSet):
    """Inventory CRUD.

    Filters: ``q``, ``brand``, ``status`` (``available``/``unavailable``),
    ``date_from``/``date_to``, ``sort`` + ``dir``, ``ordering``.
    """

    serializer_class = ProductSerializer
    pagination_class = DefaultPagination

    def get_queryset(self):
        p = self.request.query_params
        qs = services.product_queryset(p)
        ordering = (p.get("ordering") or "").strip()
        allowed = {"id", "name", "purchase_price", "sale_price", "purchase_date"}
        if ordering:
            fields = [f for f in ordering.split(",") if f.lstrip("-") in allowed]
            if fields:
                return qs.order_by(*fields)
        return qs.order_by("-id")  # stable order for pagination

    def create(self, request, *args, **kwargs):
        """POST /api/v1/products — validated/created by the service layer."""
        product = services.create_product(request.data)
        return Response(
            self.get_serializer(product).data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        """PUT/PATCH /api/v1/products/<id>/ — partial-aware product edit."""
        product = self.get_object()
        services.update_product(
            product, request.data,
            partial=request.method == "PATCH")
        product.refresh_from_db()
        return Response(self.get_serializer(product).data)

    def destroy(self, request, *args, **kwargs):
        """DELETE /api/v1/products/<id>/ — deletes the watch and its image."""
        services.delete_product(self.get_object())
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=["post"], url_path="bulk-delete")
    def bulk_delete(self, request):
        """POST /api/v1/products/bulk-delete — ``{"ids": [...]}``."""
        deleted = services.bulk_delete_products((request.data or {}).get("ids"))
        return Response({"deleted": deleted})

    @action(detail=False, methods=["get"])
    def summary(self, request):
        """GET /api/v1/products/summary — total and in-stock counts."""
        agg = Product.objects.aggregate(
            count=Count("id"),
            available=Count("id", filter=Q(available=True)),
        )
        return Response(agg)


# ---------------------------------------------------------------- sales
class SaleViewSet(viewsets.ModelViewSet):
    """Sales CRUD (cash and deposit).

    Filters: ``q``, ``sale_type``, ``pay_method``, ``date_from``/``date_to``,
    ``sort`` + ``dir``, ``ordering``, plus ``next_code=1`` on the list for
    an invoice-code preview.
    """

    serializer_class = SaleSerializer
    pagination_class = DefaultPagination
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self):
        return services.sale_queryset(self.request.query_params)

    def list(self, request, *args, **kwargs):
        if (request.query_params.get("next_code") or "").strip():
            return Response({"next_invoice_code": services.next_invoice_code()})
        return super().list(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        """POST /api/v1/sales — transactional sale + deposit receipt."""
        sale = services.create_sale(request.data)
        return Response(
            self.get_serializer(sale).data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        """PUT/PATCH /api/v1/sales/<id>/ — partial-aware sale edit."""
        sale = self.get_object()
        services.update_sale(sale, request.data)
        sale.refresh_from_db()
        return Response(self.get_serializer(sale).data)

    def destroy(self, request, *args, **kwargs):
        """DELETE /api/v1/sales/<id>/ — the watch becomes available again."""
        services.delete_sale(self.get_object())
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=["post"], url_path="bulk-delete")
    def bulk_delete(self, request):
        """POST /api/v1/sales/bulk-delete — ``{"ids": [...]}``."""
        deleted = services.bulk_delete_sales((request.data or {}).get("ids"))
        return Response({"deleted": deleted})


# ---------------------------------------------------------------- payments
class PaymentViewSet(viewsets.ModelViewSet):
    """Payment records (deposit receipts and standalone installments).

    Filters: ``status`` (``unpaid``/``paid``), ``q``, ``sale_id``,
    ``ordering``.
    """

    serializer_class = PaymentSerializer
    pagination_class = DefaultPagination

    def get_queryset(self):
        qs = services.payment_queryset(self.request.query_params)
        sale_id = self.request.query_params.get("sale_id")
        if sale_id:
            qs = qs.filter(sale_id=sale_id)
        return qs

    def create(self, request, *args, **kwargs):
        """POST /api/v1/payments — create a standalone payment record."""
        payment = services.create_payment(request.data)
        return Response(
            self.get_serializer(payment).data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        """PUT/PATCH /api/v1/payments/<id>/ — re-evaluates settlement."""
        payment = self.get_object()
        services.update_payment(
            payment, request.data,
            partial=request.method == "PATCH")
        payment.refresh_from_db()
        return Response(self.get_serializer(payment).data)

    def destroy(self, request, *args, **kwargs):
        """DELETE /api/v1/payments/<id>/."""
        services.delete_payment(self.get_object())
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["post"])
    def add(self, request, pk=None):
        """POST /api/v1/payments/<id>/add — pay an installment amount."""
        payment = services.add_payment(self.get_object(), request.data)
        return Response(self.get_serializer(payment).data)

    @action(detail=True, methods=["post"], url_path="settle-full")
    def settle_full(self, request, pk=None):
        """POST /api/v1/payments/<id>/settle-full — settle the whole balance."""
        payment = services.settle_payment_full(self.get_object())
        return Response(self.get_serializer(payment).data)

    @action(detail=False, methods=["post"], url_path="bulk-delete")
    def bulk_delete(self, request):
        """POST /api/v1/payments/bulk-delete — ``{"ids": [...]}``."""
        deleted = services.bulk_delete_payments((request.data or {}).get("ids"))
        return Response({"deleted": deleted})


# ---------------------------------------------------------------- repairs
class RepairViewSet(viewsets.ModelViewSet):
    """Repair tickets. Filters: ``status``, ``q``, ``ordering``."""

    serializer_class = RepairSerializer
    pagination_class = DefaultPagination

    def get_queryset(self):
        return services.repair_queryset(self.request.query_params)

    def create(self, request, *args, **kwargs):
        """POST /api/v1/repairs."""
        repair = services.create_repair(request.data)
        return Response(
            self.get_serializer(repair).data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        """PUT/PATCH /api/v1/repairs/<id>/."""
        repair = self.get_object()
        services.update_repair(
            repair, request.data,
            partial=request.method == "PATCH")
        repair.refresh_from_db()
        return Response(self.get_serializer(repair).data)

    def destroy(self, request, *args, **kwargs):
        """DELETE /api/v1/repairs/<id>/ — removes the image file too."""
        services.delete_repair(self.get_object())
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["post"], url_path="set-status")
    def set_status(self, request, pk=None):
        """POST /api/v1/repairs/<id>/set-status — status flow + return date."""
        repair = services.set_repair_status(self.get_object(), request.data)
        return Response(self.get_serializer(repair).data)

    @action(detail=False, methods=["post"], url_path="bulk-delete")
    def bulk_delete(self, request):
        """POST /api/v1/repairs/bulk-delete — ``{"ids": [...]}``."""
        deleted = services.bulk_delete_repairs((request.data or {}).get("ids"))
        return Response({"deleted": deleted})


# ---------------------------------------------------------------- tracking
class TrackingViewSet(viewsets.ModelViewSet):
    """Order tracking. Filters: ``status``, ``q``, ``ordering``."""

    serializer_class = TrackingSerializer
    pagination_class = DefaultPagination

    def get_queryset(self):
        return services.tracking_queryset(self.request.query_params)

    def create(self, request, *args, **kwargs):
        """POST /api/v1/tracking."""
        tracking = services.create_tracking(request.data)
        return Response(
            self.get_serializer(tracking).data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        """PUT/PATCH /api/v1/tracking/<id>/."""
        tracking = self.get_object()
        services.update_tracking(
            tracking, request.data,
            partial=request.method == "PATCH")
        tracking.refresh_from_db()
        return Response(self.get_serializer(tracking).data)

    def destroy(self, request, *args, **kwargs):
        """DELETE /api/v1/tracking/<id>/ — removes the image file too."""
        services.delete_tracking(self.get_object())
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=["post"], url_path="bulk-delete")
    def bulk_delete(self, request):
        """POST /api/v1/tracking/bulk-delete — ``{"ids": [...]}``."""
        deleted = services.bulk_delete_tracking((request.data or {}).get("ids"))
        return Response({"deleted": deleted})


# ---------------------------------------------------------------- infra
class BrandsView(APIView):
    """GET lists brands; POST adds one (``{name}``)."""

    def get(self, request):
        return Response({"ok": True, "brands": services.brands_list()})

    def post(self, request):
        services.brands_add(request.data or {})
        return Response({"ok": True})


class BrandsDeleteView(APIView):
    """POST /brands/delete — remove a brand (``{name}``)."""

    def post(self, request):
        services.brands_delete(request.data or {})
        return Response({"ok": True})


class SettingsView(APIView):
    """GET returns store settings; POST persists the whitelisted keys."""

    def get(self, request):
        return Response({"ok": True, **services.site_settings()})

    def post(self, request):
        services.save_settings(request.data or {})
        return Response({"ok": True})


class SiteIconView(APIView):
    """POST /settings/site-icon — ``{icon: "<filename>"}``."""

    def post(self, request):
        icon = services.set_site_icon((request.data or {}).get("icon"))
        return Response({"ok": True, "icon": icon})


class UploadView(APIView):
    """POST image/icon upload (JSON base64 or multipart) → ``{path}``."""

    def post(self, request):
        return Response({"ok": True, "path": services.save_upload(request)})


class CalendarView(APIView):
    """GET /calendar?jy=&jm= — one Jalali month laid out on the grid."""

    def get(self, request):
        data = services.calendar_month(
            request.query_params.get("jy"), request.query_params.get("jm"))
        return Response({"ok": True, **data})


class CalendarDayView(APIView):
    """GET /calendar/day?date=YYYY-MM-DD — full detail of one day."""

    def get(self, request):
        data = services.calendar_day(request.query_params.get("date"))
        return Response({"ok": True, **data})


class MonthlyActivityView(APIView):
    """GET /reports/monthly-activity?year=<jy> — 12 months for the chart."""

    def get(self, request):
        year, months = services.monthly_activity(request.query_params.get("year"))
        return Response({"ok": True, "year": year, "months": months})


class ExportView(APIView):
    """GET /export/<kind>.<fmt> — Excel/CSV download (kind×fmt validated)."""

    def get(self, request, kind, fmt):
        path, name = services.export_data_file(kind, fmt)
        mime = ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                if fmt == "xlsx" else "text/csv")
        quoted = quote(name)
        resp = FileResponse(open(path, "rb"), content_type=mime)
        resp["Content-Disposition"] = (
            f"attachment; filename=\"{quoted}\"; filename*=UTF-8''{quoted}")
        return resp


class ImportProductsView(APIView):
    """POST product import (multipart ``file`` + optional ``update_existing``)."""

    def post(self, request):
        f = request.FILES.get("file")
        if not f or not f.name:
            raise services.ApiError(400, "فایلی انتخاب نشده است")
        update_existing = request.POST.get("update_existing") == "1"
        stats, errors = services.import_products_file(f, update_existing)
        return Response({"ok": True, "stats": stats, "errors": errors})


class ImportTemplateView(APIView):
    """GET /import/template — the Excel import template download."""

    def get(self, request):
        path, name = services.import_template_file()
        quoted = quote(name)
        resp = FileResponse(
            open(path, "rb"),
            content_type="application/vnd.openxmlformats-officedocument"
                         ".spreadsheetml.sheet")
        resp["Content-Disposition"] = (
            f"attachment; filename=\"{quoted}\"; filename*=UTF-8''{quoted}")
        return resp


class BackupsView(APIView):
    """GET lists available database backups."""

    def get(self, request):
        return Response({"ok": True, "backups": list_backups()})


class BackupCreateView(APIView):
    """POST creates a database backup → ``{name}``."""

    def post(self, request):
        close_old_connections()
        target = backup_db()
        return Response({"ok": True, "name": os.path.basename(target)})


class BackupUploadView(APIView):
    """POST uploads a ``.db`` backup file for later restore."""

    def post(self, request):
        from django.conf import settings as dj_settings
        f = request.FILES.get("file")
        if not f or not f.name:
            raise services.ApiError(400, "فایلی انتخاب نشده است")
        fname = os.path.basename(f.name)
        if not fname.endswith(".db"):
            fname += ".db"
        backup_dir = str(dj_settings.BACKUP_DIR)
        os.makedirs(backup_dir, exist_ok=True)
        target = os.path.join(backup_dir, fname)
        with open(target, "wb") as out:
            for chunk in f.chunks():
                out.write(chunk)
        try:
            conn = sqlite3.connect(target)
            conn.execute("SELECT COUNT(*) FROM products")
            conn.close()
        except sqlite3.Error:
            os.remove(target)
            raise services.ApiError(
                400, "فایل انتخاب‌شده یک نسخه‌ی پشتیبان معتبر TikoTime نیست")
        return Response({"ok": True, "name": fname})


class BackupRestoreView(APIView):
    """POST restores a backup (``{name}``); auto-backs up first."""

    def post(self, request):
        close_old_connections()
        good, err = restore_db((request.data or {}).get("name"))
        if not good:
            raise services.ApiError(400, err)
        return Response({"ok": True})


class BackupDeleteView(APIView):
    """POST deletes a backup file (``{name}``)."""

    def post(self, request):
        good, err = delete_backup((request.data or {}).get("name"))
        if not good:
            raise services.ApiError(400, err)
        return Response({"ok": True})


class BackupDownloadView(APIView):
    """GET /backups/download/<fname> — attachment download."""

    def get(self, request, fname):
        from django.conf import settings as dj_settings
        safe = os.path.basename(fname)
        path = os.path.join(str(dj_settings.BACKUP_DIR), safe)
        if not os.path.isfile(path):
            raise services.ApiError(404, "یافت نشد")
        resp = FileResponse(open(path, "rb"), content_type="application/octet-stream")
        resp["Content-Disposition"] = f'attachment; filename="{safe}"'
        return resp


class DatabaseInfoView(APIView):
    """GET /database/info — per-table record counts (clear preview)."""

    def get(self, request):
        return Response({"ok": True, "counts": count_records()})


class DatabaseClearView(APIView):
    """POST /database/clear — wipe data for a new period (auto backup first)."""

    def post(self, request):
        close_old_connections()
        counts = clear_database()
        return Response({"ok": True, "cleared": counts})
