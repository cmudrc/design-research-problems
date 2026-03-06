"""Generate Octave-backed parity fixtures for the IoT home cooling evaluator."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GUI_DIR = Path("/Users/work/Desktop/Just-IoT-Things-master/gui")
DEFAULT_DESIGN_DIR = DEFAULT_GUI_DIR / "best_solution"
DEFAULT_OUTPUT = ROOT / "tests" / "fixtures" / "iot_octave_parity.json"

_ADD_PRODUCT = re.compile(
    r"net\.add_product\(([-+0-9.eE]+),\s*([-+0-9.eE]+),\s*'([^']+)',\s*'([dsej])'\);"
)
_SET_BTUS = re.compile(r"net\.product_list\(end\)\.btus\s*=\s*([-+0-9.eE]+);")
_SET_CFM = re.compile(r"net\.product_list\(end\)\.cfm\s*=\s*([-+0-9.eE]+);")
_SET_DM = re.compile(r"net\.product_list\(end\)\.dm\s*=\s*'([^']+)';")
_ADD_LINK = re.compile(r"net\.add_link\('([^']+)',\s*'([^']+)',\s*'([^']+)'\);")
_RESULT = re.compile(r"^RESULT\s+([-+0-9.eE]+)\s+([-+0-9.eE]+)\s+([-+0-9.eE]+)\s+([-+0-9.eE]+)\s*$")


def _parse_design_file(path: Path) -> dict[str, Any]:
    lines = path.read_text(encoding="utf-8").splitlines()
    products: list[dict[str, Any]] = []
    links: list[dict[str, str]] = []

    for line in lines:
        product_match = _ADD_PRODUCT.search(line)
        if product_match is not None:
            x_value = float(product_match.group(1))
            y_value = float(product_match.group(2))
            product_name = product_match.group(3)
            product_type = product_match.group(4)
            products.append(
                {
                    "name": product_name,
                    "type": product_type,
                    "x": x_value,
                    "y": y_value,
                    "btus": 10_000.0,
                    "cfm": 200.0,
                    "dm": None,
                }
            )
            continue

        btus_match = _SET_BTUS.search(line)
        if btus_match is not None and products:
            products[-1]["btus"] = float(btus_match.group(1))
            continue

        cfm_match = _SET_CFM.search(line)
        if cfm_match is not None and products:
            products[-1]["cfm"] = float(cfm_match.group(1))
            continue

        dm_match = _SET_DM.search(line)
        if dm_match is not None and products:
            products[-1]["dm"] = dm_match.group(1)
            continue

        link_match = _ADD_LINK.search(line)
        if link_match is not None:
            links.append(
                {
                    "init_name": link_match.group(1),
                    "term_name": link_match.group(2),
                    "name": link_match.group(3),
                }
            )

    return {
        "design_name": path.stem,
        "products": products,
        "links": links,
    }


def _run_octave_metrics(gui_dir: Path, design_dir: Path, design_name: str) -> dict[str, float]:
    command = (
        f"addpath('{gui_dir.as_posix()}'); "
        f"addpath('{design_dir.as_posix()}'); "
        f"nw={design_name}(); "
        "nw.solve(); "
        "printf('RESULT %.12f %.12f %.12f %.12f\\n', "
        "nw.total_cost, max(nw.h.T(:)), nw.capital_cost, nw.operation_cost);"
    )
    completed = subprocess.run(
        ["octave", "--silent", "--eval", command],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"Octave failed for {design_name}: exit={completed.returncode}\n"
            f"stdout={completed.stdout}\n"
            f"stderr={completed.stderr}"
        )

    for line in completed.stdout.splitlines():
        match = _RESULT.match(line.strip())
        if match is None:
            continue
        return {
            "total_cost": float(match.group(1)),
            "peak_temp_c": float(match.group(2)),
            "capital_cost": float(match.group(3)),
            "operation_cost": float(match.group(4)),
        }

    raise RuntimeError(f"No RESULT line found for {design_name}. Output:\n{completed.stdout}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gui-dir", type=Path, default=DEFAULT_GUI_DIR)
    parser.add_argument("--design-dir", type=Path, default=DEFAULT_DESIGN_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--limit", type=int, default=12)
    args = parser.parse_args()

    design_files = sorted(args.design_dir.glob("*.m"))
    if args.limit > 0:
        design_files = design_files[: args.limit]

    entries: list[dict[str, Any]] = []
    for path in design_files:
        parsed = _parse_design_file(path)
        parsed["octave"] = _run_octave_metrics(args.gui_dir, args.design_dir, parsed["design_name"])
        entries.append(parsed)
        print(f"fixture {parsed['design_name']} done")

    payload = {
        "source_gui_dir": args.gui_dir.as_posix(),
        "source_design_dir": args.design_dir.as_posix(),
        "entry_count": len(entries),
        "entries": entries,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
