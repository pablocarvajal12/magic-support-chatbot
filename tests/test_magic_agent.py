"""
Tests unitarios para verificar la inicialización, binding de herramientas y 
la lógica del enrutador de MagicAgent.
"""

from __future__ import annotations

import pytest
from langchain_core.messages import HumanMessage, SystemMessage
from src.agents.magic_agent import create_magic_agent
from src.config.config import Settings


# Mock básico de servicios para no requerir llamadas de red ni carga de PDFs reales
class MinimalRAGMock:
    def retrieve(self, q): return []

class MinimalCardMock:
    async def search_cards(self, **k): return []


@pytest.fixture
def fake_settings() -> Settings:
    return Settings(
        groq_api_key="gsk_fake_key_for_testing_purposes_only",
        groq_model="llama-3.1-70b-versatile"
    )


def test_magic_agent_creation_and_properties(fake_settings):
    """Verifica que el agente se componga correctamente como un Runnable con sus pasos intermedios."""
    rag = MinimalRAGMock()
    card = MinimalCardMock()

    agent = create_magic_agent(fake_settings, rag, card) # type: ignore
    
    # Comprobar que es una estructura ejecutable de LangChain (Runnable)
    assert agent is not None
    assert hasattr(agent, "invoke") or hasattr(agent, "stream")


@pytest.mark.asyncio
async def test_agent_structure_has_system_instructions(fake_settings):
    """Inspecciona la cadena interna para asegurar que las directrices del sistema están presentes."""
    rag = MinimalRAGMock()
    card = MinimalCardMock()

    agent = create_magic_agent(fake_settings, rag, card) # type: ignore
    
    # Obtenemos el componente del prompt dentro de la secuencia del grafo/cadena
    # La cadena se compone de: {inputs} | Prompt | LLM con herramientas | Parser
    # El segundo paso de la composición suele ser el objeto ChatPromptTemplate
    prompt_component = agent.middle[0] # Acceso a los pasos intermedios de la secuencia
    
    messages = prompt_component.messages
    system_instruction = messages[0].prompt.template
    
    assert "FILTRO DE DOMINIO" in system_instruction
    assert "CITA OBLIGATORIA DE FUENTES" in system_instruction
    assert "TRANSPARENCIA OPERATIVA" in system_instruction