"""
API برای Mini App — خواندن داده‌های واقعی از دیتابیس
"""
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import sqlite3
from datetime import datetime, timedelta
from collections import Counter

DB_PATH = Path(__file__).parent / "monitor.db"

app = FastAPI(title="Monitor API v2")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


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
        "message": "Monitor API v2",
        "database": "connected" if DB_PATH.exists() else "not found"
    }


@app.get("/api/dashboard")
def dashboard(
    from_date: str = Query(None),
    to_date: str = Query(None),
):
    conn = get_conn()
    if not conn:
        return {"error": "database not found", "total": 0}

    try:
        if not from_date:
            from_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        if not to_date:
            to_date = datetime.now().strftime("%Y-%m-%d")

        start = f"{from_date} 00:00:00"
        end = f"{to_date} 23:59:59"

        total = conn.execute(
            "SELECT COUNT(*) FROM keyword_matches WHERE message_date BETWEEN ? AND ?",
            (start, end)
        ).fetchone()[0]

        water_kw = ['آب', 'فاضلاب', 'تصفیه', 'پساب', 'آبرسانی', 'چاه', 'مخزن', 'خط انتقال', 'شبکه توزیع']
        energy_kw = ['برق', 'انرژی', 'نیروگاه', 'شبکه برق', 'توانیر', 'تجدیدپذیر', 'خورشیدی', 'بادی']

        rows = conn.execute(
            "SELECT matched_keywords FROM keyword_matches WHERE message_date BETWEEN ? AND ?",
            (start, end)
        ).fetchall()

        water_count = 0
        energy_count = 0
        for r in rows:
            kw_text = r["matched_keywords"] or ""
            if any(k in kw_text for k in water_kw):
                water_count += 1
            if any(k in kw_text for k in energy_kw):
                energy_count += 1

        daily_rows = conn.execute("""
            SELECT DATE(message_date) as d, COUNT(*) as c
            FROM keyword_matches
            WHERE message_date BETWEEN ? AND ?
            GROUP BY DATE(message_date)
            ORDER BY d
        """, (start, end)).fetchall()

        hourly_rows = conn.execute("""
            SELECT strftime('%H', message_date) as h, COUNT(*) as c
            FROM keyword_matches
            WHERE message_date BETWEEN ? AND ?
            GROUP BY strftime('%H', message_date)
        """, (start, end)).fetchall()
        hourly = [0] * 24
        for r in hourly_rows:
            if r["h"]:
                hourly[int(r["h"])] = r["c"]

        channel_rows = conn.execute("""
            SELECT channel_username, channel_title, COUNT(*) as c
            FROM keyword_matches
            WHERE message_date BETWEEN ? AND ?
            GROUP BY channel_username
            ORDER BY c DESC
        """, (start, end)).fetchall()

        channels = []
        for r in channel_rows:
            msgs = conn.execute("""
                SELECT message_id, message_text, matched_keywords, message_date, message_link
                FROM keyword_matches
                WHERE channel_username = ? AND message_date BETWEEN ? AND ?
                ORDER BY message_date DESC
                LIMIT 20
            """, (r["channel_username"], start, end)).fetchall()

            channels.append({
                "name": r["channel_title"] or r["channel_username"],
                "username": r["channel_username"],
                "count": r["c"],
                "messages": [{
                    "text": m["message_text"],
                    "date": m["message_date"][:16] if m["message_date"] else "",
                    "keywords": (m["matched_keywords"] or "").split(", "),
                    "link": m["message_link"],
                } for m in msgs]
            })

        kw_counter = Counter()
        for r in rows:
            for k in (r["matched_keywords"] or "").split(", "):
                if k.strip():
                    kw_counter[k.strip()] += 1
        categories = [{"name": k, "count": v} for k, v in kw_counter.most_common(10)]

        persons_data = [
            {"name": "عباس علی‌آبادی", "role": "وزیر نیرو", "aliases": ["علی‌آبادی", "علی آبادی", "وزیر نیرو"]},
            {"name": "احمد سلامت", "role": "مدیرعامل فاضلاب تهران", "aliases": ["سلامت"]},
            {"name": "مسعود پزشکیان", "role": "رئیس‌جمهور", "aliases": ["پزشکیان", "رئیس‌جمهور"]},
            {"name": "علیرضا عبدیان", "role": "مدیرعامل آبفای کرمان", "aliases": ["عبدیان"]},
            {"name": "بهزاد برارزاده", "role": "مدیرعامل آبفای مازندران", "aliases": ["برارزاده"]},
        ]
        persons = []
        for p in persons_data:
            mention_count = 0
            mentions = []
            for alias in p["aliases"]:
                m_rows = conn.execute("""
                    SELECT message_text, channel_title, message_date, matched_keywords
                    FROM keyword_matches
                    WHERE message_text LIKE ? AND message_date BETWEEN ? AND ?
                    LIMIT 10
                """, (f"%{alias}%", start, end)).fetchall()
                for m in m_rows:
                    mention_count += 1
                    mentions.append({
                        "text": m["message_text"][:200],
                        "channel": "@" + (m["channel_title"] or ""),
                        "date": m["message_date"][:10] if m["message_date"] else "",
                        "keywords": (m["matched_keywords"] or "").split(", "),
                    })
            if mention_count > 0:
                persons.append({
                    "name": p["name"],
                    "role": p["role"],
                    "count": mention_count,
                    "mentions": mentions[:5]
                })

        return {
            "total": total,
            "water": water_count,
            "energy": energy_count,
            "channelsCount": len(channels),
            "personsCount": len(persons),
            "daily": [{"date": r["d"], "count": r["c"]} for r in daily_rows],
            "hourly": hourly,
            "categories": categories,
            "channels": channels,
            "persons": persons,
            "range": {"from": from_date, "to": to_date}
        }
    except Exception as e:
        return {"error": str(e), "total": 0}
    finally:
        conn.close()
