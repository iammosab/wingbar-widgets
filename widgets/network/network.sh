#!/bin/bash
# wingbar widget: network
#
# Line 1: how this Mac is online, following the default route: the Wi-Fi
# network's name (or "Wi-Fi" when macOS hides it), "Ethernet", or "Offline".
# Menu (wingbar 0.4 styles: columns, meters, captions, buttons): a header
# saying what is in use, then each live connection as a section (the one in use
# first; clicking it copies its IP address) with its details: the Wi-Fi network,
# signal with a meter, noise, link rate, PHY mode and channel, security,
# interface. Then the router (opens its page) and connected VPNs, and buttons:
# Network / Wi-Fi settings, Wi-Fi off or on.
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
# a menu title and start a command) and control characters, TAB included (it
# would split a menu line into columns).
plain() { printf '%s' "$1" | tr -d '|[:cntrl:]'; }
# An IPv4 address, or nothing (addresses go into commands: only digits and dots).
ipv4() { printf '%s' "$1" | awk '/^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$/ { print; exit }'; }
addr() { ipv4 "$("$IPCONFIG" getifaddr "$1" 2>/dev/null)"; }

# "device<TAB>port name" lines ("en0	Wi-Fi")
PORTS=$("$NETWORKSETUP" -listallhardwareports 2>/dev/null | tr -d '|' | tr -d '\001-\011\013-\037\177' | awk '
	/^Hardware Port: / { sub(/^Hardware Port: /, ""); port = $0 }
	/^Device: / { if (port != "") print $2 "\t" port; port = "" }')
port_of() { printf '%s\n' "$PORTS" | awk -F '\t' -v d="$1" '$1 == d { print $2; exit }'; }
WIFI_DEV=$(printf '%s\n' "$PORTS" | awk -F '\t' '$2 == "Wi-Fi" || $2 == "AirPort" { print $1; exit }')
case $WIFI_DEV in *[!A-Za-z0-9]*) WIFI_DEV="" ;; esac

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
VPNS=$("$SCUTIL" --nc list 2>/dev/null | awk '/\(Connected\)/ { if (match($0, /"[^"]*"/)) print substr($0, RSTART + 1, RLENGTH - 2) }' | tr -d '|' | tr -d '\001-\011\013-\037\177')

# The connection in use: the default route's interface, or (under a VPN that
# takes the default route) the first live hardware connection.
PRIMARY=""
if [ -n "$DEFAULT" ] && [ -n "$(port_of "$DEFAULT")" ]; then
	PRIMARY=$DEFAULT
elif [ -n "$DEFAULT" ]; then
	PRIMARY=${LINKS%% *}
	[ -n "$VPNS" ] || VPNS=$DEFAULT
fi

# The buttons at the bottom; adjacent buttons share one row.
buttons() {
	echo "menu: > Network settings | $NETWORK_SETTINGS"
	[ -n "$WIFI_DEV" ] && echo "menu: > Wi-Fi settings | $WIFI_SETTINGS"
	if [ "$TOGGLE" = 1 ] && [ -n "$WIFI_DEV" ]; then
		if [ "$WIFI_ON" = 1 ]; then
			echo "menu: > Wi-Fi off | networksetup -setairportpower '$WIFI_DEV' off"
		else
			echo "menu: > Wi-Fi on | networksetup -setairportpower '$WIFI_DEV' on"
		fi
	fi
}
vpn_rows() { printf '%s\n' "$VPNS" | awk 'NF { printf "menu: VPN\t%s\n", $0 }'; }

if [ -z "$PRIMARY" ]; then
	if [ -n "$DEFAULT" ]; then
		echo "ok|VPN"
		SUB="VPN only"
	elif [ -n "$WIFI_DEV" ] && [ "$WIFI_ON" = 0 ]; then
		echo "dim|Wi-Fi off"
		SUB="Wi-Fi is off"
	else
		echo "dim|Offline"
		SUB="Offline"
	fi
	printf 'menu: # Network\t%s\n' "$SUB"
	[ -z "$DEFAULT" ] && echo "menu: _ No connection."
	vpn_rows
	buttons
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
			}' | tr -d '|' | tr -d '\001-\011\013-\037\177' >"$tmp"
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

# ── menu ────────────────────────────────────────────────────────────────────
if [ "$PRIMARY" = "$WIFI_DEV" ]; then
	printf 'menu: # Network\tUsing Wi-Fi\n'
else
	printf 'menu: # Network\tUsing Ethernet\n'
fi

# each live connection, the one in use first: a section (click: copy its IP)
# and its details
SEEN=""
for dev in $PRIMARY $LINKS; do
	case " $LINKS " in *" $dev "*) ;; *) continue ;; esac
	case " $SEEN " in *" $dev "*) continue ;; esac
	SEEN="$SEEN $dev"
	ip=$(addr "$dev")
	standby=""
	[ "$dev" = "$PRIMARY" ] || standby=" · standby"
	copy=""
	[ -n "$ip" ] && copy=" | printf %s '$ip' | pbcopy"
	if [ "$dev" = "$WIFI_DEV" ]; then
		printf 'menu: ## Wi-Fi\t%s%s\n' "$ip" "$copy"
		if [ -n "$SSID" ]; then
			printf 'menu: Network\t%s\n' "$SSID"
		else
			printf 'menu: Network\thidden\n'
		fi
		if [ -n "$RSSI" ]; then
			printf 'menu: Signal\t%s · %s dBm\n' "$QUALITY" "$RSSI"
			awk -v r="$RSSI" -v weak="$WEAK" 'BEGIN {
				q = (r + 90) * 100 / 60; if (q < 0) q = 0; if (q > 100) q = 100
				c = (r < weak) ? "alert" : (r < -67) ? "warn" : "green"
				printf "menu: ~%d %s\n", q, c
			}'
			[ -n "$NOISE" ] && printf 'menu: Noise\t%s dBm\n' "$NOISE"
		fi
		RATE=$(field rate)
		PHY=$(field phy)
		CHANNEL=$(field channel)
		LINK=""
		case $RATE in '' | *[!0-9.]*) ;; *) LINK="$RATE Mb/s" ;; esac
		[ -n "$PHY" ] && LINK="${LINK:+$LINK · }$PHY"
		[ -n "$CHANNEL" ] && LINK="${LINK:+$LINK · }ch $CHANNEL"
		[ -n "$LINK" ] && printf 'menu: Link\t%s\n' "$LINK"
		SEC=$(field security)
		[ -n "$SEC" ] && printf 'menu: Security\t%s\n' "$SEC"
		printf 'menu: Interface\t%s%s\n' "$dev" "$standby"
	else
		rate=$(speed "$dev")
		printf 'menu: ## Ethernet\t%s%s\n' "${rate:-$ip}" "$copy"
		[ -n "$rate" ] && [ -n "$ip" ] && printf 'menu: Address\t%s\n' "$ip"
		printf 'menu: Interface\t%s · %s%s\n' "$dev" "$(plain "$(port_of "$dev")")" "$standby"
	fi
done

ROUTER=$(ipv4 "$("$IPCONFIG" getoption "$PRIMARY" router 2>/dev/null)")
if [ -n "$ROUTER" ] || [ -n "$VPNS" ]; then
	echo "menu: ---"
	[ -n "$ROUTER" ] && printf "menu: Router\t%s | open 'http://%s'\n" "$ROUTER" "$ROUTER"
	vpn_rows
fi

[ "$WIFI_LIVE" = 1 ] && [ -z "$SSID" ] && echo "menu: _ Wi-Fi name hidden by macOS (Location Services)."
[ -n "$(addr "$PRIMARY")" ] && echo "menu: _ Click a connection to copy its IP."
buttons
