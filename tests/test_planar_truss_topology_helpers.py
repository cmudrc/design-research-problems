from __future__ import annotations

from dataclasses import replace

import pytest

from design_research_problems.problems._domains import planar_truss as planar


def test_planar_truss_seed_and_candidate_points_cover_load_layouts() -> None:
    plain = planar.build_seed_planar_truss_state(10.0, 4.0, 100.0)
    assert plain.load_joint_id == 2
    assert plain.additional_loads == ()
    assert planar.candidate_planar_truss_points(plain) == ((2.5, 2.0), (5.0, 2.0), (7.5, 2.0))
    assert planar.candidate_planar_truss_points(plain, candidate_point_fractions=((0.2, 0.75),)) == ((2.0, 3.0),)

    roof = planar.build_seed_planar_truss_state(
        10.0,
        4.0,
        120.0,
        roof_load_x_fractions=(0.25, 0.5, 0.75),
        enforce_symmetry=True,
    )
    assert roof.symmetry_axis_x == 5.0
    assert roof.load_vector == (0.0, -40.0, 0.0)
    assert len(roof.additional_loads) == 2


def test_planar_truss_candidate_expansion_handles_plain_and_symmetric_states() -> None:
    plain = planar.build_seed_planar_truss_state(10.0, 4.0, 100.0)
    expanded = planar.expand_planar_truss_candidate_joints(
        plain,
        ((2.5, 2.0), (2.5, 2.0), (5.0, 4.0)),
    )
    assert len(expanded.joints) == len(plain.joints) + 1

    symmetric = replace(plain, symmetry_axis_x=5.0)
    expanded_symmetric = planar.expand_planar_truss_candidate_joints(
        symmetric,
        ((2.5, 2.0), (7.5, 2.0), (5.0, 1.0), (5.0, 4.0)),
    )
    coordinates = {(joint.x, joint.y) for joint in expanded_symmetric.joints}
    assert {(2.5, 2.0), (7.5, 2.0), (5.0, 1.0)} <= coordinates

    assert planar.mirrored_joint_id(plain, 999) == 999
    assert planar.mirrored_joint_id(symmetric, 999) is None
    incomplete = replace(symmetric, joints=tuple(joint for joint in symmetric.joints if joint.joint_id != 1))
    assert planar.mirrored_joint_id(incomplete, 0) is None
    assert planar.mirrored_edge(incomplete, (0, 2)) is None


def test_planar_truss_edge_enumeration_and_state_building_enforce_symmetry() -> None:
    seed = planar.build_seed_planar_truss_state(10.0, 4.0, 100.0, enforce_symmetry=True)
    expanded = planar.expand_planar_truss_candidate_joints(seed, ((2.5, 2.0), (5.0, 1.0)))
    candidates = planar.enumerate_planar_truss_candidate_edges(expanded)
    assert candidates
    assert len(candidates) == len(set(candidates))

    built = planar.build_planar_truss_state_from_edges(expanded, (candidates[0],))
    assert built.members
    assert all(member.start_joint_id < member.end_joint_id for member in built.members)

    with pytest.raises(ValueError, match="existing joints"):
        planar.build_planar_truss_state_from_edges(expanded, ((0, 999),))

    asymmetric = replace(
        expanded,
        joints=tuple(joint for joint in expanded.joints if not (joint.x == 7.5 and joint.y == 2.0)),
    )
    with pytest.raises(ValueError, match="mirrored joints"):
        planar.build_planar_truss_state_from_edges(asymmetric, ((0, 3),))


def test_planar_truss_state_builder_retains_preexisting_members_and_loaded_joints() -> None:
    seed = planar.build_seed_planar_truss_state(
        10.0,
        4.0,
        100.0,
        roof_load_x_fractions=(0.25, 0.75),
    )
    with_member = replace(seed, members=(planar.PlanarMember(member_id=7, start_joint_id=0, end_joint_id=2),))
    built = planar.build_planar_truss_state_from_edges(with_member, ((1, 3),))
    assert {planar.edge_key(member.start_joint_id, member.end_joint_id) for member in built.members} == {
        (0, 2),
        (1, 3),
    }
    assert {joint.joint_id for joint in built.joints} == {0, 1, 2, 3}
