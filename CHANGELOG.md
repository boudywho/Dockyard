# Changelog

## Dockyard 3.2.0

- The sticker now renders the full reference composition — ribbon scene,
  vignette and frosted glass card — instead of a transparent card.

## Dockyard 3.1.1

- Quote cards now autofit display names and handles: the header measures the
  quote mark and steps the text down from its base size to a floor before
  ellipsizing, so long names such as `Abdulrahman ElKenany` are no longer
  truncated while the layout stays put.
- Quote messages avoid widow lines by moving one word from the previous line
  onto a lone final word when it still fits the wrap width.

## Dockyard 3.1.0

- Added `.q`, which turns a replied message into a dark-glass quote sticker
  and adds it to an automatically managed Telegram sticker pack. The same
  renderer produces a 1080x1350 PNG share card on request.
- `.q` flags: `-e` for the sticker emoji, `-p` for a pack slot from 1 to 20,
  `--preview` to skip the pack, `--photo` to blur the replied image into the
  avatar disc, `-n` to quote the last 1 to 10 messages, `--link` to quote a
  linked message, `--name` to override the display name, and `--png` to add
  the share card.
- Quote packs use `dq_<user>_<slot>_by_<assistant>` short names, are cached
  per slot, and advance one slot when a short name is occupied or a set is
  full or invalid. `.qpack` reports the current link and slot, and
  `.qpack reset` clears the slot and moves to the next free one.
- Added `quote` to the default media profile.

## Dockyard 3.0.1

- Host migration no longer aborts when a historic workspace points at a
  release that has already been pruned. Only the active `current` workspace
  must resolve; stale links are rewritten and reported as warnings.

## Dockyard 3.0.0

This is a rename release. The product, repository, install paths, service
names, environment variables, and helper scripts moved from the previous
product name to Dockyard/dockyard. Install locations now use `/opt/dockyard`,
`/var/lib/dockyard`, `/run/dockyard`, `/var/backups/dockyard`,
`/etc/dockyard`, and `/usr/local/lib/dockyard`; systemd units and operational
helpers use the `dockyard-*` names and `DOCKYARD_*` environment variables.

The upstream compatibility surface is unchanged: the `pyUltroid` package and
its imports, the `ultroid` Unix account/group, `ultroid-redis.service`, shared
database and Redis keys, callback data, command names, and the session format
keep their existing names.

A host migration is required before deploying 3.0.0. Existing installations
must move or re-provision paths, units, configuration files, the runtime
account, and legacy environment values before the new release starts. See
[MIGRATION.md](./MIGRATION.md).

## Dockyard 2.4.1

- Ported the applicable upstream `TeamUltroid/Ultroid` #512 and #513 fixes into
  the code Dockyard still ships. Upstream-only changes touching plugins Dockyard
  removed were deliberately not ported.
- Telethon is capped below 1.45, so a fresh install no longer crashes while
  importing `telethonpatch`.
- `.alive` and update output now work from a detached checkout or archive
  checkout with no active branch.
- `.shift` gained `-m` to shift media only, accepts a message link as the start
  post, and trims channel arguments.
- `.zip` no longer raises after a successful upload, because
  `fast_uploader(to_delete=True)` has already removed the archive.
- `.poll` and the suggestions poll now send `correct_answers` as an index and
  include `hash=0`.
- `KeyManager` no longer re-casts stored falsy values such as `0` or `False`.
- Expired sessions (`AuthKeyNotFound`) now exit cleanly instead of dumping a
  traceback, and a dead `VC_SESSION` is dropped.
- `mediainfo` no longer relabels every streamable video as "video as doc".
- Corrected `Image.size`, chat invite export, and snips handler registration.
- Release verification keeps `.git/index` inside the immutable mode policy and
  stops refreshing it during checks.

## Dockyard 2.4.0 - clean release

- Removed unmaintained, redundant, and experimental plugins: `aiwrapper`,
  `chatbot`, `weather`, `twitter`, `stories`, `gdrive`, `logo`, `unsplash`,
  `glitch`, `misc`, `fakeaction`, `cleanaction`, `delayspam`, `autopic`,
  `nightmode`, `words`, `beautify`, `nsfwfilter`, `profanityfilter`,
  `devtools`, and `specialtools`.
- Removed the assistant `games` plugin. Assistant plugins continue to load
  without it.
- Simplified plugin profiles to `core`, `media`, `admin`, and `automation`.
  The empty `developer` and `experimental` profiles are gone, and the official
  plugin inventory remains exactly assigned to the remaining profiles.
- Normalized the English user interface: help pages now render as
  `Plugin: <name>`, `Commands`, followed by plain command entries; decorative
  glyphs, bullets, and emoji were removed from user-facing text.
- Updated help text and plugin strings to neutral, professional English while
  preserving command syntax, placeholders, and behavior.
- Removed the developer shell and evaluation commands. The
  `ALLOW_DANGEROUS_DEV_EXEC` compatibility setting is retained, but no shipped
  plugin executes arbitrary code.
- Removed the orphaned settings and assistant UI for plugins that no longer
  ship, including Google Drive configuration, the PM Bot menu, the Emoji in
  Help toggle, and the retired Twitter inline search, and added the missing
  compressor help page.

## Dockyard 2.3.0 — consolidated upstream development

- Reconciled TeamUltroid feature and preview histories onto current Dockyard main.
  TeamUltroid main itself was already integrated at edd18d3.
- Added offline setup/doctor, redacted configuration checks, typed settings,
  owner-only official plugin controls, structured plugin load diagnostics,
  isolated supervised multi-client launching, and short FloodWait handling.
- Updated vulnerable GitPython, PyMongo, and pypdf pins; upgraded packaging
  tooling and included native SQLite in Docker for live snapshots.
- Preserved pinned dependencies, trusted addons, immutable deployment,
  PID-correlated readiness and uninterrupted encrypted backups.
- Historical alternate architectures are explicitly superseded and recoverable
  from archive tags; see docs/BRANCH_CONSOLIDATION.md for each merge decision.

## Dockyard 2.3.0 — uninterrupted backups

- Backups no longer stop or restart the Telegram workspace. SQLite sessions
  use online snapshots with integrity checks; Redis keeps its native snapshot.
- Keep only the newest three encrypted backup/signature pairs.
- Ignore zero/empty log-channel placeholders instead of overwriting saved groups.
- Verified a production encrypted backup and restore inventory with the same
  running Dockyard PID. Existing backup history was cleared at the owner's request.
- Legacy branch tips are preserved as archive tags; consolidation keeps current
  secure implementations rather than restoring incompatible historical designs.

## Unreleased — canonical service name

- Added a root-only, dry-runnable, idempotent migration from
  `ultroid.service` to the canonical `dockyard.service`, with exact unit/drop-in
  preservation, atomic selector rewrites, fresh PID-correlated readiness and
  health verification, enabled-state preservation, and verified rollback to
  the restarted legacy service.
- Kept the `ultroid` Unix account and state, `/opt/ultroid`, existing runtime
  and environment values, Telegram identifiers, and `ultroid-redis.service`
  unchanged as compatibility surfaces.

## Dockyard 2.2.6 — self-userbot text wizard

- Added a user-account-only numbered `.yt` wizard with no assistant-bot
  dependency.

## Dockyard 2.2.5 — Python launcher module-mode fix

- Signaled module-mode startup before loading `pyUltroid`, preserving the
  launcher's writable-work exclusion while restoring managed activation.

## Dockyard 2.2.4 — deployment preflight classifier fix

- Limited preflight shell syntax checks to executable files with shell shebangs,
  excluding the Python launcher from `bash -n` validation.

## Dockyard 2.2.3 — UI and media workflow polish

- Polished Dockyard UI and branding, removed inline YouTube search, and added a
  Telethon-native self-userbot `yt` media workflow with quality and timestamp
  selection, cleanup, and cancellation.

## Dockyard 2.2.2 — Python 3.10 safe-path compatibility

- Replaced the Python 3.11-only `-P` service flag with an immutable launcher
  compatible with Python 3.10. The launcher removes the writable work directory
  from `sys.path`, pins imports to the root-owned release, and disables bytecode
  writes without weakening the managed runtime boundary.

## Dockyard 2.2.1 — legacy migration readiness

- Corrected the migration `prepare` and legacy rollback gates for installations
  running Dockyard 2.1/legacy Ultroid, which predate the 2.2 readiness heartbeat.
- Legacy resume now requires a replaced nonzero systemd MainPID to remain
  active and unchanged for a bounded grace interval; managed 2.2 activation
  and rollback still require the fresh PID-correlated heartbeat.
- Repeated `prepare` validates and reuses an exact protected preparation record
  instead of stopping the legacy service or creating an ambiguous snapshot.

## Dockyard 2.2.0 — security and reliability

- Native activation now uses one atomic commit-workspace selector for immutable
  source plus writable work, verifies stopped/replaced processes around every
  transition, serializes deploy/rollback/migration, and restores legacy backup
  mode and configuration during migration rollback.

### Security

- Removed generic data/calculator/NIGHT_TIME `eval()` paths. Legacy Python
  literals remain data-only through `ast.literal_eval`.
- Added a bounded arithmetic evaluator and made owner Python execution an
  explicit `ALLOW_DANGEROUS_DEV_EXEC` opt-in, unavailable to sudo users.
- Added argv-only bounded subprocess, workspace-path, and safe archive APIs;
  migrated media, archive, upload, move, and delete operations away from shell
  interpolation.
- Disabled raw URL add-on execution by default. Trusted registry installs now
  enforce HTTPS source policy, full immutable revisions, SHA-256, size/time
  limits, valid Python syntax, atomic replacement, and rollback.
- Replaced in-bot pull/reset/pip behavior with approved Dockyard-origin
  pinned tag+commit checks and a short root-owned deployment request.

### Reliability and operations

- Added exact-tag detached deployment, immutable source plus writable runtime
  copies, verified rollback, PID-correlated readiness heartbeats, HMAC-authenticated
  age backups, exact restore manifests, health probing, and narrow sudoers.
- Added backward-compatible plugin profiles. Existing installs retain the old
  all-plugin default; new installs start with `core,media`.
- Added dashboard version/uptime/plugin/update/Redis/assistant/backup/health
  summaries using bounded, allowlisted status data.
- Restored Telethon-Patch at immutable commit `369fa3266c8a9c9aefb4a6c5608e8d44c09c7087`.
- Split optional dependencies, added direct-pin Python 3.10/3.13 constraints, stopped the
  default container from installing every integration, and removed the legacy
  Pydantic 1.8.2 Instagram fork conflict.
- Replaced auto-committing workflows with read-only CI, pinned Actions,
  CodeQL least permissions, and grouped Dependabot updates.
- Added the tested `ultroid` / `ultroid.service` / `/opt/ultroid` /
  `/etc/ultroid/ultroid.env` migration and retained rollback snapshot path.

### Compatibility

Telegram command names and callback data, session formats, environment and
database keys, `pyUltroid`, `UltroidClient`, the AGPL/upstream provenance, and
Dockyard assets remain compatible. The upstream py-Ultroid version remains
`2026.04.03`; the Dockyard product version is `2.2.0`.

## Dockyard 2.1.2

Production baseline: commit `5a7f41f`.
