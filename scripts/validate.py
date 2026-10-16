"""Validate the complete local Steep model; remote operations never apply a sync."""

import argparse
from collections import defaultdict
from copy import deepcopy
import json
import os
from pathlib import Path
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from jsonschema import Draft202012Validator
import yaml
from yamllint.config import YamlLintConfig
from yamllint.linter import run as lint

ROOT = Path(__file__).resolve().parents[1]
API = "https://api.steep.app/v1"


def definition_paths(root):
    # Definitions live at the root; workflows and regression fixtures are not models.
    return sorted([*root.glob("*.yml"), *root.glob("*.yaml")])


def file_payload(root):
    paths = definition_paths(root)
    if not paths:
        raise ValueError("No active Steep definitions found")
    return [{"path": p.name, "content": p.read_text()} for p in paths]


def load_definitions(root):
    documents, errors = {}, []
    config = YamlLintConfig(file=ROOT / ".yamllint")
    paths = definition_paths(root)
    if (root / "targets.yml.example").exists():
        paths.append(root / "targets.yml.example")
    if not paths:
        errors.append("No Steep definitions found")
    for path in paths:
        content = path.read_text()
        for problem in lint(content, config):
            errors.append(
                f"{path.name}:{problem.line}:{problem.column}: {problem.message}"
            )
        try:
            documents[path.name] = yaml.safe_load(content)
        except yaml.YAMLError as exc:
            errors.append(f"{path.name}: invalid YAML: {exc}")
    return documents, errors


def validate_documents(documents):
    errors = []
    modules, tables, metrics, entities = {}, {}, {}, set()
    graph = defaultdict(set)
    schemas = {
        kind: Draft202012Validator(
            json.loads((ROOT / "schemas" / f"{kind}.json").read_text())
        )
        for kind in ("module", "targets")
    }

    def fail(context, message):
        errors.append(f"{context}: {message}")

    for path, document in documents.items():
        kind = (
            "targets"
            if isinstance(document, dict) and "targets" in document
            else "module"
        )
        normalized = deepcopy(document)
        # Steep still accepts calculation as a deprecated alias (legacy fct_events).
        if (
            isinstance(normalized, dict)
            and isinstance(normalized.get("module"), dict)
            and isinstance(normalized["module"].get("metrics", []), list)
        ):
            for metric in normalized["module"].get("metrics", []):
                if (
                    isinstance(metric, dict)
                    and "type" not in metric
                    and "calculation" in metric
                ):
                    metric["type"] = metric["calculation"]
        problems = list(schemas[kind].iter_errors(normalized))
        for problem in problems:
            location = ".".join(map(str, problem.absolute_path)) or "root"
            fail(f"{path}:{location}", problem.message)
        if problems:
            continue
        if kind == "targets":
            if document["targets"]["schema"] != "dbt_prd":
                fail(path, "targets must use dbt_prd")
            continue
        module = document["module"]
        identifier = module["identifier"]
        if identifier in modules:
            fail(path, f"duplicate module identifier {identifier}")
        modules[identifier] = module
        key = (module["schema"], module["table"])
        if key in tables:
            fail(path, f"duplicate module table {key}")
        tables[key] = identifier
        expected_schema = "marts" if identifier == "fct_events" else "dbt_prd"
        if module["schema"] != expected_schema:
            fail(path, f"{identifier} must use {expected_schema}")
        if identifier.startswith("dim_") and module.get("metrics"):
            fail(path, "dimension modules must not define metrics")
        if identifier.startswith("fct_") and module.get("entities"):
            fail(path, "fact modules must not define entities")
        columns = [d["column"] for d in module.get("dimensions", [])]
        dimension_ids = [
            d.get("identifier", d["column"]) for d in module.get("dimensions", [])
        ]
        if len(set(columns)) != len(columns) or len(set(dimension_ids)) != len(
            dimension_ids
        ):
            fail(path, "duplicate dimension column or identifier")
        for metric in module.get("metrics", []):
            name = metric["identifier"]
            if name in metrics:
                fail(path, f"duplicate metric identifier {name}")
            metrics[name] = (identifier, metric)
            slices = [s.get("identifier", s["name"]) for s in metric.get("slices", [])]
            if len(set(slices)) != len(slices):
                fail(name, "duplicate slice identifier")
        for entity in module.get("entities", []):
            if entity["identifier"] in entities:
                fail(path, f"duplicate entity identifier {entity['identifier']}")
            entities.add(entity["identifier"])

    def resolve(source, reference, context):
        parts = reference.split(".")
        schema = modules[source]["schema"]
        if len(parts) == 1:
            return source, parts[0]
        if len(parts) == 2:
            table, column = parts
            if table == "this":
                return source, column
        elif len(parts) == 3:
            schema, table, column = parts
        else:
            fail(context, f"invalid reference {reference}")
            return None, None
        target = tables.get((schema, table))
        if target is None:
            fail(context, f"unknown table or schema in {reference}")
        return target, column

    joins = set()
    for source, module in modules.items():
        for join in module.get("joinPaths", []):
            to = join["to"]
            target, _ = resolve(
                source,
                f"{to.get('schema', module['schema'])}.{to['table']}.{to['column']}",
                source,
            )
            if target is None:
                continue
            edge = frozenset(((source, join["from"]["column"]), (target, to["column"])))
            if edge in joins:
                fail(source, "duplicate join path")
            joins.add(edge)
            if source.startswith("fct_"):
                fail(source, "declare joins on the dimension side")
            graph[source].add(target)
            graph[target].add(source)

    def reachable(source, target):
        return target in {
            source,
            *graph[source],
            *(n for x in graph[source] for n in graph[x]),
        }

    def check_reference(source, reference, context, dimension=False, time=False):
        target, column = resolve(source, reference, context)
        if target is None:
            return
        if not reachable(source, target):
            fail(context, f"{reference} is not reachable within two joins")
        dimensions = {d["column"]: d for d in modules[target].get("dimensions", [])}
        if dimension and column != "*" and column not in dimensions:
            fail(context, f"undeclared dimension {reference}")
        if time and dimensions.get(column, {}).get("type") != "time":
            fail(context, f"cohort requires a declared time dimension: {reference}")

    dependencies = defaultdict(set)
    for name, (source, metric) in metrics.items():
        for reference in metric.get("dimensions", []):
            check_reference(source, reference, name, dimension=True)
        for field in ("time", "value", "distinct_on"):
            if field in metric:
                check_reference(source, metric[field], name)
        if metric.get("cohort"):
            check_reference(
                source,
                metric["cohort"]["time_dimension"],
                name,
                dimension=True,
                time=True,
            )
        filters = list(metric.get("filters", [])) + [
            s["filter"] for s in metric.get("slices", [])
        ]
        for item in filters:
            reference = f"{item.get('schema', modules[source]['schema'])}.{item.get('table', modules[source]['table'])}.{item['column']}"
            check_reference(source, reference, name)
        if metric.get("type", metric.get("calculation")) == "derived-ratio":
            for field in ("numerator", "denominator"):
                operand = metric[field]
                operand_name = (
                    operand["metric"] if isinstance(operand, dict) else operand
                )
                if operand_name not in metrics:
                    fail(name, f"unknown {field} metric {operand_name}")
                    continue
                dependencies[name].add(operand_name)
                operand_metric = metrics[operand_name][1]
                if operand_metric.get("time_aggregation") == "last-date":
                    fail(
                        name,
                        "derived-ratio cannot use last-date operands; use a custom-ratio",
                    )
                if isinstance(operand, dict) and "slice" in operand:
                    slices = {
                        s.get("identifier", s["name"])
                        for s in operand_metric.get("slices", [])
                    }
                    if operand["slice"] not in slices:
                        fail(name, f"unknown operand slice {operand['slice']}")

    def metric_sources(name, visiting=None):
        visiting = set() if visiting is None else visiting
        if name in visiting:
            fail(name, "cyclic derived metric reference")
            return set()
        if not dependencies[name]:
            return {metrics[name][0]}
        return set().union(
            *(metric_sources(n, visiting | {name}) for n in dependencies[name])
        )

    for name in metrics:
        sources = metric_sources(name)
        # A derived metric's dimensions must be usable for each operand's fact.
        for source in sources:
            for reference in metrics[name][1].get("dimensions", []):
                target, _ = resolve(metrics[name][0], reference, name)
                if target and not reachable(source, target):
                    fail(
                        name,
                        f"operand cannot reach dimension {reference} within two joins",
                    )
    for source, module in modules.items():
        for entity in module.get("entities", []):
            for name in entity.get("metrics", []):
                if name not in metrics:
                    fail(entity["identifier"], f"unknown entity metric {name}")
                elif any(
                    not reachable(source, target) for target in metric_sources(name)
                ):
                    fail(
                        entity["identifier"],
                        f"entity metric {name} is not reachable within two joins",
                    )
    return errors


def post(path, payload, token=None):
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(
        f"{API}/{path}",
        data=json.dumps(payload).encode(),
        headers=headers,
        method="POST",
    )
    try:
        with urlopen(request, timeout=60) as response:
            return json.load(response)
    except HTTPError as exc:
        # Do not dump headers or arbitrary error bodies from an authenticated request.
        raise ValueError(f"Steep {path} returned HTTP {exc.code}") from None
    except (URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise ValueError(
            f"Steep {path} request failed ({type(exc).__name__})"
        ) from None


def check_remote(result, preview=False):
    if not isinstance(result, dict):
        raise ValueError("Malformed Steep response")
    if preview:
        if result.get("dryRun") is not True or result.get("type") != "Steep as Code":
            raise ValueError("Steep did not confirm a Steep as Code dry run")
        if "error" not in result:
            raise ValueError("Malformed preview error field")
        for field in (
            "created",
            "updated",
            "removed",
            "unchanged",
            "errors",
            "warnings",
        ):
            values = result.get(field)
            if not isinstance(values, list) or any(
                not isinstance(v, str) for v in values
            ):
                raise ValueError(f"Malformed preview {field}")
        if (
            result.get("outcome") != "completed"
            or result.get("error")
            or result.get("errors")
        ):
            raise ValueError("Steep preview failed; inspect the preview output")
        if result["warnings"]:
            raise ValueError(
                "Steep preview returned warnings; inspect the preview output"
            )
    else:
        if result.get("valid") is not True or not isinstance(
            result.get("problems"), list
        ):
            raise ValueError("Steep validation failed or returned a malformed response")
        if result["problems"]:
            raise ValueError("Steep validation returned problems, including warnings")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--online",
        action="store_true",
        help="Also call Steep's credential-free validator",
    )
    parser.add_argument(
        "--preview",
        action="store_true",
        help="Preview the complete model in Steep; never apply",
    )
    parser.add_argument(
        "--datasource-id", default=os.environ.get("STEEP_DATASOURCE_ID")
    )
    args = parser.parse_args()
    documents, errors = load_definitions(ROOT)
    errors.extend(validate_documents(documents))
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print(
        f"Local validation passed ({len(documents)} definitions, including the targets example)."
    )
    try:
        if args.online:
            result = post("code/validate", {"files": file_payload(ROOT)})
            print(json.dumps(result, indent=2))
            check_remote(result)
        if args.preview:
            token = os.environ.get("STEEP_API_KEY")
            if not token or not args.datasource_id:
                raise ValueError(
                    "Preview requires STEEP_API_KEY and STEEP_DATASOURCE_ID (or --datasource-id)"
                )
            result = post(
                "code/syncs",
                {
                    "datasourceId": args.datasource_id,
                    "dryRun": True,
                    "files": file_payload(ROOT),
                },
                token,
            )
            print(json.dumps(result, indent=2))
            check_remote(result, preview=True)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
