from ai.prompts.assessment import build_generation_prompt, build_grading_prompt


def test_generation_prompt_includes_topic_and_level():
    prompt = build_generation_prompt("Python", "intermediate")

    assert "Python" in prompt.user_content
    assert "intermediate" in prompt.user_content


def test_generation_prompt_advanced_mentions_skipping_fundamentals():
    prompt = build_generation_prompt("Python", "advanced")

    assert "advanced" in prompt.user_content.lower()
    assert "fundamentals" in prompt.user_content.lower()


def test_generation_prompt_keeps_question_count_guidance_outside_gemma_schema():
    prompt = build_generation_prompt("Python", "intermediate")

    questions_schema = prompt.response_schema["properties"]["questions"]
    assert "min_items" not in questions_schema
    assert "max_items" not in questions_schema
    assert questions_schema["type"] == "ARRAY"
    assert "between 8 and 12 questions" in prompt.user_content


def test_generation_prompt_schema_item_shape():
    prompt = build_generation_prompt("Python", "intermediate")

    item = prompt.response_schema["properties"]["questions"]["items"]
    assert set(item["required"]) == {"type", "topic_tag", "question"}
    assert item["properties"]["options"]["nullable"] is True
    assert item["properties"]["correct_option"]["nullable"] is True
    assert item["properties"]["expected_points"]["nullable"] is True


def test_grading_prompt_includes_each_question_and_answer():
    items = [
        ("Explain inheritance.", ["base class", "override"], "A subclass extends a base class."),
        ("Explain decorators.", ["wraps a function", "@syntax"], "They wrap functions."),
    ]

    prompt = build_grading_prompt("Python", items)

    for question, _points, answer in items:
        assert question in prompt.user_content
        assert answer in prompt.user_content


def test_grading_prompt_keeps_exact_count_guidance_outside_gemma_schema():
    items = [
        ("Q1", ["p1"], "A1"),
        ("Q2", ["p2"], "A2"),
        ("Q3", ["p3"], "A3"),
    ]

    prompt = build_grading_prompt("Python", items)

    gradings_schema = prompt.response_schema["properties"]["gradings"]
    assert "min_items" not in gradings_schema
    assert "max_items" not in gradings_schema
    assert "exactly 3 gradings" in prompt.user_content


def test_grading_prompt_requires_summary():
    prompt = build_grading_prompt("Python", [("Q1", ["p1"], "A1")])

    assert "summary" in prompt.response_schema["required"]
