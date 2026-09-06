# PROGRESS — Session IV started: 22-item multi-page feature request (2026-09-06 IV)

## وضعیت: جمع‌آوری زمینه — هنوز هیچ کدی تغییر نکرده ⏳

## درخواست کاربر (خلاصه ۲۲ موردی)
1. داشبورد: نمودار ۱۲ماه = فقط سود فروش ساعت‌ها، سبز، بدون خط خرید | باکس برندها: ارزش فروش کنار ارزش خرید | باکس ناموجودها: تصویر ساعت
2. انبار: تاریخ خرید → دیالوگ تقویم جلالی (فیلتر ماه/سال، انتخاب با موس) | مودال فروش: قیمت لازم = قیمت نهاییِ تخفیف‌خورده با جداکننده هزارگان هنگام تایپ | بیعانه هم قیمت نهایی | روش پرداخت اختیاری/اطلاعاتی | تاریخ فروش هم دیالوگ تقویم | نام+تلفن خریدار الزامی | کد فاکتور زیر نوع فروش
3. تقویم: تصویر محصول در فروش/خرید/تعمیر + کلیک → همه جزئیات
4. فروش‌ها: چرا محصول فروخته‌شده ظاهر نمی‌شود؟ بررسی پرداخت‌ها/بیعانه روی تاریخ درست و حضور در فروش‌ها | کلیک روی فروش → همه جزئیات + تصویر ساعت
5. تعمیرات: هزینه با جداکننده هنگام تایپ | پیگیری: قیمت با جداکننده هنگام تایپ
6. پرداخت‌ها: تصویر ساعت + همه جزئیات محصول (رفرنس، کد دفتر، کد سایت…) + تاریخ خرید و تاریخ تسویه (تاریخ تسویه در لیست فروش‌ها هم) | حذف فیلد «محصول از انبار» از ویرایش (فقط در افزودن)
7. تنظیمات: آپلود آیکون سایت با ذخیره | نام سایت «Tick O Time»

## یافته‌ها تا اینجا
- نمودار inline در انتهای dashboard.html (خطوط revenue+purchase_value)؛ `get_monthly_activity` از قبل profit می‌دهد → فقط رندر عوض می‌شود.
- `get_brand_breakdown` فقط value (خرید) دارد → Sum(sale_price) لازم است.
- `payment_dict` فقط product_name دارد؛ Sale فیلد settled_date ندارد (تصمیم: فیلد جدید + migration یا مشتق از Payment.updated_at).
- Sale کد فاکتور ندارد (پیشنهاد: از id)؛ کامپوننت تقویم جلالی وجود ندارد (باید ساخته شود)؛ moneyIn() در products.js → باید shared شود.
- E2E قبلی می‌گفت /api/sales همه‌ی فروش‌ها را می‌دهد — باگ «فروخته‌شده ظاهر نمی‌شود» باید live بازتولید شود.

## گام بعدی
خواندن: dashboard.html 60–200، products.html/js، views/sales.py، sold.html/js، payments.html/js + views/payments.py، calendar.js/py، repairs/tracking js، settings.html + settings_api.py + shared.py؛ چک static/js برای کتابخانه جلالی؛ سپس پیاده‌سازی (اول util های مشترک: دیالوگ تاریخ + فرمت پول).

---
--- (آرشیو — جلسه‌ی 2026-09-06 III) ---

# PROGRESS — Quantity reverted + serializer/launch fixes kept (Session 2026-09-06 III)

## وضعیت: تکمیل شد ✔

## کارهای این جلسه
1. **فیلد تعداد حذف شد (درخواست کاربر):** به مدل «هر ردیف = یک ساعت» برگشت. ستون `products.quantity` با migration 0003 حذف شد (0002 برای زنجیره‌ی migration ها می‌ماند)، فرم/ستون جدول/JS/اکسل/سریالایزر همه برگشت. فروش → ناموجود، حذف فروش → موجود (مثل قبل). جمع چیپ‌ها = قیمت واحد (سمنتیک قدیمی).
2. **حفظ شد (باگ‌های مستقل از تعداد):** کلیدهای سریالایزر (`total_value*`, `total_sale_value*`, `profit_per_unit*`, `availability_fa`, `purchase_date_weekday`, `status_color`, `is_warranty_fa`, `paid_percent`, `TRACKING_STATUS_COLOR`)، عدم احیای محصولِ فروخته‌شده با ویرایش، `launch.json` → port 8000.

## تست و اعتبارسنجی
- `manage.py check` تمیز، `makemigrations --check` بدون تغییر، migration 0003 اعمال شد، `PRAGMA table_info(products)` بدون ستون quantity، `node --check` OK، grep = صفر ارجاع quantity (به‌جز migration ها و fallback ورود اکسل).

---
--- (آرشیو — جلسه‌ی 2026-09-06 II) ---

# PROGRESS — Quantity restored + port bug sweep (Session 2026-09-06 II)

## وضعیت: تکمیل شد ✔

## کارهای این جلسه
1. **فیلد تعداد دوباره اضافه شد (درخواست کاربر):** فرم «افزودن ساعت» فیلد تعداد نداشت. ستون `products.quantity` (migration 0002)، فیلد فرم + ستون جدول، JS، سریالایزر، خروجی/ورود اکسل («تعداد»)، و `_REQUIRED_COLS` برای بکاپ‌های قدیمی. منطق: هر فروش یکی کم می‌کند، در صفر ناموجود؛ حذف فروش یکی برمی‌گرداند؛ API هم فروش کالای ناموجود را می‌بندد.
2. **کلیدهای حذف‌شده‌ی سریالایزر برگرشت:** `total_value*`, `total_sale_value*`, `profit_per_unit*`, `availability_fa`, `purchase_date_weekday` (چیپ‌های NaN و ستون سودِ undefined) + `repair_dict` (`status_color`, `is_warranty_fa`, `delivery_date_weekday`) + `tracking_dict` (`status_color`) + `payment_dict` (`paid_percent` — نوار پرداخت صفر بود).
3. **باگ ویرایش:** ویرایش محصولِ فروخته‌شده آن را دوباره «موجود» می‌کرد — حالا `available` فقط وقتی تعداد عوض شود از روی تعداد محاسبه می‌شود.
4. **`.claude/launch.json`:** هنوز Flask `app.py` روی :5000 را اجرا می‌کرد → `manage.py runserver 8000`.

## تست و اعتبارسنجی
- `py_compile` همه، `manage.py check` تمیز، `makemigrations --check` بدون تغییر، migration 0002 اعمال شد، `node --check` OK.
- smoke test زنده (curl، سرور 8765): ساخت qty=3 → ۳ فروش → qty 0/ناموجود → فروش چهارم رد شد → ویرایش با qty=0 ناموجود ماند → حذف فروش → qty 1/موجود. ردیف‌های تست پاک شدند؛ `data/db.sqlite3` سالم؛ سرور بسته شد.
- ⚠️ نکته‌ی shell: `pkill -f` وقتی داخل همان کامند start سرور باشد خودِ shell را می‌کشد — الگوی `[r]unserver` یا کامند جدا.

---
--- (آرشیو — جلسه‌ی 2026-09-05/06) ---

# PROGRESS — Django Port Complete + Full Verification (Session 2026-09-05/06)

## وضعیت: تکمیل شد ✔ (پروژه آماده استفاده)

## خلاصه جلسه
1. **ایندکس گراف کد** (codebase-memory): ۷۹۷ نود / ۳,۵۴۹ یال — پروژه `media-MyShit-Works-Tick-O-Time-DB-Watch-Inventory`
2. **README.md فارسی** کامل بازنویسی شد (نصب، اجرا، راهنمای استفاده هر بخش)
3. **رفع باگ qty باقی‌مانده:** `templates/dashboard.html` خط ~۱۰۰ هنوز به کلید حذف‌شده `qty` ارجاع می‌داد → خطای `{{ no such element: dict object['qty'] }}` در داشبورد و ناحیه‌ی مودال افزودن ساعت در لیست انبار. با نمایش موجود/ناموجود (available) جایگزین شد.
4. **رفع باگ واقعی is_available:** `inventory/utils.py::product_dict` فقط `available` برمی‌گرداند ولی همه‌ی JS ها (`products.js` خطوط 47/88/95/189، `calendar.js` خط 151) از `p.is_available` استفاده می‌کنند → بج موجود/ناموجود، شمارنده و دکمه‌ی «ثبت فروش» خراب بود. کلید `"is_available": bool(r.available)` اضافه شد. ⚠️ هنگام تغییر serializer ها هر دو کلید را نگه دار.
5. **تست E2E کامل با داده‌ی نمونه در همه‌ی بخش‌ها:** ۷۵/۷۵ موفق، ۰ ناموفق
   - اسکریپت: `/tmp/tikotime_fulltest.py` (در repo ذخیره نشده — اگر خواستی بگو تا به `tests/` منتقل شود)
   - دیتابیس ایزوله با `TIKOTIME_DB=/tmp/...` — دیتابیس واقعی دست‌نخورده
   - پوشش: ۸ صفحه، CRUD انبار + رد کد تکراری، برندها، فروش نقدی/بیعانه/ویرایش/ریز پرداخت، فقره خودکار بیعانه، تسویه کامل (کاسکید به فروش)، تعمیرات (گردش وضعیت + تاریخ بازگشت خودکار)، پیگیری، تقویم شمسی، تنظیمات، ۵ خروجی xlsx/csv، ورود اکسل (upsert)، آپلود/سرو تصویر (کلید `path`)، بکاپ کامل (ساخت/دانلود/آپلود معتبر و نامعتبر/بازگردانی/حذف)، حذف فروش → ساعت دوباره موجود، 404 JSON
6. **پاک‌سازی پایانی:** تصاویر تست ۱۰۸ بایتی حذف شدند، فایل‌های tmp پاک شدند، `manage.py check` بدون خطا، سرور بسته شد (پورت 8000 آزاد)

## نکات تاییدشده (برای جلسات بعد)
- وضعیت‌ها: تعمیرات `received|in_progress|waiting_parts|done|delivered` — پیگیری `new|ordered|found|delivered|cancelled`
- bulk-delete ها `deleted=len(ids)` برمی‌گردانند
- تاریخ/تلفن فارسی ورودی OK، ذخیره ISO/لاتین
- دیتابیس تست ایزوله: متغیر محیطی `TIKOTIME_DB`

## نکته برای ادامه
- اگر تست‌ها لازم شد دائمی شوند → `/tmp/tikotime_fulltest.py` را به `tests/` منتقل کن (دیتابیس اصلی را دست نمی‌زند).
- آیتم‌های باقی‌مانده‌ی جلسه قبل (node --check, ZIP و…) در بخش آرشیو پایین است — ZIP هنوز ساخته نشده.

---
--- (آرشیو — جلسه‌ی 1404/06/07، نسخه Flask) ---

# PROGRESS — حذف فیلد تعداد و بازطراحی صفحات (Session 1404/06/07)

## وضعیت: تکمیل شد ✔ (جلسه 1404/06/07)

## قطعی شده در ادامهٔ جلسه
- node --check همه js ✔؛ مهاجرت idempotent ✔ (چند بار init_db داده‌ها سالم)
- base.html badge title ← "ساعت‌های ناموجود" ✔
- smoke test کامل ✔ (اندازهٔ جمله به جمله ویرایش فروش، فیلتر، حذف، خروجی)
- README.md آپدیت ✔ (بخش مهاجرت اضافه شد)
- TikoTime.zip ساخته شد ✔ (300KB، 35 فایل: app/database/reports/excel_io/jalali/run/README/templates/static بدون .venv، data، __pycache__)

## کارهای انجام‌شده (کامل و تست‌شده)

### ۱. database.py — مهاجرت کامل
- ستون `quantity` از products و sales حذف؛ ستون `available INTEGER DEFAULT 1` در products اضافه
- ستون‌های `delivered`, `delivered_at` از sales حذف
- مهاجرت بازسازی جدول: `_migrate()` با `PRAGMA foreign_keys = OFF` (مهم! بدون آن DROP والد، sales را cascade می‌کرد)
- `init_db()`: اول `_migrate(db)` بعد `executescript(SCHEMA)` تا ایندکس‌ها بعد از بازسازی ساخته شوند
- تست شده روی کپی دیتابیس واقعی: ۴ محصول و ۱۰ فروش حفظ شد، available=3 (کاسیو qty=0)، ایندکس‌ها سالم

### ۲. reports.py — بازنویسی کامل
- بدون quantity؛ available_count، sold_count، sold_revenue=SUM(final_price)
- get_monthly_activity: revenue از final_price

### ۳. excel_io.py
- PRODUCT_HEADERS: «تعداد»→«وضعیت» (موجود/ناموجود)؛ import هم وضعیت می‌خواند (فایل قدیمی qty هم پشتیبانی)
- SALES_HEADERS جدید: کد دفتر، کد سایت، رفرنس، نام، برند، قیمت خرید، فروش، نهایی، سود، تاریخ، خریدار، تلفن، نوع فروش، نقدی، کارت‌خوان، کارت به کارت، نوع پرداخت، یادداشت

### ۴. app.py
- PRODUCT_SORT_MAP: quantity→available
- product_dict: is_available از available؛ delivered_fa حذف
- _product_values: available:1
- api_sales_create: نقدی بدون ریز پرداخت → paid_cash=final؛ با ریز پرداخت → همان مقادیر ذخیره می‌شود؛ بیعانه همین‌طور؛ product → available=0
- api_sales_update: paid_cash/pos/card2card و payment_type هم آپدیت می‌شوند؛ profit از purchase_price محصول
- api_sales_delete و bulk-delete: محصول دوباره available=1 می‌شود
- deliver/undeliver endpoints حذف شدند
- calendar API: بدون quantity؛ price_display از final_price
- badge پایین‌نوی: low = COUNT(available=0)
- dashboard route: low_stock → available=0 items

### ۵. templates/dashboard.html — کامل
- کارت «سود فروش انجام‌شده» و «مدل‌های ناموجود» حذف؛ کارت‌های جدید: فروش‌های ثبت‌شده + موجود در انبار
- نمودار خطی (line chart) ۱۲ ماه: فروش (accent) + خرید (amber) با tooltip و cursor
- جدول آخرین فروش‌ها/خریدها بدون ستون تعداد
- بخش «رو به اتمام» → «ناموجودها» با badge

### ۶. products (انبار)
- products.html: sort وضعیت → value=available؛ hidden input payment_type در فرم فروش؛ ریز پرداخت (نقدی/POS/کارت‌به‌کارت) داخل فیلد نوع پرداخت منتقل شد؛ سوییچ‌های تحویل حذف
- products.js: بدون quantity (badge موجود/ناموجود)، chips خلاصه (موجود/ناموجود)، openSaleModal اصلاح، chip handler #sale-payment-chips، updateSaleHints جدید، save بدون qty/delivered — node --check OK

### ۷. sold.html + sold.js — بازنویسی کامل (لیست مثل انبار)
- جدول: چک‌باکس، تصویر، نام، کدها (رفرنس/سایت/دفتر)، خریدار+تلفن، قیمت نهایی، تاریخ، ویرایش، حذف
- فیلتر: جستجو، نوع فروش، روش پرداخت (cash/pos/card2card/deposit)، از/تا تاریخ، مرتب‌سازی ۶ ستونه
- bulk delete با چک‌باکس؛ مودال جزئیات کامل (تلفن، قیمت خرید، سود، برند، تأمین‌کننده، نوع فروش، روش پرداخت، ریز پرداخت)؛ مودال ویرایش؛ هایلایت ?highlight=ID از تقویم (auto-open detail)
- node --check OK

### ۸. payments
- payments.html: bulk bar اضافه شد + مودال حذف گروهی (modal-delete-pay-bulk)
- payments.js: چک‌باکس در هر کارت، دکمه «تسویه‌ی کامل» کنار «ثبت پرداخت» (API settle-full موجود بود)، bulk delete handlers — باید node --check بگیرم

### ۹. calendar.js
- buy/sell بدون quantity؛ sell detail: «قیمت فروش» از price_display؛ لینک «مشاهده در فروش‌ها» → /sold?highlight=id
- node --check OK

### ۱۰. css
- app.css: انیمیشن tr.row-highlight اضافه شد (آخر فایل)

## تست‌های پاس‌شده (test client)
- همه صفحات 200؛ ساخت دو ردیف یکسان با کد متفاوت OK؛ کد تکراری رد شد
- فروش نقدی با ریز پرداخت ذخیره و نمایش OK؛ محصول ناموجود شد
- فروش بیعانه → پرداخت‌ها؛ فقط تسویه‌شده‌ها در /api/sales؛ settle-full بدون مبلغ OK → فروش ظاهر شد
- ویرایش فروش (dbg2.py) OK؛ فیلتر/مرتب‌سازی OK؛ حذف → دوباره موجود OK؛ bulk delete OK؛ export OK
- نکته: KeyError در smoke_test.py خط ۸۸ باگ خودِ اسکریپت تست است (payload ویرایش بدون paid_pos/card2card) — dbg2.py همه را پاس کرد. mig_test.py دومی هم باگ اسکریپت است (بعد از مهاجرت ستون quantity نیست — یعنی مهاجرت idempotent درست کار کرده)

## کارهای باقی‌مانده
1. node --check برای payments.js و sold.js دوباره؛ تست مهاجرت دوباره (idempotent) با اسکریپت اصلاح‌شده
2. چک base.html badge label (nav_badge_low حالا ناموجودهاست — برچسب را ببین)
3. اجرای سرور واقعی با curl (اختیاری — test client کافی است)
4. README.md آپدیت (تعداد حذف، موجود/ناموجود، فروش‌ها لیست، تسویه کامل، نمودار خطی)
5. ساخت ZIP: از پوشه پروژه، بدون .venv/__pycache__/data/.claude/ساعت‌شمار.zip — نام TikoTime.zip (جایگزین قبلی)
6. پاک‌سازی فایل‌های tmp و مطمئن شدن هیچ سروری باز نمانده

## نکات مهم برای ادامه
- هرگز PRAGMA foreign_keys را هنگام DROP جدول والد روشن نگذار
- to_float('0', default) → 0 درست کار می‌کند
- PAYMENT_TYPE_FA در app.py: cash/deposit فقط (card به cash تبدیل شده در مهاجرت)
- در sold.js ریجن highlight: باز شدن مودال با setTimeout 350ms


## نکتهٔ حیاتی
دیتابیس واقعی (data/watch_inventory.db) دستنخورده نشد — با اولین اجرای برنامه مهاجرت خودکار انجام می‌شود (این مسیر روی کپی تست شد و سالم است).
