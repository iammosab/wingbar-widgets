#!/bin/bash
# wingbar widget: salat
#
# The next prayer and the time left until it ("Asr · 1h05m") for a city in
# Morocco, from the Ministry of Habous' official timetable (habous.gov.ma).
# Morocco only: that is the timetable it reads.
#
# Levels (line 1 is "level|label"):
#   ok     the next prayer and the countdown
#   warn   WINGBAR_SALAT_WARN_MIN minutes or less before it
#   dim    offline with nothing cached, unknown city, python3 missing
#
# Menu: the city and date, today's six times (the next one marked), then
# "Mark <prayer> as prayed" with WINGBAR_SALAT_TRACK=1, "Refresh" and
# "Open habous.gov.ma".
#
# Settings (environment, all optional; see README.md):
#   WINGBAR_SALAT_CITY      city name, Habous city id, or "auto" (IP location)  [Rabat]
#   WINGBAR_SALAT_WARN_MIN  warn this many minutes before a prayer               [15]
#   WINGBAR_SALAT_ICON      bundled | sf | none                                  [bundled]
#   WINGBAR_SALAT_TRACK     1 = offer "Mark <prayer> as prayed"                   [off]
#   WINGBAR_PYTHON3, WINGBAR_CURL   the tools to use; WINGBAR_SALAT_NOW="YYYY-MM-DD HH:MM" (tests)
#
# Needs: python3 (Xcode Command Line Tools), curl (macOS). Caches in
# ${TMPDIR:-/tmp}/wingbar-salat/. Suggested interval: 30s.
#
#   salat.sh                    print the widget
#   salat.sh refresh            download again on the next run
#   salat.sh mark|unmark KEY YYYY-MM-DD   (the menu's tracking actions)

DIR=$(cd "$(dirname "$0")" && pwd)
PY=${WINGBAR_PYTHON3:-python3}
PY_PATH=$(command -v "$PY" 2>/dev/null)
# /usr/bin/python3 without the Command Line Tools only opens an install dialog
if [ -z "$PY_PATH" ] || { [ "$PY_PATH" = /usr/bin/python3 ] && ! xcode-select -p >/dev/null 2>&1; }; then
	echo "dim|Salat: needs python3"
	echo "icon: moon.stars"
	echo "menu: python3 comes with the Xcode Command Line Tools"
	echo "menu: Install the Command Line Tools | xcode-select --install"
	exit 0
fi
exec "$PY" -I "$DIR/salat.py" "$@"
