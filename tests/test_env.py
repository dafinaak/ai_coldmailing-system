import pytest
from pipeline.env import brauche_env_eines_von

def test_akzeptiert_wenn_nur_openrouter_gesetzt_ist(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    brauche_env_eines_von("ANTHROPIC_API_KEY", "OPENROUTER_API_KEY")  # darf nicht abbrechen

def test_akzeptiert_wenn_nur_anthropic_gesetzt_ist(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    brauche_env_eines_von("ANTHROPIC_API_KEY", "OPENROUTER_API_KEY")  # darf nicht abbrechen

def test_bricht_ab_wenn_keines_gesetzt_ist(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    with pytest.raises(SystemExit):
        brauche_env_eines_von("ANTHROPIC_API_KEY", "OPENROUTER_API_KEY")
