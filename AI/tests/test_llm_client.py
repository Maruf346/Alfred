import asyncio
from types import SimpleNamespace

import pytest

from app.llm_client import LLMError, OpenAIClient


class _StubCompletions:
    def __init__(self):
        self.kwargs = None

    async def create(self, **kwargs):
        self.kwargs = kwargs
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="{}"))])


def _client_with_stub():
    client = OpenAIClient.__new__(OpenAIClient)  # skip __init__: no real key/network needed
    stub = _StubCompletions()
    client._client = SimpleNamespace(chat=SimpleNamespace(completions=stub))
    client._model, client._max_tokens, client._temperature = "gpt-4o", 100, 0.0
    return client, stub


def _user_content(stub):
    return stub.kwargs["messages"][1]["content"]


def test_openai_multimodal_attaches_pdf_as_file_block():
    client, stub = _client_with_stub()
    asyncio.run(client.complete_multimodal("sys", "prompt", file_base64="QUJD", file_type="application/pdf"))
    blocks = _user_content(stub)
    assert blocks[0]["type"] == "file"
    assert blocks[0]["file"]["file_data"] == "data:application/pdf;base64,QUJD"
    assert blocks[-1] == {"type": "text", "text": "prompt"}


def test_openai_multimodal_attaches_image_block():
    client, stub = _client_with_stub()
    asyncio.run(client.complete_multimodal("sys", "prompt", file_base64="QUJD", file_type="image/png"))
    blocks = _user_content(stub)
    assert blocks[0]["type"] == "image_url"
    assert blocks[0]["image_url"]["url"] == "data:image/png;base64,QUJD"


def test_openai_multimodal_rejects_unsupported_attachment_instead_of_dropping_it():
    client, stub = _client_with_stub()
    with pytest.raises(LLMError):
        asyncio.run(client.complete_multimodal("sys", "prompt", file_base64="QUJD", file_type="text/csv"))
    assert stub.kwargs is None  # nothing was sent to the model
