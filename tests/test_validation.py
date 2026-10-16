from copy import deepcopy
from io import BytesIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from scripts import validate


class SchemaDownloadTests(unittest.TestCase):
    @patch("scripts.validate.urlopen")
    def test_downloads_and_uses_the_official_schema(self, urlopen):
        schema = {
            "type": "object",
            "properties": {"module": {"type": "object"}},
            "required": ["module"],
        }
        urlopen.return_value = BytesIO(json.dumps(schema).encode())
        validator = validate.download_schema("module")
        urlopen.assert_called_once_with(
            "https://api.steep.app/v1/code/schema/module", timeout=30
        )
        self.assertFalse(validator.is_valid({}))
        self.assertTrue(validator.is_valid({"module": {}}))

    @patch("scripts.validate.urlopen")
    def test_download_failures_stop_validation(self, urlopen):
        for error in (
            URLError("unavailable"),
            TimeoutError(),
            HTTPError("https://api.steep.app", 503, "unavailable", {}, None),
        ):
            with self.subTest(error=type(error).__name__):
                urlopen.side_effect = error
                with self.assertRaisesRegex(ValueError, "validation stopped"):
                    validate.download_schema("module")

    @patch("scripts.validate.urlopen")
    def test_invalid_json_and_schema_stop_validation(self, urlopen):
        for content in (
            b"not json",
            b"{}",
            b"true",
            b'{"type":"object","properties":null}',
            b'{"type":"object","properties":{"module":{"type":"invalid"}}}',
        ):
            with self.subTest(content=content):
                urlopen.return_value = BytesIO(content)
                with self.assertRaisesRegex(ValueError, "validation stopped"):
                    validate.download_schema("module")

    @patch(
        "scripts.validate.schema_validators",
        side_effect=ValueError("schema download failed"),
    )
    @patch("scripts.validate.post")
    def test_cli_fails_without_sending_definitions_when_schema_fetch_fails(
        self, post, schemas
    ):
        with (
            patch("sys.argv", ["validate.py", "--online"]),
            patch("builtins.print") as output,
        ):
            self.assertEqual(validate.main(), 1)
        post.assert_not_called()
        self.assertTrue(
            any("schema download failed" in str(c) for c in output.call_args_list)
        )


class ValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.documents, errors = validate.load_definitions(validate.ROOT)
        if errors:
            raise AssertionError(errors)

    def setUp(self):
        self.docs = deepcopy(self.documents)

    def module(self, name):
        return self.docs[f"{name}.yml"]["module"]

    def metric(self, name):
        return next(
            m
            for d in self.docs.values()
            for m in d.get("module", {}).get("metrics", [])
            if m["identifier"] == name
        )

    def assert_invalid(self, text):
        errors = validate.validate_documents(self.docs)
        self.assertTrue(any(text in e for e in errors), errors)

    def test_current_model_and_legacy_calculation_alias_pass(self):
        self.assertEqual(validate.validate_documents(self.docs), [])

    def test_unknown_field_and_invalid_enum_fail_official_schema(self):
        for field, value in (("typo", True), ("type", "not-a-type")):
            with self.subTest(field=field):
                self.docs = deepcopy(self.documents)
                self.metric("page_views")[field] = value
                self.assert_invalid("not valid under any of the given schemas")

    def test_required_field(self):
        del self.module("dim_jobs")["table"]
        self.assert_invalid("required property")

    def test_malformed_metrics_container_reports_schema_error(self):
        self.module("fct_web_events")["metrics"] = None
        self.assert_invalid("not of type 'array'")

    def test_duplicate_identifiers(self):
        for kind in ("module", "metric", "entity", "dimension", "slice"):
            with self.subTest(kind=kind):
                self.docs = deepcopy(self.documents)
                if kind == "module":
                    self.docs["duplicate.yml"] = deepcopy(self.docs["dim_jobs.yml"])
                elif kind == "metric":
                    self.module("fct_web_events")["metrics"].append(
                        deepcopy(self.metric("page_views"))
                    )
                elif kind == "entity":
                    self.module("dim_jobs")["entities"].append(
                        deepcopy(self.module("dim_jobs")["entities"][0])
                    )
                elif kind == "dimension":
                    self.module("dim_jobs")["dimensions"].append(
                        deepcopy(self.module("dim_jobs")["dimensions"][0])
                    )
                else:
                    slices = self.metric("email_events")["slices"]
                    slices.append(deepcopy(slices[0]))
                self.assert_invalid("duplicate")

    def test_source_dataset_contracts(self):
        for name, schema, expected in (
            ("fct_email_events", "marts", "dbt_prd"),
            ("fct_events", "dbt_prd", "marts"),
        ):
            with self.subTest(name=name):
                self.docs = deepcopy(self.documents)
                self.module(name)["schema"] = schema
                self.assert_invalid(f"must use {expected}")

    def test_targets_example_is_checked(self):
        self.docs["targets.yml.example"]["targets"]["schema"] = "marts"
        self.assert_invalid("targets must use dbt_prd")

    def test_invalid_target_structure(self):
        del self.docs["targets.yml.example"]["targets"]["table"]
        self.assert_invalid("required property")

    def test_duplicate_table(self):
        module = self.module("dim_pages")
        module["table"] = "dim_jobs"
        self.assert_invalid("duplicate module table")

    def test_module_roles(self):
        self.module("dim_jobs")["metrics"] = [deepcopy(self.metric("page_views"))]
        self.assert_invalid("dimension modules must not define metrics")
        self.module("fct_web_events")["entities"] = deepcopy(
            self.module("dim_jobs")["entities"]
        )
        self.assert_invalid("fact modules must not define entities")

    def test_missing_join_target(self):
        self.module("dim_jobs")["joinPaths"][0]["to"]["table"] = "missing"
        self.assert_invalid("unknown table or schema")

    def test_duplicate_join(self):
        joins = self.module("dim_jobs")["joinPaths"]
        joins.append(deepcopy(joins[0]))
        self.assert_invalid("duplicate join path")

    def test_fact_side_join_is_rejected(self):
        self.module("fct_web_events")["joinPaths"] = [
            {
                "from": {"column": "job_id"},
                "to": {"table": "dim_jobs", "column": "job_id"},
                "type": "one-to-one",
            }
        ]
        self.assert_invalid("declare joins on the dimension side")

    def test_broken_dimension_and_schema_references(self):
        for ref, expected in (
            ("dbt_prd.dim_jobs.missing", "undeclared dimension"),
            ("marts.dim_jobs.*", "unknown table or schema"),
            ("bad.reference.with.extra.parts", "invalid reference"),
        ):
            with self.subTest(ref=ref):
                self.docs = deepcopy(self.documents)
                self.metric("page_views")["dimensions"] = [ref]
                self.assert_invalid(expected)

    def test_join_is_bidirectional_and_two_hops_are_supported(self):
        self.metric("page_views")["dimensions"] = [
            "dbt_prd.dim_jobs.title",
            "this.page_path",
        ]
        self.metric("link_clicks")["dimensions"] = [
            "dbt_prd.dim_email_campaigns.campaign_name"
        ]
        self.assertEqual(validate.validate_documents(self.docs), [])

    def test_three_hop_dimension_is_rejected(self):
        # web events -> jobs -> email events -> email messages is three joins.
        self.metric("page_views")["dimensions"] = ["dbt_prd.dim_email_messages.subject"]
        self.assert_invalid("not reachable within two joins")

    def test_cohort_property_without_declared_time_dimension(self):
        self.module("dim_email_subscribers")["dimensions"] = []
        self.assert_invalid("cohort requires a declared time dimension")

    def test_cohort_categorical_dimension(self):
        self.module("dim_email_subscribers")["dimensions"][0]["type"] = "categorical"
        self.assert_invalid("cohort requires a declared time dimension")

    def test_broken_derived_operand(self):
        self.metric("apply_click_rate")["numerator"] = "missing"
        self.assert_invalid("unknown numerator metric")

    def test_operand_slice(self):
        self.metric("apply_click_rate")["numerator"] = {
            "metric": "email_events",
            "slice": "missing",
        }
        self.assert_invalid("unknown operand slice")

    def test_derived_cycle(self):
        self.metric("apply_click_rate")["numerator"] = "apply_click_rate"
        self.assert_invalid("cyclic derived metric reference")

    def test_derived_ratio_of_snapshot_operands_regression(self):
        metric = self.metric("listed_job_salary_coverage")
        for key in ("time", "time_aggregation", "numerator_sql", "denominator_sql"):
            del metric[key]
        metric.update(
            type="derived-ratio",
            numerator="listed_jobs_with_salary",
            denominator="listed_jobs",
        )
        self.assert_invalid("derived-ratio cannot use last-date operands")

    def test_derived_dimension_must_be_reachable_from_operands(self):
        self.metric("apply_click_rate")["numerator"] = "email_subscribers"
        self.assert_invalid("operand cannot reach dimension")

    def test_entity_metric_references(self):
        for name, expected in (
            ("missing", "unknown entity metric"),
            ("email_subscribers", "not reachable within two joins"),
        ):
            with self.subTest(name=name):
                self.docs = deepcopy(self.documents)
                self.module("dim_jobs")["entities"][0]["metrics"] = [name]
                self.assert_invalid(expected)

    def test_raw_time_and_filter_tables_must_resolve(self):
        self.metric("page_views")["time"] = "missing.time"
        self.metric("email_subscribers")["filters"][0]["schema"] = "marts"
        self.assert_invalid("unknown table or schema")

    def test_malformed_and_duplicate_key_yaml(self):
        for content in ("module: [", "module: {}\nmodule: {}\n"):
            with (
                self.subTest(content=content),
                tempfile.TemporaryDirectory() as directory,
            ):
                root = Path(directory)
                (root / "invalid.yml").write_text(content)
                _, errors = validate.load_definitions(root)
                self.assertTrue(errors)

    def test_payload_includes_complete_model_but_excludes_example_and_workflows(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "a.yml").write_text("module: {}\n")
            (root / "b.yaml").write_text("module: {}\n")
            (root / "targets.yml.example").write_text("targets: {}\n")
            (root / ".github").mkdir()
            (root / ".github" / "ci.yml").write_text("jobs: {}\n")
            self.assertEqual(
                [f["path"] for f in validate.file_payload(root)], ["a.yml", "b.yaml"]
            )

    def test_empty_payload_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "No active"):
                validate.file_payload(Path(directory))


class RemoteTests(unittest.TestCase):
    def test_public_validation_fails_closed(self):
        validate.check_remote({"valid": True, "problems": []})
        for result in (
            {},
            [],
            {"valid": False, "problems": []},
            {"valid": True, "problems": [{"severity": "warning"}]},
        ):
            with self.subTest(result=result), self.assertRaises(ValueError):
                validate.check_remote(result)

    def test_preview_fails_on_errors_warnings_or_missing_confirmation(self):
        good = {
            "dryRun": True,
            "type": "Steep as Code",
            "outcome": "completed",
            "error": None,
            "errors": [],
            "warnings": [],
            "created": [],
            "updated": [],
            "removed": [],
            "unchanged": [],
        }
        validate.check_remote(good, preview=True)
        for changes in (
            {"dryRun": False},
            {"type": "Cube"},
            {"outcome": "queued"},
            {"error": "failed"},
            {"errors": ["error"]},
            {"warnings": ["warning"]},
            {"warnings": None},
            {"errors": None},
            {"removed": None},
            {"created": [{}]},
        ):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                validate.check_remote(good | changes, preview=True)

    @patch.dict(
        "os.environ",
        {
            "STEEP_API_KEY": "test-only-key",
            "STEEP_DATASOURCE_ID": "test-only-datasource",
        },
    )
    @patch("scripts.validate.post")
    def test_preview_always_sends_dry_run_and_all_active_files(self, post):
        post.return_value = {
            "dryRun": True,
            "type": "Steep as Code",
            "outcome": "completed",
            "error": None,
            "errors": [],
            "warnings": [],
            "created": [],
            "updated": [],
            "removed": [],
            "unchanged": [],
        }
        with patch("sys.argv", ["validate.py", "--preview"]), patch("builtins.print"):
            self.assertEqual(validate.main(), 0)
        path, payload, token = post.call_args.args
        self.assertEqual(path, "code/syncs")
        self.assertIs(payload["dryRun"], True)
        self.assertEqual(payload["datasourceId"], "test-only-datasource")
        self.assertEqual(token, "test-only-key")
        self.assertEqual(
            len(payload["files"]), len(validate.definition_paths(validate.ROOT))
        )
        self.assertNotIn("targets.yml.example", [f["path"] for f in payload["files"]])

    @patch.dict("os.environ", {}, clear=True)
    @patch("scripts.validate.post")
    def test_missing_preview_credentials_does_not_send(self, post):
        with patch("sys.argv", ["validate.py", "--preview"]), patch("builtins.print"):
            self.assertEqual(validate.main(), 1)
        post.assert_not_called()


if __name__ == "__main__":
    unittest.main()
