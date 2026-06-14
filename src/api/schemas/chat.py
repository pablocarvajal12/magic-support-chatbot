from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from src.config.constant import MAX_MESSAGE_LENGTH, SYSTEM_STATUS

class ChatRequest(BaseModel):
    """Petición entrante al endpoint /chat."""

    session_id: Optional[str] = Field(
        default=None,
        description=(
            "Identificador de la sesión de conversación. "
            "Si es null, el backend crea una nueva sesión y devuelve su id. "
        ),
        examples=["3fa85f64-5717-4562-b3fc-2c963f66afa6"],
    )
    message: str = Field(
        ...,
        min_length=1,
        max_length=MAX_MESSAGE_LENGTH,
        description="Mensaje del usuario.",
        examples=["¿Qué fases tiene un turno?"],
    )


class ChatResponse(BaseModel):
    """Respuesta del endpoint /chat."""

    session_id: str = Field(
        ..., description="Identificador de la sesión (nuevo o existente)."
    )
    response: str = Field(..., description="Respuesta generada por el agente.")
    sources: list[str] = Field(
        default_factory=list
    )


class HealthResponse(BaseModel):
    """Respuesta del endpoint de health check."""

    status: str = SYSTEM_STATUS
    app_name: str