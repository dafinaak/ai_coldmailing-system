import pytest
from tests.test_apollo import FakeSession, FakeResponse

def test_openrouter_baut_richtiges_payload_und_liefert_antwort(monkeypatch):
    """OpenRouter-Pfad: Modell-Slug bekommt "anthropic/"-Prefix (Default
    "claude-sonnet-5" -> "anthropic/claude-sonnet-5"), Nachrichten sind
    System+User im OpenAI-Chat-Format, Antwort kommt aus
    choices[0].message.content."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "or-test-key")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("KI_MODELL", raising=False)
    from pipeline.ki import KI

    antwort = FakeResponse(200, {"choices": [{"message": {"content": "Hallo Welt"}}]})
    session = FakeSession([antwort])
    ki = KI(session=session)

    ergebnis = ki.frage("Du bist hilfreich.", "Sag hallo.")

    assert ergebnis == "Hallo Welt"
    assert len(session.aufrufe) == 1
    payload = session.aufrufe[0]
    assert payload["model"] == "anthropic/claude-sonnet-5"
    assert payload["max_tokens"] == 1500
    assert payload["messages"] == [
        {"role": "system", "content": "Du bist hilfreich."},
        {"role": "user", "content": "Sag hallo."},
    ]

def test_openrouter_modell_mit_slash_wird_nicht_praefigiert(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "or-test-key")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("KI_MODELL", "openai/gpt-4o")
    from pipeline.ki import KI

    antwort = FakeResponse(200, {"choices": [{"message": {"content": "ok"}}]})
    session = FakeSession([antwort])
    ki = KI(session=session)
    ki.frage("sys", "prompt")

    assert session.aufrufe[0]["model"] == "openai/gpt-4o"

def test_openrouter_fehlerstatus_wirft_runtimeerror_mit_statuscode(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "or-test-key")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    from pipeline.ki import KI

    antwort = FakeResponse(401, {}, text="Unauthorized: invalid API key")
    session = FakeSession([antwort])
    ki = KI(session=session)

    with pytest.raises(RuntimeError, match="401"):
        ki.frage("sys", "prompt")

def test_ohne_schluessel_wirft_klaren_fehler_bei_konstruktion(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    from pipeline.ki import KI

    with pytest.raises(RuntimeError):
        KI()
