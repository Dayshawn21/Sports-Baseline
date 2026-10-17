import gzip
import json
import re
import urllib.request
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta

URL = "https://www.tennisabstract.com/cgi-bin/player-classic.cgi?p=AlexanderZverev"


def pct(num, den):
    return round(num / den, 4) if den else None


def val(row, idx):
    try:
        v = row[idx]
        return float(v) if v not in ("", None, "NA") else 0.0
    except Exception:
        return 0.0


def fetch_text():
    req = urllib.request.Request(
        URL,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = resp.read()
        if resp.headers.get("Content-Encoding", "").lower() == "gzip":
            body = gzip.decompress(body)
        return body.decode("utf-8", errors="replace")


def extract_var(text, name):
    m = re.search(rf"var {re.escape(name)} = (.*?);", text)
    return m.group(1).strip() if m else None


def extract_array_var(text, name):
    m = re.search(rf"var {re.escape(name)} = (\[[\s\S]*?\]);", text)
    return json.loads(m.group(1)) if m else None


def extract_json_var(text, name):
    raw = extract_var(text, name)
    if raw is None:
        return None
    return json.loads(raw)


def parse_js_scalar(raw):
    if raw is None:
        return None
    raw = raw.strip()
    if raw.startswith("'") and raw.endswith("'"):
        return raw[1:-1]
    if raw.startswith('"') and raw.endswith('"'):
        return raw[1:-1]
    return raw


def parse_date(s):
    return datetime.strptime(str(s), "%Y%m%d").date()


def aggregate(rows):
    wins = losses = 0
    surfaces = Counter()
    opps = Counter()
    events = Counter()
    rounds = Counter()
    years = Counter()
    pts = fwon = swon = firsts = aces = dfs = games = saved = chances = 0.0
    opts = ofwon = oswon = ogames = osaved = ochances = 0.0
    match_dates = []
    top5 = top10 = top20 = top50 = 0

    for row in rows:
        if len(row) < 39:
            continue
        dt = parse_date(row[0])
        match_dates.append(dt.isoformat())
        years[str(dt.year)] += 1
        wl = row[4]
        if wl == "W":
            wins += 1
        elif wl == "L":
            losses += 1
        if row[2]:
            surfaces[row[2]] += 1
        if row[11]:
            opps[row[11]] += 1
        if row[1]:
            events[row[1]] += 1
        if row[8]:
            rounds[row[8]] += 1
        try:
            vr = int(row[12]) if row[12] not in ("", None, "NA") else None
        except Exception:
            vr = None
        if vr is not None:
            if vr <= 5:
                top5 += 1
            if vr <= 10:
                top10 += 1
            if vr <= 20:
                top20 += 1
            if vr <= 50:
                top50 += 1

        pts += val(row, 23)
        firsts += val(row, 24)
        fwon += val(row, 25)
        swon += val(row, 26)
        games += val(row, 27)
        saved += val(row, 28)
        chances += val(row, 29)
        aces += val(row, 21)
        dfs += val(row, 22)
        opts += val(row, 32)
        ofwon += val(row, 34)
        oswon += val(row, 35)
        ogames += val(row, 36)
        osaved += val(row, 37)
        ochances += val(row, 38)

    matches = wins + losses
    spw = pct(fwon + swon, pts)
    rpw = pct(opts - ofwon - oswon, opts)
    return {
        "matches": matches,
        "record": f"{wins}-{losses}",
        "win_rate": pct(wins, matches),
        "date_range": [min(match_dates) if match_dates else None, max(match_dates) if match_dates else None],
        "surfaces": dict(surfaces),
        "top_opponents": opps.most_common(15),
        "top_events": events.most_common(15),
        "rounds": dict(rounds),
        "years": dict(years),
        "vs_top": {"top5": top5, "top10": top10, "top20": top20, "top50": top50},
        "overview": {
            "first_in_pct": pct(firsts, pts),
            "first_won_pct": pct(fwon, firsts),
            "second_won_pct": pct(swon, pts - firsts),
            "svc_pts_won": spw,
            "ret_pts_won": rpw,
            "aces_pct": pct(aces, pts),
            "df_pct": pct(dfs, pts),
            "hold_pct": pct(games - (chances - saved), games),
            "break_pct": pct(ochances - osaved, ochances),
            "dominance_ratio": round(spw / (1 - rpw), 4) if spw is not None and rpw is not None and (1 - rpw) else None,
        },
    }


def latest_matches(rows, n=15):
    out = []
    for row in rows[:n]:
        out.append(
            {
                "date": parse_date(row[0]).isoformat(),
                "event": row[1],
                "surface": row[2],
                "level": row[3],
                "wl": row[4],
                "round": row[8],
                "score": row[9],
                "opponent": row[11],
                "opp_rank": row[12] if row[12] else None,
                "minutes": row[20] if row[20] else None,
            }
        )
    return out


def filtered(rows, predicate):
    return [row for row in rows if predicate(row)]


def event_records(rows):
    records = defaultdict(lambda: [0, 0])
    for row in rows:
        if len(row) < 5:
            continue
        event = row[1]
        wl = row[4]
        if wl == "W":
            records[event][0] += 1
        elif wl == "L":
            records[event][1] += 1
    out = []
    for event, (w, l) in records.items():
        out.append((event, w, l, round(w / (w + l), 4) if (w + l) else None))
    out.sort(key=lambda x: (x[1] + x[2], x[3] if x[3] is not None else 0), reverse=True)
    return out[:20]


def h2h_sample(rows):
    records = defaultdict(lambda: [0, 0])
    for row in rows:
        opp = row[11]
        wl = row[4]
        if wl == "W":
            records[opp][0] += 1
        elif wl == "L":
            records[opp][1] += 1
    out = []
    for opp, (w, l) in records.items():
        total = w + l
        if total >= 4:
            out.append((opp, w, l, total))
    out.sort(key=lambda x: (x[3], x[0]), reverse=True)
    return out[:25]


def main():
    text = fetch_text()
    with open("tmp_ta_zverev.html", "w", encoding="utf-8") as f:
        f.write(text)

    profile = {
        "fullname": parse_js_scalar(extract_var(text, "fullname")),
        "current_rank": int(extract_var(text, "currentrank")),
        "peak_rank": int(extract_var(text, "peakrank")),
        "peak_first": parse_date(extract_var(text, "peakfirst")).isoformat(),
        "peak_last": parse_date(extract_var(text, "peaklast")).isoformat(),
        "dob": parse_date(extract_var(text, "dob")).isoformat(),
        "height_cm": int(extract_var(text, "ht")),
        "hand": parse_js_scalar(extract_var(text, "hand")),
        "backhand_hands": int(parse_js_scalar(extract_var(text, "backhand"))),
        "country": parse_js_scalar(extract_var(text, "country")),
        "twitter": parse_js_scalar(extract_var(text, "twitter")),
        "itf_id": parse_js_scalar(extract_var(text, "itf_id")),
        "atp_id": parse_js_scalar(extract_var(text, "atp_id")),
        "elo_rating": int(parse_js_scalar(extract_var(text, "elo_rating"))),
        "elo_rank": int(parse_js_scalar(extract_var(text, "elo_rank"))),
    }

    rows = extract_array_var(text, "matchmx")
    today = date(2026, 4, 1)
    last_52_cutoff = today - timedelta(days=365)

    last_52 = filtered(rows, lambda r: parse_date(r[0]) >= last_52_cutoff)
    y2026 = filtered(rows, lambda r: str(r[0]).startswith("2026"))
    y2025 = filtered(rows, lambda r: str(r[0]).startswith("2025"))
    hard = filtered(rows, lambda r: r[2] == "Hard")
    clay = filtered(rows, lambda r: r[2] == "Clay")
    grass = filtered(rows, lambda r: r[2] == "Grass")
    grand_slams = filtered(rows, lambda r: r[3] == "G")
    masters = filtered(rows, lambda r: r[1] in {
        "Indian Wells Masters", "Miami Masters", "Monte Carlo Masters", "Madrid Masters",
        "Rome Masters", "Canada Masters", "Cincinnati Masters", "Shanghai Masters", "Paris Masters"
    })

    output = {
        "source_url": URL,
        "profile": profile,
        "page_sections": {
            "tabs": ["Singles Results", "Head-to-Heads", "Event Records", "Doubles Results"],
            "stat_views": ["Overview", "Serve", "Return", "Raw"],
            "filter_dimensions": ["Time Span", "Event", "vs Country", "as Rank", "vs Opponent", "vs Age", "vs Height"],
        },
        "career": aggregate(rows),
        "last_52_weeks": aggregate(last_52),
        "season_2026": aggregate(y2026),
        "season_2025": aggregate(y2025),
        "surface_splits": {
            "hard": aggregate(hard),
            "clay": aggregate(clay),
            "grass": aggregate(grass),
        },
        "grand_slams": aggregate(grand_slams),
        "masters_1000": aggregate(masters),
        "recent_matches": latest_matches(rows, 15),
        "best_known_event_records": event_records(rows),
        "h2h_sample_total_meetings_ge_4": h2h_sample(rows),
    }

    print(json.dumps(output, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
