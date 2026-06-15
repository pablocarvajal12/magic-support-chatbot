"""
ChatService — Orquestador de lógica de negocio y estado conversacional.
Administra las sesiones concurrentes, encapsula la ventana de memoria (k=10)
y ejecuta el bucle interactivo del agente inteligente (AgentExecutor).
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Optional

from langchain.agents import AgentExecutor
from langchain_core.chat_history import BaseChatMessageHistory
from langchain_community.chat_message_histories import ChatMessageHistory

from src.config.config import Settings
from src.agents.magic_agent import create_magic_agent
from src.agents.tools import create_magic_tools
from src.services.rag_service import RAGService
from src.services.card_service import CardService

logger = logging.getLogger(__name__)


class ChatService:
    """
    Servicio encargado de coordinar las sesiones de chat y la ejecución del agente.
    Mantiene un diccionario en memoria con el historial de cada hilo aislado.
    """

    def __init__(
        self, 
        settings: Settings, 
        rag_service: RAGService, 
        card_service: CardService
    ) -> None:
        self._settings = settings
        self._rag_service = rag_service
        self._card_service = card_service
        
        # Almacén local de sesiones (En producción migraría a Redis)
        self._session_store: dict[str, BaseChatMessageHistory] = {}
        
        # Instanciar el agente base y las herramientas correspondientes
        self._agent = create_magic_agent(settings, rag_service, card_service)
        self._tools = create_magic_tools(rag_service, card_service)
        
        # Ensamblar el ejecutor oficial de LangChain que controla el bucle interactivo
        self._executor = AgentExecutor(
            agent=self._agent,
            tools=self._tools,
            verbose=True,
            handle_parsing_errors=True,
        )

    def _get_session_history(self, session_id: str) -> BaseChatMessageHistory:
        """
        Recupera o inicializa el contenedor del historial para un identificador de sesión único.
        """
        if session_id not in self._session_store:
            logger.info("Creando nuevo almacén de memoria local para la sesión: %s", session_id)
            self._session_store[session_id] = ChatMessageHistory()
        return self._session_store[session_id]

    def _apply_sliding_window(self, history: BaseChatMessageHistory) -> list[Any]:
        """
        Implementa la ventana deslizante (Window Buffer Memory) de retención.
        Limita el contexto enviado al LLM a los últimos k turnos (mensajes de usuario + bot).
        Multiplicamos por 2 porque un turno completo consta de pregunta y respuesta.
        """
        max_messages = self._settings.memory_window_k * 2
        messages = history.messages
        if len(messages) > max_messages:
            # Retorna únicamente el segmento final más reciente para no saturar el prompt
            return messages[-max_messages:]
        return list(messages)

    async def execute_chat_turn(
        self, 
        message: str, 
        session_id: Optional[str] = None
    ) -> tuple[str, str, list[str]]:
        """
        Procesa de principio a fin un turno completo de conversación.
        
        Devuelve una tupla con:
          - El session_id (confirmado o recién generado).
          - El texto final redactado por el bot.
          - Una lista con las citas/fuentes de datos que alimentaron la respuesta.
        """
        # 1. Garantizar la existencia del identificador de sesión
        active_session_id = session_id or str(uuid.uuid4())
        history = self._get_session_history(active_session_id)
        
        # 2. Extraer el segmento acotado por la ventana deslizante
        truncated_history = self._apply_sliding_window(history)
        
        logger.info("Procesando consulta para la sesión '%s'. Historial retenido: %d mensajes.", 
                    active_session_id, len(truncated_history))
        
        try:
            # 3. Lanzar la consulta de manera asíncrona al AgentExecutor
            # Pasamos tanto el input del usuario como el historial acotado
            response_chunks = await self._executor.ainvoke({
                "input": message,
                "chat_history": truncated_history
            })
            
            output_text = response_chunks.get("output", "")
            
            # 4. Extraer las fuentes utilizadas analizando los pasos intermedios de las herramientas
            sources = []
            intermediate_steps = response_chunks.get("intermediate_steps", [])
            for action, observation in intermediate_steps:
                # Si se ejecutó una búsqueda en el RAG, leemos las fuentes desde el texto devuelto
                if action.tool == "magic_rules_search" and isinstance(observation, str):
                    # Extraer patrones de tipo [1] Fuente: ...
                    for line in observation.splitlines():
                        if "Fuente:" in line:
                            source_label = line.split("Fuente:", 1)[1].strip()
                            if source_label not in sources:
                                sources.append(source_label)
                # Si se consultó la API de cartas, marcamos la API como fuente oficial
                elif action.tool == "card_search":
                    sources.append("Base de datos oficial (API magicthegathering.io)")
            
            # 5. Persistir el intercambio actual de forma permanente en el historial de la sesión
            history.add_user_message(message)
            history.add_ai_message(output_text)
            
            return active_session_id, output_text, sources

        except Exception as e:
            logger.error("Fallo crítico en la ejecución del turno de chat: %s", str(e), exc_info=True)
            raise e