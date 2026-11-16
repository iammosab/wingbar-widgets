# Demo data

Fake tools that make every widget show made-up data, for screenshots and for trying a widget's
menu without an account. `scripts/demo/config.sh <dir>` writes a wingbar settings file using
them; run wingbar on it with `WINGBAR_CONFIG=<dir>/config.json wingbar --no-server`.
Nothing here talks to the network except `ci` (a public repo) and `salat` (the public timetable).
