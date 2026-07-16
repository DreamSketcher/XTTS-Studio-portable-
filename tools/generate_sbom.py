"""Generate a deterministic CycloneDX 1.5 SBOM from pinned requirements."""

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PIN_RE = re.compile(r"^([A-Za-z0-9_.-]+)==([^\s;]+)")


def normalized_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def load_components(requirements: Path) -> list[dict]:
    components = []
    for raw in requirements.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        match = PIN_RE.match(line)
        if not match:
            raise ValueError(f"Unpinned or unsupported requirement: {line}")
        name, version = match.groups()
        canonical = normalized_name(name)
        components.append(
            {
                "type": "library",
                "bom-ref": f"pkg:pypi/{canonical}@{version}",
                "name": name,
                "version": version,
                "purl": f"pkg:pypi/{canonical}@{version}",
            }
        )
    return sorted(components, key=lambda item: item["purl"])


def generate(requirements: Path, output: Path):
    components = load_components(requirements)
    document = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "serialNumber": "urn:uuid:00000000-0000-0000-0000-000000000000",
        "version": 1,
        "metadata": {
            "component": {
                "type": "application",
                "name": "XTTS Studio",
                "bom-ref": "pkg:github/DreamSketcher/XTTS-Studio",
            },
            "tools": {"components": [{"type": "application", "name": "tools/generate_sbom.py"}]},
        },
        "components": components,
        "dependencies": [
            {
                "ref": "pkg:github/DreamSketcher/XTTS-Studio",
                "dependsOn": [item["bom-ref"] for item in components],
            }
        ],
    }
    output.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--requirements", type=Path, default=ROOT / "requirements.txt")
    parser.add_argument("--output", type=Path, default=ROOT / "json" / "sbom.cdx.json")
    args = parser.parse_args()
    generate(args.requirements, args.output)


if __name__ == "__main__":
    main()
