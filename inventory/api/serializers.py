# -*- coding: utf-8 -*-
"""سریالایزرهای DRF — شکل داده‌ی API نسخه‌ی ۱.

فیلدهای محاسباتی نمایشی (…_fa، …_display، …_color) دقیقاً با کلیدهای
dict-builder های inventory/utils.py یکی هستند تا مهاجرت فرانت‌اند آسان باشد.
"""
from rest_framework import serializers

from inventory.jalali import fa_num, parse_jalali_date
from inventory.models import Payment, Product, Repair, Sale, Tracking
from inventory.utils import (
    SALE_TYPE_FA, STATUS_COLOR, STATUS_FA, TRACKING_STATUS_COLOR,
    TRACKING_STATUS_FA, fa_date, fa_money, invoice_code,
)

from .fields import JalaliDateField


# ---------------------------------------------------------------- products
class ProductSerializer(serializers.ModelSerializer):
    """همان شکل product_dict — خواندنی و نوشتنی."""
    available = serializers.BooleanField(required=False)
    available_int = serializers.SerializerMethodField()
    purchase_date = JalaliDateField(required=False, allow_blank=True, allow_null=True)
    purchase_date_fa = serializers.SerializerMethodField()
    purchase_date_weekday = serializers.SerializerMethodField()
    purchase_price_display = serializers.SerializerMethodField()
    sale_price_display = serializers.SerializerMethodField()
    profit_per_unit = serializers.SerializerMethodField()
    profit_per_unit_display = serializers.SerializerMethodField()
    total_value = serializers.SerializerMethodField()
    total_value_display = serializers.SerializerMethodField()
    total_sale_value = serializers.SerializerMethodField()
    total_sale_value_display = serializers.SerializerMethodField()
    availability_fa = serializers.SerializerMethodField()
    created_at = serializers.DateTimeField(read_only=True, format="%Y-%m-%d %H:%M:%S")
    updated_at = serializers.DateTimeField(read_only=True, format="%Y-%m-%d %H:%M:%S")

    class Meta:
        model = Product
        fields = [
            "id", "name", "reference", "office_code", "website_code", "brand",
            "purchase_price", "sale_price", "available", "available_int",
            "supplier", "purchase_date", "purchase_type", "notes", "image",
            "created_at", "updated_at",
            "purchase_date_fa", "purchase_date_weekday",
            "purchase_price_display", "sale_price_display",
            "profit_per_unit", "profit_per_unit_display",
            "total_value", "total_value_display",
            "total_sale_value", "total_sale_value_display",
            "availability_fa",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_available_int(self, obj):
        return 1 if obj.available else 0

    def get_purchase_date_fa(self, obj):
        return fa_date(obj.purchase_date)

    def get_purchase_date_weekday(self, obj):
        return fa_date(obj.purchase_date, with_weekday=True)

    def get_purchase_price_display(self, obj):
        return fa_money(obj.purchase_price)

    def get_sale_price_display(self, obj):
        return fa_money(obj.sale_price)

    def get_profit_per_unit(self, obj):
        return (obj.sale_price or 0) - (obj.purchase_price or 0)

    def get_profit_per_unit_display(self, obj):
        return fa_money(self.get_profit_per_unit(obj))

    def get_total_value(self, obj):
        return obj.purchase_price or 0

    def get_total_value_display(self, obj):
        return fa_money(obj.purchase_price)

    def get_total_sale_value(self, obj):
        return obj.sale_price or 0

    def get_total_sale_value_display(self, obj):
        return fa_money(obj.sale_price)

    def get_availability_fa(self, obj):
        return "موجود" if obj.available else "ناموجود"

    def validate_office_code(self, value):
        return self._unique_code(value, "office_code")

    def validate_website_code(self, value):
        return self._unique_code(value, "website_code")

    def _unique_code(self, value, field):
        """یگانگی کدها بدون توجه به بزرگی/کوچکی حروف (مطابق ایندکس NOCASE)."""
        value = str(value or "").strip()
        qs = Product.objects.filter(**{f"{field}__iexact": value})
        if self.instance is not None:
            qs = qs.exclude(id=self.instance.id)
        if value and qs.exists():
            raise serializers.ValidationError("این کد قبلاً استفاده شده است")
        return value

    def validate_purchase_type(self, value):
        value = str(value or "person").strip()
        return value if value in SALE_TYPE_FA else "person"

    def validate_name(self, value):
        if not str(value or "").strip():
            raise serializers.ValidationError("نام ساعت الزامی است")
        return str(value).strip()


# ---------------------------------------------------------------- sales
class SaleSerializer(serializers.ModelSerializer):
    """همان شکل sale_dict — فقط خواندنی. نوشتن با SaleWriteSerializer."""
    product_id = serializers.IntegerField(source="product.pk", read_only=True)
    is_settled = serializers.SerializerMethodField()
    product_name = serializers.SerializerMethodField()
    product_image = serializers.SerializerMethodField()
    website_code = serializers.SerializerMethodField()
    office_code = serializers.SerializerMethodField()
    reference = serializers.SerializerMethodField()
    brand = serializers.SerializerMethodField()
    supplier = serializers.SerializerMethodField()
    sale_date_fa = serializers.SerializerMethodField()
    settled_at_fa = serializers.SerializerMethodField()
    sale_price_display = serializers.SerializerMethodField()
    final_price_display = serializers.SerializerMethodField()
    profit_display = serializers.SerializerMethodField()
    purchase_price_display = serializers.SerializerMethodField()
    paid_total = serializers.SerializerMethodField()
    paid_total_display = serializers.SerializerMethodField()
    paid_breakdown_fa = serializers.SerializerMethodField()
    sale_type_fa = serializers.SerializerMethodField()
    payment_type_fa = serializers.SerializerMethodField()
    customer_phone_fa = serializers.SerializerMethodField()
    invoice_code = serializers.SerializerMethodField()
    created_at = serializers.DateTimeField(read_only=True, format="%Y-%m-%d %H:%M:%S")

    class Meta:
        model = Sale
        fields = [
            "id", "product_id", "sale_price", "purchase_price", "profit",
            "sale_date", "customer", "customer_phone", "sale_type",
            "payment_type", "final_price", "paid_cash", "paid_pos",
            "paid_card2card", "is_settled", "settled_at", "notes",
            "created_at", "product_name", "product_image", "website_code",
            "office_code", "reference", "brand", "supplier",
            "sale_date_fa", "settled_at_fa", "sale_price_display",
            "final_price_display", "profit_display", "purchase_price_display",
            "paid_total", "paid_total_display", "paid_breakdown_fa",
            "sale_type_fa", "payment_type_fa", "customer_phone_fa",
            "invoice_code",
        ]
        read_only_fields = fields

    def _p(self, obj):
        return getattr(obj, "product", None)

    def get_is_settled(self, obj):
        return 1 if obj.is_settled else 0

    def get_product_name(self, obj):
        p = self._p(obj)
        return p.name if p else ""

    def get_product_image(self, obj):
        p = self._p(obj)
        return p.image if p else ""

    def get_website_code(self, obj):
        p = self._p(obj)
        return p.website_code if p else ""

    def get_office_code(self, obj):
        p = self._p(obj)
        return p.office_code if p else ""

    def get_reference(self, obj):
        p = self._p(obj)
        return p.reference if p else ""

    def get_brand(self, obj):
        p = self._p(obj)
        return p.brand if p else ""

    def get_supplier(self, obj):
        p = self._p(obj)
        return p.supplier if p else ""

    def get_sale_date_fa(self, obj):
        return fa_date(obj.sale_date)

    def get_settled_at_fa(self, obj):
        return fa_date(obj.settled_at) if obj.settled_at else ""

    def get_sale_price_display(self, obj):
        return fa_money(obj.sale_price)

    def get_final_price_display(self, obj):
        return fa_money(obj.final_price)

    def get_profit_display(self, obj):
        return fa_money(obj.profit)

    def get_purchase_price_display(self, obj):
        return fa_money(obj.purchase_price)

    def get_paid_total(self, obj):
        return (obj.paid_cash or 0) + (obj.paid_pos or 0) + (obj.paid_card2card or 0)

    def get_paid_total_display(self, obj):
        return fa_money(self.get_paid_total(obj))

    def get_paid_breakdown_fa(self, obj):
        parts = [
            f"نقدی {fa_money(obj.paid_cash)}" if obj.paid_cash else "",
            f"کارت‌خوان {fa_money(obj.paid_pos)}" if obj.paid_pos else "",
            f"کارت به کارت {fa_money(obj.paid_card2card)}" if obj.paid_card2card else "",
        ]
        return " + ".join(filter(None, parts))

    def get_sale_type_fa(self, obj):
        return SALE_TYPE_FA.get(obj.sale_type, obj.sale_type)

    def get_payment_type_fa(self, obj):
        return "بیعانه" if obj.payment_type == "deposit" else "نقدی"

    def get_customer_phone_fa(self, obj):
        return fa_num(obj.customer_phone)

    def get_invoice_code(self, obj):
        return obj.invoice_code or invoice_code(obj.id, obj.sale_date)


class SaleWriteSerializer(serializers.Serializer):
    """ورودی ثبت/ویرایش فروش — همان قواعد API قدیمی."""
    product_id = serializers.IntegerField(required=False)
    sale_price = serializers.FloatField(required=False, min_value=0)
    discount_price = serializers.FloatField(required=False, min_value=0)
    sale_date = serializers.CharField(required=False, allow_blank=True,
                                      help_text="تاریخ شمسی مثل 1404/05/12 یا ISO")
    customer = serializers.CharField(required=False, allow_blank=True)
    customer_phone = serializers.CharField(required=False, allow_blank=True)
    sale_type = serializers.CharField(required=False, default="person")
    payment_type = serializers.CharField(required=False, default="cash")
    paid_cash = serializers.FloatField(required=False, min_value=0)
    paid_pos = serializers.FloatField(required=False, min_value=0)
    paid_card2card = serializers.FloatField(required=False, min_value=0)
    invoice_code = serializers.CharField(required=False, allow_blank=True, max_length=40)
    notes = serializers.CharField(required=False, allow_blank=True)

    def validate_sale_date(self, value):
        value = str(value or "").strip()
        if not value:
            return ""
        parsed = parse_jalali_date(value)
        if not parsed:
            raise serializers.ValidationError("تاریخ فروش معتبر نیست")
        return parsed

    def validate_sale_type(self, value):
        value = str(value or "person").strip()
        return value if value in SALE_TYPE_FA else "person"

    def validate_payment_type(self, value):
        return "deposit" if str(value or "").strip() == "deposit" else "cash"


# ---------------------------------------------------------------- payments
class PaymentSerializer(serializers.ModelSerializer):
    """همان شکل payment_dict — فقط خواندنی."""
    remaining = serializers.SerializerMethodField()
    paid_percent = serializers.SerializerMethodField()
    total_amount_display = serializers.SerializerMethodField()
    paid_amount_display = serializers.SerializerMethodField()
    remaining_display = serializers.SerializerMethodField()
    pay_date_fa = serializers.SerializerMethodField()
    settled_at_fa = serializers.SerializerMethodField()
    customer_phone_fa = serializers.SerializerMethodField()
    product_image = serializers.SerializerMethodField()
    reference = serializers.SerializerMethodField()
    website_code = serializers.SerializerMethodField()
    office_code = serializers.SerializerMethodField()
    purchase_price = serializers.SerializerMethodField()
    purchase_price_display = serializers.SerializerMethodField()
    purchase_date = serializers.SerializerMethodField()
    purchase_date_fa = serializers.SerializerMethodField()
    created_at = serializers.DateTimeField(read_only=True, format="%Y-%m-%d %H:%M:%S")
    updated_at = serializers.DateTimeField(read_only=True, format="%Y-%m-%d %H:%M:%S")

    class Meta:
        model = Payment
        fields = [
            "id", "sale", "product", "product_name", "customer_name",
            "customer_phone", "total_amount", "paid_amount", "pay_date",
            "settled_at", "notes", "created_at", "updated_at",
            "remaining", "paid_percent", "total_amount_display",
            "paid_amount_display", "remaining_display", "pay_date_fa",
            "settled_at_fa", "customer_phone_fa", "product_image",
            "reference", "website_code", "office_code", "purchase_price",
            "purchase_price_display", "purchase_date", "purchase_date_fa",
        ]
        read_only_fields = fields

    def get_remaining(self, obj):
        return max(0.0, (obj.total_amount or 0) - (obj.paid_amount or 0))

    def get_paid_percent(self, obj):
        return round(100 * (obj.paid_amount / obj.total_amount)) if obj.total_amount else 0

    def get_total_amount_display(self, obj):
        return fa_money(obj.total_amount)

    def get_paid_amount_display(self, obj):
        return fa_money(obj.paid_amount)

    def get_remaining_display(self, obj):
        return fa_money(self.get_remaining(obj))

    def get_pay_date_fa(self, obj):
        return fa_date(obj.pay_date)

    def get_settled_at_fa(self, obj):
        return fa_date(obj.settled_at) if obj.settled_at else ""

    def get_customer_phone_fa(self, obj):
        return fa_num(obj.customer_phone)

    def _p(self, obj):
        return getattr(obj, "product", None)

    def get_product_image(self, obj):
        p = self._p(obj)
        return (p.image or "") if p else ""

    def get_reference(self, obj):
        p = self._p(obj)
        return (p.reference or "") if p else ""

    def get_website_code(self, obj):
        p = self._p(obj)
        return (p.website_code or "") if p else ""

    def get_office_code(self, obj):
        p = self._p(obj)
        return (p.office_code or "") if p else ""

    def get_purchase_price(self, obj):
        p = self._p(obj)
        return (p.purchase_price or 0) if p else 0

    def get_purchase_price_display(self, obj):
        return fa_money(self.get_purchase_price(obj))

    def get_purchase_date(self, obj):
        p = self._p(obj)
        return (p.purchase_date or "") if p else ""

    def get_purchase_date_fa(self, obj):
        d = self.get_purchase_date(obj)
        return fa_date(d) if d else ""


class PaymentAddSerializer(serializers.Serializer):
    """پرداخت جدید روی فقره."""
    amount = serializers.FloatField(min_value=0.01)
    pay_date = serializers.CharField(required=False, allow_blank=True)
    notes = serializers.CharField(required=False, allow_blank=True)

    def validate_pay_date(self, value):
        value = str(value or "").strip()
        if not value:
            return ""
        parsed = parse_jalali_date(value)
        if not parsed:
            raise serializers.ValidationError("تاریخ معتبر نیست")
        return parsed


# ---------------------------------------------------------------- repairs
class RepairSerializer(serializers.ModelSerializer):
    """همان شکل repair_dict — خواندنی و نوشتنی."""
    is_warranty = serializers.BooleanField(required=False)
    is_warranty_int = serializers.SerializerMethodField()
    is_warranty_fa = serializers.SerializerMethodField()
    delivery_date = JalaliDateField(required=False, allow_blank=True, allow_null=True)
    return_date = JalaliDateField(required=False, allow_blank=True, allow_null=True)
    delivery_date_fa = serializers.SerializerMethodField()
    delivery_date_weekday = serializers.SerializerMethodField()
    return_date_fa = serializers.SerializerMethodField()
    status_fa = serializers.SerializerMethodField()
    status_color = serializers.SerializerMethodField()
    repair_price_display = serializers.SerializerMethodField()
    customer_phone_fa = serializers.SerializerMethodField()
    created_at = serializers.DateTimeField(read_only=True, format="%Y-%m-%d %H:%M:%S")
    updated_at = serializers.DateTimeField(read_only=True, format="%Y-%m-%d %H:%M:%S")

    class Meta:
        model = Repair
        fields = [
            "id", "watch_name", "watch_code", "issue", "delivery_date",
            "return_date", "customer_name", "customer_phone", "is_warranty",
            "is_warranty_int", "is_warranty_fa", "status", "repair_price",
            "image", "notes", "created_at", "updated_at",
            "delivery_date_fa", "delivery_date_weekday", "return_date_fa",
            "status_fa", "status_color", "repair_price_display",
            "customer_phone_fa",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_is_warranty_int(self, obj):
        return 1 if obj.is_warranty else 0

    def get_is_warranty_fa(self, obj):
        return "بله" if obj.is_warranty else "خیر"

    def get_delivery_date_fa(self, obj):
        return fa_date(obj.delivery_date)

    def get_delivery_date_weekday(self, obj):
        return fa_date(obj.delivery_date, with_weekday=True)

    def get_return_date_fa(self, obj):
        return fa_date(obj.return_date)

    def get_status_fa(self, obj):
        return STATUS_FA.get(obj.status, obj.status)

    def get_status_color(self, obj):
        return STATUS_COLOR.get(obj.status, "gray")

    def get_repair_price_display(self, obj):
        return fa_money(obj.repair_price)

    def get_customer_phone_fa(self, obj):
        return fa_num(obj.customer_phone)

    def validate_status(self, value):
        value = str(value or "").strip()
        if value not in STATUS_FA:
            raise serializers.ValidationError("وضعیت تعمیر معتبر نیست")
        return value

    def validate_watch_name(self, value):
        if not str(value or "").strip():
            raise serializers.ValidationError("نام ساعت الزامی است")
        return str(value).strip()


# ---------------------------------------------------------------- tracking
class TrackingSerializer(serializers.ModelSerializer):
    """همان شکل tracking_dict — خواندنی و نوشتنی."""
    status_fa = serializers.SerializerMethodField()
    status_color = serializers.SerializerMethodField()
    price_display = serializers.SerializerMethodField()
    customer_phone_fa = serializers.SerializerMethodField()
    created_at = serializers.DateTimeField(read_only=True, format="%Y-%m-%d %H:%M:%S")
    updated_at = serializers.DateTimeField(read_only=True, format="%Y-%m-%d %H:%M:%S")

    class Meta:
        model = Tracking
        fields = [
            "id", "item_name", "item_code", "customer_name", "customer_phone",
            "price", "status", "notes", "image", "created_at", "updated_at",
            "price_display", "status_fa", "status_color", "customer_phone_fa",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_status_fa(self, obj):
        return TRACKING_STATUS_FA.get(obj.status, obj.status)

    def get_status_color(self, obj):
        return TRACKING_STATUS_COLOR.get(obj.status, "gray")

    def get_price_display(self, obj):
        return fa_money(obj.price)

    def get_customer_phone_fa(self, obj):
        return fa_num(obj.customer_phone)

    def validate_status(self, value):
        value = str(value or "").strip()
        if value not in TRACKING_STATUS_FA:
            raise serializers.ValidationError("وضعیت پیگیری معتبر نیست")
        return value

    def validate_item_name(self, value):
        if not str(value or "").strip():
            raise serializers.ValidationError("نام آیتم الزامی است")
        return str(value).strip()
