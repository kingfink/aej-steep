"""Validate Steep YAML through Steep's API; previews never apply changes."""

import argparse
import json
import os
from pathlib import Path
import sys
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from yamllint.config import YamlLintConfig
from yamllint.linter import run as lint

ROOT = Path(__file__).resolve().parents[1]
API = "https://api.steep.app/v1"


def load_files(root):
    paths = sorted([*root.glob("*.yml"), *root.glob("*.yaml")])
    if not paths:
        raise ValueError("No active Steep definitions found")
    paths.append(root / "targets.yml.example")
    files = []
    config = YamlLintConfig(file=ROOT / ".yamllint")
    for path in paths:
        content = path.read_text()
        problems = list(lint(content, config))
        if problems:
            raise ValueError(f"{path.name}: " + "; ".join(map(str, problems)))
        files.append({"path": path.name, "content": content})
    return files


def validation_files(files):
    # The API requires .yml/.yaml paths. Renaming the example here only validates it;
    # it never registers a target table or includes it in a sync preview.
    return [
        dict(f, path="targets-example.yml") if f["path"] == "targets.yml.example" else f
        for f in files
    ]


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
        files = load_files(ROOT)
        result = post("code/validate", {"files": validation_files(files)})
        print(json.dumps(result, indent=2))
        check_response(result)
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
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
