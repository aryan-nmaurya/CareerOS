def test_health_returns_ok(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_profile_returns_204_before_onboarding(client):
    response = client.get("/api/profile")

    assert response.status_code == 204


def test_onboarding_happy_path(client):
    created = client.post("/api/profile", json={"name": "Aryan"})
    assert created.status_code == 201
    assert created.json()["name"] == "Aryan"
    assert created.json()["theme"] == "system"

    fetched = client.get("/api/profile")
    assert fetched.status_code == 200
    assert fetched.json()["name"] == "Aryan"

    track = client.post(
        "/api/tracks", json={"topic": "Python", "experience_level": "beginner"}
    )
    assert track.status_code == 201
    assert track.json()["is_active"] is True

    listed = client.get("/api/tracks")
    assert listed.status_code == 200
    assert len(listed.json()) == 1


def test_creating_a_second_profile_is_rejected(client):
    client.post("/api/profile", json={"name": "Aryan"})

    duplicate = client.post("/api/profile", json={"name": "Someone Else"})

    assert duplicate.status_code == 409
    assert duplicate.json()["detail"]["code"] == "profile_exists"


def test_track_before_onboarding_is_rejected(client):
    response = client.post(
        "/api/tracks", json={"topic": "Python", "experience_level": "beginner"}
    )

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "profile_not_found"


def test_activating_unknown_track_returns_404(client):
    client.post("/api/profile", json={"name": "Aryan"})

    response = client.post("/api/tracks/999/activate")

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "track_not_found"


def test_invalid_experience_level_is_rejected(client):
    client.post("/api/profile", json={"name": "Aryan"})

    response = client.post(
        "/api/tracks", json={"topic": "Python", "experience_level": "expert"}
    )

    assert response.status_code == 422


def test_patch_profile_updates_theme(client):
    client.post("/api/profile", json={"name": "Aryan"})

    response = client.patch("/api/profile", json={"theme": "dark"})

    assert response.status_code == 200
    assert response.json()["theme"] == "dark"
