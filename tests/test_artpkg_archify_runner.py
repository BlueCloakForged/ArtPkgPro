import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import sys
sys.path.insert(0, str(Path(__file__).parents[1] / "tools"))

import artpkg_archify_runner as runner


class ArchifyRunnerTests(unittest.TestCase):
    def test_validate_uses_explicit_node_and_archify_root(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact = Path(temp_dir) / "input.json"
            artifact.write_text("{}", encoding="utf-8")
            config = runner.ArchifyConfig(node_executable="C:/node/node.exe", archify_root="D:/archify/archify", receipt_dir=temp_dir)
            completed = runner.subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout=json.dumps({"ok": True, "checks": []}),
                stderr="",
            )
            with patch("artpkg_archify_runner.subprocess.run", return_value=completed) as run:
                result = runner.run_archify_validate(config, "architecture", artifact)

            artifact_digest = runner.sha256_file(artifact)
            receipt_path = Path(result["receipt_path"])

        self.assertTrue(result["ok"])
        self.assertTrue(receipt_path.name.endswith(".receipt.json"))
        self.assertEqual(artifact_digest, result["artifact_sha256"])
        self.assertEqual("validate", result["operation"])
        self.assertEqual("architecture", result["diagram_type"])
        args = run.call_args.args[0]
        self.assertEqual("C:/node/node.exe", args[0])
        self.assertEqual("bin/archify.mjs", args[1])
        self.assertIn("--json", args)
        self.assertEqual(60, run.call_args.kwargs["timeout"])
        self.assertEqual("D:/archify/archify", str(run.call_args.kwargs["cwd"]))

    def test_timeout_is_structured_and_persisted(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact = Path(temp_dir) / "input.json"
            artifact.write_text("{}", encoding="utf-8")
            config = runner.ArchifyConfig(receipt_dir=temp_dir, timeout_seconds=3)
            with patch("artpkg_archify_runner.subprocess.run", side_effect=runner.subprocess.TimeoutExpired(["node"], 3)):
                result = runner.run_archify_validate(config, "architecture", artifact)

            receipt_path = Path(result["receipt_path"])
            persisted = json.loads(receipt_path.read_text(encoding="utf-8"))

        self.assertFalse(result["ok"])
        self.assertEqual("Archify command timed out", result["receipt"]["error"])
        self.assertEqual("TIMEOUT", result["exit_code"])
        self.assertEqual(3, persisted["timeout_seconds"])
        self.assertEqual("TIMEOUT", persisted["exit_code"])

    def test_deliver_receipt_records_output_html_digest(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact = Path(temp_dir) / "input.json"
            html = Path(temp_dir) / "output.html"
            artifact.write_text("{}", encoding="utf-8")
            html.write_text("<html>current</html>", encoding="utf-8")
            config = runner.ArchifyConfig(receipt_dir=temp_dir)
            completed = runner.subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout=json.dumps({"ok": True}),
                stderr="",
            )
            with patch("artpkg_archify_runner.subprocess.run", return_value=completed):
                result = runner.run_archify_deliver(config, "architecture", artifact, html)

            html_digest = runner.sha256_file(html)
            persisted = json.loads(Path(result["receipt_path"]).read_text(encoding="utf-8"))

        self.assertTrue(result["ok"])
        self.assertEqual(html_digest, result["output_sha256"])
        self.assertEqual(result["output_sha256"], persisted["output_sha256"])

    def test_validate_uses_explicit_node_and_archify_root_without_receipt_dir(self):
        config = runner.ArchifyConfig(node_executable="C:/node/node.exe", archify_root="D:/archify/archify")
        completed = runner.subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=json.dumps({"ok": True, "checks": []}),
            stderr="",
        )
        with patch("artpkg_archify_runner.subprocess.run", return_value=completed) as run:
            result = runner.run_archify_validate(config, "architecture", "input.json")

        self.assertTrue(result["ok"])
        args = run.call_args.args[0]
        self.assertEqual("C:/node/node.exe", args[0])
        self.assertEqual("bin/archify.mjs", args[1])
        self.assertIn("--json", args)
        self.assertEqual("D:/archify/archify", str(run.call_args.kwargs["cwd"]))

    def test_nonzero_archify_result_is_not_success(self):
        config = runner.ArchifyConfig(node_executable="node", archify_root="D:/archify/archify")
        completed = runner.subprocess.CompletedProcess(
            args=[],
            returncode=1,
            stdout=json.dumps({"ok": False, "error": "bad diagram"}),
            stderr="",
        )
        with patch("artpkg_archify_runner.subprocess.run", return_value=completed):
            result = runner.run_archify_validate(config, "architecture", "input.json")

        self.assertFalse(result["ok"])
        self.assertEqual(1, result["exit_code"])
        self.assertEqual("bad diagram", result["receipt"]["error"])

    def test_invalid_json_result_is_not_success(self):
        config = runner.ArchifyConfig()
        completed = runner.subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="not json",
            stderr="",
        )
        with patch("artpkg_archify_runner.subprocess.run", return_value=completed):
            result = runner.run_archify_validate(config, "architecture", "input.json")

        self.assertFalse(result["ok"])
        self.assertEqual("Archify did not return JSON", result["receipt"]["error"])
        self.assertEqual("not json", result["receipt"]["stdout"])

    def test_non_object_json_result_is_not_success(self):
        config = runner.ArchifyConfig()
        completed = runner.subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=json.dumps(["unexpected", "receipt"]),
            stderr="",
        )
        with patch("artpkg_archify_runner.subprocess.run", return_value=completed):
            result = runner.run_archify_validate(config, "architecture", "input.json")

        self.assertFalse(result["ok"])
        self.assertEqual("Archify did not return a JSON object", result["receipt"]["error"])
        self.assertEqual(["unexpected", "receipt"], result["receipt"]["value"])
