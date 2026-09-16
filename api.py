"""
API برای Mini App — خوندن از Supabase
"""
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
import os
from datetime import datetime, timedelta
from collections import Counter

app = FastAPI(title="Monitor API v3")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("SUPABASE_URL و SUPABASE_KEY تنظیم نشده")

from supabase import create_client
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


def fetch_all_matches(client, start: str, end: str):
    """واکشی همه ردیف‌ها با pagination (دور زدن محدودیت ۱۰۰۰ تایی Supabase)"""
    # ۱) گرفتن تعداد کل با count
    try:
        count_res = (
            client.table("keyword_matches")
            .select("id", count="exact")
            .gte("message_date", start)
            .lte("message_date", end)
            .limit(0)
            .execute()
        )
        total_count = count_res.count or 0
    except Exception as e:
        print(f"[fetch_all_matches] count error: {e}")
        total_count = 0

    # ۲) واکشی با pagination
    all_rows = []
    page_size = 1000
    offset = 0
    while offset < total_count or total_count == 0:
        try:
            res = (
                client.table("keyword_matches")
                .select("*")
                .gte("message_date", start)
                .lte("message_date", end)
                .order("message_date", desc=True)
                .range(offset, offset + page_size - 1)
                .execute()
            )
        except Exception as e:
            print(f"[fetch_all_matches] fetch error at offset {offset}: {e}")
            break
        batch = res.data or []
        all_rows.extend(batch)
        if len(batch) < page_size:
            break
        offset += page_size
        if total_count == 0:
            break
    return all_rows




@app.get("/")
def root():
    return {"status": "ok", "message": "Monitor API v3", "backend": "supabase"}


@app.get("/health")
def health():
    return {"status": "healthy"}


@app.get("/api/dashboard")
def dashboard(
    from_date: str = Query(None),
    to_date: str = Query(None),
):
    try:
        if not from_date:
            from_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        if not to_date:
            to_date = datetime.now().strftime("%Y-%m-%d")

        start = f"{from_date} 00:00:00"
        end = f"{to_date} 23:59:59"

        rows = fetch_all_matches(supabase, start, end)

        total = len(rows)
        if total == 0:
            return {
                "total": 0, "water": 0, "energy": 0, "project": 0,
                "channelsCount": 0, "personsCount": 0,
                "daily": [], "hourly": [0]*24,
                "categories": [], "channels": [], "persons": [],
                "range": {"from": from_date, "to": to_date}
            }

        water_kw = ['آب', 'فاضلاب', 'تصفیه', 'پساب', 'آبرسانی', 'چاه', 'مخزن', 'خط انتقال']
        project_kw = ['پروژه', 'افتتاح', 'بهره‌برداری', 'کلنگ']

        water_count = sum(1 for r in rows if any(k in (r.get("matched_keywords") or "") for k in water_kw))
        project_count = sum(1 for r in rows if any(k in (r.get("matched_keywords") or "") for k in project_kw))

        daily_counts = Counter()
        for r in rows:
            d = (r.get("message_date") or "")[:10]
            if d:
                daily_counts[d] += 1
        daily = [{"date": d, "count": c} for d, c in sorted(daily_counts.items())]

        hourly = [0] * 24
        for r in rows:
            dt = r.get("message_date") or ""
            if len(dt) >= 13:
                try:
                    h = int(dt[11:13])
                    hourly[h] += 1
                except:
                    pass

        channel_groups = {}
        for r in rows:
            u = r.get("channel_username") or "unknown"
            channel_groups.setdefault(u, []).append(r)
        
        channels = []
        for u, msgs in sorted(channel_groups.items(), key=lambda x: -len(x[1])):
            channels.append({
                "name": msgs[0].get("channel_title") or u,
                "username": u,
                "count": len(msgs),
                "messages": [{
                    "text": m.get("message_text"),
                    "date": (m.get("message_date") or "")[:16],
                    "keywords": (m.get("matched_keywords") or "").split(", "),
                    "link": m.get("message_link"),
                } for m in msgs[:20]]
            })

        kw_counter = Counter()
        for r in rows:
            for k in (r.get("matched_keywords") or "").split(", "):
                if k.strip():
                    kw_counter[k.strip()] += 1
        categories = [{"name": k, "count": v} for k, v in kw_counter.most_common(10)]

        persons_data = [
            {"name": "عباس علی‌آبادی", "role": "وزیر نیرو", "aliases": ["علی‌آبادی", "وزیر نیرو"]},
            {"name": "علیرضا عبدیان", "role": "مدیرعامل آبفای کرمان", "aliases": ["عبدیان"]},
            {"name": "احمد سلامت", "role": "مدیرعامل فاضلاب تهران", "aliases": ["سلامت"]},
        ]
        persons = []
        for p in persons_data:
            mentions = []
            for alias in p["aliases"]:
                for r in rows:
                    if alias in (r.get("message_text") or ""):
                        mentions.append({
                            "text": (r.get("message_text") or "")[:200],
                            "channel": "@" + (r.get("channel_username") or ""),
                            "date": (r.get("message_date") or "")[:10],
                            "keywords": (r.get("matched_keywords") or "").split(", "),
                        })
            if mentions:
                persons.append({
                    "name": p["name"], "role": p["role"],
                    "count": len(mentions), "mentions": mentions[:5]
                })

        return {
            "total": total,
            "water": water_count,
            "energy": project_count,
            "project": project_count,
            "channelsCount": len(channels),
            "personsCount": len(persons),
            "daily": daily,
            "hourly": hourly,
            "categories": categories,
            "channels": channels,
            "persons": persons,
            "range": {"from": from_date, "to": to_date}
        }
    except Exception as e:
        return {"error": str(e), "total": 0}
