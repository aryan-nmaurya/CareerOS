from models.roadmap import Roadmap, RoadmapModule, RoadmapPhase
from models.user import LearningTrack
from schemas.profile import ProfileCreate, TrackCreate
from services import profile_service


def _track(db_session):
    profile_service.create_profile(db_session, ProfileCreate(name="Aryan"))
    return profile_service.create_track(
        db_session, TrackCreate(topic="Python", experience_level="beginner")
    )


def test_roadmap_phase_module_round_trip(db_session):
    track = _track(db_session)

    roadmap = Roadmap(
        track_id=track.id,
        title="Python Roadmap",
        summary="From zero to functional scripts.",
        total_weeks=8,
        weekly_hours=6,
        weekly_goals=[{"week": 1, "goal": "Learn syntax", "phase_order": 0}],
        final_project={"title": "CLI tool", "description": "...", "skills_demonstrated": ["cli"]},
    )
    db_session.add(roadmap)
    db_session.commit()

    phase = RoadmapPhase(
        roadmap_id=roadmap.id,
        order_index=0,
        title="Foundations",
        description="The basics.",
        goal="Write and run simple scripts.",
        estimated_hours=10,
    )
    db_session.add(phase)
    db_session.commit()

    module = RoadmapModule(
        phase_id=phase.id,
        order_index=0,
        title="Variables & Types",
        description="...",
        lessons=["Numbers", "Strings"],
        exercises=["Write a temperature converter"],
        project=None,
        estimated_hours=3,
        kind="module",
    )
    db_session.add(module)
    db_session.commit()

    assert roadmap.phases == [phase]
    assert phase.roadmap is roadmap
    assert phase.modules == [module]
    assert module.completed_at is None
    assert roadmap.track.id == track.id


def test_deleting_track_cascades_to_roadmap_phases_and_modules(db_session):
    track = _track(db_session)
    roadmap = Roadmap(track_id=track.id, title="T", summary="S", total_weeks=1, weekly_hours=1)
    db_session.add(roadmap)
    db_session.commit()
    phase = RoadmapPhase(roadmap_id=roadmap.id, order_index=0, title="P", description="", goal="G", estimated_hours=1)
    db_session.add(phase)
    db_session.commit()
    module = RoadmapModule(
        phase_id=phase.id, order_index=0, title="M", description="", lessons=[], exercises=[],
        project=None, estimated_hours=1, kind="module",
    )
    db_session.add(module)
    db_session.commit()
    roadmap_id, phase_id, module_id = roadmap.id, phase.id, module.id

    db_session.delete(db_session.get(LearningTrack, track.id))
    db_session.commit()

    assert db_session.get(Roadmap, roadmap_id) is None
    assert db_session.get(RoadmapPhase, phase_id) is None
    assert db_session.get(RoadmapModule, module_id) is None


def test_module_kind_and_completion_fields(db_session):
    track = _track(db_session)
    roadmap = Roadmap(track_id=track.id, title="T", summary="S", total_weeks=1, weekly_hours=1)
    db_session.add(roadmap)
    db_session.commit()
    phase = RoadmapPhase(roadmap_id=roadmap.id, order_index=0, title="P", description="", goal="G", estimated_hours=1)
    db_session.add(phase)
    db_session.commit()

    milestone = RoadmapModule(
        phase_id=phase.id, order_index=0, title="Capstone check-in", description="",
        lessons=[], exercises=[], project={"title": "Mini project", "description": "..."},
        estimated_hours=4, kind="milestone",
    )
    db_session.add(milestone)
    db_session.commit()

    assert milestone.kind == "milestone"
    assert milestone.project["title"] == "Mini project"
    assert milestone.started_at is None
    assert milestone.completed_at is None
