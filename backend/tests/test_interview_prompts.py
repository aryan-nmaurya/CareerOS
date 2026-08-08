from ai.prompts.interview import build_interview_prompt


def test_beginner_prompt_asks_foundational_questions():
    prompt = build_interview_prompt("Python", "beginner", 5)

    assert "foundational" in prompt.user_content.lower()


def test_advanced_prompt_probes_deep_understanding():
    prompt = build_interview_prompt("Python", "advanced", 5)

    assert "advanced" in prompt.user_content.lower()
    assert (
        "trade-offs" in prompt.user_content.lower()
        or "edge cases" in prompt.user_content.lower()
    )


def test_roadmap_context_is_included_when_present():
    prompt = build_interview_prompt(
        "Python", "intermediate", 8, roadmap_context=["Decorators", "Generators"]
    )

    assert "Decorators" in prompt.user_content
    assert "Generators" in prompt.user_content


def test_no_roadmap_context_omits_the_context_line():
    prompt = build_interview_prompt("Python", "intermediate", 8, roadmap_context=None)

    assert "studying" not in prompt.user_content.lower()


def test_schema_keeps_exact_question_count_guidance_outside_gemma_schema():
    prompt = build_interview_prompt("Python", "intermediate", 6)

    questions_schema = prompt.response_schema["properties"]["questions"]
    assert "min_items" not in questions_schema
    assert "max_items" not in questions_schema
    assert "exactly 6 questions" in prompt.user_content
