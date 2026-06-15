"""
MagicAgent — Orquestación del Agente Inteligente basado en Tool-Calling.
Configura el LLM (Groq/Llama-3.1), inyecta las directrices de negocio mediante el
System Prompt y ensambla la cadena de ejecución interactiva.
"""

from __future__ import annotations

import logging
from typing import Any
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import Runnable
from langchain_groq import ChatGroq

from src.config.config import Settings
from src.agents.tools import create_magic_tools
from src.services.rag_service import RAGService
from src.services.card_service import CardService

logger = logging.getLogger(__name__)


def create_magic_agent(
    settings: Settings, 
    rag_service: RAGService, 
    card_service: CardService
) -> Runnable:
    """
    Construye y retorna el agente ejecutor (`Runnable`) con soporte nativo de Tool-Calling.
    
    Aplica las políticas estrictas de la sección 2.8 del manual de arquitectura:
      - Filtro de Dominio (solo Magic: The Gathering).
      - Cita obligatoria de fuentes procedentes del RAG.
      - Honestidad técnica ante la incertidumbre.
    """
    logger.info("Inicializando MagicAgent con modelo: %s", settings.groq_model)

    # 1. Instanciar el LLM optimizado en Groq
    llm = ChatGroq(
        groq_api_key=settings.groq_api_key,
        model_name=settings.groq_model,
        temperature=settings.groq_temperature,
    )

    # 2. Fabricar las herramientas e integrarlas con los esquemas del modelo de forma nativa
    tools = create_magic_tools(rag_service, card_service)
    llm_with_tools = llm.bind_tools(tools)

    # 3. Definición del System Prompt (Guardrails y Directrices)
    system_prompt = (
        "Eres el asistente conversacional autónomo experto del 'Sistema Automatizado de Atención y Soporte "
        "— Magic TCG Chatbot'. Tu objetivo es resolver consultas sobre reglas, mecánicas y cartas del juego "
        "Magic: The Gathering de manera profesional, estructurada y concisa.\n\n"
        
        "RESTRICCIONES Y POLÍTICAS OPERATIVAS ESTRICTAS:\n"
        "1. FILTRO DE DOMINIO: Rechaza de manera explícita, cortés pero firme, cualquier interacción, "
        "pregunta o discusión ajena a la temática oficial de Magic: The Gathering (por ejemplo, política, "
        "otros juegos de cartas, etc.).\n"
        
        "2. CITA OBLIGATORIA DE FUENTES: Cuando utilices la herramienta de búsqueda de reglas "
        "('magic_rules_search'), es MANDATORIO que referencies en tu respuesta final el apartado, regla "
        "o número de página exacto provisto en los metadatos del contexto (e.g., '[Reglamento Oficial (pág. 12)]').\n"
        
        "3. TRANSPARENCIA OPERATIVA (NO ALUCINAR): Si el usuario te hace una pregunta compleja de reglas y al "
        "consultar la base de datos vectorial no obtienes información o el contexto es insuficiente, declara "
        "la falta de información de manera honesta (e.g., 'No dispongo de datos oficiales en mi manual para "
        "responder con total certeza'). Jamás inventes reglamentaciones ficticias.\n"
        
        "4. DISEÑO DE CARTAS PERSONALIZADAS: Si el usuario te pide crear, inventar o diseñar una carta, debes "
        "invocar de forma obligatoria la herramienta 'card_creator' para generar su estructura estructurada limpia.\n\n"
        
        "Flujo de trabajo: Evalúa el mensaje del usuario, invoca las herramientas necesarias en paralelo si "
        "se requiere, consolida el contexto extraído y redacta tu respuesta final justificada en castellano."
    )

    # 4. Construcción del Prompt de estructura de chat de LangChain
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        # Espacio reservado para el historial de conversación (Window Buffer Memory) gestionado aguas arriba
        MessagesPlaceholder(variable_name="chat_history"),
        ("human", "{input}"),
        # Espacio donde el agente guardará sus llamadas intermedias a herramientas y respuestas de estas
        MessagesPlaceholder(variable_name="agent_scratchpad"),
    ])

    # 5. Ensamblar la cadena de ejecución del agente (Runnable)
    # Nota: Usamos la sintaxis moderna basada en componentes funcionales en lugar del clásico AgentExecutor heredado.
    from langchain.agents.format_scratchpad.openai_tools import format_to_openai_tool_messages
    from langchain.agents.output_parsers.openai_tools import OpenAIToolsAgentOutputParser

    agent = (
        {
            "input": lambda x: x["input"],
            "chat_history": lambda x: x.get("chat_history", []),
            "agent_scratchpad": lambda x: format_to_openai_tool_messages(x["intermediate_steps"]),
        }
        | prompt
        | llm_with_tools
        | OpenAIToolsAgentOutputParser()
    )

    return agent