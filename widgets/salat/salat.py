"""wingbar widget: salat (helper of salat.sh; see README.md).

Next prayer and countdown for a city in Morocco, from the Ministry of Habous'
official timetable. Python 3.9+ (the Xcode Command Line Tools' python3), no
third-party modules.

  salat.py                    print the widget (line 1, icon, menu)
  salat.py refresh            re-download the timetable on the next run
  salat.py mark KEY DATE      (WINGBAR_SALAT_TRACK=1) tick a prayer as prayed
  salat.py unmark KEY DATE    remove that tick
"""
import json
import math
import os
import re
import subprocess
import sys
import time
import unicodedata
from datetime import date, datetime, timedelta

HABOUS = "https://www.habous.gov.ma/data/horaires-{}.js"   # one file per month, every city
CITIES_URL = "https://salat-maghrib.vercel.app/city"       # city coordinates (auto only)
GEO_URL = "https://ipinfo.io/loc"                            # "lat,lng" of this IP (auto only)
HABOUS_PAGE = "https://www.habous.gov.ma/"

CURL = os.environ.get("WINGBAR_CURL") or "curl"
CACHE = os.path.join(os.environ.get("TMPDIR") or "/tmp", "wingbar-salat")
STATE = os.path.join(os.environ.get("XDG_STATE_HOME") or os.path.expanduser("~/.local/state"), "wingbar-salat")
SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "salat.sh")

FALLBACK_ID = 1   # Rabat: used when WINGBAR_SALAT_CITY=auto can't find a city
RETRY_S = 600     # after a failed download, wait this long before trying again
MONTH_MAX_AGE = 7 * 86400
CITIES_MAX_AGE = 7 * 86400
AUTO_MAX_AGE = 6 * 3600
AUTO_MAX_KM = 300  # farther than this from every listed city: not in Morocco
STATE_KEEP_DAYS = 60

# Habous column order. Display names, bundled wingbar icons, SF Symbols.
ORDER = ["fajr", "chorouq", "dohr", "asr", "maghrib", "ishae"]
FIVE = ["fajr", "dohr", "asr", "maghrib", "ishae"]
NAMES = {"fajr": "Fajr", "chorouq": "Sunrise", "dohr": "Dhuhr", "asr": "Asr", "maghrib": "Maghrib", "ishae": "Isha"}
BUNDLED = {"fajr": "Fajr", "chorouq": "Chorouq", "dohr": "Dohr", "asr": "Asr", "maghrib": "Maghrib", "ishae": "Ishae"}
SF = {"fajr": "sunrise", "chorouq": "sun.horizon", "dohr": "sun.max", "asr": "sun.haze",
      "maghrib": "sunset", "ishae": "moon.stars"}

# Latin names of the Habous city ids (the timetable names cities in Arabic;
# Arabic names and plain ids work too). The first name is the one shown.
LATIN = {
    1: ["Rabat"], 2: ["Khemisset"], 3: ["Tiflet"], 6: ["Bouznika"], 7: ["Kenitra"],
    8: ["Sidi Kacem"], 10: ["Sidi Slimane"], 11: ["Souk El Arbaa"], 14: ["Tangier", "Tanger", "Tangiers"],
    15: ["Tetouan"], 16: ["Larache"], 17: ["Asilah"], 18: ["Chefchaouen", "Chaouen"], 19: ["Martil"],
    20: ["M'diq"], 21: ["Ksar El Kebir"], 23: ["Al Hoceima"], 24: ["Ceuta", "Sebta"], 25: ["Fnideq"],
    29: ["Ouazzane"], 31: ["Oujda"], 32: ["Berkane"], 33: ["Figuig"], 34: ["Bouarfa"], 35: ["Guercif"],
    36: ["Jerada"], 38: ["Taourirt"], 39: ["Nador"], 40: ["Melilla"], 49: ["Saidia"], 54: ["Zaio"],
    55: ["Driouch"], 58: ["Casablanca", "Casa"], 59: ["Mohammedia"], 60: ["Benslimane"], 61: ["Settat"],
    64: ["Ben Ahmed"], 65: ["Berrechid"], 66: ["El Jadida"], 67: ["Azemmour"], 68: ["Sidi Bennour"],
    70: ["Khenifra"], 73: ["Beni Mellal"], 74: ["Azilal"], 75: ["Fquih Ben Salah"], 76: ["Demnate"],
    78: ["Kasba Tadla"], 79: ["Khouribga"], 80: ["Oued Zem"], 81: ["Fes", "Fez"], 82: ["Sefrou"],
    83: ["Moulay Yacoub"], 85: ["Missour"], 89: ["Taza"], 90: ["Taounate"], 99: ["Meknes"], 100: ["Ifrane"],
    101: ["El Hajeb"], 103: ["Azrou"], 104: ["Marrakech", "Marrakesh"], 105: ["Kelaat Sraghna"],
    106: ["Essaouira"], 107: ["Chichaoua"], 108: ["Ben Guerir"], 111: ["Safi"], 112: ["Oualidia"],
    113: ["Youssoufia"], 117: ["Agadir"], 118: ["Taroudant"], 119: ["Tiznit"], 122: ["Tafraout"],
    123: ["Tata"], 127: ["Ouled Teima"], 128: ["Errachidia"], 129: ["Rissani"], 130: ["Erfoud"],
    135: ["Rich"], 136: ["Midelt"], 137: ["Zagora"], 138: ["Ouarzazate"], 139: ["Tinghir"],
    141: ["Kalaat M'Gouna"], 148: ["Sidi Ifni"], 149: ["Guelmim"], 150: ["Assa"], 152: ["Tan-Tan"],
    156: ["Laayoune"], 157: ["Smara"], 158: ["Boujdour"], 159: ["Tarfaya"], 165: ["Dakhla"],
    305: ["Imintanoute"],
}

HHMM = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
out = []


def emit(line):
    out.append(line)


def clean(s):
    """Text from elsewhere, safe in a menu title: no `|`, no control characters."""
    return "".join(c for c in str(s) if c != "|" and unicodedata.category(c)[0] != "C").strip()


def norm(s):
    s = unicodedata.normalize("NFKD", s.strip().lower())
    return "".join(c for c in s if c.isalnum() and not unicodedata.combining(c))


def ensure_dir(d):
    os.makedirs(d, exist_ok=True)


def age(path):
    try:
        return time.time() - os.stat(path).st_mtime
    except OSError:
        return None


def write_atomic(path, text):
    tmp = f"{path}.{os.getpid()}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, path)


def fetch(url, dest, check, max_time=10):
    """Download url to dest if `check(text)` accepts it. After a failure, no new
    try for RETRY_S (so an offline Mac doesn't wait on curl every run)."""
    stamp = dest + ".failed"
    a = age(stamp)
    if a is not None and a < RETRY_S:
        return False
    tmp = f"{dest}.{os.getpid()}.dl"
    ok = False
    try:
        r = subprocess.run([CURL, "-sfL", "--max-time", str(max_time), "-A", "wingbar-salat", "-o", tmp, url],
                           stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           timeout=max_time + 5)
        if r.returncode == 0:
            with open(tmp, encoding="utf-8") as f:
                ok = bool(check(f.read()))
    except (OSError, subprocess.SubprocessError, UnicodeDecodeError, ValueError):
        ok = False
    if ok:
        os.replace(tmp, dest)
        try:
            os.remove(stamp)
        except OSError:
            pass
    else:
        try:
            os.remove(tmp)
        except OSError:
            pass
        with open(stamp, "w"):
            pass
    return ok


# ── the Habous timetable ──────────────────────────────────────────────────────

def parse_month(text):
    """{city id: {"n": arabic name, "h": [[6 times] per day]}} from a monthly file."""
    data = json.loads(text[text.index("push(") + 5: text.rindex(")")])
    return {int(v["c"]): v for v in data["villes"]}


_months = {}


def month(ym):
    """The parsed monthly file for "YYYY-MM", downloading it when missing or a
    week old (an old copy is still used when the download fails)."""
    if ym in _months:
        return _months[ym]
    path = os.path.join(CACHE, f"habous_{ym}.js")
    a = age(path)
    if a is None or a > MONTH_MAX_AGE:
        fetch(HABOUS.format(ym), path, parse_month, max_time=15)
    try:
        with open(path, encoding="utf-8") as f:
            m = parse_month(f.read())
    except (OSError, ValueError, KeyError, TypeError):
        m = None
    _months[ym] = m
    return m


def times_for(day, cid):
    """{"fajr": "HH:MM", ...} for one day and city, cached per day."""
    path = os.path.join(CACHE, f"times_{day.isoformat()}_{cid}.json")
    try:
        with open(path, encoding="utf-8") as f:
            t = json.load(f)
        if all(HHMM.match(str(t.get(k, ""))) for k in ORDER):
            return t
    except (OSError, ValueError, AttributeError):
        pass
    m = month(day.strftime("%Y-%m"))
    if not m or cid not in m:
        return None
    try:
        row = m[cid]["h"][day.day - 1]
    except (IndexError, KeyError, TypeError):
        return None
    t = dict(zip(ORDER, row))
    if len(row) < 6 or not all(HHMM.match(str(t[k])) for k in ORDER):
        return None
    write_atomic(path, json.dumps(t))
    return t


def tidy(today):
    """Keep yesterday's to tomorrow's day files and last to next month's files."""
    days = {(today + timedelta(days=d)).isoformat() for d in (-1, 0, 1)}
    first = today.replace(day=1)
    prev = (first - timedelta(days=1)).strftime("%Y-%m")
    nxt = (first + timedelta(days=32)).strftime("%Y-%m")
    months = {prev, today.strftime("%Y-%m"), nxt}
    for name in os.listdir(CACHE):
        m = re.match(r"^times_(\d{4}-\d\d-\d\d)_\d+\.json$", name)
        h = re.match(r"^habous_(\d{4}-\d\d)\.js(\.failed)?$", name)
        if (m and m.group(1) not in days) or (h and h.group(1) not in months):
            try:
                os.remove(os.path.join(CACHE, name))
            except OSError:
                pass


# ── the city ──────────────────────────────────────────────────────────────────

def city_name(cid, m):
    if cid in LATIN:
        return LATIN[cid][0]
    if m and cid in m:
        return clean(m[cid].get("n", "")) or f"city {cid}"
    return f"city {cid}"


def city_by_name(setting, m):
    """A city id for a name (Latin from the table, or the timetable's Arabic) or id."""
    s = setting.strip()
    if s.isdigit():
        return int(s)
    want = norm(s)
    for cid, names in LATIN.items():
        if any(norm(n) == want for n in names):
            return cid
    for cid, v in (m or {}).items():
        if norm(str(v.get("n", ""))) == want:
            return cid
    return None


def dms(v):
    """The city list's coordinates are degrees.minutes (33.34 = 33°34'), with
    trailing zeros dropped (.4 = 40', unless that is over 59, then 4')."""
    sign = -1 if v < 0 else 1
    v = abs(v)
    d = int(v)
    mins = round((v - d) * 100, 4)
    if mins >= 60:
        mins /= 10
    return sign * (d + mins / 60)


def km(lat1, lng1, lat2, lng2):
    p = math.pi / 180
    a = (0.5 - math.cos((lat2 - lat1) * p) / 2
         + math.cos(lat1 * p) * math.cos(lat2 * p) * (1 - math.cos((lng2 - lng1) * p)) / 2)
    return 12742 * math.asin(math.sqrt(a))


def auto_city(m):
    """(city id, note): the listed city nearest to this IP's location, cached
    for 6 hours (only the id is kept, never the coordinates)."""
    path = os.path.join(CACHE, "auto_city")
    try:
        with open(path) as f:
            cached = int(f.read().strip())
    except (OSError, ValueError):
        cached = None
    a = age(path)
    if cached is not None and a is not None and a < AUTO_MAX_AGE:
        return cached, ""
    cities_path = os.path.join(CACHE, "cities.json")
    ca = age(cities_path)
    if ca is None or ca > CITIES_MAX_AGE:
        fetch(CITIES_URL, cities_path, lambda t: isinstance(json.loads(t), list), max_time=8)
    geo_stamp = os.path.join(CACHE, "geo")
    loc = None
    ga = age(geo_stamp + ".failed")
    if ga is None or ga > RETRY_S:
        try:
            r = subprocess.run([CURL, "-sf", "--max-time", "5", "-A", "wingbar-salat", GEO_URL],
                               stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=10)
            g = re.match(r"^\s*(-?\d+(?:\.\d+)?),\s*(-?\d+(?:\.\d+)?)\s*$", r.stdout or "")
            if r.returncode == 0 and g:
                loc = (float(g.group(1)), float(g.group(2)))
        except (OSError, subprocess.SubprocessError):
            pass
        if loc is None:
            with open(geo_stamp + ".failed", "w"):
                pass
    best = None
    if loc:
        try:
            with open(cities_path, encoding="utf-8") as f:
                cities = json.load(f)
            for c in cities:
                cid = int(c["id"])
                if m and cid not in m:
                    continue
                d = km(loc[0], loc[1], dms(float(c["latitude"])), dms(float(c["longitude"])))
                if best is None or d < best[1]:
                    best = (cid, d)
        except (OSError, ValueError, KeyError, TypeError):
            best = None
    if best and best[1] <= AUTO_MAX_KM:
        write_atomic(path, str(best[0]))
        return best[0], ""
    if cached is not None:
        return cached, "location not updated"
    why = "not in Morocco" if best else "location unavailable"
    return FALLBACK_ID, f"{why}, using {LATIN[FALLBACK_ID][0]}"


# ── tracking (WINGBAR_SALAT_TRACK=1) ─────────────────────────────────────────

def ticks(day):
    """{key: "HH:MM"} prayed on a prayer-day."""
    got = {}
    try:
        with open(os.path.join(STATE, day.isoformat())) as f:
            for line in f:
                p = line.split()
                if len(p) == 2 and p[0] in FIVE:
                    got[p[0]] = p[1]
    except OSError:
        pass
    return got


def set_tick(key, ds, on):
    if key not in FIVE or not re.match(r"^\d{4}-\d\d-\d\d$", ds or ""):
        sys.exit(2)
    day = date.fromisoformat(ds)
    got = ticks(day)
    if on:
        got.setdefault(key, clock().strftime("%H:%M"))
    else:
        got.pop(key, None)
    ensure_dir(STATE)
    path = os.path.join(STATE, ds)
    if got:
        write_atomic(path, "".join(f"{k} {got[k]}\n" for k in FIVE if k in got))
    else:
        try:
            os.remove(path)
        except OSError:
            pass
    cutoff = time.time() - STATE_KEEP_DAYS * 86400
    for name in os.listdir(STATE):
        p = os.path.join(STATE, name)
        if re.match(r"^\d{4}-\d\d-\d\d$", name) and os.stat(p).st_mtime < cutoff:
            os.remove(p)


# ── the widget ────────────────────────────────────────────────────────────────

def at(day, hhmm):
    h, mi = map(int, hhmm.split(":"))
    return datetime(day.year, day.month, day.day, h, mi)


def countdown(mins):
    h, m = divmod(mins, 60)
    return f"{h}h{m:02d}m" if h else f"{m}m"


def q(s):
    """Always single-quoted for the shell."""
    return "'" + s.replace("'", "'\\''") + "'"


def action(title, *args):
    """A menu action that runs this script again, with the folders this run used
    (settings given in `command` don't reach menu commands otherwise)."""
    env = "".join(f"{k}={q(os.environ[k])} " for k in ("TMPDIR", "XDG_STATE_HOME") if os.environ.get(k))
    return f"menu: {title} | {env}bash {q(SCRIPT)} " + " ".join(q(a) for a in args)


def fail(label, *lines):
    emit(f"dim|{label}")
    emit("icon: moon.stars")
    for line in lines:
        emit(f"menu: {clean(line)}")
    emit("menu: ---")
    emit(action("Refresh", "refresh"))
    emit(f"menu: Open habous.gov.ma | open {q(HABOUS_PAGE)}")


def clock():
    """Now, or WINGBAR_SALAT_NOW ("YYYY-MM-DD HH:MM", for tests)."""
    fake = os.environ.get("WINGBAR_SALAT_NOW")
    return datetime.strptime(fake, "%Y-%m-%d %H:%M") if fake else datetime.now()


def widget():
    ensure_dir(CACHE)
    now = clock()
    today = now.date()
    setting = (os.environ.get("WINGBAR_SALAT_CITY") or "").strip() or LATIN[FALLBACK_ID][0]
    try:
        warn_min = max(0, int(os.environ.get("WINGBAR_SALAT_WARN_MIN") or 15))
    except ValueError:
        warn_min = 15
    icons = (os.environ.get("WINGBAR_SALAT_ICON") or "bundled").strip().lower()
    track = os.environ.get("WINGBAR_SALAT_TRACK") == "1"

    m = month(today.strftime("%Y-%m"))
    note = ""
    if setting.lower() == "auto":
        cid, note = auto_city(m)
    else:
        cid = city_by_name(setting, m)
        if cid is None:
            if m is None:
                return fail("Salat: offline", "Couldn't download the timetable from habous.gov.ma")
            return fail("Salat: unknown city", f"No Moroccan city named “{setting}”",
                        "Set WINGBAR_SALAT_CITY to a city (Casablanca), a Habous city id, or auto")
    times = times_for(today, cid)
    if times is None:
        if m is None:
            return fail("Salat: offline", "Couldn't download the timetable from habous.gov.ma",
                        "It's kept for the month once downloaded")
        return fail("Salat: unknown city", f"City id {cid} is not in the Habous timetable",
                    "Set WINGBAR_SALAT_CITY to a city (Casablanca), a Habous city id, or auto")
    tidy(today)
    name = city_name(cid, m)

    nxt_key, nxt_at, tomorrow = None, None, False
    for k in ORDER:
        t = at(today, times[k])
        if t > now:
            nxt_key, nxt_at = k, t
            break
    if nxt_key is None:
        # after Isha: tomorrow's Fajr (from next month's file on the last day;
        # today's Fajr when that isn't published yet, a minute or two off)
        day2 = today + timedelta(days=1)
        t2 = times_for(day2, cid)
        nxt_key, nxt_at, tomorrow = "fajr", at(day2, (t2 or times)["fajr"]), True
    mins = max(1, math.ceil((nxt_at - now).total_seconds() / 60))
    level = "warn" if mins <= warn_min else "ok"
    emit(f"{level}|{NAMES[nxt_key]} · {countdown(mins)}")
    if icons == "bundled":
        emit(f"icon: {BUNDLED[nxt_key]}")
    elif icons == "sf":
        emit(f"icon: {SF[nxt_key]}")

    emit(f"menu: {clean(name)} · {now:%a %-d %b}" + (f" ({clean(note)})" if note else ""))
    emit("menu: ---")
    done = ticks(today) if track else {}
    for k in ORDER:
        mark = "▸ " if k == nxt_key and not tomorrow else ("✓ " if k in done else "")
        extra = f"  · in {countdown(mins)}" if mark == "▸ " else ""
        emit(f"menu: {mark}{NAMES[k]}  {times[k]}{extra}")
    if tomorrow:
        emit(f"menu: ▸ Fajr (tomorrow)  {nxt_at:%H:%M}  · in {countdown(mins)}")
    emit("menu: ---")
    if track:
        started = [k for k in FIVE if at(today, times[k]) <= now]
        cur, cur_day = (started[-1], today) if started else ("ishae", today - timedelta(days=1))
        cur_done = ticks(cur_day).get(cur)
        if cur_done:
            emit(f"menu: ✓ {NAMES[cur]} prayed at {cur_done}")
            emit(action(f"Unmark {NAMES[cur]}", "unmark", cur, cur_day.isoformat()))
        else:
            emit(action(f"Mark {NAMES[cur]} as prayed", "mark", cur, cur_day.isoformat()))
        emit(f"menu: {sum(1 for k in FIVE if k in done)}/5 prayed today")
        emit("menu: ---")
    emit(action("Refresh", "refresh"))
    emit(f"menu: Open habous.gov.ma | open {q(HABOUS_PAGE)}")


def refresh():
    """Make the next run download again (the old copies stay until it works)."""
    if not os.path.isdir(CACHE):
        return
    for name in os.listdir(CACHE):
        p = os.path.join(CACHE, name)
        if name.endswith(".failed") or name == "auto_city":
            os.remove(p)
        elif name.startswith("habous_") or name == "cities.json":
            os.utime(p, (0, 0))
        elif name.startswith("times_"):
            os.remove(p)


def main(argv):
    cmd = argv[1] if len(argv) > 1 else ""
    if cmd == "refresh":
        refresh()
    elif cmd in ("mark", "unmark"):
        set_tick(argv[2] if len(argv) > 2 else "", argv[3] if len(argv) > 3 else "", cmd == "mark")
    else:
        try:
            widget()
        except Exception as e:  # never fail noisily on the bar
            out.clear()
            fail("Salat: error", f"{type(e).__name__}: {e}"[:120])
        print("\n".join(out))


if __name__ == "__main__":
    main(sys.argv)
