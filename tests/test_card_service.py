from __future__ import annotations

import pytest

from src.services.card_service import CardService

RAW_CARDS_RESPONSE = {
    "cards": [
        {
            "name": "Pinguino Guerrero",
            "manaCost": "{1}{W}",
            "cmc": 2,
            "colors": ["White"],
            "type": "Creature - Warrior",
            "types": ["Creature"],
            "subtypes": ["Warrior"],
            "rarity": "Common",
            "set": "TST",
            "text": "Vigilance.",
            "power": "1",
            "toughness": "1",
            "imageUrl": "http://example.com/card1.png",
        },
        {
            "name": "Caballero Costoso",
            "manaCost": "{4}{W}",
            "cmc": 5,
            "colors": ["White"],
            "type": "Creature - Knight",
            "types": ["Creature"],
            "subtypes": ["Knight"],
            "rarity": "Rare",
            "set": "TST",
            "text": "First strike.",
            "power": "4",
            "toughness": "4",
            "imageUrl": "http://example.com/card2.png",
        },
    ]
}


class _FakeResponse:
    def __init__(self, payload: dict):
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


class _FakeAsyncClient:
    """Sustituye a httpx.AsyncClient como context manager async."""

    def __init__(self, payload: dict, *args, **kwargs):
        self._payload = payload

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def get(self, url, params=None):
        self.last_url = url
        self.last_params = params
        return _FakeResponse(self._payload)


@pytest.fixture
def card_service(test_settings) -> CardService:
    return CardService(test_settings)


@pytest.mark.asyncio
async def test_search_cards_returns_summaries(card_service, mocker):
    mocker.patch(
        "src.services.card_service.httpx.AsyncClient",
        lambda *a, **kw: _FakeAsyncClient(RAW_CARDS_RESPONSE, *a, **kw),
    )

    results = await card_service.search_cards(colors="White", page_size=5)

    assert len(results) == 2
    assert results[0]["name"] == "Pinguino Guerrero"
    # Solo campos "ligeros", no el objeto completo de la API.
    assert set(results[0].keys()) == {
        "name",
        "manaCost",
        "cmc",
        "colors",
        "type",
        "types",
        "subtypes",
        "rarity",
        "set",
        "text",
        "power",
        "toughness",
        "imageUrl",
    }


@pytest.mark.asyncio
async def test_search_cards_filters_by_max_cmc(card_service, mocker):
    mocker.patch(
        "src.services.card_service.httpx.AsyncClient",
        lambda *a, **kw: _FakeAsyncClient(RAW_CARDS_RESPONSE, *a, **kw),
    )

    # "coste inferior a 2" -> max_cmc=1 debe descartar la carta de cmc=5
    results = await card_service.search_cards(colors="White", max_cmc=2)

    assert len(results) == 1
    assert results[0]["name"] == "Pinguino Guerrero"


@pytest.mark.asyncio
async def test_search_cards_no_results(card_service, mocker):
    mocker.patch(
        "src.services.card_service.httpx.AsyncClient",
        lambda *a, **kw: _FakeAsyncClient({"cards": []}, *a, **kw),
    )

    results = await card_service.search_cards(name="CartaInexistente")

    assert results == []