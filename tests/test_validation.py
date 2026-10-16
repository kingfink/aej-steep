from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import validate


class APITests(unittest.TestCase):
    def test_public_validation_rejects_errors_warnings_and_malformed_responses(self):
        validate.check_response({"valid": True, "problems": []})
        for response in (
            {},
            [],
            {"valid": False, "problems": []},
            {"valid": True, "problems": [{"code": "cohort-dimension-not-found"}]},
        ):
            with self.subTest(response=response), self.assertRaises(ValueError):
                validate.check_response(response)

    def test_preview_requires_explicit_success(self):
        good = dict(
            dryRun=True,
            outcome="completed",
            error=None,
            errors=[],
            warnings=[],
            created=[],
            updated=[],
            removed=[],
            unchanged=[],
        )
        validate.check_response(good, preview=True)
        for change in (
            dict(dryRun=False),
            dict(outcome="failed"),
            dict(errors=["error"]),
            dict(warnings=["warning"]),
            dict(removed=None),
        ):
            with self.subTest(change=change), self.assertRaises(ValueError):
                validate.check_response(good | change, preview=True)

    @patch.dict(
        "os.environ",
        {"STEEP_API_KEY": "test-key", "STEEP_DATASOURCE_ID": "test-source"},
    )
    @patch("scripts.validate.post")
    def test_validation_checks_example_but_preview_sends_only_active_files(self, post):
        post.side_effect = [
            {"valid": True, "problems": []},
            dict(
                dryRun=True,
                outcome="completed",
                error=None,
                errors=[],
                warnings=[],
                created=[],
                updated=[],
                removed=[],
                unchanged=[],
            ),
        ]
        with patch("sys.argv", ["validate.py", "--preview"]), patch("builtins.print"):
            self.assertEqual(validate.main(), 0)
        validation, preview = post.call_args_list
        self.assertIn(
            "targets-example.yml", [f["path"] for f in validation.args[1]["files"]]
        )
        payload = preview.args[1]
        self.assertIs(payload["dryRun"], True)
        self.assertEqual(payload["datasourceId"], "test-source")
        self.assertNotIn("targets-example.yml", [f["path"] for f in payload["files"]])
        self.assertNotIn("targets.yml.example", [f["path"] for f in payload["files"]])
        self.assertEqual(len(payload["files"]), len(validation.args[1]["files"]) - 1)

    def test_bad_yaml_stops_before_api_calls(self):
        for content in ("module: [", "module: {}\nmodule: {}\n"):
            with tempfile.TemporaryDirectory() as directory:
                (Path(directory) / "bad.yml").write_text(content)
                with self.assertRaises(ValueError):
                    validate.load_files(Path(directory))


if __name__ == "__main__":
    unittest.main()
