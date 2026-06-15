"""
Router de la API — Endpoints de comunicación para el chatbot.
Expone los puntos de entrada HTTP y delega la ejecución en el ChatService.
"""

from __future__ import annotations

import logging
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Request, status

from src.schemas.chat import ChatRequest, ChatResponse, HealthResponse
from src.config.config import Settings, get_settings
from src.services.chat_service import ChatService

logger = logging.getLogger(__name__)
router = APIRouter()


# Inyección de dependencias corregida usando el objeto Request nativo de FastAPI
async def get_chat_service(request: Request) -> ChatService:
    """
    Recupera la instancia única (Singleton) de ChatService del estado de la aplicación
    a través del objeto Request, evitando importaciones circulares con main.py.
    """
    if not hasattr(request.app.state, "chat_service"):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="El servicio de chat no está inicializado en el servidor."
        )
    return request.app.state.chat_service


@router.post(
    "/chat", 
    response_model=ChatResponse, 
    status_code=status.HTTP_200_OK,
    summary="Enviar un mensaje al agente experto en Magic"
)
async def chat_endpoint(
    request_data: ChatRequest,
    chat_service: Annotated[ChatService, Depends(get_chat_service)]
) -> ChatResponse:
    """
    Procesa un turno de conversación de forma asíncrona.
    Recibe la pregunta del usuario y el ID de sesión, y retorna la respuesta con sus fuentes.
    """
    if not request_data.message.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="El mensaje del usuario no puede contener únicamente espacios en blanco."
        )
    
    try:
        session_id, response_text, sources = await chat_service.execute_chat_turn(
            message=request_data.message,
            session_id=request_data.session_id
        )
        
        return ChatResponse(
            session_id=session_id,
            response=response_text,
            sources=sources
        )
    except Exception as e:
        logger.error("Error controlado en el endpoint /chat: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error interno al procesar la solicitud por el agente: {str(e)}"
        )


@router.get(
    "/health", 
    response_model=HealthResponse, 
    status_code=status.HTTP_200_OK,
    summary="Verificar el estado de salud y versión del backend"
)
async def health_endpoint(
    settings: Annotated[Settings, Depends(get_settings)]
) -> HealthResponse:
    """Retorna el estado operativo actual de la aplicación."""
    return HealthResponse(app_name=settings.app_name)