from ai.stream_parser import PhaseStreamParser


def _feed_all(parser: PhaseStreamParser, chunks: list[str]):
    events = []
    for chunk in chunks:
        events.extend(parser.feed(chunk))
    return events


def test_emits_meta_once_scalars_and_phases_key_are_seen():
    parser = PhaseStreamParser()
    events = _feed_all(
        parser,
        [
            '{"title": "T", "summary": "S", "total_weeks": 4, "weekly_hours": 8, ',
            '"weekly_goals": [{"week": 1, "goal": "G", "phase_order": 0}], ',
            '"final_project": {"title": "F", "description": "D", "skills_demonstrated": ["x"]}, ',
            '"phases": [',
        ],
    )
    assert len(events) == 1
    event, data = events[0]
    assert event == "meta"
    assert data["title"] == "T"
    assert data["total_weeks"] == 4
    assert data["weekly_goals"] == [{"week": 1, "goal": "G", "phase_order": 0}]
    assert data["final_project"]["title"] == "F"


def test_emits_one_phase_event_per_completed_phase_object():
    parser = PhaseStreamParser()
    chunks = [
        '{"title": "T", "summary": "S", "total_weeks": 1, "weekly_hours": 5, ',
        '"weekly_goals": [], "final_project": {"title": "F", "description": "D", "skills_demonstrated": []}, ',
        '"phases": [',
        '{"title": "Phase 1: Fundamentals & Syntax", "goal": "Master the core building blocks of Python, incl',
        'uding variables and loops.", "modules": []},',
        '{"title": "Phase 2: Functions, Data Structures & Basic Projects", "goal": "Learn to',
        ' organize code using functions and collections.", "modules": []}',
        ']}',
    ]
    events = _feed_all(parser, chunks)

    assert [e for e, _ in events] == ["meta", "phase", "phase"]
    _, phase1 = events[1]
    _, phase2 = events[2]
    assert phase1["title"] == "Phase 1: Fundamentals & Syntax"
    assert phase2["title"] == "Phase 2: Functions, Data Structures & Basic Projects"


def test_handles_nested_module_objects_inside_a_phase():
    parser = PhaseStreamParser()
    chunks = [
        '{"title": "T", "summary": "S", "total_weeks": 1, "weekly_hours": 5, ',
        '"weekly_goals": [], "final_project": {"title": "F", "description": "D", "skills_demonstrated": []}, ',
        '"phases": [',
        '{"title": "P1", "goal": "G1", "modules": [',
        '{"title": "M1", "description": "D1", "lessons": ["l1"], "exercises": [], "project": null, ',
        '"estimated_hours": 2, "kind": "module"}',
        ']}',
        ']}',
    ]
    events = _feed_all(parser, chunks)

    assert [e for e, _ in events] == ["meta", "phase"]
    _, phase = events[1]
    assert len(phase["modules"]) == 1
    assert phase["modules"][0]["title"] == "M1"


def test_literal_braces_inside_string_values_do_not_confuse_depth_tracking():
    parser = PhaseStreamParser()
    chunks = [
        '{"title": "T", "summary": "S", "total_weeks": 1, "weekly_hours": 5, ',
        '"weekly_goals": [], "final_project": {"title": "F", "description": "D", "skills_demonstrated": []}, ',
        '"phases": [',
        '{"title": "Uses {curly} braces", "goal": "explain dict literals like {\\"a\\": 1}", "modules": []}',
        ']}',
    ]
    events = _feed_all(parser, chunks)

    assert [e for e, _ in events] == ["meta", "phase"]
    _, phase = events[1]
    assert phase["title"] == "Uses {curly} braces"
    assert phase["goal"] == 'explain dict literals like {"a": 1}'


def test_multiple_phases_closing_within_a_single_chunk_all_emit():
    parser = PhaseStreamParser()
    chunks = [
        '{"title": "T", "summary": "S", "total_weeks": 1, "weekly_hours": 5, ',
        '"weekly_goals": [], "final_project": {"title": "F", "description": "D", "skills_demonstrated": []}, ',
        '"phases": [',
        '{"title": "P1", "goal": "G1", "modules": []},{"title": "P2", "goal": "G2", "modules": []}',
        ']}',
    ]
    events = _feed_all(parser, chunks)

    assert [e for e, _ in events] == ["meta", "phase", "phase"]


def test_truncated_stream_emits_only_completed_phases_no_crash():
    parser = PhaseStreamParser()
    chunks = [
        '{"title": "T", "summary": "S", "total_weeks": 1, "weekly_hours": 5, ',
        '"weekly_goals": [], "final_project": {"title": "F", "description": "D", "skills_demonstrated": []}, ',
        '"phases": [',
        '{"title": "P1", "goal": "G1", "modules": []},',
        '{"title": "P2 is cut off mid',
        # stream ends here — no crash, no partial "phase" event for P2
    ]
    events = _feed_all(parser, chunks)

    assert [e for e, _ in events] == ["meta", "phase"]
