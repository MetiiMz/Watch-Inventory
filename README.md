# TikoTime — سیستم مدیریت انبار فروشگاه ساعت

سیستم کامل مدیریت انبار، فروش، تعمیرات و سفارش‌های فروشگاه ساعت — کاملاً محلی، آفلاین، فارسی و با تقویم شمسی.

> **نسخه‌ی فعلی روی Django 5.2 + Django REST Framework بازنویسی شده است.** بک‌اند کاملاً API‌محور است: همه‌ی منطق کسب‌وکار در لایه‌ی سرویس (`inventory/api/services.py`) جمع شده و از طریق DRF در `/api/v1/` ارائه می‌شود. فرانت‌اند (قالب‌ها و JS) دست‌نخورده باقی مانده و فعلاً از همان مسیرهای `/api/*` (آداپتورهای `inventory/api/compat.py` با همان شکل پاسخ قدیمی) استفاده می‌کند — هر دو لایه از یک منطق مشترک بهره می‌برند. کد قدیمی Flask به‌طور کامل حذف شده است.

---

## معماری بک‌اند (API-first)

```
inventory/api/
├── services.py     # تمام قواعد کسب‌وکار (اعتبارسنجی + نوشتن‌های تراکنشی) — تک منبع حقیقت
├── serializers.py  # سریالایزرهای DRF (شکل خواندن داده‌ها)
├── views.py        # ViewSet های CRUD + ویوهای زیرساختی (زیر /api/v1/)
├── urls.py         # روتر DRF با trailing_slash=False
├── exceptions.py   # تبدیل ApiError به پاسخ استاندارد DRF
├── fields.py       # فیلد تاریخ شمسی
└── compat.py       # آداپتورهای /api/* با شکل پاسخ قدیمی (بدون منطق)
```

- **`/api/v1/`** — API اصلی و نسخه‌بندی‌شده (CRUD کامل محصولات/فروش‌ها/فقره‌ها/تعمیرات/پیگیری‌ها، تقویم، بکاپ، تنظیمات، خروجی/ورودی).
- **`/api/*`** — همان مسیرهایی که فرانت‌اند فعلی صدا می‌زند؛ فقط آداپتور نازک روی `services.py` هستند و تا مهاجرت فرانت‌اند به `/api/v1/` باقی می‌مانند.


## اجرا

### پیش‌نیازها
- پایتون ۳.۱۰ یا بالاتر (تا نسخه‌ی ۳.۱۴ تست شده) — اگر نصب نیست از [python.org](https://www.python.org/downloads/) بگیرید. در ویندوز حتماً گزینه‌ی «Add Python to PATH» را تیک بزنید.
- بقیه‌ی پیش‌نیازها داخل `requirements.txt` هستند: Django، Jinja2، gunicorn، whitenoise و openpyxl.

### نصب (فقط بار اول)

**لینوکس / مک:**
```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python manage.py migrate
```

**ویندوز (در PowerShell یا CMD داخل پوشه‌ی پروژه):**
```bat
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python manage.py migrate
```

### اجرا

**لینوکس / مک:**
```bash
.venv/bin/python manage.py runserver
```

**ویندوز:**
```bat
.venv\Scripts\python manage.py runserver
```

سپس در مرورگر باز کنید: **http://127.0.0.1:8000**

> بعد از اولین اجرا، همه‌چیز کاملاً آفلاین کار می‌کند و به اینترنت نیازی نیست.

### اجرا در حالت تولید (سرور)

```bash
.venv/bin/python manage.py collectstatic --noinput
.venv/bin/gunicorn tikotime.wsgi -b 0.0.0.0:8000
```

این دستور با وب‌سرور آماده‌ی production (gunicorn + whitenoise) بالا می‌آید و برای systemd یا Docker مناسب است.

### متغیرهای محیطی (اختیاری)

| متغیر | پیش‌فرض | توضیح |
|---|---|---|
| `TIKOTIME_DB` | `data/db.sqlite3` | مسیر فایل پایگاه‌داده (مثلاً برای تست: `TIKOTIME_DB=/tmp/test.db`) |
| `DJANGO_DEBUG` | `1` | روی سرور روی `0` بگذارید |
| `DJANGO_SECRET_KEY` | کلید توسعه | روی سرور حتماً یک مقدار تصادفی اختصاصی بگذارید |

---

## امکانات

<!-- CONT1 -->
