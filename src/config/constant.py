# --- Nombres de las tools del agente ---
TOOL_RULES_SEARCH = "magic_rules_search"
TOOL_CARD_SEARCH = "card_search"
TOOL_CARD_CREATOR = "card_creator"

# --- Metadatos de los chunks del RAG ---
METADATA_SOURCE_KEY = "source"
METADATA_SECTION_KEY = "section"
DEFAULT_SOURCE_LABEL = "Reglamento de Magic: The Gathering"

# --- Mensajes ---
ERROR_EMPTY_MESSAGE = "El campo 'message' no puede estar vacío."
ERROR_AGENT_FAILURE = (
    "No he podido procesar tu consulta en este momento. "
    "Un agente humano revisará tu caso."
)
SYSTEM_STATUS = "APP is UP | Last commit: feat: add chat service"

# --- Límites ---
MAX_MESSAGE_LENGTH = 2000