from copy import deepcopy
from io import BytesIO
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import URLError

from scripts import validate


class ContractTests(unittest.TestCase):
    def setUp(self):
        _, self.docs = validate.load_files(validate.ROOT)
        self.modules = {
            d["module"]["identifier"]: d["module"] for d in self.docs if "module" in d
        }
        self.metrics = {
            m["identifier"]: m
            for module in self.modules.values()
            for m in module.get("metrics", [])
        }

    def test_current_contracts_pass(self):
        self.assertEqual(validate.repository_errors(self.docs), [])

    def test_datasets_and_targets_regressions(self):
        self.modules["fct_email_events"]["schema"] = "marts"
        self.modules["fct_events"]["schema"] = "dbt_prd"
        self.docs[-1]["targets"]["schema"] = "marts"
        errors = "\n".join(validate.repository_errors(self.docs))
        for expected in (
            "fct_email_events: must use dbt_prd",
            "fct_events: must use marts",
            "Targets must use dbt_prd",
        ):
            self.assertIn(expected, errors)

    def test_missing_operands_and_snapshot_ratio_regressions(self):
        self.metrics["apply_click_rate"]["numerator"] = "missing"
        self.metrics["apply_click_rate"]["denominator"] = "listed_jobs"
        errors = "\n".join(validate.repository_errors(self.docs))
        self.assertIn("unknown operand missing", errors)
        self.assertIn("last-date operands require a custom-ratio", errors)

    def test_operand_slice_reference(self):
        self.metrics["apply_click_rate"]["numerator"] = {
            "metric": "email_events",
            "slice": "missing",
        }
        self.assertIn(
            "unknown operand slice", "\n".join(validate.repository_errors(self.docs))
        )

    def test_join_entity_and_qualified_schema_references(self):
        self.modules["dim_jobs"]["joinPaths"][0]["to"]["table"] = "missing"
        self.modules["dim_jobs"]["entities"][0]["metrics"] = ["missing"]
        self.metrics["page_views"]["dimensions"] = ["marts.dim_jobs.*"]
        errors = "\n".join(validate.repository_errors(self.docs))
        for expected in (
            "unknown join target",
            "unknown entity metric",
            "unknown table/schema",
        ):
            self.assertIn(expected, errors)

    def test_module_roles(self):
        self.modules["dim_jobs"]["metrics"] = [deepcopy(self.metrics["page_views"])]
        self.modules["fct_web_events"]["entities"] = self.modules["dim_jobs"][
            "entities"
        ]
        errors = "\n".join(validate.repository_errors(self.docs))
        self.assertIn("metrics belong on facts", errors)
        self.assertIn("entities and joins belong on dimensions", errors)


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

    @patch("scripts.validate.urlopen")
    def test_network_and_invalid_json_fail_clearly(self, urlopen):
        urlopen.side_effect = URLError("unavailable")
        with self.assertRaisesRegex(ValueError, "request failed"):
            validate.post("code/validate", {})
        urlopen.side_effect = None
        urlopen.return_value = BytesIO(b"not json")
        with self.assertRaisesRegex(ValueError, "request failed"):
            validate.post("code/validate", {})

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

    @patch.dict("os.environ", {}, clear=True)
    @patch("scripts.validate.post", return_value={"valid": True, "problems": []})
    def test_missing_credentials_never_call_sync(self, post):
        with patch("sys.argv", ["validate.py", "--preview"]), patch("builtins.print"):
            self.assertEqual(validate.main(), 1)
        self.assertEqual(post.call_count, 1)
        self.assertEqual(post.call_args.args[0], "code/validate")

    def test_bad_yaml_stops_before_api_calls(self):
        for content in ("module: [", "module: {}\nmodule: {}\n"):
            with tempfile.TemporaryDirectory() as directory:
                (Path(directory) / "bad.yml").write_text(content)
                with self.assertRaises(ValueError):
                    validate.load_files(Path(directory))


if __name__ == "__main__":
    unittest.main()
