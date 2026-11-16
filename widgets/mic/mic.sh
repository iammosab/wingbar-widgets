#!/bin/bash
# wingbar widget: mic
#
# Line 1: whether the microphone is muted ("On" / "Muted"), with icon "mic" or
# "mic.slash". Menu (wingbar 0.4 styles: columns, a meter, captions, buttons):
# a header, the input device, its input volume with a meter, how it is muted,
# and Mute / Unmute and "Sound settings" buttons.
#
# `mic.sh toggle` mutes or unmutes (the click action and the menu action).
#
# Two ways to mute:
#   - CoreAudio's mute switch, through the small Swift helper next to this
#     script (mic_control.swift). It mutes every input device that has a mute
#     switch and keeps the input volume as it was. The helper is compiled once
#     into ${TMPDIR:-/tmp}/wingbar-mic/ with swiftc, when the Xcode Command Line
#     Tools are installed (about 2 s, first run only).
#   - Otherwise (no swiftc, the build failed, WINGBAR_MIC_HELPER=0, or the device
#     has no mute switch): input volume 0 through osascript, and back to the
#     volume it had (kept in ${TMPDIR:-/tmp}/wingbar-mic/volume; 75 when unknown).
#
# Settings: see README.md. Tool overrides (for tests): WINGBAR_OSASCRIPT,
# WINGBAR_SWIFTC, WINGBAR_MIC_CONTROL (a ready helper binary).

DIR=$(cd "$(dirname "$0")" && pwd)
OSASCRIPT=${WINGBAR_OSASCRIPT:-osascript}
USE_HELPER=${WINGBAR_MIC_HELPER:-1}
CACHE="${TMPDIR:-/tmp}/wingbar-mic"
SAVED="$CACHE/volume"
SRC="$DIR/mic_control.swift"
BIN="$CACHE/mic_control"

# text we don't control (the device name) loses "|" (it would start a command)
# and control characters, TAB included (it would make a column)
plain() { printf '%s' "$1" | tr -d '|[:cntrl:]'; }
SOUND_SETTINGS="open 'x-apple.systempreferences:com.apple.Sound-Settings.extension?input'"

# The helper, compiled when missing or older than its source. A failed build is
# remembered (for that source) so it is not retried on every run.
helper() {
	[ "$USE_HELPER" = 1 ] || return 1
	if [ -n "${WINGBAR_MIC_CONTROL:-}" ]; then
		[ -x "$WINGBAR_MIC_CONTROL" ] && echo "$WINGBAR_MIC_CONTROL"
		return
	fi
	[ -f "$SRC" ] || return 1
	if [ -x "$BIN" ] && [ ! "$SRC" -nt "$BIN" ]; then
		echo "$BIN"
		return
	fi
	mkdir -p "$CACHE" 2>/dev/null || return 1
	[ -f "$CACHE/build-failed" ] && [ ! "$SRC" -nt "$CACHE/build-failed" ] && return 1
	local swiftc=(${WINGBAR_SWIFTC:-})
	if [ ${#swiftc[@]} -eq 0 ]; then
		# without a developer folder /usr/bin/swiftc would offer to install the
		# Command Line Tools: ask xcode-select first, which never prompts. xcrun
		# runs swiftc with the SDK set.
		xcode-select -p >/dev/null 2>&1 || return 1
		xcrun --find swiftc >/dev/null 2>&1 || return 1
		swiftc=(xcrun swiftc)
	fi
	if ! mkdir "$CACHE/build.lock" 2>/dev/null; then
		# another run is building; a lock left by a killed build is cleared after 2 min
		local age=$(($(date +%s) - $(stat -f %m "$CACHE/build.lock" 2>/dev/null || date +%s)))
		[ "$age" -gt 120 ] && rmdir "$CACHE/build.lock" 2>/dev/null
		return 1
	fi
	if "${swiftc[@]}" -O "$SRC" -o "$BIN.$$" >"$CACHE/build.log" 2>&1 && [ -x "$BIN.$$" ]; then
		mv -f "$BIN.$$" "$BIN"
		rm -f "$CACHE/build-failed"
	else
		rm -f "$BIN.$$"
		: >"$CACHE/build-failed"
	fi
	rmdir "$CACHE/build.lock" 2>/dev/null
	[ -x "$BIN" ] && echo "$BIN"
}

osa_volume() {
	"$OSASCRIPT" -e 'input volume of (get volume settings)' 2>/dev/null | tr -d '[:space:]'
}

HELPER=$(helper)
DEVICE="" VOLUME="" HW_MUTED=0 CAN_MUTE=0
if [ -n "$HELPER" ] && STATUS=$("$HELPER" status 2>/dev/null); then
	DEVICE=$(plain "$(printf '%s\n' "$STATUS" | sed -n 's/^device=//p' | head -1)")
	VOLUME=$(printf '%s\n' "$STATUS" | sed -n 's/^volume=//p' | head -1)
	[ "$(printf '%s\n' "$STATUS" | sed -n 's/^muted=//p')" = 1 ] && HW_MUTED=1
	[ "$(printf '%s\n' "$STATUS" | sed -n 's/^canmute=//p')" = 1 ] && CAN_MUTE=1
else
	HELPER=""
	VOLUME=$(osa_volume)
fi
case $VOLUME in *[!0-9]*) VOLUME="" ;; esac

MUTED=0
[ "$HW_MUTED" = 1 ] && MUTED=1
[ "$VOLUME" = 0 ] && MUTED=1

if [ "${1:-}" = "toggle" ]; then
	mkdir -p "$CACHE" 2>/dev/null
	if [ "$MUTED" = 1 ]; then
		[ -n "$HELPER" ] && "$HELPER" unmute >/dev/null 2>&1
		if [ "$VOLUME" = 0 ]; then
			BACK=$(tr -d '[:space:]' <"$SAVED" 2>/dev/null)
			case $BACK in '' | *[!0-9]* | 0) BACK=75 ;; esac
			"$OSASCRIPT" -e "set volume input volume $BACK" >/dev/null 2>&1
		fi
	elif [ -n "$HELPER" ] && [ "$CAN_MUTE" = 1 ] && "$HELPER" mute >/dev/null 2>&1; then
		:
	elif [ -n "$VOLUME" ]; then
		printf '%s\n' "$VOLUME" >"$SAVED" 2>/dev/null
		"$OSASCRIPT" -e 'set volume input volume 0' >/dev/null 2>&1
	fi
	exit 0
fi

if [ -z "$VOLUME" ] && [ "$CAN_MUTE" = 0 ] && [ "$HW_MUTED" = 0 ]; then
	# neither a volume nor a mute switch we can use: muted or not can't be told
	echo "dim|No level"
	echo "icon: mic"
	printf 'menu: # Microphone\tNo level\n'
	[ -n "$HELPER" ] && printf 'menu: Input\t%s\n' "${DEVICE:-none}"
	echo "menu: _ This input has no volume or mute switch macOS can set."
	[ -z "$HELPER" ] && [ "$USE_HELPER" = 1 ] && echo "menu: _ The Xcode Command Line Tools add mute-switch support."
	echo "menu: > Sound settings | $SOUND_SETTINGS"
	exit 0
fi

if [ "$MUTED" = 1 ]; then
	echo "alert|Muted"
	echo "icon: mic.slash"
	printf 'menu: # Microphone\tMuted\n'
else
	echo "ok|On"
	echo "icon: mic"
	printf 'menu: # Microphone\tOn\n'
fi
[ -n "$HELPER" ] && printf 'menu: Input\t%s\n' "${DEVICE:-none}"
if [ -n "$VOLUME" ]; then
	printf 'menu: Input volume\t%s%%\n' "$VOLUME"
	# dim while muted by the switch (the volume is kept but not heard)
	if [ "$MUTED" = 1 ]; then echo "menu: ~$VOLUME dim"; else echo "menu: ~$VOLUME green"; fi
fi
if [ "$HW_MUTED" = 1 ]; then
	echo "menu: _ Muted with the device's mute switch."
elif [ "$VOLUME" = 0 ]; then
	echo "menu: _ Muted with input volume 0."
fi
[ -z "$HELPER" ] && [ "$USE_HELPER" = 1 ] && echo "menu: _ Mutes by volume (no swiftc for the mute helper)."

ME=$(printf '%q' "$DIR/mic.sh")
if [ "$MUTED" = 1 ]; then
	echo "menu: > Unmute | bash $ME toggle"
else
	echo "menu: > Mute | bash $ME toggle"
fi
echo "menu: > Sound settings | $SOUND_SETTINGS"
