def _onboard_and_track(client, level="intermediate"):
    client.post("/api/profile", json={"name": "Aryan"})
    track = client.post(
        "/api/tracks", json={"topic": "Python", "experience_level": level}
    )
    return track.json()["id"]


def _generation_payload(count=8):
    questions = []
    for i in range(count):
        if i == 0:
            questions.append(
                {
                    "type": "mcq",
                    "topic_tag": "loops",
                    "question": "Q0?",
                    "options": ["a", "b", "c", "d"],
                    "correct_option": 1,
                }
            )
        else:
            questions.append(
                {
                    "type": "mcq",
                    "topic_tag": f"tag{i}",
                    "question": f"Q{i}?",
                    "options": ["a", "b", "c", "d"],
                    "correct_option": 0,
                }
            )
    return {"questions": questions}


def test_start_assessment_returns_201_with_questions(client, fake_ai):
    track_id = _onboard_and_track(client)
    fake_ai.queue_response(_generation_payload())

    response = client.post(f"/api/tracks/{track_id}/assessment")

    assert response.status_code == 201
    body = response.json()
    assert len(body["questions"]) == 8
    # correct_option is populated in the DB immediately at generation time,
    # but to_assessment_out withholds it from the response until the
    # assessment is completed — this is the reveal-gating from Task 7 Step 3.
    assert body["questions"][0]["correct_option"] is None
    assert body["questions"][0]["score"] is None


def test_start_assessment_on_beginner_track_returns_400(client):
    track_id = _onboard_and_track(client, level="beginner")

    response = client.post(f"/api/tracks/{track_id}/assessment")

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "assessment_not_applicable"


def test_start_assessment_unknown_track_returns_404(client):
    client.post("/api/profile", json={"name": "Aryan"})

    response = client.post("/api/tracks/999/assessment")

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "track_not_found"


def test_get_assessment_unknown_returns_404(client):
    response = client.get("/api/assessments/999")

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "assessment_not_found"


def test_full_lifecycle_answer_and_submit(client, fake_ai):
    track_id = _onboard_and_track(client)
    fake_ai.queue_response(_generation_payload())
    started = client.post(f"/api/tracks/{track_id}/assessment").json()
    assessment_id = started["id"]

    for question in started["questions"]:
        answer = "1" if question["topic_tag"] == "loops" else "0"
        saved = client.patch(
            f"/api/assessments/{assessment_id}/answers",
            json={"question_id": question["id"], "answer": answer},
        )
        assert saved.status_code == 204

    submitted = client.post(f"/api/assessments/{assessment_id}/submit")

    assert submitted.status_code == 200
    body = submitted.json()
    assert body["status"] == "completed"
    assert body["score"] == 100.0
    # After submit, correct_option is revealed — the DB column is now set.
    assert body["questions"][0]["correct_option"] == 1
    assert body["questions"][0]["score"] == 10.0


def test_submit_unknown_assessment_returns_404(client):
    response = client.post("/api/assessments/999/submit")

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "assessment_not_found"


def test_submit_twice_returns_409(client, fake_ai):
    track_id = _onboard_and_track(client)
    fake_ai.queue_response(_generation_payload())
    started = client.post(f"/api/tracks/{track_id}/assessment").json()
    client.post(f"/api/assessments/{started['id']}/submit")

    response = client.post(f"/api/assessments/{started['id']}/submit")

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "assessment_already_submitted"


def test_list_assessments_returns_history(client, fake_ai):
    track_id = _onboard_and_track(client)
    fake_ai.queue_response(_generation_payload())
    client.post(f"/api/tracks/{track_id}/assessment")

    response = client.get("/api/assessments")

    assert response.status_code == 200
    assert len(response.json()) == 1


def test_answer_unknown_question_returns_404(client, fake_ai):
    track_id = _onboard_and_track(client)
    fake_ai.queue_response(_generation_payload())
    started = client.post(f"/api/tracks/{track_id}/assessment").json()

    response = client.patch(
        f"/api/assessments/{started['id']}/answers",
        json={"question_id": 999999, "answer": "x"},
    )

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "question_not_found"
