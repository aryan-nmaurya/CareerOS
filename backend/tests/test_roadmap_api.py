import json

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


def _onboard_and_track(client, level="beginner"):
    client.post("/api/profile", json={"name": "Aryan"})
    track = client.post(
        "/api/tracks", json={"topic": "Python", "experience_level": level}
    )
    return track.json()["id"]


def _parse_sse(text):
    events = []
    for block in text.strip().split("\n\n"):
        if not block:
            continue
        lines = block.splitlines()
        event = next(l.split(": ", 1)[1] for l in lines if l.startswith("event: "))
        data = next(l.split(": ", 1)[1] for l in lines if l.startswith("data: "))
        events.append((event, json.loads(data)))
    return events


def test_generate_roadmap_streams_meta_phase_and_done(client, fake_ai):
    track_id = _onboard_and_track(client)
    fake_ai.queue_stream(_HAPPY_CHUNKS)

    response = client.post(f"/api/tracks/{track_id}/roadmap/stream")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    events = _parse_sse(response.text)
    assert [e for e, _ in events] == ["meta", "phase", "done"]
    assert events[0][1]["title"] == "Python Roadmap"


def test_generate_roadmap_unknown_track_streams_error_event(client, fake_ai):
    response = client.post("/api/tracks/999/roadmap/stream")

    events = _parse_sse(response.text)
    assert events == [("error", {"code": "track_not_found", "message": "That learning track does not exist."})]
    assert fake_ai.stream_calls == []


def test_get_roadmap_returns_full_shape_with_progress(client, fake_ai):
    track_id = _onboard_and_track(client)
    fake_ai.queue_stream(_HAPPY_CHUNKS)
    client.post(f"/api/tracks/{track_id}/roadmap/stream")

    response = client.get(f"/api/tracks/{track_id}/roadmap")

    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "Python Roadmap"
    assert len(body["phases"]) == 1
    assert len(body["phases"][0]["modules"]) == 1
    assert body["phases"][0]["modules"][0]["title"] == "Variables"
    assert body["progress"]["total_modules"] == 1
    assert body["progress"]["completed_modules"] == 0


def test_get_roadmap_before_generation_returns_404(client):
    track_id = _onboard_and_track(client)

    response = client.get(f"/api/tracks/{track_id}/roadmap")

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "roadmap_not_found"


def test_patch_module_toggles_completion_both_ways(client, fake_ai):
    track_id = _onboard_and_track(client)
    fake_ai.queue_stream(_HAPPY_CHUNKS)
    client.post(f"/api/tracks/{track_id}/roadmap/stream")
    module_id = client.get(f"/api/tracks/{track_id}/roadmap").json()["phases"][0]["modules"][0]["id"]

    completed = client.patch(f"/api/modules/{module_id}", json={"completed": True})
    assert completed.status_code == 200
    completed_body = completed.json()
    assert completed_body["module"]["completed_at"] is not None
    assert completed_body["progress"]["completed_modules"] == 1
    assert completed_body["progress"]["completion_pct"] == 100.0

    uncompleted = client.patch(f"/api/modules/{module_id}", json={"completed": False})
    uncompleted_body = uncompleted.json()
    assert uncompleted_body["module"]["completed_at"] is None
    assert uncompleted_body["progress"]["completed_modules"] == 0


def test_patch_module_unknown_returns_404(client):
    response = client.patch("/api/modules/999", json={"completed": True})

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "module_not_found"


def test_get_progress_before_roadmap_returns_404(client):
    track_id = _onboard_and_track(client)

    response = client.get(f"/api/tracks/{track_id}/progress")

    assert response.status_code == 404


def test_get_progress_matches_roadmap_progress(client, fake_ai):
    track_id = _onboard_and_track(client)
    fake_ai.queue_stream(_HAPPY_CHUNKS)
    client.post(f"/api/tracks/{track_id}/roadmap/stream")

    response = client.get(f"/api/tracks/{track_id}/progress")

    assert response.status_code == 200
    assert response.json()["total_modules"] == 1
