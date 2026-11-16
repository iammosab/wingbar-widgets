# salat

The next Islamic prayer and the time left until it, for a city in **Morocco**:

```
Asr · 1h05m
```

**Morocco only.** Times come from the official timetable of the Moroccan Ministry of Habous and
Islamic Affairs (habous.gov.ma), which covers about 190 Moroccan cities and localities in Moroccan
legal time. Elsewhere this widget is the wrong tool (see "Another country" below).

The icon follows the next prayer (wingbar's bundled Fajr, Chorouq, Dohr, Asr, Maghrib and Ishae
icons). The label turns `warn` a few minutes before a prayer (15 by default). The next "prayer" can
also be Sunrise, which ends Fajr's time.

## Menu (on hover)

A panel in wingbar's rich menu style:

- A header: the city on the left, today's date on the right (`Rabat    Mon 16 Nov`). With `auto`,
  a caption under it says when the city is a fallback.
- Today's six times in two columns: Fajr, Sunrise, Dhuhr, Asr, Maghrib, Isha. The next one is a
  bold row with its countdown (`Asr    15:03 · in 1h05m`) and a meter under it showing how far
  through the time from the previous prayer to the next one it is; the meter turns `warn` with the
  label. After Isha, tomorrow's Fajr is added as the next row.
- With `WINGBAR_SALAT_TRACK=1`: prayers you marked get a `✓`, then "Prayed today  2/5" and
  **Mark *Asr* as prayed** for the prayer whose time is running (before Fajr, last night's Isha);
  once marked, **Unmark Asr** with the time you marked it.
- A caption with the source: "Habous timetable · Moroccan time".
- Two buttons side by side: **Refresh** (download the timetable again on the next run; the copy you
  have stays until the download works) and **habous.gov.ma** (opens the site).

With `theme.menus: "native"` the same lines show as a plain macOS menu (columns joined, no meter).

## Needs

- wingbar 0.4 or later (for the menu's columns and meters).
- `python3`: comes with the Xcode Command Line Tools (`xcode-select --install`). Without them the
  widget shows `Salat: needs python3` and offers to install them.
- `curl` (part of macOS).
- A network connection once a month (the timetable is one file per month, about 300 KB). Offline,
  the cached month keeps working; with nothing cached it shows a dim `Salat: offline`.

## Install

Copy this folder to `~/.config/wingbar/widgets/salat/`, add the entry from `widget.json` under
`"widgets"` in wingbar's `config.json`, and place `"salat"` in `left` or `right`. Set your city in
`command`.

## Settings

Environment variables at the start of `command`:

| Setting | Default | What it does |
| --- | --- | --- |
| `WINGBAR_SALAT_CITY` | `Rabat` | The city: a name (`Casablanca`, `Fes`, `Tangier`, `Agadir`, …; case and accents don't matter), the city's Arabic name as the timetable writes it (`الدار البيضاء`), a Habous city id (`58`), or `auto` to pick the city nearest to your IP address's location (see Privacy). |
| `WINGBAR_SALAT_WARN_MIN` | `15` | Level `warn` this many minutes (or fewer) before the next prayer. `0` turns it off. |
| `WINGBAR_SALAT_ICON` | `bundled` | `bundled`: wingbar's own prayer icons; `sf`: SF Symbols (sunrise, sun.horizon, sun.max, sun.haze, sunset, moon.stars); `none`: no `icon:` line, so the widget's `icon` or `"iconFromLabel": "prayer"` decides (that option also colours each prayer's icon by its time of day). |
| `WINGBAR_SALAT_TRACK` | off | `1` adds "Mark … as prayed" to the menu and keeps the ticks (see Privacy). |
| `WINGBAR_PYTHON3`, `WINGBAR_CURL` | `python3`, `curl` | The tools to use (for testing). |
| `WINGBAR_SALAT_NOW` | the clock | `"YYYY-MM-DD HH:MM"`: pretend it is that time (for testing). |

City names known in Latin letters: about 90 cities (Rabat, Casablanca, Fes, Meknes, Tangier,
Tetouan, Oujda, Nador, Kenitra, Agadir, Laayoune, Dakhla, …, see `LATIN` in `salat.py`).
Any other locality in the timetable works by its Arabic name or id and is shown in Arabic.

**Fallback:** with `WINGBAR_SALAT_CITY` unset the city is **Rabat**. With `auto`, when the location
can't be found, or is more than 300 km from every city in the timetable (not in Morocco), the widget
uses the last city it found, else **Rabat**, and says so in the menu.

Times are Moroccan legal time and are compared with your Mac's clock, so the Mac should be on
Morocco's time.

## Privacy

- **Reads:** the settings above and its own cache. With `WINGBAR_SALAT_TRACK=1`, its tick files.
- **Sends:**
  - to **habous.gov.ma** (`https://www.habous.gov.ma/data/horaires-YYYY-MM.js`): a plain download
    of the month's timetable, about once a week (it contains every city, so your city is not sent).
  - only with `WINGBAR_SALAT_CITY=auto`:
    - to **ipinfo.io** (`https://ipinfo.io/loc`): a request that reveals your **public IP
      address**, from which ipinfo.io returns its approximate location; at most every 6 hours.
    - to **salat-maghrib.vercel.app** (`/city`, a community deployment of
      [salat-api](https://github.com/kafiln/salat-api)): a download of the list of city
      coordinates, at most weekly. Nothing about you is sent beyond the request itself (your IP
      reaches every server you contact).
  - Requests go through `curl` with the user agent `wingbar-salat`.
- **Stores:**
  - `${TMPDIR:-/tmp}/wingbar-salat/`: the monthly timetables (last, this and next month), the day's
    times for your city (`times_YYYY-MM-DD_<city id>.json`, yesterday to tomorrow), with `auto`
    the city list and the id of the matched city (`auto_city`; your coordinates are never
    written), and empty `*.failed` markers (a failed download is retried after 10 minutes).
  - only with `WINGBAR_SALAT_TRACK=1`: `${XDG_STATE_HOME:-~/.local/state}/wingbar-salat/YYYY-MM-DD`,
    one line per prayer you marked (`asr 15:20`: which prayer and the time you marked it). Files
    older than 60 days are deleted when you mark a prayer. Delete the folder to forget them.
- No notifications, no background process, nothing else.

## Another country

The widget reads one data source: `month()` and `times_for()` in `salat.py` turn the Habous monthly
file into `{"fajr": "HH:MM", "chorouq": …, "dohr": …, "asr": …, "maghrib": …, "ishae": …}` for a day
and city id. To use another service (for example a calculation API that takes coordinates and a
method), replace those two functions so they return the same dictionary, and `city_by_name()` /
`auto_city()` with that service's way of naming places. The rest (countdown, menu, tracking) does not
change.
