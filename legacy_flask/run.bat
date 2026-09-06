@echo off
rem اجرای سیستم مدیریت انبار ساعت — TikoTime (ویندوز)
cd /d "%~dp0"

if not exist ".venv" (
    echo در حال آماده‌سازی اولیه (فقط بار اول^)...
    python -m venv .venv
    .venv\Scripts\pip install flask openpyxl waitress
)

.venv\Scripts\python app.py
