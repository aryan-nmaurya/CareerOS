import pytest

from ai.client import FakeAIClient, Prompt


def _prompt(text: str = "hello") -> Prompt:
    return Prompt(
        system_instruction="system",
        user_content=text,
        response_schema={"type": "OBJECT", "properties": {}},
    )


def test_fake_client_returns_queued_responses_in_order():
    client = FakeAIClient()
    client.queue_response({"a": 1})
    client.queue_response({"a": 2})

    first = client.generate_json(_prompt())
    second = client.generate_json(_prompt())

    assert first == {"a": 1}
    assert second == {"a": 2}


def test_fake_client_records_calls():
    client = FakeAIClient()
    client.queue_response({"a": 1})

    client.generate_json(_prompt("specific text"))

    assert len(client.calls) == 1
    assert client.calls[0].user_content == "specific text"


def test_fake_client_raises_when_queue_is_empty():
    client = FakeAIClient()

    with pytest.raises(AssertionError):
        client.generate_json(_prompt())
