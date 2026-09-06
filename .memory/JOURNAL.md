# Journal — TikoTime (Watch Inventory)

> Commit-style activity log. Newest entries first. One entry per meaningful action.

---
## 7332513 — 2026-09-07 (session IV, ui change)
**type:** ui
**scope:** sidebar (base.html)
**subject:** removed count badge from Watch Inventory nav item; other badges kept

- **User request:** «عدد کنار بخش انبار ساعت‌ها در منوی کنار حذف شود؛ بج‌های تعمیرات، پیگیری و پرداخت‌ها بماند.»
- The products nav badge was `nav_badge_low` (count of out-of-stock watches, title «ساعت‌های ناموجود»). Removed the `{% if nav_badge_low %}…{% endif %}` line; left an HTML comment noting it was removed per user request. `nav_badge_low` is still computed in the context — only display removed, so it can be restored with one line.
- **Verified live:** dashboard 200; remaining badges exactly 3 — «تعمیرات در جریان» (repairs), «سفارش‌های در جریان» (tracking), «فقره‌های با مانده بدهی» (payments); products badge absent (grep count 0). Server stopped. Commit `7332513`.
- **Gotcha re-confirmed:** `pkill -f` self-match — a shell whose command line contains the plain `manage.py runserver 127.0.0.1:8765` string kills ITSELF when the same command also pkills that pattern (bracket trick in the pattern doesn't help if another part of the same command line matches plainly). Always run pkill and the server-start in SEPARATE shell invocations.

---


## 4fe5591 — 2026-09-07 (session IV, bugfix)
**type:** fix
**scope:** settings / app.js
**subject:** site-icon upload was silently swallowed by app.js auto-binding — now fixed + hardened

- **User report:** «انتخاب آیکون هیچ اتفاقی نمی‌افتد — آیا دکمه‌ی Apply لازم است؟»
- **ROOT CAUSE (real, confirmed):** app.js `$$(".img-upload").forEach(setupImageUpload)` auto-bound the icon wrapper in settings.html (same class). Its change handler runs FIRST, starts a generic multipart upload, and **synchronously clears `input.value = ""`** → the page's dedicated icon handler (bound second) reads `files[0]` → already empty → `return`. Result: icon uploaded as generic image, `site_icon` setting NEVER set, no preview update, no icon toast — "nothing happens". Server side was always fine (upload + /api/settings/site-icon verified by curl).
- **Debug journey (recorded for reuse):** CDP/headless Chromium harness (node 24 built-in WebSocket, /tmp/icon_cdp.js pattern): network capture showed `ERR_ALPN_NEGOTIATION_FAILED` on multipart POSTs with CDP-injected files — a SNAP-CHROMIUM artifact (confined browser can't read host files set via DOM.setFileInputFiles; JS-built `File`/Blob uploads work). Classic bug-masking lesson: `input.value=""` cannot clear a `defineProperty`-mocked FileList, which is why the first CDP test "passed" while the real flow was broken. Always pair mocked-input tests with handler-order analysis.
- **Fix:** (1) app.js auto-binding now skips `[data-manual]` (`.img-upload:not([data-manual])` in both init + modal:opened); settings icon wrapper marked `data-manual`. (2) Icon upload switched to robust JSON/base64 path: `api_upload` now accepts both multipart (unchanged for products/repairs) and `{kind,name,data}` JSON (dataURL/base64, 2MB cap, shared `_save_uploaded`). (3) UX: preview image is clickable, filename + «در حال ذخیره…» shown live, explicit success toast («همین حالا اعمال شد ✓»), button disabled during upload, cache-busted preview, placeholder SVG fixed (`innerHTML` on `<img>` never worked → inline data-URI src). **Answer to user: no Apply button — applies instantly on select**, now stated in the hint text.
- **Verified:** node --check; manage.py check; curl JSON upload (200, real PNG saved); headless full-flow with mocked File → single JSON upload, no stray multipart, site_icon persisted, correct toast, products-page auto-binding regression clean (1 img-upload bound, no exceptions). All test icon files deleted, site_icon reset to "", server stopped. Commit `4fe5591`.

---


## 7f1a632 — 2026-09-07 (session IV, feature)
**type:** feat
**scope:** calendar
**subject:** reference code shown on day-box items — رفرنس for buy/sell, watch_code for repairs

- **User request:** «شماره رفرنس ساعت خریداری‌شده، فروخته‌شده و تعمیری هم نمایش داده شود.»
- **Field reality:** purchases (`product_dict`) and sales (`sale_dict`, from linked product) have `reference`; Repair has NO reference column — its identifier is `watch_code` (user's own «کد ساعت» convention from the repair form), so repairs show that labeled «کد:».
- **eventItem meta line now:** buy/sell → `رفرنس: <reference>` (empty if the product has none); rep_in/rep_out → `<customer> — کد: <watch_code>` (parts omitted when blank). Card stays otherwise minimal per 1115b6d.
- **Verified:** node --check pass; isolated render test (buy «رفرنس: 2105», sell «رفرنس: R-99», rep «اسدی — کد: WC-12», all with image); live API real data: 2026-09-06 sales refs 3185 / LJ.160.21.721, repair «الکسا» code 2019 customer اسدی, 2026-09-01 purchase ref 0595. Server stopped. Committed `7f1a632`.

---


## 1115b6d — 2026-09-07 (session IV, feature)
**type:** feat
**scope:** calendar
**subject:** day-box items minimized to image+name+price (repairs: +customer, no price); totals جمع مبلغ خرید / جمع مبلغ فروش

- **User request:** «جعبه‌ی سمت چپ فقط تصویر، نام ساعت و قیمت را نشان دهد — خرید: قیمت خرید، فروش: قیمت فروش، تعمیر: فقط تصویر و نام ساعت و نام شخص — و زیر خریدها و فروش‌ها جمع مبلغ خرید و جمع مبلغ فروش.»
- **eventItem changes (static/js/calendar.js:93):** removed the sub-line for buy/sell (supplier / sale-type+buyer+phone gone — details remain in the click modal); buy price now `purchase_price_display` (was `total_value_display` — same value post-quantity-removal but explicit); sell price `final_price_display || sale_price_display` (final==sale when no discount, discounted price otherwise); repairs (`rep_in`/`rep_out`): NO price element, meta = customer name only (`customer_name || customer` — the old code read `e.customer` which repair_dict doesn't even have, so customer never showed before); name resolution `name || product_name || watch_name`; image `image || product_image` fallback (same as detail modal).
- **Totals:** purchases → «جمع مبلغ خرید» (sum of `purchase_price` numeric, blue); sales → «جمع مبلغ فروش» (sum of `final_price`, green). REMOVED the «جمع سود روز» row per the minimal-box request (profit still visible per-sale in the click modal and on the dashboard chart). Was: «جمع ارزش خرید روز»/«جمع فروش روز»+«جمع سود روز».
- **Verified:** node --check pass; isolated eventItem render test for all 4 kinds (img/price/meta flags correct — sell img:false in first run was a test-object artifact using old keys, re-verified true with product_image fallback); live API data shapes confirmed: 2026-09-06 sales carry name+image+final_price_display, rep_in «الکسا/اسدی», 2026-09-01 purchase «ویولت زنانه کرنو/۱۲٬۰۰۰٬۰۰۰». Server stopped. Committed `1115b6d`.

---


## 6364203 — 2026-09-07 (session IV, fix)
**type:** fix
**scope:** calendar
**subject:** sold watch image missing in day-panel list — sale_dict key mismatch (product_image/product_name vs image/name)

- **User report:** day box shows purchase/repair thumbnails but sold products show the placeholder clock icon until clicked.
- **Root cause:** the shared left-box renderer `eventItem(e, kind)` in `static/js/calendar.js:93` reads `e.image` and `e.name`. Month-view sale entries (built inline in `calendar.py` month loop) carry `image`/`name`, but the DAY panel (`api_calendar_day`) used `sale_dict`, whose keys are `product_image`/`product_name` → falsy `e.image` → placeholder branch. Purchases (`product_dict`) and repairs (`repair_dict`) already had `image`/`name`, hence «everything is perfect for purchases and repairs».
- **Fix (backend only, calendar.py):** day API now emits `{**sale_dict(s), "name": product.name or "محصول حذف‌شده", "image": product.image or ""}` — additive aliases, legacy keys kept (serializer gotcha). No JS change; the already-proven eventItem path picks them up. Deleted-product sales degrade gracefully (empty image → placeholder, name fallback).
- **Verified live:** `check` clean; `/api/calendar/day?date=2026-09-07` sale entry now has `name: الکسا اتومات`, `image: img_20260906_140316_7c34f189.webp` (plus legacy `product_image`), customer + final_price_display intact. Server stopped. Committed `6364203`.

---


## 7551e14 — 2026-09-07 (session IV, feature)
**type:** feat
**scope:** sales (inventory sell modal)
**subject:** optional manual invoice-code input — user enters their own value, auto TT-code only when left empty

- **User request:** «در بخش فروش صفحه انبار، زیر فیلد نوع فروش یک فیلد اختیاری کد فاکتور اضافه کن تا خودم مقدارش را وارد کنم — نه مقدار پیش‌فرض تو.»
- **Why a migration was needed:** `invoice_code` was NOT a DB column — it was computed on the fly in `sale_dict` as `invoice_code(r.id, r.sale_date)` → `TT-<jy><jm>-<sale_id:04d>` (utils.py:141). To store a manual value, added `Sale.invoice_code` CharField(40, blank) — migration `0006_sale_invoice_code` (applied).
- **Changes:** models.py (field) · utils.py `sale_dict`: `r.invoice_code or invoice_code(...)` (single display point — sold list, detail modal, calendar all follow) · sales.py `_create`: accepts `invoice_code` payload key, `clean()`ed, ≤40 chars, **duplicate rejected** with Persian error, passed to `Sale.objects.create` · products.html: new optional field «کد فاکتور (اختیاری)» right below «نوع فروش», dir=ltr, maxlength=40, with `#invoice-code-hint` moved under it and reworded to «اگر خالی بگذارید، خودکار صادر می‌شود: TT-…» · products.js: `invoice_code` added to sell payload; `form.reset()` on modal open clears it (line 295 path).
- **Bonus fix found while testing:** `/api/sales?q=` search did NOT cover invoice_code — `q=MY-CODE` returned nothing. Added `Q(invoice_code__icontains=q)` to the search filter in `api_sales`.
- **Verified live (runserver):** POST with `invoice_code=MY-CODE-77` → stored + echoed in `sale.invoice_code`; duplicate POST → `{"ok":false, "error":"کد فاکتور «MY-CODE-77» قبلاً استفاده شده است"}`; POST with empty code → auto `TT-140506-0014`; search `q=MY-CODE` finds it after the Q-fix; field renders on `/products` (grep count 1). Test sales 13/14 deleted afterward — DB back to 4 original sales, both test products re-available. `check` clean, migration applied, `node --check` pass. Server stopped. Committed `7551e14`.
- **Note:** edit flow (sold.js PUT) does not expose invoice_code — out of scope of the request; the manual code is fixed at creation for now.

---


## 6e8cce4 — 2026-09-07 (session IV, hotfix)
**type:** fix
**scope:** sales (sold page)
**subject:** /sold page rendered nothing — missing $() wrapper killed the whole sold.js script

- **Symptom (user):** «صفحه فروش‌ها هیچ چیز نشان نمی‌دهد». API `/api/sales` and the template were fine (curl 200, 4 sales, all fields present), but headless Chromium showed 0 rows.
- **Root cause:** `static/js/sold.js:323` — `["#filter-date-from","#filter-date-to"].forEach((sel) => { sel.addEventListener(...) })` was missing the `$()` wrapper, so `sel` was the selector STRING → `TypeError: sel.addEventListener is not a function`. Because the throw happens at TOP-LEVEL evaluation, everything after it — including the `DOMContentLoaded → loadSales()` registration — never ran → table stayed empty forever. Note the earlier `node --check` could not catch this (it's a runtime error, not syntax).
- **Fix:** one char-class change — `$(sel).addEventListener(...)`. Audited all `static/js/*.js` for the same pattern (`[...].forEach((sel)=>` loops): `products.js:481/484` already correct; bug was only in sold.js.
- **Debug technique that nailed it (remember):** grep-based ID checks and API curls were all green — only real execution exposed it. `chromium --headless --no-sandbox --virtual-time-budget=6000 --dump-dom URL` + `--enable-logging=stderr --v=0` prints CONSOLE errors to stderr. Repro signature: summary chips rendered («فقره» present) but `ev-row` count 0 and `#sold-empty` still hidden = render() threw between chips and rows.
- **Verified after fix:** node --check pass; headless DOM now has 4 `ev-row`s, no console errors; row for sale 12 shows every required detail — image `/data/images/img_….webp`, name «الکسا اتومات», reference pill `2105`, site-code pill `121553`, office-code pill `159`, buyer «علی», phone ۰۹۱۲۲۴۶۰۳۵۷, Jalali date ۱۴۰۵/۰۶/۱۶. Click-row detail modal (showSaleDetail) adds invoice code, prices/discount/profit/purchase, brand, supplier, sale type, payment breakdown, settlement status, notes.
- Committed `6e8cce4` (sold.js only). Smoke server stopped.

---


## 3984de6 — 2026-09-07 (session IV, correction)
**type:** fix
**scope:** dashboard
**subject:** 12-month chart corrected per user: THREE lines (purchases, sales, profit) — not profit-only

- **User clarification:** «در نمودار ۱۲ماه، خرید، فروش و سود فروش — یک نمودار با سه خط که مشخص باشد هر ماه چه خریدی، چه فروشی و چه سودی داشتم.» The earlier task_0001 interpretation (profit-only green line, commit `277eacf`) was wrong.
- **Fix (templates/dashboard.html only — `reports.get_monthly_activity` already returned `revenue`/`purchase_value`/`profit` per month, no backend change):** card retitled «فعالیت ۱۲ ماه اخیر — خرید، فروش و سود» with a 3-item legend (فروش `--accent` آبی / خرید `--amber` کهربایی / سود `--green` سبز — all theme-aware vars); Y-scale now maxes over all three series; three paths drawn back-to-front (purchases w2.2 → sales w2.6 → profit w2.8, subtle green area under profit kept); dots per series per month; tooltip now lists فروش/خرید/سود فروش (+تعداد فروش) per month with matching colors; empty-state text mentions خرید یا فروش.
- **Verified:** `manage.py check` clean; live curl of /dashboard shows 3-item legend + new title + monthly JSON with `revenue`/`purchase_value` keys; inline chart JS extracted and `node --check` pass; server stopped. Committed `3984de6`.

---

## f985c66 — 2026-09-07 (session IV, completed)
**type:** feat
**scope:** multi-page-features
**subject:** All 22 items of the session-IV request done, verified live, committed per feature

- **Commits (in order):** `277eacf` dashboard (chart initially profit-only — corrected to 3 lines خرید/فروش/سود in `3984de6`; brand sales value, out-of-stock images) · `7a4ed12` inventory/sale modal (shared Jalali popup datepicker `static/js/jalali-datepicker.js`, final-price required + thousands-sep, buyer name+phone required, invoice code TT-YYYYMM-NNNN via `utils.invoice_code`) · `841dd1d` calendar (images + full detail modals, day-panel price fix) · `daaf190` sales (sold-list subtitle, invoice in detail, sale-date edit syncs linked Payment.pay_date) · `28ea0fb` repairs/tracking (shared `bindMoneyInput`/`moneyIn` moved to app.js) · `8efd352` payments (product image + full details on cards/edit, settlement date: new `settled_at` on Sale+Payment, migration `0004_sale_payment_settled_at`, inventory picker hidden when editing) · `170e266` settings (store name drives sidebar brand + tab title on every page, live update on save) · `f985c66` settings (default name = «Tick O Time», migration `0005_store_name_default` seeds the Setting row).
- **Settings item ㉑ note:** site-icon file upload already existed and persists (`/api/settings/site-icon` → `Setting.key=site_icon`, rendered in favicon + sidebar brand mark by `page_ctx.site_icon`).
- **Final verification (task_0009):** `manage.py check` clean · `makemigrations --check` in sync (0001–0005 applied) · `node --check` pass on all 9 files in `static/js/` · live curl: all 8 pages 200, `/api/products`, `/api/calendar/day`, `/api/payments`, `/api/settings` return data; store name «Tick O Time» renders in `<title>` and `.brand-name`.
- **Serializer gotcha to remember:** when adding keys, keep legacy ones too (see session II) — this session followed it (payment_dict extended, nothing dropped).

---

## c4e8a12 — 2026-09-06 (session IV)
**type:** chore
**scope:** git
**subject:** Git repository initialized — every completed task gets a commit from now on

- **Repo:** `git init -b main` + local identity (`meti <meti@local>`) + global `safe.directory` exception (repo dir owned by root → "dubious ownership" error otherwise).
- **`.gitignore` (new):** `__pycache__/`, `*.py[cod]`, `.venv/`, `staticfiles/`, `data/` (live DBs `db.sqlite3`/`watch_inventory.db`, images, backups, exports), `.codebase-memory/`. `.memory/` + `.claude/` ARE versioned.
- **Commit `776891f` (initial):** 71 files / 12,658 insertions — full working app (Django port complete & verified, all session I–III fixes included).
- **New standing rule (user request):** after each completed task, commit with a descriptive message.
- **Bonus finding:** `static/js/jalali.js` exists (client-side Jalali math) — reuse it for the planned Jalali date-picker component.
- Next: resume session IV feature work (22-item list, state in JOURNAL b7d2f90); commit per page/feature as each is completed and verified.

---
## b7d2f90 — 2026-09-06 (session IV, in progress)
**type:** explore
**scope:** multi-page-features
**subject:** Large 8-page feature request received — context gathering started, NO code edits yet

**Full request breakdown (user, verbatim intent):**
- **Dashboard:** ① 12-month activity chart = watch-sale profit ONLY (green), no purchases line ② Brand box: show sales value next to purchase value ③ Out-of-Stock box: show watch images.
- **Inventory page:** ④ purchase date → popup Jalali date-picker (month+year filters, mouse-selectable) ⑤ sale modal: sale-price field fixed; REQUIRED field = final discounted price, thousands-separated while typing ⑥ Deposit section: final-price field too, thousands-sep ⑦ payment-method fields optional/informational only ⑧ sale date → same popup picker ⑨ buyer name + phone REQUIRED ⑩ show invoice code under sale-type field.
- **Calendar:** ⑪ product image next to sale/purchase/repair details; click → all details.
- **Sales page:** ⑫ sold product not appearing — investigate ⑬ verify payments/deposit rows appear on correct date AND in Sales page ⑭ clicking a sold product → ALL details incl. watch image.
- **Repairs:** ⑮ repair cost thousands-sep while typing. **Tracking:** ⑯ price thousands-sep while typing.
- **Payments:** ⑰ show watch image ⑱ all product details (reference, office/site codes, …) ⑲ show purchase date + settlement date; settlement date also in Sales list ⑳ remove «محصول از انبار» search field from Edit modal (keep in Add).
- **Settings:** ㉑ site-icon upload + save ㉒ site name = «Tick O Time».

**Findings so far (files read: reports.py, dashboard.html [truncated tail], utils.py, models.py):**
- Chart is inline JS at the end of `templates/dashboard.html`: two lines — `revenue` (accent) + `purchase_value` (amber), fed by `reports.get_monthly_activity()` which already returns `revenue/profit/count/purchase_value` per Jalali month → ① = drop purchase line, plot `profit` in `var(--green)`, adjust tooltip.
- `reports.get_brand_breakdown()` returns only brand/count/purchase `value` → ② needs `Sum("sale_price")` added + template box edit.
- `payment_dict` has only `product_name` → ⑰/⑱ need product join fields (image, reference, office_code, website_code, purchase_date…).
- No `settled_at`/`settled_date` on `Sale` (only `is_settled` bool, `created_at`) → ⑲ needs a new model field + migration, or derive from linked Payment `updated_at`. Decision pending.
- No invoice-code field on `Sale` → ⑩ likely format from `sale.id` (e.g. فاکتور-<id>); decision pending.
- No reusable Jalali date-picker component exists → ④/⑧ need a new shared JS component (check `static/js/` for existing jalali math first).
- Thousands-sep-while-typing: products.js has `moneyIn()` helper → extract to shared util for ⑤/⑥/⑮/⑯.
- E2E history says `/api/sales` lists ALL sales regardless of `is_settled` — ⑫ must be reproduced live before fixing (sold.html/sold.js + views/sales.py not yet re-read).

**Next steps:** read dashboard.html 60–200, products.html/js, views/sales.py, sold.html/js, payments.html/js + views/payments.py, calendar.js/py, repairs/tracking js, settings.html + settings_api.py + shared.py; check static/js for jalali lib; then implement in page order (shared datepicker + money-format util first).

---
## a1c7e44 — 2026-09-06 (session III)
**type:** revert
**scope:** inventory-quantity
**subject:** Quantity field removed — reverted to one-row-one-watch model (user request)

- **Full revert of f5a9d21's quantity feature** (user asked to go back to the previous state): `products.quantity` removed from the model (`0003_remove_product_quantity`, applied to `data/db.sqlite3`), form field + table column removed from `templates/products.html`, render/edit/payload references removed from `products.js`, `product_dict` back to unit-price totals (`total_value` = purchase price, `total_sale_value` = sale price — legacy semantics), Excel headers/rows/import back to the 11-column format (import still tolerates old files that had a count in the وضعیت column), `_REQUIRED_COLS` quantity entry removed, sale flow back to available=True→False on sale, True on delete (F-import and stock guard removed).
- **Kept (pre-existing bug fixes, unrelated to quantity):** restored legacy serializer keys (`total_value*`, `total_sale_value*`, `profit_per_unit*`, `availability_fa`, `purchase_date_weekday`, `status_color`, `is_warranty_fa`, `paid_percent`, `TRACKING_STATUS_COLOR`), edit no longer resurrects sold products (`values.pop("available")` in `_update`), `.claude/launch.json` → `manage.py runserver 8000`.
- **Migration history:** 0002 (add) → 0003 (remove) both kept — Django requires the chain; the column never ships to fresh DBs.
- **Verified:** `manage.py check` clean, `makemigrations --check` = "No changes detected", migration applied OK, `PRAGMA table_info(products)` has no quantity column, `node --check` products.js OK, grep shows no quantity references outside migration files + the intentional import fallback.

---
## f5a9d21 — 2026-09-06 12:55
**type:** fix
**scope:** inventory-quantity
**subject:** Quantity field restored end-to-end + dropped serializer keys fixed + edit-flips-availability bug + stale launch.json

- **Quantity field restored (user request):** the Add-Product form had no تعداد field (removed in the 1404/06/07 Flask redesign, never restored). Re-added end-to-end: `products.quantity` column (`0002_product_quantity`, applied), form field + table column in `templates/products.html`, `products.js` (render/edit payload/sale-modal stock hint), `product_dict` serializer, Excel export/import (`تعداد` column; legacy files that stored the count in the وضعیت column still parse), and `dbhelpers._REQUIRED_COLS` so old restored backups get the column.
- **Stock semantics:** selling decrements quantity (ناموجود only at 0); deleting a sale/bulk-deleting sales restores one unit each (`F("quantity") + 1`); API now rejects selling an unavailable/0-stock product (previously only the frontend disabled the button).
- **Bug fix 3 (NaN chips / undefined cells):** `product_dict` dropped legacy keys `total_value*`, `total_sale_value*`, `profit_per_unit*`, `availability_fa`, `purchase_date_weekday` → inventory summary chips showed `NaN` and the سود واحد column `undefined`. Recomputed with quantity (total = unit price × qty). `repair_dict` gained `status_color`, `is_warranty_fa`, `delivery_date_weekday`; `tracking_dict` gained `status_color` (`TRACKING_STATUS_COLOR` added to utils); `payment_dict` gained `paid_percent` (payments progress bars were stuck at 0).
- **Bug fix 4 (edit resurrects sold items):** `products._update` applied `available=True` from `_product_values` unconditionally — editing a sold (ناموجود) product flipped it back to موجود while its sale still existed. Now availability is preserved unless the quantity actually changes (`available = quantity > 0` on change; zero allowed on update, min 1 on create).
- **Fix 5:** `.claude/launch.json` still launched the removed Flask `app.py` on port 5000 → now `manage.py runserver 8000`.
- **Verified:** `py_compile` all touched files, `manage.py check` clean, `makemigrations --check` = "No changes detected", migration applied, `node --check` products.js OK. Live curl smoke test: create qty=3 → 3 sales → qty 0/ناموجود → 4th sale rejected («این ساعت ناموجود است») → edit with qty 0 stays unavailable → delete sale → qty 1/موجود. Test rows deleted; real `data/db.sqlite3` otherwise untouched; server stopped.

---

## e4b2c08 — 2026-09-06 01:30
**type:** feat
**scope:** django-port
**subject:** Django port completed & fully verified — qty remnant fixed, is_available bug fixed, 75/75 tests pass

- **Indexing:** repo indexed into codebase-memory graph (797 nodes / 3,549 edges; project `media-MyShit-Works-Tick-O-Time-DB-Watch-Inventory`). Only flagged file: `templates/dashboard.html` (parse_partial at line 108 — cosmetic).
- **Bug fix 1 (qty remnant):** `templates/dashboard.html` line ~100 still referenced removed `qty` dict key → rendered `{{ no such element: dict object['qty'] }}` on dashboard AND inside the Add-Watch modal area of the inventory list. Replaced with the `available`-based (موجود/ناموجود) display per the 1404/06/07 design decision.
- **Bug fix 2 (real, found by testing):** `inventory/utils.py::product_dict` returned only `available` but ALL frontend JS uses `p.is_available` (`static/js/products.js` lines 47/88/95/189, `static/js/calendar.js` line 151) → availability badges, available-count chip and the "ثبت فروش" button were broken for every row. Added `"is_available": bool(r.available)` next to `available`.
- **Full E2E test run** (test-client script, isolated DB via `TIKOTIME_DB=/tmp/...`): **75/75 PASS, 0 FAIL** — pages (8), products CRUD + duplicate-code rejection, brands, sales (cash w/ breakdown, discount, deposit → auto Payment receipt, Persian phone → latin, available flip on sale/delete), payments (remaining math, /add over-remaining rejected, settle-full cascades to sale.is_settled + paid_cash, manual receipt, unpaid filter), repairs (status flow, delivered auto return_date, bulk delete, search), tracking, Jalali calendar (events + day detail), settings, all 5 exports (xlsx/csv) + import template, Excel import (1 added + 1 updated verified), image upload (response key `path`) + serving, backups (create/list/download/upload valid+invalid/restore/delete), sale-delete → product available again, 404 JSON.
- Status-name facts verified: repairs `received|in_progress|waiting_parts|done|delivered`; tracking `new|ordered|found|delivered|cancelled`; bulk-delete returns `deleted=len(ids)`.
- **README.md rewritten in Persian** (~2.7KB): install, venv, runserver, usage per section, backup/export notes.
- Verified real DB untouched; server stopped at session end (`pkill -f manage.py runserver`, port 8000 free); temp test DB/xlsx/images cleaned.

---


## a3d7f19 — 2026-09-03 19:44
**type:** chore
**scope:** memory
**subject:** memory checkpoint: save all progress (Sales-page bug + Django port state)

- Full progress checkpoint written to `.memory/` at user request: this journal (entries 9b2e4c6, 7f1d0a8, a3d7f19), updated `INDEX.md` (Django migration state + known-issue list), and new `COMMANDS.md` (persistent log of every command executed, per user request).

---

## 9b2e4c6 — 2026-09-03 19:40
**type:** chore
**scope:** memory
**subject:** handoff: record pending Django-port work and open decisions

- Pending (user paused work with «stop»):
  1. Finish Django port — views package (products/sales/repairs/tracking/payments/calendar/export-import/backups/settings), URL wiring, template integration via django-jinja2 (UI/UX must stay untouched).
  2. Fix Sales-page bug **in the Django rewrite** (see 7f1d0a8): list must include deposit sales.
  3. Full DB reset (`makemigrations` + `migrate` on a fresh SQLite file) so the user can test from scratch.
  4. Run professionally in a virtualenv via `requirements.txt` (no shell script — user explicitly rejected `run.sh`).
  5. Performance: indexes already declared in models; keep queries batched (no N+1) and reuse the existing JS as-is.
  6. Tests: user will ask later — do NOT write tests until requested.
- Open items to verify when resuming: `inventory/views/` and `inventory/management/commands/` are empty packages; `inventory/migrations/` has no migration files yet; templates still reference `/static/...` and `/data/images/...` paths (must map to Django static/media serving); `excel_io.py` not yet ported.

---

## 7f1d0a8 — 2026-09-03 19:30
**type:** explore
**scope:** sales
**subject:** diagnose: deposit sales never appear on the Sales page

- User reported: «when a product is sold, it does not appear there [Sales page]».
- Root cause found in `legacy_flask/app.py::api_sales` (line ~607): the list query filters `WHERE s.is_settled = 1`, but deposit (بیعانه) sales are created with `is_settled = 0` (only flips to 1 when the receipt is fully settled via payments «settle-full»/«add»).
- Consequence: a product sold as deposit disappears from inventory (`available = 0`) **and** is invisible on the Sales page until fully paid — looks like the sale vanished.
- Evidence the UI intends to show deposits: `static/js/sold.js` defines `PAYMENT_BADGE = {cash: نقدی, deposit: بیعانه}` (amber badge) and the edit modal supports `payment_type=deposit`.
- Correct fix (to apply in Django port): filter by payment lifecycle, not settledness — e.g. list all sales (or `is_settled IN (0,1)`) and keep the بیعانه badge; settledness stays a payment-page concern. Calendar already lists both types.

---

## 4c8b2e1 — 2026-09-03 18:05
**type:** feat
**scope:** django
**subject:** scaffold Django rewrite: project, app, models, settings, requirements

- User decision: rebuild the app on **Django** instead of Flask; keep UI/UX byte-identical; run via venv + `requirements.txt` (no shell script); optimize for speed; tests come later on request.
- Moved the entire legacy Flask code to `legacy_flask/` (reference only — `app.py`, `database.py`, `excel_io.py`, `reports.py`, old `jalali.py`).
- Created `requirements.txt` (pinned): `Django==5.2.6`, `Jinja2==3.1.6`, `gunicorn==23.0.0`, `whitenoise==6.11.0`, `openpyxl==3.1.5`.
- Django project `tikotime/`: `settings.py` (SQLite in `data/`, whitenoise for static, Jinja2 template env for the existing templates), `jinja.py` (Jinja2 environment exposing `fa_date`/`fa_money`/`fa_num` and the same template globals Flask injected), `urls.py` (page routes mirroring legacy paths `/dashboard`, `/products`, …), `wsgi.py`, `manage.py`.
- App `inventory/`: `models.py` — ORM models mirroring the repaired legacy schema (`Setting`, `Product`, `Sale`, `Payment`, `Repair`, `Tracking`) with proper PK/FK (`Sale.product` CASCADE, `Payment.sale` CASCADE, `Payment.product` SET_NULL) and covering indexes for the hot sort/filter columns; ISO-string dates kept for drop-in compatibility with the existing JS; `jalali.py` copied unchanged; `utils.py` (fa_date/fa_money/parsers, product/sale dict serializers matching legacy JSON shape); `reports.py` (dashboard stats ported to ORM aggregates).
- Scaffolded empty packages: `inventory/views/`, `inventory/management/commands/`, `inventory/migrations/` — contents pending (see 9b2e4c6).

---

---

## f4a8c22 — 2026-09-03 17:05
**type:** fix
**scope:** db
**subject:** repair: rebuild products/sales with real PK/FK, fix NULL ids and raw Jalali dates

- Root cause of «deleted sales still showing in Calendar»: production `products`/`sales` tables had `id INT` (no PRIMARY KEY) instead of `INTEGER PRIMARY KEY`, so `PRAGMA foreign_keys=ON` cascades never fired — deleting a product left orphan sale rows that kept appearing in the Calendar as «محصول حذف‌شده», and inserts could even produce `id = NULL` rows that were undeletable from the UI (one found in production, customer «علی»).
- Added idempotent repair migration in `database.py::_migrate_inner`: rebuilds `products`/`sales` with full DDL (PK + FK ON DELETE CASCADE) using the existing `__rebuild` pattern, only when `PRAGMA table_info` shows the id column is not a true INTEGER PK.
- Assigns ids to NULL-id rows (collision-safe), normalizes raw Jalali sale dates (e.g. `1405/06/07` → `2026-08-29`) to ISO, adds missing columns for very old schemas, guards `payments`-update step, and syncs `sqlite_sequence` (guarding DBs where it doesn't exist yet).
- Migrated the real production DB after backing it up (see d9e1b05): all 4 products / 11 sales / 22 settings preserved, `integrity_check=ok`, `foreign_key_check` clean, NULL-id row now id=12 with correct ISO date.

---

## c5d9e17 — 2026-09-03 16:55
**type:** fix
**scope:** sales
**subject:** store parsed ISO dates, not raw Jalali strings, on sale create/deposit receipt

- `api_sales_create` parsed the incoming Jalali date (`۱۴۰۵/۰۶/۱۲` — the format the UI sends via `todayJalaliStr()`) but then INSERTed the raw string into `sales.sale_date`, so the row could never match the calendar's ISO date-range queries.
- Now inserts `parsed` (ISO) for `sales.sale_date`, and the auto-created deposit receipt (`payments.pay_date`) also stores `parsed`, matching the standalone payments route convention.
- `api_sales_update` already stored `parsed` — verified, no change needed.

---

## b3e7f60 — 2026-09-03 16:40
**type:** fix
**scope:** calendar
**subject:** auto-refresh calendar on bfcache back-navigation and tab focus

- Calendar is a live query over `sales`, but the page could show stale data after a sale was deleted elsewhere (browser Back restores the page from bfcache without refetching; another tab/computer on the LAN could delete while the calendar sits open).
- Added `refreshCalendar()` in `static/js/calendar.js`: re-fetches the current month and re-renders the selected day panel on `pageshow` (when `event.persisted`) and on `visibilitychange → visible`. Network errors are swallowed so the current view survives offline blips.

---

## d9e1b05 — 2026-09-03 16:28
**type:** chore
**scope:** data
**subject:** backup production DB before structural migration

- Copied `data/watch_inventory.db` → `data/backups/pre_migration_backup_20260903.db` (90,112 bytes) before running the PK/FK repair migration against the real database.

---

## e8c4a93 — 2026-09-03 17:10
**type:** test
**scope:** calendar
**subject:** add 37-check integration suite for sales/calendar consistency

- New `tests/test_calendar_sale_deletion.py` (Flask test client + temp DB via `TIKOTIME_DB`), covering: legacy-schema migration repair (NULL ids, raw Jalali dates, PK/FK rebuild, id preservation, sequence sync, no id collisions), Jalali→ISO date storage, calendar month/day visibility, single + bulk sale deletion removing entries from both calendar views, product-delete cascade removing its sales from the calendar, deposit receipt lifecycle, legacy undeletable row becoming deletable, and zero orphans in DB.
- Result: **37/37 PASS**. Run: `.venv/bin/python tests/test_calendar_sale_deletion.py`.
- App boot smoke-tested after changes: `/calendar`, `/payments`, `/api/calendar` → 200.



---

## a1f9c3e — 2026-09-03 00:00
**type:** chore
**scope:** memory
**subject:** init: create local memory/journal system

- Created `.memory/` directory at project root as the persistent local memory store.
- Added `JOURNAL.md` (this file) — GitHub-commit-style activity log for all work done on the project.
- Added `INDEX.md` — project context snapshot (stack, key files, domain concepts, data locations) for fast session orientation.
- Convention set: every future action on this project (code changes, fixes, exploration, decisions) will be logged here with a pseudo-hash, timestamp, type, scope, subject, and body.

---

## b7e2d41 — 2026-09-03 00:00
**type:** explore
**scope:** project
**subject:** docs: capture project baseline and structure

- Inspected project root: Flask app (`app.py`), SQLite layer (`database.py`), Excel/CSV I/O (`excel_io.py`), Jalali calendar (`jalali.py`), reports (`reports.py`), plus `templates/`, `static/`, and `data/` (db, images, backups, exports).
- Read `README.md`: TikoTime is a fully local, offline Persian watch-shop inventory system with Jalali calendar, one-row-per-watch inventory model, sales/repairs/payments/order-tracking modules, backup system, and light/dark RTL UI.
- No code modified — baseline observation only. Findings recorded in `.memory/INDEX.md`.
