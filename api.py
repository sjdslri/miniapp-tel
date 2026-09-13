"""
API برای Mini App — خواندن داده از دیتابیس
اگر دیتابیس خالی باشد، داده‌های نمونه برمی‌گرداند.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import sqlite3
import os

DB_PATH = Path(__file__).parent / "monitor.db"

app = FastAPI(title="Monitor API")

# اجازه دسترسی از هر دامنه (GitHub Pages)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


# ============================================================
# داده‌های نمونه (اگر دیتابیس نبود)
# ============================================================
SAMPLE_DATA = {
    "total": 288,
    "water": 254,
    "energy": 34,
    "channels_count": 31,
    "persons_count": 7,
    "daily": [
        {"date": "۱۴ شهریور", "count": 32},
        {"date": "۱۵ شهریور", "count": 45},
        {"date": "۱۶ شهریور", "count": 28},
        {"date": "۱۷ شهریور", "count": 51},
        {"date": "۱۸ شهریور", "count": 62},
        {"date": "۱۹ شهریور", "count": 38},
        {"date": "۲۰ شهریور", "count": 201},
        {"date": "۲۱ شهریور", "count": 87},
    ],
    "categories": [
        {"name": "فاضلاب و تصفیه", "count": 97},
        {"name": "مدیریت و مقامات", "count": 93},
        {"name": "سایر", "count": 80},
        {"name": "آموزش و فرهنگ", "count": 42},
        {"name": "پروژه و آبرسانی", "count": 37},
        {"name": "برق و انرژی", "count": 34},
        {"name": "مدیریت مصرف", "count": 32},
        {"name": "افتتاح و بهره‌برداری", "count": 28},
        {"name": "روستا و محرومیت", "count": 26},
    ],
    "channels": [
        {"name": "صدا و سیمای استان البرز", "username": "alborz_tv", "count": 58},
        {"name": "صدا و سیمای کرمانشاه", "username": "tvzagross", "count": 35},
        {"name": "همکار", "username": "hamkaar", "count": 31},
        {"name": "آبفا خبر", "username": "abfa_khabar", "count": 18},
        {"name": "شرکت آب و فاضلاب فارس", "username": "abfafars", "count": 15},
        {"name": "خبرگزاری صدا و سیما", "username": "iribnews", "count": 12},
        {"name": "آب و فاضلاب خراسان جنوبی", "username": "abfakhj", "count": 12},
        {"name": "کانال خبری وزارت نیرو", "username": "niroonline", "count": 12},
    ],
    "persons": [
        {"name": "احمد سلامت", "role": "مدیرعامل فاضلاب تهران", "count": 13},
        {"name": "مسعود پزشکیان", "role": "رئیس‌جمهور", "count": 8},
        {"name": "عباس علی‌آبادی", "role": "وزیر نیرو", "count": 7},
        {"name": "محمدرضا عارف", "role": "معاون اول", "count": 2},
        {"name": "بهزاد برارزاده", "role": "مدیرعامل آبفای مازندران", "count": 2},
        {"name": "محمدرضا رمضان‌زاده", "role": "مدیر آبفای ورامین", "count": 1},
        {"name": "محمد اله‌داد", "role": "مدیرعامل توانیر", "count": 1},
    ],
}


def get_conn():
    if not DB_PATH.exists():
        return None
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


@app.get("/")
def root():
    return {
        "status": "ok",
        "message": "Monitor API is running",
        "database": "connected" if DB_PATH.exists() else "not found (using sample data)",
    }


@app.get("/api/dashboard")
def dashboard():
    """دریافت داده‌های داشبورد"""
    conn = get_conn()
    if not conn:
        return SAMPLE_DATA

    try:
        total = conn.execute("SELECT COUNT(*) FROM keyword_matches").fetchone()[0]
        if total == 0:
            return SAMPLE_DATA

        water = conn.execute(
            "SELECT COUNT(*) FROM keyword_matches WHERE matched_keywords LIKE '%آب%' OR matched_keywords LIKE '%فاضلاب%'"
        ).fetchone()[0]
        energy = conn.execute(
            "SELECT COUNT(*) FROM keyword_matches WHERE matched_keywords LIKE '%برق%' OR matched_keywords LIKE '%انرژی%'"
        ).fetchone()[0]

        daily_rows = conn.execute("""
            SELECT DATE(message_date) as d, COUNT(*) as c
            FROM keyword_matches
            WHERE message_date >= DATE('now', '-7 days')
            GROUP BY DATE(message_date)
            ORDER BY d
        """).fetchall()

        channel_rows = conn.execute("""
            SELECT channel_username, channel_title, COUNT(*) as c
            FROM keyword_matches
            GROUP BY channel_username
            ORDER BY c DESC
            LIMIT 10
        """).fetchall()

        return {
            "total": total,
            "water": water,
            "energy": energy,
            "channels_count": len(channel_rows),
            "persons_count": 7,
            "daily": [{"date": r["d"], "count": r["c"]} for r in daily_rows],
            "categories": SAMPLE_DATA["categories"],
            "channels": [
                {"name": r["channel_title"] or r["channel_username"],
                 "username": r["channel_username"],
                 "count": r["c"]}
                for r in channel_rows
            ],
            "persons": SAMPLE_DATA["persons"],
        }
    finally:
        conn.close()
