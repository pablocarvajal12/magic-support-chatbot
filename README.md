# Magic TCG Chatbot — Demo

Asistente conversacional para el call center de soporte de Magic: The
Gathering. Resuelve dudas de reglas (RAG sobre el reglamento oficial),
busca cartas reales (API magicthegathering.io) y genera cartas custom,
manteniendo el hilo de la conversación.

El diseño completo (decisiones técnicas, alternativas consideradas,
arquitectura productiva, monitorización, etc.) está documentado en
`docs/arquitectura.md`.

## Estructura del proyecto

\`\`\`text
magic-chatbot/
├── app/
│   ├── routers/         # Endpoints (chat.py)
│   └── schemas/         # DTOs (ChatRequest, ChatResponse)
│   ├── services/             # rag_service, card_service, chat_service
│   ├── agents/                # magic_agent + tools/
│   ├── config/                  # config.py (Settings), constants.py
│   └── main.py                # App FastAPI + lifespan
├── tests/                     # pytest + mocks
├── frontend/
│   └── streamlit.py       # Demo UI (desacoplada vía HTTP)
├── data/
│   └── magic_rules.pdf        # Reglamento oficial (no incluido en git)
├── docs/
│   └── decisions.md       # Documento de decisiones técnicas
├── .env.example
└── requirements.txt
\`\`\`

## Requisitos previos

- Python 3.11+
- Una API key de Groq (https://console.groq.com/keys)
- El PDF del reglamento de Magic: The Gathering en `data/magic_rules.pdf`

## Instalación

\`\`\`bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

\`\`\`powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt


cp .env.example .env
# editar .env y añadir GROQ_API_KEY
\`\`\`

## Ejecución

### Backend (FastAPI)

\`\`\`powershell
uvicorn src.main:app
\`\`\`

La primera vez, el backend indexará `data/magic_rules.pdf` en Chroma
(`./chroma_db`). En arranques posteriores, el índice se carga desde
disco (patrón load-or-create, ver documento de arquitectura).

### Frontend (Streamlit)

\`\`\`powershell
streamlit run frontend/streamlit.py
\`\`\`

## Tests

\`\`\`bash
pytest
\`\`\`

Todas las dependencias externas (LLM, vector store, API de cartas) están
mockeadas; los tests no requieren `GROQ_API_KEY` real ni acceso a red.

## Endpoints

- `POST /api/v1/chat` — endpoint conversacional único.

  Request:
{
  "session_id": "8fa21b44-2391-4cfd-b6a8-a3f1146522ef",
  "response": "Al comienzo de la partida, cada jugador roba una mano inicial de siete cartas (Regla 103.4).",
  "sources": [
    "Section 103.4 - Magic Comprehensive Rules.pdf"
  ]
}

  Response:
{
  "session_id": "8fa21b44-2391-4cfd-b6a8-a3f1146522ef",
  "response": "Al comienzo de la partida, cada jugador roba una mano inicial de siete cartas (Regla 103.4).",
  "sources": [
    "Section 103.4 - Magic Comprehensive Rules.pdf"
  ]
}

## Ejemplos desde la interfaz
. Ejemplo desde la Interfaz Web (Streamlit)

Una vez abierta la interfaz, puedes interactuar de forma natural utilizando consultas complejas de juego:

    Búsqueda de cartas (API externa): Busca la carta llamada Black Lotus y muéstrame su texto.

    Creación de cartas personalizadas (JSON Creator): Diseña una carta de criatura dragón roja legendaria que cueste 5 manás.

    Consulta de reglas (RAG): ¿Qué ocurre si ataco con una criatura con dañar primero y mi oponente bloquea con una normal?



- `GET /api/v1/health` — health check.