#!/bin/bash
# wingbar widget: network
#
# Line 1: how this Mac is online, following the default route: the Wi-Fi
# network's name (or "Wi-Fi" when macOS hides it), "Ethernet", or "Offline".
# Menu: every live connection with its address (the one in use first), Wi-Fi
# signal, link rate, PHY mode, channel and security, the router, connected
# VPNs, and actions: copy the IP address, open the router's page, open Wi-Fi /
# Network Settings, turn Wi-Fi off or on.
#
# Wi-Fi details come from `system_profiler SPAirPortDataType` (2-3 s), so they
# are cached for WINGBAR_NETWORK_WIFI_TTL seconds in ${TMPDIR:-/tmp}/wingbar-network/.
# Everything else is read fresh each run (route, scutil, ipconfig, ifconfig,
# networksetup; a few milliseconds).
#
# Settings: see README.md. Tool overrides (for tests): WINGBAR_ROUTE,
# WINGBAR_NETWORKSETUP, WINGBAR_IPCONFIG, WINGBAR_IFCONFIG, WINGBAR_SCUTIL,
# WINGBAR_SYSTEM_PROFILER.

export LC_ALL=C
ROUTE=${WINGBAR_ROUTE:-route}
NETWORKSETUP=${WINGBAR_NETWORKSETUP:-networksetup}
IPCONFIG=${WINGBAR_IPCONFIG:-ipconfig}
IFCONFIG=${WINGBAR_IFCONFIG:-ifconfig}
SCUTIL=${WINGBAR_SCUTIL:-scutil}
SYSTEM_PROFILER=${WINGBAR_SYSTEM_PROFILER:-system_profiler}

TTL=${WINGBAR_NETWORK_WIFI_TTL:-60}
WEAK=${WINGBAR_NETWORK_WEAK_DBM:--75}
SPEED=${WINGBAR_NETWORK_SPEED:-0}
TOGGLE=${WINGBAR_NETWORK_WIFI_TOGGLE:-1}
case $TTL in '' | *[!0-9]*) TTL=60 ;; esac
case $WEAK in -[0-9]*) case ${WEAK#-} in *[!0-9]*) WEAK=-75 ;; esac ;; *) WEAK=-75 ;; esac

CACHE="${TMPDIR:-/tmp}/wingbar-network"
NETWORK_SETTINGS="open 'x-apple.systempreferences:com.apple.Network-Settings.extension'"
WIFI_SETTINGS="open 'x-apple.systempreferences:com.apple.wifi-settings-extension'"

# Text we don't control (network, port and VPN names) loses "|" (it would end
# a menu title and start a command) and control characters.
plain() { printf '%s' "$1" | tr -d '|[:cntrl:]'; }
# An IPv4 address, or nothing (addresses go into commands: only digits and dots).
ipv4() { printf '%s' "$1" | awk '/^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$/ { print; exit }'; }
addr() { ipv4 "$("$IPCONFIG" getifaddr "$1" 2>/dev/null)"; }

# "device<TAB>port name" lines ("en0	Wi-Fi")
PORTS=$("$NETWORKSETUP" -listallhardwareports 2>/dev/null | tr -d '|' | tr -d '\001-\010\013-\037\177' | awk '
	/^Hardware Port: / { sub(/^Hardware Port: /, ""); port = $0 }
	/^Device: / { if (port != "") print $2 "\t" port; port = "" }')
port_of() { printf '%s\n' "$PORTS" | awk -F '\t' -v d="$1" '$1 == d { print $2; exit }'; }
WIFI_DEV=$(printf '%s\n' "$PORTS" | awk -F '\t' '$2 == "Wi-Fi" || $2 == "AirPort" { print $1; exit }')

WIFI_ON=0
if [ -n "$WIFI_DEV" ] && "$NETWORKSETUP" -getairportpower "$WIFI_DEV" 2>/dev/null | grep -q ': On$'; then
	WIFI_ON=1
fi

DEFAULT=$(plain "$("$ROUTE" -n get default 2>/dev/null | awk '$1 == "interface:" { print $2; exit }')")

# Live hardware connections (an IPv4 address), in macOS's service order, so
# the first is the one traffic uses. Bridges and VPN tunnels are left out.
LINKS=""
for dev in $(plain "$("$SCUTIL" --nwi 2>/dev/null | awk -F': *' '/^Network interfaces:/ { print $2; exit }')") $(printf '%s\n' "$PORTS" | cut -f1); do
	case " $LINKS " in *" $dev "*) continue ;; esac
	port=$(port_of "$dev")
	[ -n "$port" ] || continue
	case $port in *Bridge*) continue ;; esac
	[ -n "$(addr "$dev")" ] || continue
	LINKS="$LINKS $dev"
done
LINKS=${LINKS# }

# Connected VPN services (scutil --nc), by name.
VPNS=$("$SCUTIL" --nc list 2>/dev/null | awk '/\(Connected\)/ { if (match($0, /"[^"]*"/)) print substr($0, RSTART + 1, RLENGTH - 2) }' | tr -d '|' | tr -d '\001-\010\013-\037\177')

# The connection in use: the default route's interface, or (under a VPN that
# takes the default route) the first live hardware connection.
PRIMARY=""
if [ -n "$DEFAULT" ] && [ -n "$(port_of "$DEFAULT")" ]; then
	PRIMARY=$DEFAULT
elif [ -n "$DEFAULT" ]; then
	PRIMARY=${LINKS%% *}
	[ -n "$VPNS" ] || VPNS=$DEFAULT
fi

tail_actions() {
	echo "menu: ---"
	[ -n "$WIFI_DEV" ] && echo "menu: Open Wi-Fi Settings | $WIFI_SETTINGS"
	echo "menu: Open Network Settings | $NETWORK_SETTINGS"
	if [ "$TOGGLE" = 1 ] && [ -n "$WIFI_DEV" ]; then
		if [ "$WIFI_ON" = 1 ]; then
			echo "menu: Turn Wi-Fi Off | networksetup -setairportpower '$WIFI_DEV' off"
		else
			echo "menu: Turn Wi-Fi On | networksetup -setairportpower '$WIFI_DEV' on"
		fi
	fi
}

if [ -z "$PRIMARY" ]; then
	if [ -n "$DEFAULT" ]; then
		echo "ok|VPN"
	elif [ -n "$WIFI_DEV" ] && [ "$WIFI_ON" = 0 ]; then
		echo "dim|Wi-Fi off"
	else
		echo "dim|Offline"
	fi
	[ -z "$DEFAULT" ] && echo "menu: No connection"
	printf '%s\n' "$VPNS" | awk 'NF { print "menu: VPN: " $0 }'
	tail_actions
	exit 0
fi

# ── Wi-Fi details: system_profiler, cached ──────────────────────────────────
WIFI_TXT="$CACHE/wifi.txt"
wifi_details() {
	local now mtime
	now=$(date +%s)
	mtime=$(stat -f %m "$WIFI_TXT" 2>/dev/null || echo 0)
	if [ $((now - mtime)) -ge "$TTL" ] || ! grep -qx "dev=$WIFI_DEV" "$WIFI_TXT" 2>/dev/null; then
		mkdir -p "$CACHE" 2>/dev/null || return
		local tmp="$CACHE/wifi.$$"
		# fields of the interface's "Current Network Information" only (its first
		# line, the network's name, is skipped)
		"$SYSTEM_PROFILER" SPAirPortDataType 2>/dev/null | awk -v dev="$WIFI_DEV" '
			function ind(s) { match(s, /^ */); return RLENGTH }
			$0 ~ "^ +" dev ":$" { inif = 1; base = ind($0); next }
			# (only header lines, which end in ":", count: a long value can wrap
			# onto an unindented line)
			inif && ind($0) <= base && /:$/ { inif = 0 }
			inif && /Current Network Information:$/ { cur = 1; cbase = ind($0); next }
			cur && ind($0) <= cbase + 2 && /:$/ { if (seen) exit; seen = 1; next }
			cur && inif {
				line = $0; sub(/^ +/, "", line)
				k = line; sub(/:.*/, "", k); v = line; sub(/^[^:]*: */, "", v)
				if (k == "PHY Mode") print "phy=" v
				else if (k == "Channel") print "channel=" v
				else if (k == "Security") print "security=" v
				else if (k == "Signal / Noise") print "signal=" v
				else if (k == "Transmit Rate") print "rate=" v
			}' | tr -d '|' | tr -d '\001-\010\013-\037\177' >"$tmp"
		echo "dev=$WIFI_DEV" >>"$tmp"
		mv -f "$tmp" "$WIFI_TXT" 2>/dev/null || rm -f "$tmp"
	fi
}
field() { awk -F= -v k="$1" '$1 == k { sub(/^[^=]*=/, ""); print; exit }' "$WIFI_TXT" 2>/dev/null; }

WIFI_LIVE=0
[ -n "$WIFI_DEV" ] && case " $LINKS " in *" $WIFI_DEV "*) WIFI_LIVE=1 ;; esac

RSSI="" NOISE="" QUALITY=""
if [ "$WIFI_LIVE" = 1 ]; then
	[ "$TTL" -gt 0 ] && wifi_details
	read -r RSSI NOISE <<EOF
$(field signal | awk '{ r = $1; n = $4; if (r ~ /^-?[0-9]+$/) print r, (n ~ /^-?[0-9]+$/ ? n : "") }')
EOF
	if [ -n "$RSSI" ]; then
		if [ "$RSSI" -ge -55 ]; then QUALITY=Excellent
		elif [ "$RSSI" -ge -67 ]; then QUALITY=Good
		elif [ "$RSSI" -ge -75 ]; then QUALITY=Fair
		else QUALITY=Weak; fi
	fi
fi

SSID=""
if [ "$WIFI_LIVE" = 1 ]; then
	# the least indented "SSID : " line is the interface's own
	SSID=$("$IPCONFIG" getsummary "$WIFI_DEV" 2>/dev/null | awk '
		/^[[:space:]]*SSID : / {
			match($0, /^[[:space:]]*/)
			if (!found || RLENGTH < depth) { found = 1; depth = RLENGTH; v = $0; sub(/^[[:space:]]*SSID : /, "", v) }
		}
		END { if (found) print v }')
	case $SSID in "<"*">") SSID="" ;; esac
	SSID=$(plain "$SSID")
fi

speed() {
	"$IFCONFIG" "$1" 2>/dev/null | awk '/media:/ && match($0, /\([0-9]+base/) {
		m = substr($0, RSTART + 1, RLENGTH - 5) + 0
		if (m >= 1000) printf "%g Gb/s\n", m / 1000; else printf "%d Mb/s\n", m; exit }'
}

# ── line 1 ──────────────────────────────────────────────────────────────────
if [ "$PRIMARY" = "$WIFI_DEV" ]; then
	L=ok
	[ -n "$RSSI" ] && [ "$RSSI" -lt "$WEAK" ] && L=warn
	echo "$L|${SSID:-Wi-Fi}"
else
	S=""
	[ "$SPEED" = 1 ] && S=$(speed "$PRIMARY")
	echo "eth|Ethernet${S:+ · $S}"
fi

# ── menu: connections ───────────────────────────────────────────────────────
for dev in $LINKS; do
	ip=$(addr "$dev")
	mark="○"
	[ "$dev" = "$PRIMARY" ] && mark="●"
	if [ "$dev" = "$WIFI_DEV" ]; then
		name="Wi-Fi${SSID:+ $SSID}"
		extra=""
	else
		name=$(plain "$(port_of "$dev")")
		extra=$(speed "$dev")
	fi
	standby=""
	[ "$dev" = "$PRIMARY" ] || standby="standby"
	printf 'menu: %s %s (%s): %s%s%s\n' "$mark" "$name" "$dev" "$ip" "${extra:+ · $extra}" "${standby:+ · $standby}"
done

if [ "$WIFI_LIVE" = 1 ]; then
	if [ -n "$RSSI" ]; then
		echo "menu: Signal: $QUALITY ($RSSI dBm${NOISE:+, noise $NOISE dBm})"
	fi
	RATE=$(field rate)
	PHY=$(field phy)
	CHANNEL=$(field channel)
	LINK=""
	case $RATE in '' | *[!0-9.]*) ;; *) LINK="$RATE Mb/s" ;; esac
	[ -n "$PHY" ] && LINK="${LINK:+$LINK · }$PHY"
	[ -n "$CHANNEL" ] && LINK="${LINK:+$LINK · }ch $CHANNEL"
	[ -n "$LINK" ] && echo "menu: Link: $LINK"
	SEC=$(field security)
	[ -n "$SEC" ] && echo "menu: Security: $SEC"
	[ -z "$SSID" ] && echo "menu: Wi-Fi name hidden by macOS (Location Services)"
fi

ROUTER=$(ipv4 "$("$IPCONFIG" getoption "$PRIMARY" router 2>/dev/null)")
[ -n "$ROUTER" ] && echo "menu: Router: $ROUTER"
printf '%s\n' "$VPNS" | awk 'NF { print "menu: VPN: " $0 }'

# ── menu: actions ───────────────────────────────────────────────────────────
IP=$(addr "$PRIMARY")
echo "menu: ---"
[ -n "$IP" ] && echo "menu: Copy IP Address | printf %s '$IP' | pbcopy"
[ -n "$ROUTER" ] && echo "menu: Open Router Page | open 'http://$ROUTER'"
tail_actions | tail -n +2
