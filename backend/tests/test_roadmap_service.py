from datetime import datetime

from ai.errors import AIUnavailable
from models.assessment import Assessment
from models.roadmap import Roadmap
from schemas.profile import ProfileCreate, TrackCreate
from services import profile_service
from services.roadmap_service import stream_roadmap

_HAPPY_CHUNKS = [
    '{"title": "Python Roadmap", "summary": "From zero to functional scripts.", ',
    '"total_weeks": 4, "weekly_hours": 5, ',
    '"weekly_goals": [{"week": 1, "goal": "Learn syntax", "phase_order": 0}], ',
    '"final_project": {"title": "CLI Tool", "description": "Build a CLI", "skills_demonstrated": ["cli"]}, ',
    '"phases": [',
    '{"title": "Foundations", "description": "The basics.", "goal": "Write simple scripts.", '
    '"estimated_hours": 10, "modules": [',
    '{"title": "Variables", "description": "Learn variables.", "lessons": ["l1"], "exercises": ["e1"], ',
    '"project": null, "estimated_hours": 3, "kind": "module"}',
    ']}',
    ']}',
]


def _track(db_session, level="beginner"):
    profile_service.create_profile(db_session, ProfileCreate(name="Aryan"))
    return profile_service.create_track(
        db_session, TrackCreate(topic="Python", experience_level=level)
    )


def _raising_stream(chunks, exc):
    yield from chunks
    raise exc


def test_stream_roadmap_persists_meta_and_phases_and_yields_matching_events(db_session, fake_ai):
    track = _track(db_session)
    fake_ai.queue_stream(_HAPPY_CHUNKS)

    events = list(stream_roadmap(db_session, fake_ai, track.id))

    assert [e for e, _ in events] == ["meta", "phase", "done"]
    roadmap = db_session.query(Roadmap).filter_by(track_id=track.id).one()
    assert roadmap.title == "Python Roadmap"
    assert roadmap.assessment_id is None
    assert len(roadmap.phases) == 1
    assert roadmap.phases[0].title == "Foundations"
    assert len(roadmap.phases[0].modules) == 1
    assert roadmap.phases[0].modules[0].title == "Variables"
    assert roadmap.phases[0].modules[0].kind == "module"
    _, done_data = events[2]
    assert done_data["roadmap_id"] == roadmap.id


def test_stream_roadmap_beginner_path_skips_assessment_lookup(db_session, fake_ai):
    track = _track(db_session, level="beginner")
    fake_ai.queue_stream(_HAPPY_CHUNKS)

    list(stream_roadmap(db_session, fake_ai, track.id))

    assert "zero prior knowledge" in fake_ai.stream_calls[0].user_content.lower()


def test_stream_roadmap_intermediate_path_uses_latest_completed_assessment(db_session, fake_ai):
    track = _track(db_session, level="intermediate")
    assessment = Assessment(
        track_id=track.id,
        level="intermediate",
        status="completed",
        completed_at=datetime(2026, 1, 1),
        strengths=["loops"],
        weaknesses=["oop"],
    )
    db_session.add(assessment)
    db_session.commit()
    fake_ai.queue_stream(_HAPPY_CHUNKS)

    list(stream_roadmap(db_session, fake_ai, track.id))

    assert "loops" in fake_ai.stream_calls[0].user_content
    assert "oop" in fake_ai.stream_calls[0].user_content
    roadmap = db_session.query(Roadmap).filter_by(track_id=track.id).one()
    assert roadmap.assessment_id == assessment.id


def test_stream_roadmap_unknown_track_yields_error_and_makes_no_ai_call(db_session, fake_ai):
    events = list(stream_roadmap(db_session, fake_ai, 999))

    assert len(events) == 1
    event, data = events[0]
    assert event == "error"
    assert data["code"] == "track_not_found"
    assert fake_ai.stream_calls == []


def test_stream_roadmap_rejects_stream_with_no_phases_and_rolls_back(db_session, fake_ai):
    track = _track(db_session)
    no_phase_chunks = [
        '{"title": "T", "summary": "S", "total_weeks": 1, "weekly_hours": 1, ',
        '"weekly_goals": [], "final_project": {"title": "F", "description": "D", "skills_demonstrated": []}, ',
        '"phases": []}',
    ]
    fake_ai.queue_stream(no_phase_chunks)

    events = list(stream_roadmap(db_session, fake_ai, track.id))

    assert [e for e, _ in events] == ["meta", "error"]
    assert events[1][1]["code"] == "ai_invalid_response"
    assert db_session.query(Roadmap).filter_by(track_id=track.id).count() == 0


def test_stream_roadmap_rolls_back_everything_on_mid_stream_ai_failure(db_session, fake_ai):
    track = _track(db_session)
    fake_ai.queue_stream(_raising_stream(_HAPPY_CHUNKS[:9], AIUnavailable("boom")))

    events = list(stream_roadmap(db_session, fake_ai, track.id))

    assert [e for e, _ in events] == ["meta", "phase", "error"]
    assert events[2][1]["code"] == "ai_unavailable"
    assert db_session.query(Roadmap).filter_by(track_id=track.id).count() == 0
