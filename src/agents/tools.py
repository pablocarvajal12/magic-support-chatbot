"""
Tools del Agente — Abstracciones funcionales nativas (Tool-Calling)
Permiten al orquestador (LLM) invocar servicios internos de forma determinista.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from src.config.constant import TOOL_RULES_SEARCH, TOOL_CARD_SEARCH, TOOL_CARD_CREATOR
from src.services.rag_service import RAGService
from src.services.card_service import CardService

logger = logging.getLogger(__name__)


class RulesSearchInput(BaseModel):
    query: str = Field(
        ..., 
        description="Consulta semántica en lenguaje natural sobre las reglas oficiales de Magic, fases del turno o mecánicas."
    )

class CardSearchInput(BaseModel):
    name: Optional[str] = Field(None, description="Nombre exacto o parcial de la carta en inglés.")
    colors: Optional[str] = Field(None, description="Colores separados por coma (e.g., 'White,Blue').")
    type_: Optional[str] = Field(None, description="Tipo de carta (e.g., 'Creature', 'Instant').")
    max_cmc: Optional[float] = Field(None, description="Coste de maná convertido (CMC) máximo.")

class CardCreatorInput(BaseModel):
    name: str = Field(..., description="Nombre de la carta personalizada.")
    mana_cost: str = Field(..., description="Coste de maná con formato oficial (e.g., '{1}{W}{B}').")
    type_line: str = Field(..., description="Línea de tipo completa (e.g., 'Legendary Creature - Vampire').")
    text: str = Field(..., description="Texto de reglas, habilidades y efectos de la carta.")
    power: Optional[str] = Field(None, description="Fuerza de la criatura si aplica (e.g., '3').")
    toughness: Optional[str] = Field(None, description="Resistencia de la criatura si aplica (e.g., '4').")
    rarity: str = Field("Rare", description="Rareza de la carta (Common, Uncommon, Rare, Mythic).")


# =====================================================================
# 2. FABRICA DE TOOLS
# =====================================================================

def create_magic_tools(rag_service: RAGService, card_service: CardService) -> list[Any]:
    """
    Inyecta dinámicamente las dependencias de los servicios en las herramientas de LangChain.
    Retorna la lista de herramientas listas para ser vinculadas (.bind_tools) al LLM.
    """

    @tool(TOOL_RULES_SEARCH, args_schema=RulesSearchInput)
    def magic_rules_search(query: str) -> str:
        """
        Busca de manera semántica en el reglamento oficial de Magic: The Gathering.
        Úsala cuando el usuario tenga dudas sobre tiempos, prioridades, fases o palabras clave.
        """
        try:
            logger.info("Invocando tool '%s' con query: %s", TOOL_RULES_SEARCH, query)
            docs = rag_service.retrieve(query)
            if not docs:
                return "No se encontraron reglas específicas en el documento para esta consulta."
            
            # Formateamos los resultados para el contexto denso del LLM
            formatted_chunks = []
            for i, doc in enumerate(docs, 1):
                source = doc.metadata.get("section", "Reglamento Oficial")
                formatted_chunks.append(f"[{i}] Fuente: {source}\nContenido:\n{doc.page_content}")
            
            return "\n\n---\n\n".join(formatted_chunks)
        except Exception as e:
            logger.error("Error en tool %s: %s", TOOL_RULES_SEARCH, str(e), exc_info=True)
            return f"Error al acceder a la base de conocimiento de reglas: {str(e)}"


    @tool(TOOL_CARD_SEARCH, args_schema=CardSearchInput)
    async def card_search(
        name: Optional[str] = None,
        colors: Optional[str] = None,
        type_: Optional[str] = None,
        max_cmc: Optional[float] = None,
    ) -> str:
        """
        Consulta la base de datos oficial para validar la existencia, atributos, textos e imágenes de cartas reales.
        """
        try:
            logger.info("Invocando tool '%s' de manera asíncrona.", TOOL_CARD_SEARCH)
            cards = await card_service.search_cards(
                name=name,
                colors=colors,
                type_=type_,
                max_cmc=max_cmc
            )
            if not cards:
                return "No se encontraron cartas oficiales que coincidan con los criterios especificados."
            
            return json.dumps(cards, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error("Error en tool %s: %s", TOOL_CARD_SEARCH, str(e), exc_info=True)
            return f"Error al consultar la API externa de cartas: {str(e)}"


    @tool(TOOL_CARD_CREATOR, args_schema=CardCreatorInput)
    def card_creator(
        name: str,
        mana_cost: str,
        type_line: str,
        text: str,
        power: Optional[str] = None,
        toughness: Optional[str] = None,
        rarity: str = "Rare"
    ) -> str:
        """
        Genera una estructura estructurada JSON limpia bajo un esquema estricto de Magic.
        Úsala únicamente cuando el usuario solicite explícitamente diseñar, inventar o crear una carta personalizada.
        """
        logger.info("Invocando tool '%s' para la carta custom: %s", TOOL_CARD_CREATOR, name)
        custom_card = {
            "custom_card_v1": {
                "name": name,
                "manaCost": mana_cost,
                "typeLine": type_line,
                "text": text,
                "rarity": rarity,
                "stats": {"power": power, "toughness": toughness} if power or toughness else None
            }
        }
        return json.dumps(custom_card, indent=2, ensure_ascii=False)

    return [magic_rules_search, card_search, card_creator]