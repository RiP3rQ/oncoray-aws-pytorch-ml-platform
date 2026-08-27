from __future__ import annotations

import contextlib
import io
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import public_repo_guard as guard


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


class PublicRepoGuardTests(unittest.TestCase):
    def test_sensitive_filename_allowlist_is_narrow(self) -> None:
        self.assertEqual(guard._sensitive_filename_rule(".env"), "forbidden-sensitive-filename")
        self.assertIsNone(guard._sensitive_filename_rule(".env.example"))
        self.assertIsNone(guard._sensitive_filename_rule(".npmrc"))
        self.assertEqual(guard._sensitive_filename_rule("packages/private/.npmrc"), "forbidden-sensitive-filename")
        self.assertEqual(guard._sensitive_filename_rule("infra/prod/terraform.tfvars"), "forbidden-sensitive-filename")
        self.assertIsNone(guard._sensitive_filename_rule("infra/prod/terraform.tfvars.example"))
        self.assertEqual(
            guard._sensitive_filename_rule("docs/AWS_CLOUD_TEARDOWN_LOG.md"),
            "forbidden-sensitive-filename",
        )
        self.assertEqual(guard._sensitive_filename_rule("certificates/server.pem"), "forbidden-sensitive-filename")

    def test_root_npmrc_allows_behavior_config_but_rejects_literal_auth(self) -> None:
        self.assertEqual(guard.scan_text("auto-install-peers=true", ".npmrc", "tree"), [])
        findings = guard.scan_text("//registry.example/:_authToken=literal-secret", ".npmrc", "tree")
        self.assertEqual({finding.rule for finding in findings}, {"npm-auth-config"})
        self.assertEqual(guard.scan_text("//registry.example/:_authToken=${NPM_TOKEN}", ".npmrc", "tree"), [])

    def test_strict_signatures_report_metadata_only(self) -> None:
        access_key = "AK" + "IA" + ("Z" * 16)
        secret_key = "s" * 40
        github_token = "gh" + "p_" + ("G" * 36)
        signature = "A" * 32
        account_id = "4" * 12
        windows_path = "C:" + "\\Users\\" + "alice\\project"
        private_header = "-----BEGIN " + "PRIVATE KEY-----"
        text = "\n".join(
            (
                "AWS_ACCESS_KEY_ID=" + access_key,
                "AWS_SECRET_ACCESS_KEY=" + secret_key,
                "token=" + github_token,
                "url=https://bucket.s3.amazonaws.com/x?X-Amz-" + "Signature=" + signature,
                "aws_account_id=" + account_id,
                windows_path,
                private_header,
            )
        )

        findings = guard.scan_text(text, "docs/transcript.txt", "tree")
        rules = {finding.rule for finding in findings}
        self.assertEqual(
            rules,
            {
                "aws-access-key-id",
                "aws-secret-access-key",
                "github-token",
                "signed-url",
                "aws-account-id",
                "local-user-path",
                "private-key",
            },
        )
        rendered = guard._render_human(findings)
        self.assertNotIn(access_key, rendered)
        self.assertNotIn(secret_key, rendered)
        self.assertNotIn(github_token, rendered)
        self.assertNotIn(signature, rendered)
        self.assertNotIn(account_id, rendered)
        self.assertNotIn("alice", rendered)

    def test_documented_samples_and_placeholders_are_allowed(self) -> None:
        sample_access = "AK" + "IAIOSFODNN7EXAMPLE"
        sample_secret = "wJalrXUtnFEMI/K7MDENG/bPxRfi" + "CYEXAMPLEKEY"
        text = "\n".join(
            (
                "AWS_ACCESS_KEY_ID=" + sample_access,
                "AWS_SECRET_ACCESS_KEY=" + sample_secret,
                "aws_account_id=123456789012 # example account",
                "DATABASE_URL=postgres://user:your-password@example.invalid/db",
                "C:" + "\\Users\\username\\example",
            )
        )
        self.assertEqual(guard.scan_text(text, "tests/fixtures/config.example.txt", "tree"), [])

    def test_test_database_password_allowlist_does_not_apply_to_production_config(self) -> None:
        url = "DATABASE_URL=postgres://" + "user:" + "pass" + "@localhost/db"
        self.assertEqual(guard.scan_text(url, "tests/test_config.py", "tree"), [])
        findings = guard.scan_text(url, "config/production.env", "tree")
        self.assertEqual({finding.rule for finding in findings}, {"database-url-credential"})

    def test_history_scans_removed_blob_and_current_tree(self) -> None:
        access_key = "AS" + "IA" + ("Q" * 16)
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            _git(root, "init", "-q")
            _git(root, "config", "user.email", "guard@example.invalid")
            _git(root, "config", "user.name", "Guard Test")
            document = root / "docs" / "AWS_DEPLOYMENT_LOGS.md"
            document.parent.mkdir(parents=True)
            document.write_text("AWS_ACCESS_KEY_ID=" + access_key + "\n", encoding="utf-8")
            _git(root, "add", ".")
            _git(root, "commit", "-qm", "fixture commit")
            _git(root, "rm", "-q", "docs/AWS_DEPLOYMENT_LOGS.md")
            _git(root, "commit", "-qm", "remove transcript")

            self.assertEqual(guard.scan_tree(root), [])
            findings = guard.scan_history(root)
            self.assertTrue(any(finding.scope == "history" for finding in findings))
            self.assertTrue(any(finding.rule == "aws-access-key-id" for finding in findings))
            self.assertTrue(any(finding.object_id for finding in findings))
            rendered = guard._render_human(findings)
            self.assertNotIn(access_key, rendered)

    def test_cli_json_is_redacted_and_returns_failure(self) -> None:
        access_key = "AK" + "IA" + ("R" * 16)
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            _git(root, "init", "-q")
            _git(root, "config", "user.email", "guard@example.invalid")
            _git(root, "config", "user.name", "Guard Test")
            document = root / "config.txt"
            document.write_text("AWS_ACCESS_KEY_ID=" + access_key + "\n", encoding="utf-8")
            _git(root, "add", ".")
            _git(root, "commit", "-qm", "fixture commit")

            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                exit_code = guard.main(["tree", "--root", str(root), "--json"])
            self.assertEqual(exit_code, 1)
            self.assertIn('"rule": "aws-access-key-id"', output.getvalue())
            self.assertNotIn(access_key, output.getvalue())

    def test_commit_messages_private_refs_and_unreachable_objects_are_scanned(self) -> None:
        access_key = "AK" + "IA" + ("M" * 16)
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            _git(root, "init", "-q")
            _git(root, "config", "user.email", "guard@example.invalid")
            _git(root, "config", "user.name", "Guard Test")
            document = root / "safe.txt"
            document.write_text("safe\n", encoding="utf-8")
            _git(root, "add", ".")
            _git(root, "commit", "-qm", "message " + access_key)
            _git(root, "update-ref", "refs/t3/private", "HEAD")
            dangling = root / "dangling.txt"
            dangling.write_text("unreachable\n", encoding="utf-8")
            _git(root, "hash-object", "-w", "dangling.txt")

            findings = guard.scan_history(root)
            rules = {finding.rule for finding in findings}
            self.assertIn("aws-access-key-id", rules)
            self.assertIn("private-git-ref", rules)
            self.assertIn("unreachable-git-object", rules)
            rendered = guard._render_human(findings)
            self.assertNotIn(access_key, rendered)


if __name__ == "__main__":
    unittest.main()
