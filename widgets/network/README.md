# network

How this Mac is online, with the details you'd otherwise dig out of System Settings.

- **Bar:** the connection traffic actually uses (the default route): the Wi-Fi network's name,
  `Ethernet` (optionally with its speed, `Ethernet · 1 Gb/s`), `VPN` when only a VPN is up,
  `Wi-Fi off` or `Offline`. Levels: `ok` on Wi-Fi, `warn` on Wi-Fi with a weak signal, `eth` on a
  wire (blue, cable icon), `dim` offline.
- **Menu (hover):** a panel in wingbar 0.4's menu styles:
  - a header saying what is in use (`Network   Using Wi-Fi`, `Using Ethernet`, `VPN only`,
    `Wi-Fi is off`, `Offline`);
  - every live connection as a bold section, the one in use first: `Wi-Fi   <IP address>` or
    `Ethernet   1 Gb/s` (its address on the next row). Clicking a connection copies its IP address
    to the clipboard;
  - under Wi-Fi: the network's name, the signal in words and numbers (`Signal   Good · -61 dBm`)
    with a meter (green, `warn` below -67 dBm, `alert` below the weak setting), the noise, the
    link (`866 Mb/s · 802.11ac · ch 36 (5GHz, 80MHz)`) and security; under each connection its
    interface (and port name for wired ones), marked `standby` when it isn't the one in use;
  - *Router* with its address (click: opens `http://<router>` in your browser) and connected VPNs
    (by their name in Network Settings);
  - buttons: *Network settings*, *Wi-Fi settings*, *Wi-Fi off* / *Wi-Fi on*.

  In a macOS menu (`theme.menus: "native"`) the same lines show as plain items, without meters.

Compared with wingbar's catalog `network` widget, this one adds the signal, link and channel
readings, the router, VPN names, every live connection and the copy / router / Wi-Fi power
actions.

**The Wi-Fi name:** recent macOS hides it from apps without Location Services permission; the bar
then shows `Wi-Fi` and the menu says the name is hidden. The rest of the Wi-Fi details still show.

**Cost:** route, addresses, VPNs and Wi-Fi power are read fresh each run (a few milliseconds). The
Wi-Fi details come from `system_profiler SPAirPortDataType`, which takes 2-3 s, so they are cached
for 60 s: one run a minute is slower, the others aren't. After moving to another network the signal
readings can be up to that old.

## Needs

- wingbar 0.4 or later (for the menu's columns and meters).
- Nothing to install: `route`, `scutil`, `ipconfig`, `ifconfig`, `networksetup`,
  `system_profiler`, `pbcopy` and `awk` come with macOS.

## Install

Copy this folder to `~/.config/wingbar/widgets/network/`, paste the entry from `widget.json` under
`"widgets"` in `~/.config/wingbar/config.json`, and add `"network"` to `left` or `right`.

## Settings

Set as environment variables at the start of `command` in `widget.json`.

| Setting | Default | What it does |
| --- | --- | --- |
| `WINGBAR_NETWORK_WIFI_TTL` | `60` | Seconds the Wi-Fi details are reused. `0` leaves them out and never runs `system_profiler`. |
| `WINGBAR_NETWORK_WEAK_DBM` | `-75` | Signal (dBm) below which Wi-Fi turns `warn`. |
| `WINGBAR_NETWORK_SPEED` | `0` | `1` adds a wired link's speed to the bar (`Ethernet · 1 Gb/s`). |
| `WINGBAR_NETWORK_WIFI_TOGGLE` | `1` | `0` leaves the *Wi-Fi off / on* button out of the menu. |
| `WINGBAR_ROUTE`, `WINGBAR_NETWORKSETUP`, `WINGBAR_IPCONFIG`, `WINGBAR_IFCONFIG`, `WINGBAR_SCUTIL`, `WINGBAR_SYSTEM_PROFILER` | the command names | Tool paths (for testing). |

## Privacy

- **Reads:** local network state only: the default route, interfaces and their IPv4 addresses,
  hardware port names, the router address, Wi-Fi power, the Wi-Fi network name (when macOS allows
  it), the current Wi-Fi link's signal, noise, rate, PHY mode, channel and security
  (`system_profiler`), and the names of connected VPN services (`scutil --nc list`).
- **Sends:** nothing. It makes no network requests. The *Router* row opens your router's address
  in your browser only when you choose it.
- **Stores:** `${TMPDIR:-/tmp}/wingbar-network/wifi.txt`: the Wi-Fi interface name and the link's
  PHY mode, channel, security, signal / noise and rate, overwritten every 60 s. It does not store
  the network's name, the router or any address.
- Clicking a connection puts this Mac's local IP address on the clipboard, only when you choose it.
