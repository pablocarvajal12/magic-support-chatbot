"""
Tests de integración de la API utilizando TestClient de FastAPI.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from src.main import app
from src.config.config import get_settings


@pytest.fixture
def api_client() -> TestClient:
    """Genera un cliente de pruebas HTTP conectado a la app."""
    return TestClient(app)


def test_health_endpoint(api_client):
    """Valida que el endpoint público de health check responda correctamente."""
    settings = get_settings()
    prefix = settings.api_v1_prefix
    
    response = api_client.get(f"{prefix}/health")
    
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert data["app_name"] == settings.app_name


def test_chat_endpoint_validation_error(api_client):
    """Verifica que Pydantic y FastAPI rechacen strings vacíos con un código 422."""
    settings = get_settings()
    prefix = settings.api_v1_prefix
    
    # Intentamos mandar un cuerpo inválido (message vacío)
    payload = {
        "session_id": "test-session",
        "message": ""
    }
    
    response = api_client.post(f"{prefix}/chat", json=payload)
    assert response.status_code == 422