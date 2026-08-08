from types import SimpleNamespace

from ai.prompts.roadmap import build_roadmap_prompt


def test_beginner_prompt_assumes_zero_knowledge():
    prompt = build_roadmap_prompt("Python", "beginner")

    assert "zero prior knowledge" in prompt.user_content.lower()


def test_advanced_prompt_includes_strengths_weaknesses_and_skips_fundamentals():
    assessment = SimpleNamespace(strengths=["loops"], weaknesses=["oop"])

    prompt = build_roadmap_prompt("Python", "advanced", assessment)

    assert "skip fundamentals" in prompt.user_content.lower()
    assert "loops" in prompt.user_content
    assert "oop" in prompt.user_content
    assert "interview" in prompt.user_content.lower()


def test_intermediate_prompt_weights_toward_weaknesses():
    assessment = SimpleNamespace(strengths=["loops"], weaknesses=["oop"])

    prompt = build_roadmap_prompt("Python", "intermediate", assessment)

    assert "loops" in prompt.user_content
    assert "oop" in prompt.user_content


def test_schema_requires_phases_last_and_prompt_preserves_phase_count_guidance():
    prompt = build_roadmap_prompt("Python", "beginner")

    keys = list(prompt.response_schema["properties"].keys())
    assert keys[-1] == "phases"
    phases_schema = prompt.response_schema["properties"]["phases"]
    assert "min_items" not in phases_schema
    assert "max_items" not in phases_schema
    assert "4-10 learning phases" in prompt.user_content


def test_module_schema_includes_kind_enum():
    prompt = build_roadmap_prompt("Python", "beginner")

    module_schema = prompt.response_schema["properties"]["phases"]["items"]["properties"]["modules"]["items"]
    assert set(module_schema["properties"]["kind"]["enum"]) == {
        "module",
        "checkpoint",
        "milestone",
        "project",
    }
