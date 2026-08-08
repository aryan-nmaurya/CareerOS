from ai.prompts.evaluation import build_evaluation_prompt


def test_evaluation_prompt_batches_questions_and_includes_pacing_signals():
    prompt = build_evaluation_prompt(
        "Python",
        "intermediate",
        [("What is the GIL?", ["lock", "threads"], "It limits some CPU work.", 12),
         ("Explain generators.", ["yield"], None, None)],
    )
    assert "Question 1" in prompt.user_content
    assert "Word count: 5" in prompt.user_content
    assert "[empty transcript]" in prompt.user_content
    questions_schema = prompt.response_schema["properties"]["questions"]
    assert "min_items" not in questions_schema
    assert "max_items" not in questions_schema
    assert "exactly 2 interview answers" in prompt.user_content
