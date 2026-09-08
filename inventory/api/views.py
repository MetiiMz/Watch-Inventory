# -*- coding: utf-8 -*-
"""ویوهای API نسخه‌ی ۱ — لایه‌ی مستقل از فرانت‌اند.

معماری:
- خواندن (list/retrieve): DRF بومی — ViewSet + فیلتر/مرتب‌سازی/صفحه‌بندی + سریالایزر.
- نوشتن (create/update/delete): از منطق تراکنشی موجود (inventory.views) از طریق
  آداپتور `_legacy` استفاده می‌شود تا قواعد کسب‌وکار فقط یک‌جا تعریف شوند؛
  پاسخ موفق با سریالایزر DRF بازسازی می‌شود و خطاها به‌صورت استاندارد DRF
  (400/404 با body["detail"]) برمی‌گردند.
- endpoint های زیرساختی (بکاپ، تقویم، تنظیمات، آپلود، خروجی/ورودی): پاس‌ترو.
"""
import json

from django.db.models import Count, Q
from rest_framework import exceptions, status, viewsets
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from inventory.models import Payment, Product, Repair, Sale, Tracking
from inventory.views import (
    backups as legacy_backups,
    calendar as legacy_calendar,
    dashboard_api as legacy_dashboard,
    exportimport as legacy_exportimport,
    payments as legacy_payments,
    products as legacy_products,
    repairs as legacy_repairs,
    sales as legacy_sales,
    settings_api as legacy_settings,
    shared as legacy_shared,
    tracking as legacy_tracking,
)

from .serializers import (
    PaymentAddSerializer, PaymentSerializer, ProductSerializer,
    RepairSerializer, SaleSerializer, SaleWriteSerializer, TrackingSerializer,
)


class ApiError(exceptions.APIException):
    """خطای لایه‌ی منطق — با همان وضعیت و پیام API قدیمی."""

    def __init__(self, message, code):
        super().__init__(message)
        self.status_code = code


def _legacy(fn, request, *args):
    """اجرا‌ی ویوی تراکنشی موجود و تبدیل پاسخش به استاندارد DRF."""
    resp = fn(request, *args)
    if resp.status_code >= 400:
        try:
            msg = json.loads(resp.content).get("error", "")
        except (ValueError, AttributeError):
            msg = ""
        raise ApiError(msg or f"خطای سرور ({resp.status_code})", resp.status_code)
    try:
        return json.loads(resp.content)
    except ValueError:
        return {}


def _strip_ok(data):
    return {k: v for k, v in data.items() if k != "ok"}


def _complete_partial(request, obj, serializer_class, writable=None):
    """ویوهای قدیمی فقط PUT کامل می‌پذیرند؛ PATCH جزئی را با مقادیر فعلی
    شیء کامل می‌کنیم تا معنای استاندارد PATCH حفظ شود.

    serializer_class فقط-خواندنی است (Sale/Payment) یا فیلدهای نمایشی دارد؛
    برای فیلدهای نوشتنی که در سریالایزر خواندنی‌اند، نگاشت «writable» مقدار
    فعلی را مستقیم از مدل می‌خواند — وگرنه PUT قدیمی مقدار خالی می‌گرفت.
    """
    provided = request.data if isinstance(request.data, dict) else {}
    ser = serializer_class(obj)
    merged = {
        name: ser.data[name]
        for name, field in ser.fields.items()
        if not getattr(field, "read_only", False) and name not in provided
    }
    for key, getter in (writable or {}).items():
        if key not in provided and key not in merged:
            merged[key] = getter(obj)
    request._request._body = json.dumps(
        {**merged, **provided}, ensure_ascii=False).encode("utf-8")


# فیلدهای نوشتنی که در SaleSerializer فقط-خواندنی‌اند — کلیدهای PUT قدیمی
_SALE_WRITABLE = {
    "product_id": lambda o: o.product_id,
    "sale_price": lambda o: o.sale_price,
    "discount_price": lambda o: o.final_price,
    "sale_date": lambda o: o.sale_date or "",
    "customer": lambda o: o.customer or "",
    "customer_phone": lambda o: o.customer_phone or "",
    "sale_type": lambda o: o.sale_type or "person",
    "payment_type": lambda o: o.payment_type or "cash",
    "paid_cash": lambda o: o.paid_cash or 0,
    "paid_pos": lambda o: o.paid_pos or 0,
    "paid_card2card": lambda o: o.paid_card2card or 0,
    "invoice_code": lambda o: getattr(o, "invoice_code", "") or "",
    "notes": lambda o: o.notes or "",
}

# فیلدهای نوشتنی که در PaymentSerializer فقط-خواندنی‌اند
_PAYMENT_WRITABLE = {
    "product_name": lambda o: o.product_name or "",
    "customer_name": lambda o: o.customer_name or "",
    "customer_phone": lambda o: o.customer_phone or "",
    "total_amount": lambda o: o.total_amount or 0,
    "paid_amount": lambda o: o.paid_amount or 0,
    "pay_date": lambda o: o.pay_date or "",
    "notes": lambda o: o.notes or "",
}


class DefaultPagination(PageNumberPagination):
    page_size = 100
    page_size_query_param = "page_size"
    max_page_size = 1000


# ---------------------------------------------------------------- products
class ProductViewSet(viewsets.ModelViewSet):
    """CRUD محصولات. فیلترها: q، brand، available، ordering."""

    serializer_class = ProductSerializer
    pagination_class = DefaultPagination

    def get_queryset(self):
        qs = Product.objects.all()
        p = self.request.query_params
        q = (p.get("q") or "").strip()
        if q:
            qs = qs.filter(Q(name__icontains=q) | Q(office_code__icontains=q)
                           | Q(website_code__icontains=q))
        brand = (p.get("brand") or "").strip()
        if brand:
            qs = qs.filter(brand=brand)
        avail = (p.get("available") or "").lower()
        if avail in ("1", "true"):
            qs = qs.filter(available=True)
        elif avail in ("0", "false"):
            qs = qs.filter(available=False)
        ordering = (p.get("ordering") or "").strip()
        allowed = {"id", "name", "purchase_price", "sale_price", "purchase_date"}
        if ordering:
            fields = [f for f in ordering.split(",") if f.lstrip("-") in allowed]
            if fields:
                return qs.order_by(*fields)
        return qs.order_by("-id")  # ترتیب پایدار برای صفحه‌بندی

    def create(self, request, *args, **kwargs):
        data = _legacy(legacy_products.api_products, request)
        obj = Product.objects.get(id=data["product"]["id"])
        return Response(self.get_serializer(obj).data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        obj = self.get_object()
        _complete_partial(request, obj, ProductSerializer)
        request.method = "PUT"  # ویوی قدیمی فقط PUT را ویرایش می‌داند
        _legacy(legacy_products.api_product_detail, request, obj.id)
        obj.refresh_from_db()
        return Response(self.get_serializer(obj).data)

    def destroy(self, request, *args, **kwargs):
        obj = self.get_object()
        _legacy(legacy_products.api_product_detail, request, obj.id)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=["post"], url_path="bulk-delete")
    def bulk_delete(self, request):
        return Response(_strip_ok(_legacy(legacy_products.api_products_bulk_delete, request)))

    @action(detail=False, methods=["get"])
    def summary(self, request):
        agg = Product.objects.aggregate(
            count=Count("id"),
            available=Count("id", filter=Q(available=True)),
        )
        return Response(agg)


# ---------------------------------------------------------------- sales
class SaleViewSet(viewsets.ModelViewSet):
    """فروش‌ها. فیلترها: q (مشتری/فاکتور)، settled، product_id، ordering."""

    serializer_class = SaleSerializer
    pagination_class = DefaultPagination
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self):
        qs = Sale.objects.select_related("product").all()
        p = self.request.query_params
        q = (p.get("q") or "").strip()
        if q:
            qs = qs.filter(Q(customer__icontains=q) | Q(invoice_code__icontains=q))
        settled = (p.get("settled") or "").lower()
        if settled in ("1", "true"):
            qs = qs.filter(is_settled=True)
        elif settled in ("0", "false"):
            qs = qs.filter(is_settled=False)
        pid = p.get("product_id")
        if pid:
            qs = qs.filter(product_id=pid)
        ordering = (p.get("ordering") or "").strip()
        allowed = {"id", "sale_date", "sale_price", "created_at"}
        if ordering:
            fields = [f for f in ordering.split(",") if f.lstrip("-") in allowed]
            if fields:
                return qs.order_by(*fields)
        return qs.order_by("-id")  # ترتیب پایدار برای صفحه‌بندی

    def create(self, request, *args, **kwargs):
        SaleWriteSerializer(data=request.data).is_valid(raise_exception=True)
        data = _legacy(legacy_sales.api_sales, request)
        obj = Sale.objects.get(id=data["sale"]["id"])
        return Response(self.get_serializer(obj).data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        obj = self.get_object()
        SaleWriteSerializer(data=request.data, partial=True).is_valid(raise_exception=True)
        _complete_partial(request, obj, SaleSerializer, writable=_SALE_WRITABLE)
        request.method = "PUT"  # ویوی قدیمی فقط PUT را ویرایش می‌داند
        _legacy(legacy_sales.api_sale_detail, request, obj.id)
        obj.refresh_from_db()
        return Response(self.get_serializer(obj).data)

    def destroy(self, request, *args, **kwargs):
        obj = self.get_object()
        _legacy(legacy_sales.api_sale_detail, request, obj.id)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=["post"], url_path="bulk-delete")
    def bulk_delete(self, request):
        return Response(_strip_ok(_legacy(legacy_sales.api_sales_bulk_delete, request)))


# ---------------------------------------------------------------- payments
class PaymentViewSet(viewsets.GenericViewSet):
    """فقره‌های پرداخت. فیلترها: sale_id، settled، q. تغییرها از منطق موجود."""

    serializer_class = PaymentSerializer
    pagination_class = DefaultPagination

    def get_queryset(self):
        qs = Payment.objects.select_related("sale__product").all()
        p = self.request.query_params
        sale_id = p.get("sale_id")
        if sale_id:
            qs = qs.filter(sale_id=sale_id)
        q = (p.get("q") or "").strip()
        if q:
            qs = qs.filter(Q(sale__customer__icontains=q)
                           | Q(sale__invoice_code__icontains=q))
        return qs.order_by("-id")

    def list(self, request, *args, **kwargs):
        page = self.paginate_queryset(self.get_queryset())
        return self.get_paginated_response(self.get_serializer(page, many=True).data)

    def retrieve(self, request, *args, **kwargs):
        return Response(self.get_serializer(self.get_object()).data)

    def create(self, request, *args, **kwargs):
        data = _legacy(legacy_payments.api_payments, request)
        obj = Payment.objects.get(id=data["payment"]["id"])
        return Response(self.get_serializer(obj).data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        obj = self.get_object()
        _complete_partial(request, obj, PaymentSerializer, writable=_PAYMENT_WRITABLE)
        request.method = "PUT"  # ویوی قدیمی فقط PUT را ویرایش می‌داند
        _legacy(legacy_payments.api_payment_detail, request, obj.id)
        obj.refresh_from_db()
        return Response(self.get_serializer(obj).data)

    partial_update = update  # PATCH همان PUT است (پارشال با _complete_partial)

    def destroy(self, request, *args, **kwargs):
        obj = self.get_object()
        _legacy(legacy_payments.api_payment_detail, request, obj.id)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["post"])
    def add(self, request, pk=None):
        PaymentAddSerializer(data=request.data).is_valid(raise_exception=True)
        data = _legacy(legacy_payments.api_payment_add, request, int(pk))
        obj = Payment.objects.get(id=data["payment"]["id"])
        return Response(self.get_serializer(obj).data)

    @action(detail=True, methods=["post"], url_path="settle-full")
    def settle_full(self, request, pk=None):
        _legacy(legacy_payments.api_payment_settle_full, request, int(pk))
        obj = Payment.objects.get(id=int(pk))
        return Response(self.get_serializer(obj).data)

    @action(detail=False, methods=["post"], url_path="bulk-delete")
    def bulk_delete(self, request):
        return Response(_strip_ok(_legacy(legacy_payments.api_payments_bulk_delete, request)))


# ---------------------------------------------------------------- repairs
class RepairViewSet(viewsets.GenericViewSet):
    """تعمیرات. فیلترها: status، q."""

    serializer_class = RepairSerializer
    pagination_class = DefaultPagination

    def get_queryset(self):
        qs = Repair.objects.all()
        p = self.request.query_params
        st = (p.get("status") or "").strip()
        if st:
            qs = qs.filter(status=st)
        q = (p.get("q") or "").strip()
        if q:
            qs = qs.filter(Q(customer_name__icontains=q)
                           | Q(device_name__icontains=q)
                           | Q(problem__icontains=q))
        return qs.order_by("-id")

    def list(self, request, *args, **kwargs):
        page = self.paginate_queryset(self.get_queryset())
        return self.get_paginated_response(self.get_serializer(page, many=True).data)

    def retrieve(self, request, *args, **kwargs):
        return Response(self.get_serializer(self.get_object()).data)

    def create(self, request, *args, **kwargs):
        data = _legacy(legacy_repairs.api_repairs, request)
        obj = Repair.objects.get(id=data["repair"]["id"])
        return Response(self.get_serializer(obj).data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        obj = self.get_object()
        _complete_partial(request, obj, RepairSerializer)
        request.method = "PUT"  # ویوی قدیمی فقط PUT را ویرایش می‌داند
        _legacy(legacy_repairs.api_repair_detail, request, obj.id)
        obj.refresh_from_db()
        return Response(self.get_serializer(obj).data)

    partial_update = update  # PATCH همان PUT است (پارشال با _complete_partial)

    def destroy(self, request, *args, **kwargs):
        obj = self.get_object()
        _legacy(legacy_repairs.api_repair_detail, request, obj.id)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["post"], url_path="set-status")
    def set_status(self, request, pk=None):
        _legacy(legacy_repairs.api_repair_status, request, int(pk))
        obj = Repair.objects.get(id=int(pk))
        return Response(self.get_serializer(obj).data)

    @action(detail=False, methods=["post"], url_path="bulk-delete")
    def bulk_delete(self, request):
        return Response(_strip_ok(_legacy(legacy_repairs.api_repairs_bulk_delete, request)))


# ---------------------------------------------------------------- tracking
class TrackingViewSet(viewsets.GenericViewSet):
    """پیگیری‌ها. فیلترها: status، q."""

    serializer_class = TrackingSerializer
    pagination_class = DefaultPagination

    def get_queryset(self):
        qs = Tracking.objects.all()
        p = self.request.query_params
        st = (p.get("status") or "").strip()
        if st:
            qs = qs.filter(status=st)
        q = (p.get("q") or "").strip()
        if q:
            qs = qs.filter(Q(customer_name__icontains=q)
                           | Q(item_name__icontains=q)
                           | Q(item_code__icontains=q))
        return qs.order_by("-id")

    def list(self, request, *args, **kwargs):
        page = self.paginate_queryset(self.get_queryset())
        return self.get_paginated_response(self.get_serializer(page, many=True).data)

    def retrieve(self, request, *args, **kwargs):
        return Response(self.get_serializer(self.get_object()).data)

    def create(self, request, *args, **kwargs):
        data = _legacy(legacy_tracking.api_tracking, request)
        obj = Tracking.objects.get(id=data["tracking"]["id"])
        return Response(self.get_serializer(obj).data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        obj = self.get_object()
        _complete_partial(request, obj, TrackingSerializer)
        request.method = "PUT"  # ویوی قدیمی فقط PUT را ویرایش می‌داند
        _legacy(legacy_tracking.api_tracking_detail, request, obj.id)
        obj.refresh_from_db()
        return Response(self.get_serializer(obj).data)

    partial_update = update  # PATCH همان PUT است (پارشال با _complete_partial)

    def destroy(self, request, *args, **kwargs):
        obj = self.get_object()
        _legacy(legacy_tracking.api_tracking_detail, request, obj.id)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=["post"], url_path="bulk-delete")
    def bulk_delete(self, request):
        return Response(_strip_ok(_legacy(legacy_tracking.api_tracking_bulk_delete, request)))


# ---------------------------------------------------------------- infra
# endpoint های زیرساختی — پاس‌ترو به منطق موجود (همان شکل پاسخ ok(...))
class BrandsView(APIView):
    def get(self, request):
        return legacy_shared.api_brands(request)

    def post(self, request):
        return legacy_shared.api_brands(request)


class BrandsDeleteView(APIView):
    def post(self, request):
        return legacy_shared.api_brands_delete(request)


class SettingsView(APIView):
    def get(self, request):
        return legacy_settings.api_settings(request)

    def post(self, request):
        return legacy_settings.api_settings(request)


class SiteIconView(APIView):
    def post(self, request):
        return legacy_settings.api_settings_site_icon(request)


class BackupsView(APIView):
    def get(self, request):
        return legacy_backups.api_backups(request)


class BackupCreateView(APIView):
    def post(self, request):
        return legacy_backups.api_backups_create(request)


class BackupUploadView(APIView):
    def post(self, request):
        return legacy_backups.api_backups_upload(request)


class BackupRestoreView(APIView):
    def post(self, request):
        return legacy_backups.api_backups_restore(request)


class BackupDeleteView(APIView):
    def post(self, request):
        return legacy_backups.api_backups_delete(request)


class BackupDownloadView(APIView):
    def get(self, request, fname):
        return legacy_backups.api_backups_download(request, fname)


class DatabaseInfoView(APIView):
    def get(self, request):
        return legacy_backups.api_database_info(request)


class DatabaseClearView(APIView):
    def post(self, request):
        return legacy_backups.api_database_clear(request)


class CalendarView(APIView):
    def get(self, request):
        return legacy_calendar.api_calendar(request)


class CalendarDayView(APIView):
    def get(self, request):
        return legacy_calendar.api_calendar_day(request)


class MonthlyActivityView(APIView):
    def get(self, request):
        return legacy_dashboard.api_monthly_activity(request)


class UploadView(APIView):
    def post(self, request):
        return legacy_shared.api_upload(request)


class ImportProductsView(APIView):
    def post(self, request):
        return legacy_exportimport.api_import_products(request)


class ImportTemplateView(APIView):
    def get(self, request):
        return legacy_exportimport.api_import_template(request)


class ExportView(APIView):
    def get(self, request, kind, fmt):
        return legacy_exportimport.export_file(request, kind, fmt)



