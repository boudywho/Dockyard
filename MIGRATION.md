# Dockyard migration and rollback

## Migrating a live BoudyOS host to Dockyard

Use `ops/dockyard-migrate-host` for an installed host that still uses the
legacy `/etc/boudyos`, `/opt/boudyos`, `/var/lib/boudyos`, and
`/var/backups/boudyos` layout. The tool is fail-closed: it requires the legacy
trees to exist, the Dockyard trees to be absent, a repository checkout, and a
snapshot. Run the steps in this order.

1. **Snapshot.** Create a root-only snapshot directory containing
   `host-artifacts.tar.gz` of `etc/`, `usr/local/`, and `usr/lib/tmpfiles.d/`
   before any change. Keep it outside the migrated trees.
2. **Plan.** Review every ordered action and installed command; `plan` changes
   nothing:
   `sudo ops/dockyard-migrate-host plan --snapshot /root/dockyard-migration`
3. **Apply.** Move the four trees, rewrite the `current` and workspace
   `source` symlinks, convert configuration to `DOCKYARD_*`, install the
   helpers/units/sudoers, and enable the new timers and
   `dockyard-paths.service`. `dockyard.service` is deliberately left stopped:
   `sudo ops/dockyard-migrate-host apply --snapshot /root/dockyard-migration --tag v3.0.0 --commit <40-hex>`
4. **Deploy.** Run the pinned deploy command printed by `apply`; it stages and
   activates the new release:
   `sudo /usr/local/sbin/dockyard-deploy deploy`
5. **Verify.** Run the read-only post-checks for legacy strings, modes,
   symlinks, imports, sudoers, and the release pin:
   `sudo ops/dockyard-migrate-host verify --snapshot /root/dockyard-migration`
6. **Rollback.** On failure the tool rolls back automatically. To restore a
   completed migration deliberately, restore the trees and the snapshot, then
   start and verify the legacy unit:
   `sudo ops/dockyard-migrate-host rollback --snapshot /root/dockyard-migration`

The migration does not change the `ultroid` account or group, the Redis unit,
database or Redis keys, callback data, commands, or the session file format.
It only relocates the host paths and renames the operational surface. A
non-`/` `--root` runs the same flow against a disposable tree and prints
privileged commands as `[sandbox] would run: ...`.

## Rename migration to 3.0.0

Dockyard 3.0.0 renames the product and its operational surface. The code
package (`pyUltroid`), the `ultroid` Unix account/group, `ultroid-redis.service`,
database and Redis keys, callback data, commands, and session files are
unchanged.

Before deploying 3.0.0 over an installation created by the previous release:

1. Take and verify an authenticated encrypted backup.
2. Install the new operational assets: units from `ops/systemd/`, sudoers from
   `ops/sudoers/`, `ops/tmpfiles.d/dockyard.conf`, and the `ops/config/*.example`
   files as `/etc/dockyard/*`.
3. Move or re-provision managed state under the new paths: `/opt/dockyard`,
   `/var/lib/dockyard`, `/run/dockyard`, and `/var/backups/dockyard`. The
   service account remains `ultroid` for fresh and legacy managed installs; it
   is a compatibility contract with Redis and existing session state.
4. Convert every legacy environment/configuration key to its `DOCKYARD_*`
   equivalent, including the deploy, backup, health, and systemd values.
5. Point the deploy configuration at the `dockyard-*` helpers and the
   `dockyard.service` unit, then run the deploy `check`/`stage` flow before
   activation.

Rolling back means restoring the previous release and its original units,
paths, and legacy configuration. Database contents are not rewritten by the
rename.

## Existing installations

Before changing units, complete an authenticated encrypted backup and restore
verification. Pin both `v2.2.2` and its exact 40-hex peeled commit in the
root-owned deploy configuration. A placeholder is documentation only and is
rejected by operational actions.

Unset `PLUGIN_PROFILES` never removes commands from an upgraded installation.
The first 2.2 load writes `PLUGIN_PROFILE_POLICY=legacy-all-v1` independently
of `INIT_DEPLOY` and `LOG_OFF`. Only new provisioning writes
`new-safe-v1` with `core,media`.

Leave `ALLOW_DANGEROUS_DEV_EXEC` and `ALLOW_UNTRUSTED_PLUGINS` false. The
owner shell and eval commands were removed in 2.4.0; the dangerous execution
opt-in is retained only as a compatibility key. Attachment, raw URL,
plugin-channel, and unverified local code load paths require owner-controlled
untrusted-plugin opt-in.

## Exact legacy production layout

The supported legacy layout is:

```text
user:    ultroid
service: ultroid.service
source:  /opt/ultroid
env:     /etc/ultroid/ultroid.env
```

Use `ops/config/deploy-ultroid.conf.example`,
`ops/config/backup-ultroid.conf.example`,
`ops/config/backup-paths-ultroid.example`,
`ops/config/health-ultroid.conf.example`,
`ops/sudoers/ultroid-dockyard-deploy`, and
`ops/systemd/ultroid-dockyard.conf.example`. Replace the commit placeholder and
validate sudoers before installation. Install
`ops/tmpfiles.d/dockyard.conf` and `ops/systemd/dockyard-paths.service` as
documented in `docs/operations.md`, run `systemd-tmpfiles --create` before any
unit is started, and enable the provisioning service. The legacy drop-in also
uses `RuntimeDirectory=dockyard` and `StateDirectory=dockyard/app-status`, so
systemd deterministically applies `ultroid:ultroid` ownership to those two
writable directories before `ExecStart`.

Run:

```bash
sudo /usr/local/sbin/dockyard-migrate-ultroid plan
sudo /usr/local/sbin/dockyard-migrate-ultroid prepare
sudo /usr/local/sbin/dockyard-deploy check
sudo /usr/local/sbin/dockyard-deploy stage
# Replace the live backup allowlist/config and health config with the managed
# examples (preserving separately provisioned recipient/key values).
sudo /usr/local/sbin/dockyard-migrate-ultroid activate
```

Before `prepare`, install the legacy backup and health examples at their
documented live paths. `prepare` briefly stops `ultroid.service`, creates a
root-only rollback
snapshot under `/var/lib/dockyard/migration-snapshots`, copies the environment
to `/etc/dockyard/runtime.env` with group `ultroid`, creates an
root-owned runtime seed containing an `ultroid`-owned `work/`, and restarts the
legacy unit. The source snapshot, environment, session/local database files,
add-ons, auth, downloads, and external Redis configuration remain available.
Only mutable state is seeded into `work/`; legacy official source files are not
copied into an executable runtime position. It does not delete or rewrite
`/opt/ultroid` or `/etc/ultroid/ultroid.env`.

`stage` builds, preflights, quarantines/replaces any prior target directories,
and prepares a root-owned commit workspace containing an exact root-owned
`source` link and service-owned `work/` state. Official code is executed
through that link; no code selector is placed below writable state. It atomically records the
exact verified source and runtime paths, tag, and full commit in root-owned
mode-0640 staged state.
`activate` rejects linked, traversing, mismatched, or insecure staged state and
refuses to stop the legacy unit until the live backup, allowlist, and health
configuration all target the managed runtime. It
loads the drop-in template only from that exact staged source. It installs the
reviewed drop-in only after those exact tag+commit directories, ownership,
modes, and work layout verify. It repeats validation after the link switch,
before start. It removes stale readiness, switches the existing
`ultroid.service` to immutable Dockyard code and venv with `work/` as its
writable cwd, and
requires fresh PID-correlated readiness. Failure removes the drop-in and
restarts the original unit.

After activation and production verification, rename only the application
unit to its canonical `dockyard.service` name:

```bash
sudo /usr/local/sbin/dockyard-rename-service plan
sudo /usr/local/sbin/dockyard-rename-service rename
```

The rename preserves the complete effective legacy unit and drop-in bytes and
changes only `ultroid.service` selectors in the root-managed deploy, backup,
and health configuration. The production Unix user/group remain `ultroid`,
and `/opt/ultroid`, existing Dockyard runtime/state paths and environment
values, Telegram identifiers, and `ultroid-redis.service` remain compatibility
surfaces. A repeated rename reports that migration is already complete and
does not mutate the installation.

## Rollback

For a deployed Dockyard release:

```bash
sudo /usr/local/sbin/dockyard-deploy rollback
```

The helper does not report success until the retained prior release is active
and fresh-ready. It does not rewrite database keys.

For the legacy layout migration, before the separate service-name rename:

```bash
sudo /usr/local/sbin/dockyard-migrate-ultroid rollback
```

This verifies a stop before changing anything, removes the managed selectors,
restores the recorded legacy drop-in/backup/allowlist/health configuration,
reloads systemd, and establishes a new ready PID for the original
`ultroid.service`. Backup status is reset to sanitized `legacy` mode so a
managed-workspace backup cannot be reported for the running legacy process;
the root-only snapshot and staged release are retained for safe reactivation.
Verify Redis, session
login, assistant connection, media writes, and a restore drill before removing
any legacy files.

The service-name command itself automatically restores the exact unit,
drop-ins, selectors, enabled state, and running `ultroid.service` when any
rename or target verification step fails. The manual legacy-layout rollback
above intentionally remains the procedure while the application unit is still
named `ultroid.service`; complete any decision to use it before performing the
final canonical-name migration.

The upstream py-Ultroid version remains `2026.04.03`; Dockyard is `2.2.2`.
