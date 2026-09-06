#!/usr/bin/env bash
# اجرای سیستم مدیریت انبار ساعت — TikoTime
cd "$(dirname "$0")"

# اگر محیط مجازی وجود ندارد، بساز
if [ ! -d ".venv" ]; then
    echo "در حال آماده‌سازی اولیه (فقط بار اول)…"
    python3 -m venv .venv
    ./.venv/bin/pip install --quiet flask openpyxl waitress
fi

exec ./.venv/bin/python app.py
