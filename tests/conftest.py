"""Fixtures compartidas para la suite de tests."""

from __future__ import annotations

import pytest

from src.config.config import Settings


@pytest.fixture
def test_settings(tmp_path) -> Settings:
    """
    Settings de test: usa rutas temporales para Chroma/PDF y una
    groq_api_key ficticia (no se realiza ninguna llamada real a Groq
    en los tests, siempre se mockea el LLM/agente).
    """
    return Settings(
        groq_api_key="test-key",
        chroma_persist_dir=str(tmp_path / "chroma_db"),
        rules_pdf_path=str(tmp_path / "magic_rules.pdf"),
        memory_window_k=10,
        retrieval_k=4,
    )
