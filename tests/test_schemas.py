"""
Tests de los DTOs de la API (`src/api/schemas/chat.py`).

Validan las reglas de Pydantic que usará FastAPI para devolver 422
automáticamente ante peticiones inválidas (mensaje vacío o demasiado
largo), y los valores por defecto de las respuestas.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.api.schemas.chat import ChatRequest, ChatResponse, HealthResponse
from src.config.constant import MAX_MESSAGE_LENGTH


class TestChatRequest:
    def test_session_id_is_optional(self):
        request = ChatRequest(message="¿Qué fases tiene un turno?")
        assert request.session_id is None
        assert request.message == "¿Qué fases tiene un turno?"

    def test_accepts_existing_session_id(self):
        request = ChatRequest(session_id="session-123", message="hola")
        assert request.session_id == "session-123"

    def test_rejects_empty_message(self):
        with pytest.raises(ValidationError):
            ChatRequest(message="")

    def test_rejects_message_over_max_length(self):
        too_long = "a" * (MAX_MESSAGE_LENGTH + 1)
        with pytest.raises(ValidationError):
            ChatRequest(message=too_long)

    def test_accepts_message_at_max_length(self):
        exactly_max = "a" * MAX_MESSAGE_LENGTH
        request = ChatRequest(message=exactly_max)
        assert len(request.message) == MAX_MESSAGE_LENGTH

    def test_requires_message_field(self):
        with pytest.raises(ValidationError):
            ChatRequest()


class TestChatResponse:
    def test_sources_default_to_empty_list(self):
        response = ChatResponse(session_id="session-123", response="texto")
        assert response.sources == []

    def test_accepts_sources(self):
        response = ChatResponse(
            session_id="session-123",
            response="texto",
            sources=["Reglamento (pág. 12)"],
        )
        assert response.sources == ["Reglamento (pág. 12)"]


class TestHealthResponse:
    def test_status_defaults_to_ok(self):
        health = HealthResponse(app_name="Magic Chatbot")
        assert health.app_name == "Magic Chatbot"