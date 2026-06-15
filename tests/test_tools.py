"""
Tests unitarios y de integración simulada para las Tools del Agente.
"""

from __future__ import annotations

import json
import pytest
from langchain_core.documents import Document
from src.agents.tools import create_magic_tools
from src.config.constant import TOOL_RULES_SEARCH, TOOL_CARD_SEARCH, TOOL_CARD_CREATOR


# =====================================================================
# MOCKS / FAKES DE SERVICIOS
# =====================================================================

class FakeRAGService:
    def __init__(self, should_return_data: bool = True):
        self.should_return_data = should_return_data

    def retrieve(self, query: str, k=None) -> list[Document]:
        if not self.should_return_data:
            return []
        return [
            Document(
                page_content="Regla 502.1: El paso de enderezar no usa la prioridad.",
                metadata={"section": "Reglamento de Magic: The Gathering (pág. 45)"}
            )
        ]

class FakeCardService:
    def __init__(self, should_return_data: bool = True):
        self.should_return_data = should_return_data

    async def search_cards(self, **kwargs) -> list[dict]:
        if not self.should_return_data:
            return []
        return [{
            "name": "Black Lotus",
            "manaCost": "{0}",
            "type": "Artifact",
            "text": "Sacrifice Black Lotus: Add three mana of any one color."
        }]


# =====================================================================
# SUITE DE PRUEBAS
# =====================================================================

def test_tools_initialization():
    """Valida que la fábrica instancie y asigne los nombres correctos a las herramientas."""
    tools = create_magic_tools(FakeRAGService(), FakeCardService())
    
    assert len(tools) == 3
    tool_names = {t.name for t in tools}
    assert tool_names == {TOOL_RULES_SEARCH, TOOL_CARD_SEARCH, TOOL_CARD_CREATOR}


def test_magic_rules_search_success():
    """Verifica el parseo y formateado de los chunks recuperados por el RAG."""
    tools = create_magic_tools(FakeRAGService(), FakeCardService())
    rules_tool = next(t for t in tools if t.name == TOOL_RULES_SEARCH)
    
    result = rules_tool.invoke({"query": "fase de enderezar"})
    
    assert "Regla 502.1" in result
    assert "pág. 45" in result


def test_magic_rules_search_empty():
    """Verifica la respuesta controlada cuando el RAG no encuentra coincidencias."""
    tools = create_magic_tools(FakeRAGService(should_return_data=False), FakeCardService())
    rules_tool = next(t for t in tools if t.name == TOOL_RULES_SEARCH)
    
    result = rules_tool.invoke({"query": "MecánicaInexistente"})
    assert "No se encontraron reglas específicas" in result


@pytest.mark.asyncio
async def test_card_search_success():
    """Verifica que la herramienta asíncrona de búsqueda de cartas devuelva un JSON correcto."""
    tools = create_magic_tools(FakeRAGService(), FakeCardService())
    card_tool = next(t for t in tools if t.name == TOOL_CARD_SEARCH)
    
    # Invocamos asíncronamente a través de .ainvoke por ser una tool async
    result_str = await card_tool.ainvoke({"name": "Black Lotus"})
    result = json.loads(result_str)
    
    assert isinstance(result, list)
    assert result[0]["name"] == "Black Lotus"
    assert "Artifact" in result[0]["type"]


def test_card_creator_json_generation():
    """Valida el output estructurado del generador de cartas personalizadas."""
    tools = create_magic_tools(FakeRAGService(), FakeCardService())
    creator_tool = next(t for t in tools if t.name == TOOL_CARD_CREATOR)
    
    payload = {
        "name": "Sliver Supremo",
        "mana_cost": "{W}{U}{B}{R}{G}",
        "type_line": "Creature - Sliver",
        "text": "All Slivers have flying.",
        "power": "5",
        "toughness": "5"
    }
    
    result_str = creator_tool.invoke(payload)
    result = json.loads(result_str)
    
    assert "custom_card_v1" in result
    assert result["custom_card_v1"]["name"] == "Sliver Supremo"
    assert result["custom_card_v1"]["stats"]["power"] == "5"