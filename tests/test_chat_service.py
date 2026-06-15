"""
Tests unitarios y de integración simulada para el ChatService.
"""

from __future__ import annotations

import pytest
from langchain_core.documents import Document
from src.config.config import Settings
from src.services.chat_service import ChatService
from langchain.agents import AgentExecutor

# =====================================================================
# CONFIGURACIÓN DE ENTORNO DE PRUEBAS CONTROLADO
# =====================================================================

class MinimalRAGMock:
    def retrieve(self, q, k=None):
        return [Document(page_content="Regla de prueba", metadata={"section": "Manual Pag 5"})]

class MinimalCardMock:
    async def search_cards(self, **k):
        return [{"name": "Mock Card"}]


@pytest.fixture
def test_settings_chat() -> Settings:
    return Settings(
        groq_api_key="gsk_mock_key_abc123",
        groq_model="llama-3.1-70b-versatile",
        memory_window_k=2  # Forzamos una ventana pequeña para probar el recorte con facilidad
    )


# =====================================================================
# SUITE DE PRUEBAS UNITARIAS
# =====================================================================

def test_session_isolation(test_settings_chat):
    """Garantiza que el almacén cree hilos de memoria independientes y aislados."""
    service = ChatService(test_settings_chat, MinimalRAGMock(), MinimalCardMock()) # type: ignore
    
    hist1 = service._get_session_history("id-1")
    hist2 = service._get_session_history("id-2")
    
    hist1.add_user_message("Hola")
    
    assert len(hist1.messages) == 1
    assert len(hist2.messages) == 0


def test_sliding_window_truncation(test_settings_chat):
    """Verifica que la ventana deslizante trunque correctamente cuando se supera la constante k."""
    service = ChatService(test_settings_chat, MinimalRAGMock(), MinimalCardMock()) # type: ignore
    history = service._get_session_history("id-prueba")
    
    # Añadimos 6 mensajes (3 turnos completos). Como memory_window_k=2, el límite son 4 mensajes.
    for i in range(3):
        history.add_user_message(f"Mensaje de usuario {i}")
        history.add_ai_message(f"Respuesta del bot {i}")
        
    truncated = service._apply_sliding_window(history)
    
    assert len(truncated) == 4
    # Comprobar que retiene los elementos más recientes en el tiempo
    assert truncated[0].content == "Mensaje de usuario 1"
    assert truncated[-1].content == "Respuesta del bot 2"


@pytest.mark.asyncio
async def test_execute_chat_turn_generates_session_id(test_settings_chat, mocker):
    """Valida que si no se provee session_id, el servicio genere uno dinámicamente usando un UUID."""
    # Simulamos la respuesta del AgentExecutor para aislar el test de Groq
    mocker.patch.object(
        AgentExecutor, 
        "ainvoke", 
        return_value={"output": "Respuesta simulada", "intermediate_steps": []}
    )
    
    service = ChatService(test_settings_chat, MinimalRAGMock(), MinimalCardMock()) # type: ignore
    
    session_id, response, sources = await service.execute_chat_turn("Hola bot", session_id=None)
    
    assert session_id is not None
    assert isinstance(session_id, str)
    assert response == "Respuesta simulada"
    assert sources == []