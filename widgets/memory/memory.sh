#!/bin/bash
# wingbar widget: memory
#
# Line 1: the share of RAM in use, counted as Activity Monitor does
# (app memory + wired + compressed), coloured by macOS's memory pressure.
# Menu: pressure, used of total, the app / wired / compressed split, swap,
# the apps using the most memory (helpers counted with their app) and
# "Open Activity Monitor".
#
# Line 1 comes from vm_stat and sysctl (a few milliseconds). The app list needs
# `top -l 1` (about a second), so it is cached for WINGBAR_MEMORY_TOP_TTL
# seconds in ${TMPDIR:-/tmp}/wingbar-memory/.
#
# Settings: see README.md. Tool overrides (for tests): WINGBAR_VM_STAT,
# WINGBAR_SYSCTL, WINGBAR_TOP, WINGBAR_PS.

export LC_ALL=C
VM_STAT=${WINGBAR_VM_STAT:-vm_stat}
SYSCTL=${WINGBAR_SYSCTL:-sysctl}
TOP=${WINGBAR_TOP:-top}
PS=${WINGBAR_PS:-ps}

TOP_N=${WINGBAR_MEMORY_TOP:-6}
TTL=${WINGBAR_MEMORY_TOP_TTL:-30}
case $TOP_N in '' | *[!0-9]*) TOP_N=6 ;; esac
case $TTL in '' | *[!0-9]*) TTL=30 ;; esac
[ "$TOP_N" -gt 15 ] && TOP_N=15

CACHE="${TMPDIR:-/tmp}/wingbar-memory"
APPS="$CACHE/top-apps.txt"

# ── line 1 and the summary: vm_stat + sysctl ────────────────────────────────
TOTAL=$("$SYSCTL" -n hw.memsize 2>/dev/null | tr -d '[:space:]')
case $TOTAL in '' | *[!0-9]* | 0)
	echo "dim|RAM ?"
	echo "menu: Memory unavailable (sysctl hw.memsize failed)"
	exit 0
	;;
esac
LEVEL=$("$SYSCTL" -n kern.memorystatus_vm_pressure_level 2>/dev/null | tr -d '[:space:]')
SWAP=$("$SYSCTL" -n vm.swapusage 2>/dev/null | awk '{ for (i = 1; i < NF; i++) if ($i == "used") { v = $(i + 2); sub(/M$/, "", v); print v; exit } }')

# app = anonymous - purgeable; used = app + wired + compressed (capped at total)
read -r APP WIRED COMP <<EOF
$("$VM_STAT" 2>/dev/null | awk '
	/page size of/ { for (i = 1; i <= NF; i++) if ($i == "of") page = $(i + 1) }
	{ v = $NF; sub(/\.$/, "", v) }
	/^Anonymous pages:/ { anon = v }
	/^Pages purgeable:/ { purg = v }
	/^Pages wired down:/ { wired = v }
	/^Pages occupied by compressor:/ { comp = v }
	END {
		if (page == "") page = 16384
		app = (anon - purg) * page; if (app < 0) app = 0
		printf "%.0f %.0f %.0f\n", app, wired * page, comp * page
	}')
EOF
case "$APP$WIRED$COMP" in '' | *[!0-9]*)
	echo "dim|RAM ?"
	echo "menu: Memory unavailable (vm_stat failed)"
	exit 0
	;;
esac

case $LEVEL in
2) PRESSURE=warning L=warn ;;
4) PRESSURE=critical L=alert ;;
*) PRESSURE=normal L=ok ;;
esac

awk -v t="$TOTAL" -v a="$APP" -v w="$WIRED" -v c="$COMP" -v s="${SWAP:-0}" -v l="$L" -v p="$PRESSURE" 'BEGIN {
	g = 1024 * 1024 * 1024
	u = a + w + c; if (u > t) u = t
	printf "%s|%d%%\n", l, (u * 100 / t) + 0.5
	printf "menu: Pressure: %s\n", p
	printf "menu: Used: %.1f of %.0f GB (%d%%)\n", u / g, t / g, (u * 100 / t) + 0.5
	printf "menu: App %.1f · Wired %.1f · Compressed %.1f GB\n", a / g, w / g, c / g
	if (s + 0 > 0) printf "menu: Swap: %.1f GB used\n", s / 1024
}'

# ── top apps: cached ────────────────────────────────────────────────────────
fresh() {
	[ -f "$APPS" ] || return 1
	local now mtime
	now=$(date +%s)
	mtime=$(stat -f %m "$APPS" 2>/dev/null) || return 1
	[ $((now - mtime)) -lt "$TTL" ]
}

# Writes "<bytes><TAB><app name>" lines, largest first: each process's memory
# footprint (top's MEM column, what Activity Monitor shows), summed per app so
# a browser's helpers count once (a process inside Foo.app counts as "Foo").
refresh_apps() {
	mkdir -p "$CACHE" 2>/dev/null || return
	LOCK="$CACHE/lock" TMP="$CACHE/top.$$"
	local lock=$LOCK tmp=$TMP
	if ! mkdir "$lock" 2>/dev/null; then
		# a refresh is running (or died): use what is there; clear a stale lock
		local age=$(($(date +%s) - $(stat -f %m "$lock" 2>/dev/null || date +%s)))
		[ "$age" -gt 60 ] && rmdir "$lock" 2>/dev/null
		return
	fi
	trap 'rm -f "$TMP" "$TMP.pids"; rmdir "$LOCK" 2>/dev/null' EXIT
	"$TOP" -l 1 -o mem -stats pid,mem -n 120 2>/dev/null | awk '
		$1 == "PID" { rows = 1; next }
		rows && $1 ~ /^[0-9]+$/ {
			m = $2; sub(/[+-]+$/, "", m)
			u = substr(m, length(m)); n = substr(m, 1, length(m) - 1) + 0
			f = (u == "G") ? 1073741824 : (u == "M") ? 1048576 : (u == "K") ? 1024 : 1
			if (u ~ /[0-9]/) { n = m + 0; f = 1 }
			print $1 "\t" n * f
		}' >"$tmp.pids"
	if [ -s "$tmp.pids" ]; then
		"$PS" -o pid=,comm= -p "$(cut -f1 "$tmp.pids" | paste -sd, -)" 2>/dev/null |
			awk -F '\t' 'NR == FNR { mem[$1] = $2; next }
			{
				line = $0; sub(/^[[:space:]]+/, "", line)
				pid = line; sub(/[[:space:]].*$/, "", pid)
				path = line; sub(/^[0-9]+[[:space:]]+/, "", path)
				name = path
				if (match(path, /\/[^\/]+\.app\//)) name = substr(path, RSTART + 1, RLENGTH - 6)
				else sub(/^.*\//, "", name)
				gsub(/[|[:cntrl:]]/, "", name)
				if (name == "") name = "?"
				sum[name] += mem[pid]
			}
			END { for (n in sum) printf "%.0f\t%s\n", sum[n], n }' "$tmp.pids" - |
			sort -t "$(printf '\t')" -k1,1nr | head -15 >"$tmp"
	fi
	# an empty result (top failed) is cached too, so a broken top is not rerun every time
	mv -f "$tmp" "$APPS" 2>/dev/null || : >"$APPS"
	rm -f "$tmp.pids"
	rmdir "$lock" 2>/dev/null
	trap - EXIT
}

if [ "$TOP_N" -gt 0 ]; then
	fresh || refresh_apps
	if [ -s "$APPS" ]; then
		echo "menu: ---"
		echo "menu: Top apps"
		head -n "$TOP_N" "$APPS" | awk -F '\t' '{
			b = $1; n = substr($2, 1, 28)
			if (b >= 1073741824) printf "menu: %s  %.1f GB\n", n, b / 1073741824
			else printf "menu: %s  %.0f MB\n", n, b / 1048576
		}'
	fi
fi

echo "menu: ---"
echo "menu: Open Activity Monitor | open -a 'Activity Monitor'"
