import os
import stat
import subprocess
import tarfile
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "ops/dockyard-migrate-host"
COMMIT = "0123456789abcdef0123456789abcdef01234567"
SECRET = "fixture-secret-never-print"


class HostMigrationSandboxTests(unittest.TestCase):
    def make_fixture(self):
        temporary = tempfile.TemporaryDirectory(prefix="dockyard-migrate-")
        self.addCleanup(temporary.cleanup)
        fake = Path(temporary.name) / "host"
        snapshot = Path(temporary.name) / "snapshot"
        snapshot.mkdir()

        for relative in (
            "etc/boudyos",
            "opt/boudyos/releases/v2.2.2",
            "var/lib/boudyos/workspaces/ws/work",
            "var/backups/boudyos",
            "etc/systemd/system/boudyos.service.d",
            "etc/sudoers.d",
            "usr/local/sbin",
            "usr/local/lib/boudyos",
            "usr/lib/tmpfiles.d",
        ):
            (fake / relative).mkdir(parents=True, exist_ok=True)

        configs = {
            "deploy.conf": (
                "DOCKYARD_UNUSED=keep\n"
                "BOUDYOS_RELEASE_TAG=v2.2.2\n"
                "BOUDYOS_RELEASE_COMMIT=" + "f" * 40 + "\n"
                "BOUDYOS_RELEASE_ROOT=/opt/boudyos/releases\n"
                "BOUDYOS_RUNTIME_ROOT=/var/lib/boudyos/workspaces\n"
                "BOUDYOS_RUNTIME_LINK=/var/lib/boudyos/current\n"
                "BOUDYOS_RUNTIME_USER=ultroid\n"
                "BOUDYOS_SERVICE=boudyos.service\n"
                "BOUDYOS_READY_FILE=/run/boudyos/ready\n"
                "BOUDYOS_SECRET=" + SECRET + "\n"
            ),
            "health.conf": (
                "SERVICE=boudyos.service\n"
                "READY_FILE=/run/boudyos/ready\n"
                "RELEASE_ROOT=/opt/boudyos/releases\n"
                "WORKSPACE_ROOT=/var/lib/boudyos/workspaces\n"
                "REDIS_ENV_FILE=/etc/boudyos/redis.env\n"
            ),
            "backup.conf": (
                "BACKUP_DIR=/var/backups/boudyos\n"
                "QUIESCE_SERVICE=boudyos.service\n"
                "DOCKYARD_OPS_HELPER=/usr/local/lib/boudyos/dockyard_ops.py\n"
                "REDIS_ENV_FILE=/etc/boudyos/redis.env\n"
            ),
            "runtime.env": "BOUDYOS_RUNTIME_MODE=legacy\n",
            "redis.env": "REDIS_HOST=127.0.0.1\n",
            "backup-auth.key": SECRET + "\n",
        }
        modes = {
            "deploy.conf": 0o640,
            "health.conf": 0o600,
            "backup.conf": 0o640,
            "runtime.env": 0o600,
            "redis.env": 0o600,
            "backup-auth.key": 0o600,
        }
        for name, content in configs.items():
            path = fake / "etc/boudyos" / name
            path.write_text(content, "utf-8")
            path.chmod(modes[name])

        release = fake / "opt/boudyos/releases/v2.2.2"
        (release / "pyUltroid").mkdir()
        (release / "pyUltroid/__init__.py").write_text("", "utf-8")

        workspace = fake / "var/lib/boudyos/workspaces/ws"
        (workspace / "work" / "session.txt").write_text("legacy\n", "utf-8")
        os.symlink(
            "/opt/boudyos/releases/v2.2.2", workspace / "source"
        )
        os.symlink(
            "/var/lib/boudyos/workspaces/ws", fake / "var/lib/boudyos/current"
        )
        (fake / "var/backups/boudyos/legacy.tar").write_text("backup\n", "utf-8")

        unit = (
            "[Unit]\nDescription=Legacy\n\n"
            "[Service]\nEnvironmentFile=/etc/boudyos/runtime.env\n"
            "User=ultroid\nExecStart=/opt/boudyos/current/source/startup\n"
        )
        for name in (
            "boudyos.service",
            "boudyos-health.service",
            "boudyos-health.timer",
            "boudyos-backup.service",
            "boudyos-backup.timer",
            "boudyos-update-check.service",
            "boudyos-update-check.timer",
            "boudyos-deploy.service",
            "boudyos-deploy.path",
            "boudyos-paths.service",
        ):
            (fake / "etc/systemd/system" / name).write_text(unit, "utf-8")
        (fake / "etc/systemd/system/boudyos.service.d/legacy.conf").write_text(
            "[Service]\nEnvironment=LEGACY=1\n", "utf-8"
        )
        (fake / "etc/sudoers.d/boudyos-deploy").write_text(
            "ultroid ALL=(root) NOPASSWD: /usr/local/sbin/boudyos-deploy request\n",
            "utf-8",
        )
        (fake / "usr/local/sbin/boudyos-health").write_text(
            "#!/usr/bin/env bash\nexit 0\n", "utf-8"
        )
        (fake / "usr/local/sbin/boudyos-health").chmod(0o755)
        (fake / "usr/local/lib/boudyos/dockyard_ops.py").write_text(
            "# legacy helper\n", "utf-8"
        )
        (fake / "usr/lib/tmpfiles.d/boudyos.conf").write_text(
            "d /var/lib/boudyos 0755 root root -\n", "utf-8"
        )

        with tarfile.open(snapshot / "host-artifacts.tar.gz", "w:gz") as archive:
            for name in ("etc", "usr/local", "usr/lib/tmpfiles.d"):
                archive.add(fake / name, arcname=name)

        marker = fake / "systemctl-invoked"
        bin_dir = fake / "fakebin"
        bin_dir.mkdir()
        fake_systemctl = bin_dir / "systemctl"
        fake_systemctl.write_text(
            "#!/usr/bin/env bash\nprintf '%s\\n' \"$*\" >>\"$SYSTEMCTL_MARKER\"\n",
            "utf-8",
        )
        fake_systemctl.chmod(0o755)
        environment = {
            **os.environ,
            "PATH": str(bin_dir) + os.pathsep + os.environ["PATH"],
            "SYSTEMCTL_MARKER": str(marker),
        }
        return fake, snapshot, environment, marker

    def run_script(self, *arguments, environment):
        return subprocess.run(
            [str(SCRIPT), *map(str, arguments)],
            text=True,
            capture_output=True,
            timeout=120,
            check=False,
            env=environment,
        )

    def test_plan_is_read_only(self):
        fake, snapshot, environment, _marker = self.make_fixture()
        before = {
            path: path.read_bytes()
            for path in (
                fake / "etc/boudyos/deploy.conf",
                fake / "etc/boudyos/health.conf",
                fake / "etc/systemd/system/boudyos.service",
            )
        }
        result = self.run_script(
            "plan",
            "--root", fake,
            "--snapshot", snapshot,
            "--tag", "v3.0.0",
            "--commit", COMMIT,
            environment=environment,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("plan:", result.stdout)
        self.assertIn("v3.0.0", result.stdout)
        self.assertIn("install -m 0755", result.stdout)
        self.assertIn("systemctl enable dockyard-paths.service", result.stdout)
        self.assertFalse((fake / "etc/dockyard").exists())
        self.assertFalse((fake / "opt/dockyard").exists())
        self.assertFalse((snapshot / "migration.log").exists())
        for path, content in before.items():
            self.assertEqual(path.read_bytes(), content)
        self.assertNotIn(SECRET, result.stdout + result.stderr)

    def test_apply_migrates_and_verify_passes(self):
        fake, snapshot, environment, marker = self.make_fixture()
        result = self.run_script(
            "apply",
            "--root", fake,
            "--snapshot", snapshot,
            "--tag", "v3.0.0",
            "--commit", COMMIT,
            environment=environment,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn(SECRET, result.stdout + result.stderr)

        self.assertTrue((fake / "opt/dockyard/releases/v2.2.2").is_dir())
        self.assertTrue((fake / "var/lib/dockyard/workspaces/ws/work").is_dir())
        self.assertTrue((fake / "var/backups/dockyard/legacy.tar").is_file())
        self.assertFalse((fake / "etc/boudyos").exists())
        self.assertFalse((fake / "opt/boudyos").exists())
        self.assertFalse((fake / "var/lib/boudyos").exists())
        self.assertFalse((fake / "var/backups/boudyos").exists())

        current = fake / "var/lib/dockyard/current"
        source = fake / "var/lib/dockyard/workspaces/ws/source"
        self.assertEqual(
            os.readlink(current),
            str(fake / "var/lib/dockyard/workspaces/ws"),
        )
        self.assertEqual(
            os.readlink(source),
            str(fake / "opt/dockyard/releases/v2.2.2"),
        )
        self.assertTrue(current.exists())
        self.assertTrue(source.exists())

        deploy = (fake / "etc/dockyard/deploy.conf").read_text("utf-8")
        self.assertIn("DOCKYARD_RELEASE_TAG=v3.0.0", deploy)
        self.assertIn("DOCKYARD_RELEASE_COMMIT=" + COMMIT, deploy)
        self.assertIn("DOCKYARD_RELEASE_ROOT=/opt/dockyard/releases", deploy)
        self.assertIn("DOCKYARD_UNUSED=keep", deploy)
        self.assertNotIn("BOUDYOS_", deploy)
        health = (fake / "etc/dockyard/health.conf").read_text("utf-8")
        self.assertIn("SERVICE=dockyard.service", health)
        self.assertIn("READY_FILE=/run/dockyard/ready", health)
        self.assertIn("REDIS_ENV_FILE=/etc/dockyard/redis.env", health)
        self.assertNotIn("/opt/boudyos", health)
        self.assertNotIn("/var/lib/boudyos", health)

        self.assertEqual(
            stat.S_IMODE((fake / "etc/dockyard/deploy.conf").stat().st_mode),
            0o640,
        )
        for name, mode in (
            ("health.conf", 0o600),
            ("backup.conf", 0o640),
            ("runtime.env", 0o600),
            ("redis.env", 0o600),
            ("backup-auth.key", 0o600),
        ):
            self.assertEqual(
                stat.S_IMODE((fake / "etc/dockyard" / name).stat().st_mode),
                mode,
            )

        for name in (
            "dockyard.service",
            "dockyard-health.timer",
            "dockyard-backup.timer",
            "dockyard-update-check.timer",
            "dockyard-deploy.path",
            "dockyard-paths.service",
        ):
            self.assertTrue((fake / "etc/systemd/system" / name).is_file(), name)
        self.assertFalse((fake / "etc/systemd/system/boudyos.service").exists())
        self.assertFalse((fake / "etc/sudoers.d/boudyos-deploy").exists())
        self.assertTrue((fake / "etc/sudoers.d/dockyard-deploy").is_file())
        self.assertEqual(
            stat.S_IMODE((fake / "etc/sudoers.d/dockyard-deploy").stat().st_mode),
            0o440,
        )
        self.assertTrue((fake / "usr/lib/tmpfiles.d/dockyard.conf").is_file())
        for helper in (
            "dockyard-deploy",
            "dockyard-health",
            "dockyard-backup",
            "dockyard-restore-verify",
            "dockyard-rename-service",
            "dockyard-migrate-ultroid",
        ):
            path = fake / "usr/local/sbin" / helper
            self.assertTrue(path.is_file(), helper)
            self.assertTrue(os.access(path, os.X_OK), helper)

        log = (snapshot / "migration.log").read_text("utf-8")
        self.assertIn("[sandbox] would run: systemctl stop boudyos.service", log)
        self.assertIn("[sandbox] would run: systemctl enable dockyard-paths.service", log)
        self.assertNotIn("systemctl start dockyard.service", log)
        self.assertFalse(marker.exists(), "systemctl was invoked in the sandbox")

        verify = self.run_script(
            "verify", "--root", fake, environment=environment
        )
        self.assertEqual(verify.returncode, 0, verify.stderr)
        self.assertIn("verify: all checks passed", verify.stdout)
        self.assertIn("ok: no BoudyOS unit files remain", verify.stdout)
        self.assertNotIn(SECRET, verify.stdout + verify.stderr)

    def test_rollback_restores_the_legacy_layout_and_is_idempotent(self):
        fake, snapshot, environment, marker = self.make_fixture()
        original_deploy = (fake / "etc/boudyos/deploy.conf").read_bytes()
        original_unit = (
            fake / "etc/systemd/system/boudyos.service"
        ).read_bytes()

        applied = self.run_script(
            "apply",
            "--root", fake,
            "--snapshot", snapshot,
            "--tag", "v3.0.0",
            "--commit", COMMIT,
            environment=environment,
        )
        self.assertEqual(applied.returncode, 0, applied.stderr)

        rolled_back = self.run_script(
            "rollback",
            "--root", fake,
            "--snapshot", snapshot,
            environment=environment,
        )
        self.assertEqual(rolled_back.returncode, 0, rolled_back.stderr)
        self.assertNotIn(SECRET, rolled_back.stdout + rolled_back.stderr)

        self.assertTrue((fake / "etc/boudyos").is_dir())
        self.assertTrue((fake / "opt/boudyos/releases/v2.2.2").is_dir())
        self.assertTrue((fake / "var/lib/boudyos/workspaces/ws/work").is_dir())
        self.assertTrue((fake / "var/backups/boudyos/legacy.tar").is_file())
        self.assertFalse((fake / "etc/dockyard").exists())
        self.assertFalse((fake / "opt/dockyard").exists())
        self.assertFalse((fake / "var/lib/dockyard").exists())
        self.assertFalse((fake / "var/backups/dockyard").exists())

        self.assertEqual(
            (fake / "etc/boudyos/deploy.conf").read_bytes(), original_deploy
        )
        self.assertEqual(
            (fake / "etc/systemd/system/boudyos.service").read_bytes(),
            original_unit,
        )
        self.assertTrue((fake / "usr/local/sbin/boudyos-health").is_file())
        self.assertTrue((fake / "usr/lib/tmpfiles.d/boudyos.conf").is_file())
        self.assertFalse((fake / "usr/lib/tmpfiles.d/dockyard.conf").exists())
        self.assertFalse((fake / "etc/systemd/system/dockyard.service").exists())
        self.assertFalse((fake / "usr/local/sbin/dockyard-deploy").exists())

        current = fake / "var/lib/boudyos/current"
        source = fake / "var/lib/boudyos/workspaces/ws/source"
        self.assertTrue(current.exists())
        self.assertTrue(source.exists())
        self.assertIn("var/lib/boudyos/workspaces/ws", os.readlink(current))
        self.assertIn("opt/boudyos/releases/v2.2.2", os.readlink(source))

        log = (snapshot / "migration.log").read_text("utf-8")
        self.assertIn("[sandbox] would run: systemctl start boudyos.service", log)
        self.assertFalse(marker.exists(), "systemctl was invoked in the sandbox")

        second = self.run_script(
            "rollback",
            "--root", fake,
            "--snapshot", snapshot,
            environment=environment,
        )
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertTrue((fake / "etc/boudyos").is_dir())
        self.assertFalse((fake / "etc/dockyard").exists())
        self.assertFalse(marker.exists(), "systemctl was invoked in the sandbox")


if __name__ == "__main__":
    unittest.main()
