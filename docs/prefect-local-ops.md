# Prefect Local Ops

This repository runs the local Prefect worker on macOS with `launchd` and a thin shell wrapper.

## Assets

- Worker wrapper: `ops/scripts/prefect-worker.sh`
- `launchd` template: `ops/launchd/com.helaicopter.prefect-worker.plist.template`
- Worker logs:
  - `.oats/logs/prefect-worker.stdout.log`
  - `.oats/logs/prefect-worker.stderr.log`

## Install

1. Copy `ops/launchd/com.helaicopter.prefect-worker.plist.template` to a real plist.
2. Replace `{{REPO_ROOT}}` with the absolute repository path.
3. Install it into `~/Library/LaunchAgents/com.helaicopter.prefect-worker.plist`.
4. Load it:

```bash
launchctl bootstrap "gui/$(id -u)" ~/Library/LaunchAgents/com.helaicopter.prefect-worker.plist
launchctl kickstart -k "gui/$(id -u)/com.helaicopter.prefect-worker"
```

## Operate

Check status:

```bash
launchctl print "gui/$(id -u)/com.helaicopter.prefect-worker"
```

Unload:

```bash
launchctl bootout "gui/$(id -u)" ~/Library/LaunchAgents/com.helaicopter.prefect-worker.plist
```
