# -*- coding: utf-8 -*-
"""فیلد تاریخ شمسی — ورودی شمسی، ذخیره‌سازی ISO."""
from rest_framework import serializers

from inventory.jalali import parse_jalali_date


class JalaliDateField(serializers.CharField):
    """تاریخ را شمسی یا ISO می‌پذیرد و به‌صورت ISO ذخیره می‌کند."""

    def to_internal_value(self, data):
        value = super().to_internal_value(data)
        value = str(value or "").strip()
        if not value:
            return ""
        parsed = parse_jalali_date(value)
        if not parsed:
            raise serializers.ValidationError("تاریخ معتبر نیست")
        return parsed
