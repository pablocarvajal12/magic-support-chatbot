from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.config.config import Settings


def test_settings_requires_groq_api_key(monkeypatch):
    # Nos asegura que no hay GROQ_API_KEY "filtrada" desde el entorno
    # ni desde un .env local que pudiera existir.
    monkeypatch.delenv("GROQ_API_KEY", raising=False)

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_settings_loads_with_required_value_and_defaults():
    settings = Settings(_env_file=None, groq_api_key="test-key")

    assert settings.groq_api_key == "test-key"
    # Defaults documentados en la sección 2.x del documento de arquitectura
    assert settings.groq_model == "llama-3.1-70b-versatile"
    assert settings.chunk_size == 500
    assert settings.chunk_overlap == 50
    assert settings.retrieval_k == 4
    assert settings.memory_window_k == 10


def test_settings_overrides_defaults_from_kwargs():
    settings = Settings(
        _env_file=None,
        groq_api_key="test-key",
        chunk_size=800,
        memory_window_k=5,
    )

    assert settings.chunk_size == 800
    assert settings.memory_window_k == 5