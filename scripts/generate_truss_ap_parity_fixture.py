"""Generate parity fixtures from MATLAB Truss Analysis Program `.mat` trajectories."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy
import scipy.io

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_DIR = Path("/tmp/trussprogram_extracted_2/TrussProgram/example_data")
DEFAULT_OUTPUT = ROOT / "tests" / "fixtures" / "truss_ap_matlab_parity.json"
DEFAULT_SUPPORT_ENABLED = (True, True, True)

_SLOT_TO_DIRECTION = {
    1: "left",
    2: "down",
    3: "right",
    4: "up",
}


def _scalar(value: Any) -> float:
    array = numpy.asarray(value)
    return float(array.reshape(-1)[0])


def _round_key(x_value: float, y_value: float) -> tuple[float, float]:
    return (round(x_value, 9), round(y_value, 9))


def _parse_file(path: Path) -> dict[str, Any]:
    mat = scipy.io.loadmat(path)

    node_info = mat["node_info"]
    nodes: list[dict[str, Any]] = []
    joint_id_by_key: dict[tuple[float, float], int] = {}
    for index in range(node_info.shape[1]):
        entry = node_info[0, index]
        x_value = _scalar(entry["x"])
        y_value = _scalar(entry["y"])
        joint_id = index + 1
        node = {
            "joint_id": joint_id,
            "x": x_value,
            "y": y_value,
            "is_fixed": joint_id <= 5,
            "loads": {
                "left": _scalar(entry["LOAD1"]),
                "down": _scalar(entry["LOAD2"]),
                "right": _scalar(entry["LOAD3"]),
                "up": _scalar(entry["LOAD4"]),
            },
        }
        nodes.append(node)
        joint_id_by_key[_round_key(x_value, y_value)] = joint_id

    member_info = mat["member_info"]
    members: list[dict[str, Any]] = []
    for index in range(member_info.shape[1]):
        entry = member_info[0, index]
        x_values = numpy.asarray(entry["x"]).reshape(-1)
        y_values = numpy.asarray(entry["y"]).reshape(-1)
        start_joint_id = joint_id_by_key[_round_key(float(x_values[0]), float(y_values[0]))]
        end_joint_id = joint_id_by_key[_round_key(float(x_values[1]), float(y_values[1]))]
        linewidth = _scalar(entry["LW"])
        members.append(
            {
                "member_id": index + 1,
                "start_joint_id": start_joint_id,
                "end_joint_id": end_joint_id,
                "size_index": round(linewidth / 2.0),
                "linewidth": linewidth,
            }
        )

    loads: list[dict[str, Any]] = []
    for node in nodes:
        for _slot_index, direction in _SLOT_TO_DIRECTION.items():
            magnitude = node["loads"][direction]
            if magnitude == -1.0:
                continue
            loads.append(
                {
                    "joint_id": node["joint_id"],
                    "direction": direction,
                    "magnitude_n": magnitude,
                }
            )

    fos_values = numpy.asarray(mat.get("FOS", numpy.asarray([0.0]))).reshape(-1).astype(float)
    expected_min_fos = float(numpy.min(fos_values)) if fos_values.size > 0 else 0.0

    return {
        "design_name": path.stem,
        "state": {
            "joints": [{k: node[k] for k in ("joint_id", "x", "y", "is_fixed")} for node in nodes],
            "members": members,
            "loads": loads,
            "support_enabled": list(DEFAULT_SUPPORT_ENABLED),
        },
        "expected": {
            "mass_kg": _scalar(mat.get("mass", numpy.asarray([[0.0]]))),
            "min_fos": expected_min_fos,
            "joint_count": len(nodes),
            "member_count": len(members),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--limit", type=int, default=24)
    args = parser.parse_args()

    files = sorted(args.data_dir.rglob("*.mat"))
    if args.limit > 0:
        files = files[: args.limit]

    entries = [_parse_file(path) for path in files]
    payload = {
        "source_data_dir": args.data_dir.as_posix(),
        "support_enabled_assumption": list(DEFAULT_SUPPORT_ENABLED),
        "support_enabled_note": (
            "MATLAB .mat snapshots do not encode support checkbox state; "
            "fixtures assume all three supports are enabled."
        ),
        "entry_count": len(entries),
        "entries": entries,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"wrote {args.output} ({len(entries)} entries)")


if __name__ == "__main__":
    main()
