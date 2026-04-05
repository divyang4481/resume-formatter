import pytest
from app.adapters.llm.ollama_runtime import LocalOllamaLlmRuntime

def test_ollama_runtime_signature():
    runtime = LocalOllamaLlmRuntime()
    # Mock httpx to avoid real calls, we just want to ensure it passes the parameters
    import httpx

    class MockResponse:
        status_code = 200
        def json(self):
            return {"response": "test response"}

    class MockClient:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def post(self, url, json, timeout):
            self.last_payload = json
            return MockResponse()

    mock_client = MockClient()

    # Patch httpx.Client
    import sys
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(httpx, "Client", lambda: mock_client)

    runtime.generate(
        prompt="Test",
        system_prompt="System",
        response_format={"type": "object"},
        temperature=0.5,
        raw=True
    )

    assert mock_client.last_payload["prompt"] == "Test"
    assert mock_client.last_payload["system"] == "System"
    assert mock_client.last_payload["format"] == {"type": "object"}
    assert mock_client.last_payload["raw"] is True
    assert mock_client.last_payload["options"]["temperature"] == 0.5

    monkeypatch.undo()
