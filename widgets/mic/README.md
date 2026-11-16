# mic

Whether the microphone is muted, with a mute switch that works on more devices.

- **Bar:** an icon: `mic` (green) when live, `mic.slash` when muted. With `iconOnly` off the label
  shows too (`On` / `Muted`).
- **Menu (hover):** the input device, its input volume, how it is muted (the device's mute switch,
  or input volume 0), *Mute Microphone* / *Unmute Microphone*, and *Open Sound Input Settings*.
- **Click:** mutes or unmutes.

**How it mutes.** wingbar's catalog `mic` widget mutes by setting the input volume to 0, which
fails on inputs without a volume macOS can set (many USB and Bluetooth mics, where it shows
`No level`). This one uses CoreAudio's mute switch through a small Swift helper,
`mic_control.swift`: it mutes **every** input device that has a switch (so a headset plugged in
while muted is muted too) and leaves the input volume where it was. A mic counts as muted when its
switch is on or its input volume is 0.

The helper ships as source, never as a binary. On the first run `mic.sh` compiles it with
`xcrun swiftc` into `${TMPDIR:-/tmp}/wingbar-mic/mic_control` (about 2 s, once; again only when
`mic_control.swift` changes). Without the Xcode Command Line Tools, when the build fails, or when
the device has no mute switch, it falls back to input volume 0 through `osascript` and restores the
previous volume on unmute (75 % when unknown). A failed build is not retried until the source
changes; delete `${TMPDIR:-/tmp}/wingbar-mic/` to retry. `$TMPDIR` is cleared on restart, so the
helper is rebuilt after one.

## Needs

- `osascript` (comes with macOS).
- For the mute switch: the Xcode Command Line Tools (`xcode-select --install`) or Xcode, which
  provide `swiftc`. Optional: without them the widget mutes by volume.

## Install

Copy this folder to `~/.config/wingbar/widgets/mic/`, paste the entry from `widget.json` under
`"widgets"` in `~/.config/wingbar/config.json`, and add `"mic"` to `left` or `right`. To mute from
a hotkey (AeroSpace, skhd, …), bind it to `bash ~/.config/wingbar/widgets/mic/mic.sh toggle`.

## Settings

Set as environment variables at the start of `command` (and of `click`) in `widget.json`.

| Setting | Default | What it does |
| --- | --- | --- |
| `WINGBAR_MIC_HELPER` | `1` | `0` never builds or uses the Swift helper: mute by input volume only (like the catalog widget). |
| `WINGBAR_SWIFTC` | `xcrun swiftc` | The Swift compiler command for the helper. |
| `WINGBAR_MIC_CONTROL` | (built helper) | Use this ready helper binary instead of building one (for testing). |
| `WINGBAR_OSASCRIPT` | `osascript` | Tool path (for testing). |

## Privacy

- **Reads:** the default input device's name, input volume and mute state (CoreAudio, or
  `osascript` for the volume). It never records or listens to audio, and asks for no microphone
  permission.
- **Changes:** only when you mute or unmute: the mute switch of the input devices, or the input
  volume.
- **Sends:** nothing. No network access.
- **Stores:** in `${TMPDIR:-/tmp}/wingbar-mic/`: the compiled helper (`mic_control`), its build
  output (`build.log`, plus `build-failed` after a failed build), and `volume`, the input volume
  before a mute by volume.
