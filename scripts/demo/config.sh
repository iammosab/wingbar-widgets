#!/bin/bash
# Write <dir>/config.json: every widget of the collection on demo data, in two wings
# (made-up AeroSpace workspaces on the left), as a real setup would have them.
set -euo pipefail
D=$(cd "${1:?usage: config.sh DIR}" && pwd); F=$(cd "$(dirname "$0")" && pwd); W=$(cd "$F/../../widgets" && pwd)
mkdir -p "$D/tmp"
e="TMPDIR=$D/tmp/"
cat > "$D/config.json" <<JSON
{ "version": 2, "bar": { "server": false },
  "windowManager": "aerospace", "aerospacePath": "$F/aerospace",
  "theme": { "icons": "simple-bar" },
  "left": ["spaces", "clickup", "claude"],
  "right": ["ci", "cpu", "memory", "mic", "sound", "network", "battery", "salat", "date", "time"],
  "widgets": {
    "spaces": { "type": "spaces" },
    "cpu": { "type": "cpu" }, "sound": { "type": "sound" }, "battery": { "type": "battery" },
    "date": { "type": "date" },
    "ci": { "type": "script", "command": "$e WINGBAR_CI_REPO=cli/cli WINGBAR_CI_BRANCH=trunk WINGBAR_CI_LIMIT=5 WINGBAR_CI_PRS=3 bash $W/ci/ci.sh", "every": "60s", "icon": "GitHub", "levels": { "ok": "green", "alert": "red" }, "menuOn": "hover" },
    "claude": { "type": "script", "command": "$e WINGBAR_CLAUDE_PLAN=1 WINGBAR_CLAUDE_OFFERS=1 WINGBAR_SECURITY=$F/security WINGBAR_CURL=$F/curl bash $W/claude/claude.sh", "every": "60s", "icon": "Claude", "levels": { "ok": "orange" }, "menuOn": "hover" },
    "clickup": { "type": "script", "command": "$e CLICKUP_TOKEN=demo WINGBAR_CLICKUP_SHOW_TASK=0 WINGBAR_CURL=$F/curl bash $W/clickup/clickup.sh", "every": "15s", "icon": "ClickUp", "levels": { "ok": "green" }, "menuOn": "hover" },
    "memory": { "type": "script", "command": "$e WINGBAR_TOP=$F/top WINGBAR_PS=$F/ps bash $W/memory/memory.sh", "every": "5s", "icon": "memorychip", "menuOn": "hover" },
    "network": { "type": "script", "command": "$e WINGBAR_IPCONFIG=$F/ipconfig WINGBAR_ROUTE=$F/route WINGBAR_SCUTIL=$F/scutil bash $W/network/network.sh", "every": "10s", "icon": "wifi", "levels": { "ok": "green" }, "menuOn": "hover" },
    "mic": { "type": "script", "command": "$e bash $W/mic/mic.sh", "every": "5s", "icon": "mic", "levels": { "ok": "green" }, "menuOn": "hover" },
    "salat": { "type": "script", "command": "$e WINGBAR_SALAT_CITY=Rabat bash $W/salat/salat.sh", "every": "30s", "levels": { "ok": "green" }, "menuOn": "hover" },
    "time": { "type": "time" } } }
JSON
echo "$D/config.json"
