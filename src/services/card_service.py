from __future__ import annotations

import logging
from typing import Any, Optional

import httpx

from src.config.config import Settings

logger = logging.getLogger(__name__)


class CardService:
    """Cliente de la API de cartas de magicthegathering.io."""

    def __init__(self, settings: Settings) -> None:
        self._base_url = settings.mtg_api_base_url.rstrip("/")

    async def search_cards(
        self,
        name: Optional[str] = None,
        colors: Optional[str] = None,
        color_identity: Optional[str] = None,
        type_: Optional[str] = None,
        subtypes: Optional[str] = None,
        max_cmc: Optional[float] = None,
        min_cmc: Optional[float] = None,
        page_size: int = 5,
    ) -> list[dict[str, Any]]:
        """
        Busca cartas según los filtros dados.

        La API de magicthegathering.io no soporta directamente "coste < X",
        así que cuando se indica `max_cmc`/`min_cmc` se sobre-pide
        (`pageSize` ampliado) y se filtra el campo `cmc` en el cliente.

        Devuelve una lista de diccionarios "ligeros" (solo los campos
        relevantes para el chatbot) para no saturar el prompt del LLM.
        """
        params: dict[str, Any] = {"pageSize": page_size}
        if name:
            params["name"] = name
        if colors:
            params["colors"] = colors
        if color_identity:
            params["colorIdentity"] = color_identity
        if type_:
            params["type"] = type_
        if subtypes:
            params["subtypes"] = subtypes

        needs_cmc_filter = max_cmc is not None or min_cmc is not None
        if needs_cmc_filter:
            # Pedimos más resultados de los necesarios porque luego
            # filtramos por cmc localmente.
            params["pageSize"] = max(page_size * 4, 20)

        url = f"{self._base_url}/cards"

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

        cards = data.get("cards", [])

        if needs_cmc_filter:
            cards = [
                card
                for card in cards
                if self._matches_cmc(card.get("cmc"), min_cmc, max_cmc)
            ]

        cards = cards[:page_size]
        return [self._to_summary(card) for card in cards]

    @staticmethod
    def _matches_cmc(
        cmc: Optional[float], min_cmc: Optional[float], max_cmc: Optional[float]
    ) -> bool:
        """Comprueba si el coste de maná convertido (cmc) está en rango."""
        if cmc is None:
            return False
        if min_cmc is not None and cmc < min_cmc:
            return False
        if max_cmc is not None and cmc > max_cmc:
            return False
        return True

    @staticmethod
    def _to_summary(card: dict[str, Any]) -> dict[str, Any]:
        """Reduce el objeto carta completo a los campos relevantes."""
        return {
            "name": card.get("name"),
            "manaCost": card.get("manaCost"),
            "cmc": card.get("cmc"),
            "colors": card.get("colors"),
            "type": card.get("type"),
            "types": card.get("types"),
            "subtypes": card.get("subtypes"),
            "rarity": card.get("rarity"),
            "set": card.get("set"),
            "text": card.get("text"),
            "power": card.get("power"),
            "toughness": card.get("toughness"),
            "imageUrl": card.get("imageUrl"),
        }