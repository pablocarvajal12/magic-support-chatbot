"""
Frontend Streamlit — Interfaz gráfica de usuario para la demo del Magic Chatbot.
Consume los servicios expuestos por el backend de FastAPI de forma desacoplada.
"""

from __future__ import annotations

import logging
import os
import requests
import streamlit as st

# Configuración básica de logs para el frontend
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# =====================================================================
# 1. CONFIGURACIÓN DE LA PÁGINA Y ESTILOS
# =====================================================================
st.set_page_config(
    page_title="Magic TCG Chatbot",
    page_icon="🃏",
    layout="centered",
    initial_sidebar_state="expanded"
)

# Variables de configuración (URLs del Backend)
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
API_PREFIX = os.getenv("API_V1_PREFIX", "/api/v1")
CHAT_ENDPOINT = f"{BACKEND_URL}{API_PREFIX}/chat"
HEALTH_ENDPOINT = f"{BACKEND_URL}{API_PREFIX}/health"

# =====================================================================
# 2. ESTADO DE LA SESIÓN (PERSISTENCIA LOCAL)
# =====================================================================
if "session_id" not in st.session_state:
    st.session_state.session_id = None

if "messages" not in st.session_state:
    # Historial de renderizado en pantalla para la UI de Streamlit
    st.session_state.messages = []

# =====================================================================
# 3. BARRA LATERAL (CONTROL Y DIAGNÓSTICO)
# =====================================================================
with st.sidebar:
    st.title("⚙️ Panel de Control")
    st.markdown("---")
    
    # Botón para limpiar el hilo actual y forzar una nueva sesión
    if st.button("🗑️ Limpiar Conversación", use_container_width=True):
        st.session_state.session_id = None
        st.session_state.messages = []
        st.rerun()
        
    st.markdown("---")
    st.subheader("🌐 Estado del Sistema")
    
    # Verificación de conectividad en tiempo real con el Backend de FastAPI
    try:
        response = requests.get(HEALTH_ENDPOINT, timeout=3.0)
        if response.status_code == 200:
            st.success("Backend: ONLINE")
            data = response.json()
            st.caption(f"**Status:** {data.get('status', 'N/A')}")
        else:
            st.error(f"Backend: ERROR ({response.status_code})")
    except requests.exceptions.RequestException:
        st.error("Backend: OFFLINE (Inalcanzable)")

    st.markdown("---")
    st.caption("🤖 **Magic TCG Chatbot v1.0.0**\n\nBasado en Llama-3.1-70B sobre Groq LPUs y Chroma DB local.")

# =====================================================================
# 4. ÁREA PRINCIPAL DE CHAT
# =====================================================================
st.title("🪄 Magic TCG Chatbot")
st.markdown(
    "Bienvenido al asistente experto en el reglamento oficial e interacciones de **Magic: The Gathering**. "
    "Pregúntame sobre fases del turno, prioridades, palabras clave o pídeme buscar y diseñar cartas."
)

# Renderizar los mensajes previos almacenados en la sesión local
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        # Si el mensaje del bot contenía fuentes extraídas, las mostramos en un desplegable
        if msg["role"] == "assistant" and msg.get("sources"):
            with st.expander("📚 Fuentes y Documentación Consultada"):
                for source in msg["sources"]:
                    st.markdown(f"- {source}")

# Captura de la entrada de texto del usuario
if user_input := st.chat_input("¿Qué ocurre si ataco con una criatura con dañar primero y otra normal?"):
    
    # 1. Mostrar inmediatamente el mensaje del usuario en la pantalla
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)
        
    # 2. Llamada interactiva al Backend de FastAPI
    with st.chat_message("assistant"):
        response_placeholder = st.empty()
        spinner_placeholder = st.spinner("Pensando y consultando las fuentes oficiales...")
        
        payload = {
            "session_id": st.session_state.session_id,
            "message": user_input
        }
        
        try:
            with spinner_placeholder:
                res = requests.post(CHAT_ENDPOINT, json=payload, timeout=15.0)
                
            if res.status_code == 200:
                data = res.json()
                
                # Sincronizar el identificador de sesión retornado por el backend
                st.session_state.session_id = data.get("session_id")
                
                bot_response = data.get("response", "")
                sources = data.get("sources", [])
                
                # Renderizar la respuesta final en la UI
                response_placeholder.markdown(bot_response)
                
                if sources:
                    with st.expander("📚 Fuentes y Documentación Consultada"):
                        for source in sources:
                            st.markdown(f"- {source}")
                            
                # Guardar en el estado local de la sesión para persistir el renderizado
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": bot_response,
                    "sources": sources
                })
                
            else:
                error_msg = f"⚠️ Ocurrió un error en el servidor (Código {res.status_code})."
                response_placeholder.error(error_msg)
                logger.error("Error en respuesta del backend: %s", res.text)
                
        except requests.exceptions.Timeout:
            response_placeholder.error("🕒 El servidor tardó demasiado en responder (Timeout).")
        except requests.exceptions.ConnectionError:
            response_placeholder.error("🔌 No se pudo establecer conexión con el backend de FastAPI. ¿Está encendido?")
        except Exception as e:
            response_placeholder.error(f"❌ Error inesperado: {str(e)}")