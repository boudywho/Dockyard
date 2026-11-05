# Dockyard operations runbook

## Profiles and dependency constraints

`PLUGIN_PROFILES` accepts `core`, `media`, `admin`, and `automation`. Every
loadable file under `plugins/` belongs to exactly one profile. Assistant
modules are separate and are loaded independently of plugin profiles.

New provisioning writes:

```text
PLUGIN_PROFILES=core,media
PLUGIN_PROFILE_POLICY=new-safe-v1
```

An upgraded database with no profile or policy marker is explicitly migrated
to `legacy-all-v1`; this is independent of `INIT_DEPLOY` and `LOG_OFF`.

`requirements/database.txt` contains the Redis/hiredis, MongoDB, and PostgreSQL
drivers required by the documented startup configurations and is included by
the default media profile. Optional Google, Instagram, X, and Heroku clients
remain outside that default. `constraints/py310.txt` and
`constraints/py313.txt` are tested direct pins for core/media/database, not
complete transitive hash locks. CPython 3.10–3.12 uses the
py310 set; 3.13+ uses py313. Every installer supplies its matching constraint
and runs `pip check`. Telethon-Patch is a VCS requirement fixed at commit
`369fa3266c8a9c9aefb4a6c5608e8d44c09c7087`. Some vulnerability tools cannot
map a VCS distribution reliably to advisory databases, so CI audits the
installed environment and this VCS result must be reviewed separately.

## Transactional releases

The canonical application unit name is `dockyard.service`. Existing production
installations that still run the application through `ultroid.service` must use
the transactional service-name migration after the managed Dockyard activation
is healthy:

```bash
install -o root -g root -m 0755 ops/dockyard-rename-service \
  /usr/local/sbin/dockyard-rename-service
sudo /usr/local/sbin/dockyard-rename-service plan
sudo /usr/local/sbin/dockyard-rename-service rename
```

The command copies the exact legacy unit and complete drop-in directory to the
canonical name, rewrites only the unit-name selectors in `deploy.conf`,
`backup.conf`, and `health.conf`, and verifies fresh PID-correlated readiness
and health before removing the legacy unit files. It retains the root-only
snapshot and canonical-state record at `/var/lib/dockyard/service-rename`,
restores the snapshot and restarts `ultroid.service` on failure, and is a no-op
after a verified successful migration. The Unix account and group remain
`ultroid`, as do `/opt/ultroid`, the existing Dockyard runtime/state and
environment values, Telegram identifiers, and the required
`ultroid-redis.service` unit. A service rename does not authorize renaming any
of those surfaces. Nonstandard test or staging locations may override
`DOCKYARD_UNIT_DIR`,
`DOCKYARD_DEPLOY_CONFIG`, `DOCKYARD_BACKUP_CONFIG`,
`DOCKYARD_HEALTH_CONFIG`, `DOCKYARD_READY_FILE`,
`DOCKYARD_HEALTH_COMMAND`, `DOCKYARD_HEALTH_PYTHONPATH`,
`DOCKYARD_RENAME_RECORD`, and `DOCKYARD_RENAME_LOCK`; production should use the
defaults.

Install the helper root-owned and non-group/world-writable. Before enabling or
starting any Dockyard unit, install and run the path provisioner:

```bash
install -d -o root -g root -m 0755 /usr/local/lib/dockyard
install -o root -g root -m 0644 ops/dockyard_ops.py \
  /usr/local/lib/dockyard/dockyard_ops.py
install -o root -g root -m 0644 ops/tmpfiles.d/dockyard.conf \
  /usr/lib/tmpfiles.d/dockyard.conf
install -o root -g root -m 0644 ops/systemd/dockyard-paths.service \
  /etc/systemd/system/dockyard-paths.service
systemd-tmpfiles --create /usr/lib/tmpfiles.d/dockyard.conf
systemctl daemon-reload
systemctl enable dockyard-paths.service
```

The prerequisite deterministically creates `/opt/dockyard`,
`/var/lib/dockyard`, `/var/lib/dockyard/status`, `/run/dockyard`,
`/run/lock/dockyard`, and `/var/backups/dockyard` before protected service
namespaces are built.
Application units then use `RuntimeDirectory=` and `StateDirectory=` to apply
the selected service account to `/run/dockyard` and
`/var/lib/dockyard/app-status`. Deploy applies the configured runtime group to
the root-owned workspace selectors, while status truth remains root-owned and
service non-writable.

Install the remaining path and service units, then validate the exact sudoers
file with `visudo -cf`.
Telegram is allowed only:

```text
/usr/local/sbin/dockyard-deploy request --non-interactive
```

The short action validates root configuration, atomically replaces
`/var/lib/dockyard/deploy.request`, and exits. The path unit starts the long
root `deploy` action. The root update check publishes the configured target
tag and commit in the sanitized shared status directory; the bot compares its
active immutable metadata with that target and never reads the root config.

Copy `ops/config/deploy.conf.example` to `/etc/dockyard/deploy.conf` as
root:root 0640. Replace the documented zero placeholder. Real
`check`, `preflight`, `request`, and `deploy` fail closed unless both values are
present and the commit is nonzero 40-hex:

```text
DOCKYARD_RELEASE_TAG=v2.2.2
DOCKYARD_RELEASE_COMMIT=<exact 40-hex peeled tag commit>
```

`check` and `deploy` fetch only
`+refs/tags/$DOCKYARD_RELEASE_TAG:refs/tags/$DOCKYARD_RELEASE_TAG`, compare the
peeled tag to the pin, verify the approved origin, refuse downgrade/unrelated
history, and use detached `HEAD`. Deployment builds a fresh venv, runs unit,
compile, import, JSON/YAML, shell, diff, and `pip check` preflight. An existing
target directory is quarantined and replaced; it is never silently reused.

Immutable source and `.venv` remain root-owned under `/opt/dockyard/releases`.
Each `/var/lib/dockyard/workspaces/<40-hex-commit>` is root-owned 0750 and
contains exactly a root-owned `source` symlink to
`/opt/dockyard/releases/<same-commit>` plus a service-owned 0700 `work/`.
Systemd uses `current/work` as `WorkingDirectory`, starts
`current/source/.venv/bin/python` with safe-path mode, and sets `PYTHONPATH` to
`current/source`. The single atomic `/var/lib/dockyard/current` replacement
therefore selects immutable code and writable state together. The process
therefore imports `pyUltroid`, official `plugins`, `assistant`, and `strings`
directly from the immutable release even if a namesake appears in writable
state.

`work/` contains writable add-ons, downloads, sessions, databases, logs,
temporary files, VCBot state, and `resources/{auth,auths,downloads}`. Bundled
images/fonts and the trusted add-on registry are addressed from source
constants derived from module location. The unit makes the workspace selector
and workspace root read-only and allowlists only `current/work`, `/run/dockyard`,
and app status as writable. Prior mutable state is validated as regular,
link-free content and copied into the new `work/`; official source is never
copied there. This preserves relative media and command output.

Before every start the helper removes the readiness marker. Start, stop, link,
or readiness failure enters rollback. Rollback is reported successful only
after the previous service is active with a fresh PID-correlated heartbeat
and its exact tag plus full commit have been derived from the retained
immutable release and atomically republished. The configured newer target
remains `available` after a rollback. Release and workspace ownership, modes,
shape, and absence of writable official selectors are validated before the
link switch and again before service start. An invalid retained target is
refused and never executed.

## Authenticated encrypted backup

Install `age` and the native `sqlite3` CLI (with `-nofollow` support, SQLite
3.31 or newer). Snapshots fail closed if that tool is unavailable. Provision
at least 32 random bytes as root:root 0600 at the
configured `HMAC_KEY_FILE`, separate from backups and the age identity, for
example:

```bash
install -d -m 0700 /etc/dockyard
python3 /usr/local/lib/dockyard/dockyard_ops.py ensure-hmac-key \
  /etc/dockyard/backup-auth.key
```

Configure the public `AGE_RECIPIENT`, root-readable allowlist, native Redis
connection, age identity path, and HMAC key path. Backups never stop or restart
the bot service. SQLite files use the online backup API with integrity checks;
transient SQLite journals are excluded. Other allowlisted files are copied live;
symlink or special-file sources fail. Redis uses its native `redis-cli --rdb`
snapshot. Each database is consistent independently, not a single atomic
snapshot across Redis and all files; transient downloads/logs can change during
copying. `LOG_CHANNEL=0` is only an installer placeholder and must not overwrite
a saved log-group ID on startup.

The supplied allowlist names `/var/lib/dockyard/current`. The root backup helper
accepts that one activation symlink only when it resolves directly to
`/var/lib/dockyard/workspaces/<40-hex-commit>`. It requires the workspace to
contain the exact root-owned `source` link and `work/`, copies only real mutable
state from `work/`, rejects every other link or special entry, and does not
traverse historic workspaces or immutable source. Backup status includes only
the sanitized `managed` or `legacy` mode, never a source path.
In legacy mode the allowlist names `/opt/ultroid`, but the helper copies only
its session/database/add-on/auth/download/log mutable set; executable code and
virtual-environment links are not archived as mutable state.

The manifest is an exact regular-file inventory excluding only manifest
metadata. Verification checks path, size, mode, SHA-256, missing and extra
files, and rejects links/devices/FIFOs. The encrypted ciphertext receives a
detached HMAC-SHA256 sidecar. Restore verification authenticates ciphertext
before age decrypts or tar parsing begins. The HMAC key is read from its file,
never placed in arguments or logs. There is no plaintext fallback.

Rotation keeps only the newest three archive/signature pairs.
`dockyard-restore-verify` uses a private temporary directory and never writes
production.

### Disabling scheduled backups

Retire the schedule before removing its target directory:

```bash
systemctl disable --now dockyard-backup.timer
systemctl reset-failed dockyard-backup.service
```

Removing `/var/backups/dockyard` while the timer is still enabled makes the
oneshot unit fail with `status=226/NAMESPACE`, which then appears as a failed
job even though backups were intentionally disabled. Re-enabling the timer
requires recreating the directory with
`systemd-tmpfiles --create /usr/lib/tmpfiles.d/dockyard.conf` and confirming the
configured age recipient and HMAC key are still present.

## Health, readiness, and status

The application writes readiness after initialization even with `LOG_OFF` and
refreshes it every 15 seconds. Deploy and health default to a 45-second maximum
age and require the marker PID to equal systemd `MainPID`.

Set `DOCKYARD_STATUS_DIR=/var/lib/dockyard/status` as the root-owned truth
directory and `DOCKYARD_APP_STATUS_DIR=/var/lib/dockyard/app-status` as the
service-owned output directory. Root truth is root-owned, group-readable where
the dashboard needs it, and never group-writable: directories are 0750,
sanitized dashboard files are 0640, and private alert state is 0600. The bot
unit mounts root truth read-only and cannot replace it; app-side update reports
go only to `app-status`. Root health never reads app-owned status.

Health covers service/restarts, readiness, Redis, disk, memory, immutable
source ownership, exact workspace/work layout, backup freshness, and update
freshness. Alert cooldown advances
only after a successful Telegram response; failure is recorded only as the
fixed sanitized state `alert delivery failed`.

Review:

```bash
systemctl status dockyard.service dockyard-deploy.path \
  dockyard-health.timer dockyard-backup.timer
/usr/local/sbin/dockyard-deploy status
journalctl -u dockyard.service --since today
```

Never share raw configuration, exceptions, paths, URLs, chat IDs, or logs.

## Release verification

Before handoff run the commands listed in `MIGRATION.md`, including both Python
versions, JSON/YAML parsing, ShellCheck, Docker exact-source smoke tests when
the registry/network is available, `git diff --check`, and the AST/grep safety
checks in `scripts/quality_checks.py`.

## Upstream sync

Fetch TeamUltroid as a separate upstream, review its range, and preserve AGPL
headers and internal identifiers, callback data, session formats, database
keys, and environment contracts. Upstream is never an in-app deploy target.
