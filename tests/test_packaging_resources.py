from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ASSETS_ROOT = REPO_ROOT / "src" / "design_research_problems" / "_assets"
RESOURCE_FILES = tuple(
    str(path.relative_to(REPO_ROOT / "src")).replace(os.sep, "/")
    for path in sorted(PACKAGE_ASSETS_ROOT.rglob("*"))
    if path.is_file()
)


def _build_wheel(tmp_path: Path) -> Path:
    shutil.rmtree(REPO_ROOT / "build", ignore_errors=True)

    probe = subprocess.run(
        [sys.executable, "-m", "pip", "--version"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if probe.returncode != 0:
        pytest.skip("pip is unavailable in this environment.")

    backend_probe = subprocess.run(
        [sys.executable, "-c", "import setuptools.build_meta"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if backend_probe.returncode != 0:
        pytest.skip("setuptools.build_meta is unavailable in this environment.")

    wheel_dir = tmp_path / "wheelhouse"
    wheel_dir.mkdir(parents=True, exist_ok=True)
    completed = subprocess.run(
        [sys.executable, "-m", "pip", "wheel", ".", "--no-build-isolation", "--no-deps", "-w", str(wheel_dir)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    wheels = sorted(wheel_dir.glob("design_research_problems-*.whl"))
    assert wheels
    return wheels[0]


def test_wheel_includes_packaged_resources(tmp_path: Path) -> None:
    wheel_path = _build_wheel(tmp_path)
    with zipfile.ZipFile(wheel_path) as archive:
        names = set(archive.namelist())
    missing = sorted(resource for resource in RESOURCE_FILES if resource not in names)
    assert not missing


def test_installed_wheel_loads_registry(tmp_path: Path) -> None:
    wheel_path = _build_wheel(tmp_path)
    install_dir = tmp_path / "install"
    install_dir.mkdir(parents=True, exist_ok=True)
    completed = subprocess.run(
        [sys.executable, "-m", "pip", "install", "--no-deps", "--target", str(install_dir), str(wheel_path)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    env = dict(os.environ)
    env["PYTHONPATH"] = str(install_dir)
    probe = subprocess.run(
        [
            sys.executable,
            "-c",
            ("import json;from design_research_problems import list_problems;print(json.dumps(list(list_problems())))"),
        ],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert probe.returncode == 0, probe.stderr
    payload = json.loads(probe.stdout.strip())
    assert payload == [
        "ideation_accessible_drinking_fountain",
        "ideation_accessible_drinking_fountain_derivative",
        "ideation_car_mounted_bicycle_rack",
        "ideation_chocolate_packaging",
        "ideation_disposable_spill_proof_coffee_cup",
        "ideation_home_energy_conservation",
        "ideation_human_motion_energy_harvesting",
        "ideation_human_motion_energy_harvesting_rural_communities",
        "ideation_injured_athlete_campus_mobility",
        "ideation_joint_immobilization_device",
        "ideation_joint_immobilization_mountain_trek",
        "ideation_measure_passage_of_time",
        "ideation_measure_passage_of_time_room_clock",
        "ideation_measuring_cup_for_blind_users",
        "ideation_measuring_cup_for_blind_users_jansson_smith_1991",
        "ideation_milk_frothing_product",
        "ideation_milk_frothing_product_toh_miller_2014",
        "ideation_one_handed_lidded_container_opening",
        "ideation_one_handed_lidded_container_opening_framework",
        "ideation_out_of_reach_book_retrieval",
        "ideation_out_of_reach_book_retrieval_cardoso_badke_schaub_2011",
        "ideation_peanut_shelling",
        "ideation_peanut_shelling_fu_cagan_kotovsky_2010",
        "ideation_peanut_shelling_linsey_green_murphy_wood_markman_2005",
        "ideation_powdered_surface_coating",
        "ideation_powdered_surface_coating_domain_specific",
        "ideation_powdered_surface_coating_general",
        "ideation_public_belongings_security",
        "ideation_public_place_belongings_securer",
        "ideation_remote_village_rainwater_access",
        "ideation_remote_village_rainwater_access_framework",
        "ideation_small_towel_folding",
        "ideation_small_towel_folding_linsey_wood_markman_2008",
        "ideation_snow_transport_for_novices",
        "ideation_snow_transport_for_novices_framework",
        "ideation_travel_exercise_device",
        "ideation_travel_exercise_device_linsey_viswanathan_2014",
        "ideation_walking_texting_accident_reduction",
        "ideation_walking_texting_accident_reduction_miller_bailey_kirlik_2014",
        "ideation_wheelchair_peach_picking",
        "moneymaker_hip_pump_cost_min",
        "pill_capsule_min_area",
        "planar_truss_span",
        "treadle_pump_ide_material_min",
    ]
