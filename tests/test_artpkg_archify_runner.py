import json
import unittest
from pathlib import Path
from unittest.mock import patch

import sys
sys.path.insert(0, str(Path(__file__).parents[1] / "tools"))

import artpkg_archify_runner as runner


class ArchifyRunnerTests(unittest.TestCase):
    def test_validate_uses_explicit_node_and_archify_root(self):
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
