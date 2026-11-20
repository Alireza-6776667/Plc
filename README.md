# PLC Ladder Telegram Bot

یک ربات تلگرام همراه با Mini App برای طراحی نقشه‌ی Ladder (LD) مطابق IEC 61131-3.

## امکانات
- ویرایشگر Ladder داخل تلگرام (کنتاکت NO/NC، کویل، ست/ریست، TON، CTU)
- پیش‌نمایش ASCII نقشه
- تولید خودکار کد Structured Text (`.st`)
- ذخیره‌ی محلی برنامه داخل مرورگر Mini App

## ساختار
```
plc-telegram-bot/
├── bot.py              # ربات aiogram (اعتبارسنجی، ASCII و تولید ST)
├── docs/index.html     # Mini App (برای GitHub Pages)
├── requirements.txt
├── .env.example
└── .gitignore
```

## ۱. ساخت ربات
1. در تلگرام به @BotFather پیام بدهید و `/newbot` را بزنید. توکن را کپی کنید.

## ۲. انتشار Mini App روی GitHub Pages
1. این پروژه را در یک ریپازیتوری گیت‌هاب push کنید.
2. در تنظیمات ریپو: **Settings → Pages → Build and deployment**
   - Source: `Deploy from a branch`
   - Branch: `main` و پوشه `/docs`
3. بعد از چند دقیقه آدرسی شبیه `https://USERNAME.github.io/plc-telegram-bot/` ساخته می‌شود.

## ۳. اجرای ربات
```bash
cp .env.example .env
# مقادیر BOT_TOKEN و WEBAPP_URL را در .env وارد کنید

python -m venv .venv
source .venv/bin/activate        # ویندوز: .venv\Scripts\activate
pip install -r requirements.txt
python bot.py
```

## ۴. استفاده
1. در ربات `/start` بزنید.
2. دکمه‌ی «🛠 باز کردن نقشه‌کش PLC» را بزنید.
3. ردیف‌ها را بسازید؛ هر ردیف باید در انتها یک خروجی داشته باشد.
4. «📤 ارسال به ربات» را بزنید تا پیش‌نمایش و فایل `program.st` دریافت شود.

## نکات مهم
- Mini App فقط داخل تلگرام و در چت خصوصی با ربات کار می‌کند.
- تلگرام محدودیت حدود ۴ کیلوبایت برای داده‌ی ارسالی از Mini App دارد؛ برای برنامه‌های خیلی بزرگ باید بخش ارسال را با یک API یا Webhook جایگزین کنید.
- این ابزار برای طراحی و تولید کد است و به PLC واقعی متصل نمی‌شود. قبل از اجرای روی سخت‌افزار، کد را در محیط شبیه‌ساز تست کنید.
- فایل `.env` را هرگز commit نکنید (در `.gitignore` قرار دارد). اگر توکن لو رفت، از BotFather آن را revoke کنید.

## گسترش‌های پیشنهادی
- شاخه‌های موازی (Parallel branches) در Ladder
- خروجی به فرمت PLCopen XML برای Codesys/TIA Portal
- ذخیره‌ی پروژه در دیتابیس با شناسه‌ی کاربر تلگرام
