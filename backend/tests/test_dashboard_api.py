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


def test_dashboard_before_any_profile_returns_empty_shape(client):
    response = client.get("/api/dashboard")

    assert response.status_code == 200
    body = response.json()
    assert body["profile"] is None
    assert body["active_track"] is None
    assert body["completed_modules"] == 0
    assert body["remaining_modules"] == 0
    assert body["completion_pct"] == 0.0
    assert body["next_module"] is None
    assert body["recent_interviews"] == []


def test_dashboard_with_profile_but_no_active_track_returns_partial_shape(client):
    client.post("/api/profile", json={"name": "Aryan"})

    response = client.get("/api/dashboard")

    body = response.json()
    assert body["profile"]["name"] == "Aryan"
    assert body["active_track"] is None
    assert body["roadmap_summary"] is None


def test_dashboard_with_track_but_no_roadmap_returns_partial_shape(client):
    client.post("/api/profile", json={"name": "Aryan"})
    client.post("/api/tracks", json={"topic": "Python", "experience_level": "beginner"})

    response = client.get("/api/dashboard")

    body = response.json()
    assert body["active_track"]["topic"] == "Python"
    assert body["roadmap_summary"] is None
    assert body["current_phase"] is None
    assert body["next_module"] is None


def test_dashboard_reflects_roadmap_progress_and_updates_after_module_completion(client, fake_ai):
    client.post("/api/profile", json={"name": "Aryan"})
    track_id = client.post(
        "/api/tracks", json={"topic": "Python", "experience_level": "beginner"}
    ).json()["id"]
    fake_ai.queue_stream(_HAPPY_CHUNKS)
    client.post(f"/api/tracks/{track_id}/roadmap/stream")

    before = client.get("/api/dashboard").json()
    assert before["roadmap_summary"] == "From zero to functional scripts."
    assert before["current_phase"] == "Foundations"
    assert before["completed_modules"] == 0
    assert before["remaining_modules"] == 1
    assert before["completion_pct"] == 0.0
    assert before["next_module"]["title"] == "Variables"
    assert before["next_module"]["kind"] == "module"

    module_id = before["next_module"]["id"]
    client.patch(f"/api/modules/{module_id}", json={"completed": True})

    after = client.get("/api/dashboard").json()
    assert after["completed_modules"] == 1
    assert after["remaining_modules"] == 0
    assert after["completion_pct"] == 100.0
    assert after["next_module"] is None


def test_dashboard_reflects_recent_interviews(client, fake_ai):
    client.post("/api/profile", json={"name": "Aryan"})
    track_id = client.post(
        "/api/tracks", json={"topic": "Python", "experience_level": "intermediate"}
    ).json()["id"]
    fake_ai.queue_response(
        {
            "questions": [
                {"question": f"Q{i}?", "expected_points": ["a", "b"]} for i in range(5)
            ]
        }
    )
    client.post(
        f"/api/tracks/{track_id}/interviews",
        json={"level": "intermediate", "question_count": 5},
    )

    body = client.get("/api/dashboard").json()

    assert len(body["recent_interviews"]) == 1
    assert body["recent_interviews"][0]["level"] == "intermediate"
    assert body["recent_interviews"][0]["status"] == "active"
