"""Local, self-hosted model routes must not require Vertex credentials."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from harness2 import config, install


class WorkBuddyLocalRoutesTests(unittest.TestCase):
    def test_local_solver_and_judge_use_openai_compatible_backend(self):
        with tempfile.TemporaryDirectory() as directory:
            with (
                patch.object(config, "SOLVER_MODEL_OC", "lmstudio/qwen3.5-9b-mtp"),
                patch.object(config, "JUDGE_MODEL", "openai/qwen3.5-9b-mtp"),
                patch.object(config, "VERTEX_PROJECT", ""),
                patch.object(config, "WB_BASE_URL", "http://127.0.0.1:1234/v1", create=True),
                patch.object(config, "wb_repo", return_value=Path(directory)),
            ):
                install.workbuddy_models()
                models = [
                    json.loads((Path(directory) / f"configs/models/harness2/{role}.yaml").read_text())["model"]
                    for role in ("solver", "judge")
                ]
        self.assertEqual([model["name"] for model in models], [
            "openai/qwen3.5-9b-mtp", "openai/qwen3.5-9b-mtp"
        ])
        for model in models:
            self.assertEqual(model["backend_url_env"], "HARNESS2_WB_MODEL_URL")
            self.assertNotIn("backend_key_command", model)
            self.assertFalse(model.get("thought_signature_passback", False))

    def test_local_backend_missing_url_fails_closed(self):
        with (
            patch.object(config, "SOLVER_MODEL_OC", "lmstudio/qwen3.5-9b-mtp"),
            patch.object(config, "JUDGE_MODEL", "openai/qwen3.5-9b-mtp"),
            patch.object(config, "WB_BASE_URL", "", create=True),
        ):
            with self.assertRaisesRegex(config.ConfigError, "HARNESS2_WB_BASE_URL"):
                install.workbuddy_models()

    def test_local_opencode_routes_are_isolated_from_global_config(self):
        with patch.object(config, "OPENCODE_CONFIG_HOME", Path("/tmp/harness2-config"), create=True):
            generated = config.opencode_env({"XDG_CONFIG_HOME": "/home/shared", "PATH": "/bin"}, model="lmstudio/qwen3.5-9b-mtp")
        self.assertEqual(generated["XDG_CONFIG_HOME"], "/tmp/harness2-config")
        self.assertEqual(generated["PATH"], "/bin")
        self.assertEqual(generated["OPENCODE_DISABLE_EXTERNAL_SKILLS"], "1")

    def test_local_opencode_config_contains_exact_model_and_endpoint(self):
        with (
            patch.object(config, "SOLVER_MODEL_OC", "lmstudio/qwen3.5-9b-mtp"),
            patch.object(config, "IMPROVER_MODEL", "lmstudio/qwen3.5-9b-mtp"),
        ):
            generated = config.opencode_local_config()
            providers = generated["provider"]
        self.assertEqual(generated["$schema"], "https://opencode.ai/config.json")
        self.assertEqual(set(providers["lmstudio"]["models"]), {"qwen3.5-9b-mtp"})
        self.assertEqual(providers["lmstudio"]["options"]["baseURL"], "http://127.0.0.1:1234/v1")

    def test_vertex_route_keeps_original_adc_and_signature_behavior(self):
        with (
            patch.object(config, "SOLVER_MODEL_OC", "google-vertex/gemini-test"),
            patch.object(config, "JUDGE_MODEL", "gemini-judge"),
            patch.object(config, "VERTEX_PROJECT", "project-id"),
        ):
            solver = config.workbuddy_route("solver")["model"]
            judge = config.workbuddy_route("judge")["model"]
        self.assertEqual(solver["name"], "google/gemini-test")
        self.assertEqual(judge["name"], "google/gemini-judge")
        self.assertTrue(solver["thought_signature_passback"])
        self.assertIn("gcloud", solver["backend_key_command"])

    def test_pinned_bun_skips_postinstall_when_executable_is_valid(self):
        from unittest.mock import Mock

        with (
            patch.object(install, "run") as runner,
            patch("harness2.install.subprocess.run", return_value=Mock(returncode=0, stdout="1.3.11\n")),
        ):
            install.ensure_bun()
        self.assertEqual(runner.call_count, 1)

    def test_pinned_bun_repairs_blocked_postinstall(self):
        from unittest.mock import Mock

        with (
            patch.object(install, "run") as runner,
            patch("harness2.install.subprocess.run", side_effect=[
                Mock(returncode=126, stdout=""),
                Mock(returncode=0, stdout="1.3.11\n"),
            ]),
        ):
            install.ensure_bun()
        self.assertEqual(runner.call_count, 2)
        self.assertEqual(runner.call_args.kwargs["cwd"], config.DEPENDENCIES / "tools")

    def test_workbuddy_auth_key_is_scrubbed_from_agents(self):
        self.assertNotIn("HARNESS2_WB_API_KEY", config.scrub_env({
            "HARNESS2_WB_API_KEY": "secret", "PATH": "/usr/bin"
        }))


if __name__ == "__main__":
    unittest.main()
