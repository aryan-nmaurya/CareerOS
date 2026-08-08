def _onboard_and_track(client, level="intermediate"):
    client.post("/api/profile", json={"name": "Aryan"})
    track = client.post(
        "/api/tracks", json={"topic": "Python", "experience_level": level}
    )
    return track.json()["id"]


def _generation_payload(count=5):
    return {
        "questions": [
            {"question": f"Q{i}?", "expected_points": [f"a{i}", f"b{i}"]}
            for i in range(count)
        ]
    }


def test_start_interview_returns_201_with_questions(client, fake_ai):
    track_id = _onboard_and_track(client)
    fake_ai.queue_response(_generation_payload(5))

    response = client.post(
        f"/api/tracks/{track_id}/interviews",
        json={"level": "intermediate", "question_count": 5},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "active"
    assert len(body["questions"]) == 5
    assert body["questions"][0]["transcript"] is None


def test_start_interview_unknown_track_returns_404(client):
    response = client.post(
        "/api/tracks/999/interviews", json={"level": "intermediate", "question_count": 5}
    )

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "track_not_found"


def test_start_interview_rejects_invalid_question_count(client):
    track_id = _onboard_and_track(client)

    response = client.post(
        f"/api/tracks/{track_id}/interviews",
        json={"level": "intermediate", "question_count": 7},
    )

    assert response.status_code == 422


def test_get_interview_returns_full_shape(client, fake_ai):
    track_id = _onboard_and_track(client)
    fake_ai.queue_response(_generation_payload(5))
    interview_id = client.post(
        f"/api/tracks/{track_id}/interviews",
        json={"level": "intermediate", "question_count": 5},
    ).json()["id"]

    response = client.get(f"/api/interviews/{interview_id}")

    assert response.status_code == 200
    assert response.json()["track_id"] == track_id


def test_get_interview_unknown_returns_404(client):
    response = client.get("/api/interviews/999")

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "interview_not_found"


def test_save_answer_stores_transcript(client, fake_ai):
    track_id = _onboard_and_track(client)
    fake_ai.queue_response(_generation_payload(5))
    interview = client.post(
        f"/api/tracks/{track_id}/interviews",
        json={"level": "intermediate", "question_count": 5},
    ).json()
    question_id = interview["questions"][0]["id"]

    response = client.post(
        f"/api/interviews/{interview['id']}/questions/{question_id}/answer",
        json={"transcript": "Spoken answer here.", "duration_s": 30},
    )

    assert response.status_code == 204
    refreshed = client.get(f"/api/interviews/{interview['id']}").json()
    assert refreshed["questions"][0]["transcript"] == "Spoken answer here."
    assert refreshed["questions"][0]["answer_duration_s"] == 30


def test_save_answer_unknown_interview_returns_404(client):
    response = client.post(
        "/api/interviews/999/questions/1/answer",
        json={"transcript": "x", "duration_s": 1},
    )

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "interview_not_found"


def test_submit_interview_marks_completed(client, fake_ai):
    track_id = _onboard_and_track(client)
    fake_ai.queue_response(_generation_payload(5))
    interview_id = client.post(
        f"/api/tracks/{track_id}/interviews",
        json={"level": "intermediate", "question_count": 5},
    ).json()["id"]

    response = client.post(f"/api/interviews/{interview_id}/submit")

    assert response.status_code == 200
    assert response.json()["status"] == "completed"


def test_submit_interview_already_completed_returns_409(client, fake_ai):
    track_id = _onboard_and_track(client)
    fake_ai.queue_response(_generation_payload(5))
    interview_id = client.post(
        f"/api/tracks/{track_id}/interviews",
        json={"level": "intermediate", "question_count": 5},
    ).json()["id"]
    client.post(f"/api/interviews/{interview_id}/submit")

    response = client.post(f"/api/interviews/{interview_id}/submit")

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "interview_not_active"


def test_quit_interview_marks_terminated(client, fake_ai):
    track_id = _onboard_and_track(client)
    fake_ai.queue_response(_generation_payload(5))
    interview_id = client.post(
        f"/api/tracks/{track_id}/interviews",
        json={"level": "intermediate", "question_count": 5},
    ).json()["id"]

    response = client.post(f"/api/interviews/{interview_id}/quit")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "terminated"
    assert body["termination_reason"] == "user_quit"


def test_quit_interview_already_terminated_returns_409(client, fake_ai):
    track_id = _onboard_and_track(client)
    fake_ai.queue_response(_generation_payload(5))
    interview_id = client.post(
        f"/api/tracks/{track_id}/interviews",
        json={"level": "intermediate", "question_count": 5},
    ).json()["id"]
    client.post(f"/api/interviews/{interview_id}/quit")

    response = client.post(f"/api/interviews/{interview_id}/quit")

    assert response.status_code == 409
