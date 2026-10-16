"""Validate Steep YAML through Steep's API and a few AEJ-specific safeguards."""

import argparse
import json
import os
from pathlib import Path
import sys
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import yaml
from yamllint.config import YamlLintConfig
from yamllint.linter import run as lint

ROOT = Path(__file__).resolve().parents[1]
API = "https://api.steep.app/v1"


def load_files(root):
    paths = sorted([*root.glob("*.yml"), *root.glob("*.yaml")])
    if not paths:
        raise ValueError("No active Steep definitions found")
    paths.append(root / "targets.yml.example")
    files, documents = [], []
    config = YamlLintConfig(file=ROOT / ".yamllint")
    for path in paths:
        content = path.read_text()
        problems = list(lint(content, config))
        if problems:
            raise ValueError(f"{path.name}: " + "; ".join(map(str, problems)))
        documents.append(yaml.safe_load(content))
        files.append({"path": path.name, "content": content})
    return files, documents


def validation_files(files):
    # The API requires .yml/.yaml paths. Renaming the example here only validates it;
    # it never registers a target table or includes it in a sync preview.
    return [
        dict(f, path="targets-example.yml") if f["path"] == "targets.yml.example" else f
        for f in files
    ]


def repository_errors(documents):
    """Run after Steep has accepted the structure; do not rebuild its validator."""
    modules = [d["module"] for d in documents if "module" in d]
    tables = {m["table"]: m["schema"] for m in modules}
    metrics = {
        metric["identifier"]: metric for m in modules for metric in m.get("metrics", [])
    }
    errors = []
    for document in documents:
        if "targets" in document and document["targets"]["schema"] != "dbt_prd":
            errors.append("Targets must use dbt_prd")
    for module in modules:
        name = module["identifier"]
        expected = "marts" if name == "fct_events" else "dbt_prd"
        if module["schema"] != expected:
            errors.append(f"{name}: must use {expected}")
        if name.startswith("dim_") and module.get("metrics"):
            errors.append(f"{name}: metrics belong on facts")
        if name.startswith("fct_") and (
            module.get("entities") or module.get("joinPaths")
        ):
            errors.append(f"{name}: entities and joins belong on dimensions")
        for join in module.get("joinPaths", []):
            target = join["to"]
            if tables.get(target["table"]) != target.get("schema", module["schema"]):
                errors.append(f"{name}: unknown join target {target['table']}")
        for entity in module.get("entities", []):
            for reference in entity.get("metrics", []):
                if reference not in metrics:
                    errors.append(f"{name}: unknown entity metric {reference}")
        for metric in module.get("metrics", []):
            references = metric.get("dimensions", []) + [
                metric.get("cohort", {}).get("time_dimension", "")
            ]
            for reference in references:
                parts = reference.split(".")
                if len(parts) == 3 and tables.get(parts[1]) != parts[0]:
                    errors.append(
                        f"{metric['identifier']}: unknown table/schema in {reference}"
                    )
            if metric.get("type") != "derived-ratio":
                continue
            for field in ("numerator", "denominator"):
                reference = metric[field]
                identifier = (
                    reference["metric"] if isinstance(reference, dict) else reference
                )
                operand = metrics.get(identifier)
                if operand is None:
                    errors.append(
                        f"{metric['identifier']}: unknown operand {identifier}"
                    )
                elif operand.get("time_aggregation") == "last-date":
                    errors.append(
                        f"{metric['identifier']}: last-date operands require a custom-ratio"
                    )
                elif isinstance(reference, dict) and "slice" in reference:
                    slices = {
                        s.get("identifier", s["name"])
                        for s in operand.get("slices", [])
                    }
                    if reference["slice"] not in slices:
                        errors.append(
                            f"{metric['identifier']}: unknown operand slice {reference['slice']}"
                        )
    return errors


def post(path, payload, token=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(
        f"{API}/{path}", data=json.dumps(payload).encode(), headers=headers
    )
    try:
        with urlopen(request, timeout=60) as response:
            return json.load(response)
    except HTTPError as exc:
        raise ValueError(f"Steep {path} returned HTTP {exc.code}") from None
    except (OSError, ValueError) as exc:
        raise ValueError(
            f"Steep {path} request failed ({type(exc).__name__})"
        ) from None


def check_response(result, preview=False):
    if not isinstance(result, dict):
        raise ValueError("Malformed Steep response")
    if preview:
        if result.get("dryRun") is not True or result.get("outcome") != "completed":
            raise ValueError("Steep did not confirm a completed dry-run preview")
        for key in ("errors", "warnings", "created", "updated", "removed", "unchanged"):
            if not isinstance(result.get(key), list):
                raise ValueError(f"Malformed Steep preview: {key}")
        if (
            "error" not in result
            or result["error"]
            or result["errors"]
            or result["warnings"]
        ):
            raise ValueError("Steep preview reported errors or warnings")
    elif result.get("valid") is not True or result.get("problems") != []:
        raise ValueError("Steep validation failed or reported problems")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--preview", action="store_true", help="Also preview a sync; never apply it"
    )
    args = parser.parse_args()
    try:
        files, documents = load_files(ROOT)
        result = post("code/validate", {"files": validation_files(files)})
        print(json.dumps(result, indent=2))
        check_response(result)
        errors = repository_errors(documents)
        if errors:
            raise ValueError("\n".join(errors))
        print(
            f"Validated {len(files)} definitions, including the documentation-only targets example."
        )
        if args.preview:
            token, datasource = (
                os.environ.get("STEEP_API_KEY"),
                os.environ.get("STEEP_DATASOURCE_ID"),
            )
            if not token or not datasource:
                raise ValueError(
                    "Preview requires STEEP_API_KEY and STEEP_DATASOURCE_ID"
                )
            active = [f for f in files if f["path"] != "targets.yml.example"]
            result = post(
                "code/syncs",
                {"datasourceId": datasource, "dryRun": True, "files": active},
                token,
            )
            print(json.dumps(result, indent=2))
            check_response(result, preview=True)
    except (OSError, ValueError, yaml.YAMLError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
