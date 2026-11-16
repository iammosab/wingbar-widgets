# memory

RAM in use, counted the way Activity Monitor counts it, with the apps using the most memory.

- **Bar:** the share of RAM in use, e.g. `62%` (app memory + wired + compressed, as Activity
  Monitor's "Memory Used"). The colour follows macOS's memory pressure, the same signal as
  Activity Monitor's pressure graph: `ok` when normal, `warn` at warning, `alert` at critical.
- **Menu (hover):** pressure, used of total (`Used: 9.9 of 16 GB (62%)`), the app / wired /
  compressed split, swap in use (when there is any), the top apps by memory (a browser's or an
  editor's helper processes are added to their app, so each app appears once), and
  *Open Activity Monitor*.
- **Click:** opens Activity Monitor.

It replaces wingbar's built-in `memory` widget (same key) with one that has a menu. The bar
number comes from `vm_stat` and `sysctl` (a few milliseconds). The app list needs `top -l 1`,
which takes about a second, so it is cached for 30 s: most runs don't start `top` at all.

## Needs

Nothing to install: `vm_stat`, `sysctl`, `top`, `ps` and `awk` come with macOS.

## Install

Copy this folder to `~/.config/wingbar/widgets/memory/`, paste the entry from `widget.json` under
`"widgets"` in `~/.config/wingbar/config.json` (it replaces a built-in `memory` entry), and keep
or add `"memory"` in `left` or `right`.

## Settings

Set as environment variables at the start of `command` in `widget.json`.

| Setting | Default | What it does |
| --- | --- | --- |
| `WINGBAR_MEMORY_TOP` | `6` | How many apps the menu lists (at most 15). `0` leaves the list out and never runs `top`. |
| `WINGBAR_MEMORY_TOP_TTL` | `30` | Seconds the app list is reused before `top` runs again. |
| `WINGBAR_VM_STAT`, `WINGBAR_SYSCTL`, `WINGBAR_TOP`, `WINGBAR_PS` | `vm_stat`, `sysctl`, `top`, `ps` | Tool paths (for testing). |

## Privacy

- **Reads:** system memory counters (`vm_stat`, `sysctl hw.memsize`,
  `kern.memorystatus_vm_pressure_level`, `vm.swapusage`), and every 30 s the memory footprint of
  the 120 largest processes (`top`) and their executable paths (`ps`), only to name the app each
  belongs to.
- **Sends:** nothing. No network access.
- **Stores:** `${TMPDIR:-/tmp}/wingbar-memory/top-apps.txt`: app names and their memory, the
  largest 15, overwritten every 30 s. Nothing else is written.
