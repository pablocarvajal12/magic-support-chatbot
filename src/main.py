from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.config.config import get_settings
from src.routers.chat import router as chat_router
from src.services.rag_service import RAGService
from src.services.card_service import CardService
from src.services.chat_service import ChatService

# Configuración básica de logs de la aplicación
settings = get_settings()
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app_fastapi: FastAPI) -> AsyncGenerator[None, None]:
    """
    Gestión del Ciclo de Vida (Lifespan) de la Aplicación.
    Ejecuta tareas críticas de inicio (bootstrap) y de apagado del servidor.
    """
    logger.info("=== Iniciando secuencia de arranque del Magic Chatbot Backend ===")
    app_settings = get_settings()

    # 1. Instanciar e indexar la base de datos vectorial (Chroma)
    rag_service = RAGService(app_settings)
    try:
        # Carga desde disco o lee el PDF y genera los embeddings locales de forma centralizada
        rag_service.load_or_build_index()
    except Exception as e:
        logger.critical("Fallo crítico: No se pudo construir o cargar el índice RAG: %s", str(e))
        # No detenemos el arranque para permitir que endpoints de diagnóstico como /health respondan,
        # pero el sistema quedará en modo degradado.

    # 2. Instanciar los clientes HTTP de servicios externos
    card_service = CardService(app_settings)

    # 3. Ensamblar el orquestador principal (ChatService) y persistirlo en el estado global
    chat_service = ChatService(app_settings, rag_service, card_service)
    app_fastapi.state.chat_service = chat_service

    logger.info("=== Backend listo y escuchando peticiones entrantes ===")
    
    yield  # Aquí se detiene la ejecución mientras la app está corriendo
    
    logger.info("=== Apagando el servidor... Limpiando recursos y conexiones ===")


# Inicialización oficial de la app de FastAPI vinculando el ciclo de vida
app = FastAPI(
    title=settings.app_name,
    description="API REST que expone la lógica del Agente Inteligente del Reglamento de Magic.",
    version="1.0.0",
    lifespan=lifespan
)

# Configuración de CORS para permitir la conexión fluida del frontend en Streamlit
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En producción acotar al dominio del frontend
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Registro de rutas modulares bajo el prefijo unificado de la sección 2.6
app.include_router(chat_router, prefix=settings.api_v1_prefix)