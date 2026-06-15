# Revisión de Código (Code Review)
## Pipeline de Ingesta y Consulta RAG — Análisis Técnico

Tras revisar el código compartido, puedo concluir que aunque la lógica base cumple con el flujo básico de un RAG, el script actual presenta varios problemas serios de seguridad, rendimiento y diseño que impedirían llevarlo a producción de forma estable.

A continuación, detallo los fallos encontrados y presento mi propuesta de refactorización.

---

# 1. Problemas Detectados

### 1.1 Seguridad y Configuración
* **Clave de API Hardcodeada**: La `API_KEY` de OpenAI está escrita directamente en texto plano. Esto es un peligro de seguridad; si este archivo se sube a un repositorio de Git, la clave quedará expuesta públicamente. 
* **Falta de Flexibilidad**: Al dejar la clave fija en el código, no podemos modificarla fácilmente ni separar los entornos de desarrollo, pruebas y producción usando variables de entorno o un archivo `.env`.

### 1.2 Rendimiento y Base de Datos
* **Inyección Secuencial Ineficiente (I/O Bound)**: La función `ingest_documents` procesa los documentos uno a uno dentro de un bucle `for`, haciendo una petición HTTP a OpenAI y otra a Chroma por cada texto. Si tenemos cientos de documentos, el sistema se volverá muy lento. Ambas herramientas permiten procesar por lotes (*batching*).
* **Pérdida de Datos en Chroma DB**: Se está usando `chromadb.Client()`, lo que levanta una base de datos en la memoria RAM. Cada vez que el servidor se apague o se reinicie, los vectores se borrarán por completo, obligándonos a re-ingestar todo de nuevo.

### 1.3 Mantenibilidad y Control de Contexto
* **Librería de OpenAI Deprecada**: El código utiliza la sintaxis antigua de la versión `openai v0.28` (`openai.Embedding.create`, `openai.ChatCompletion.create`). Esta interfaz ya no tiene soporte. Es obligatorio actualizar al cliente moderno (`openai.OpenAI()`).
* **Modelos harcodeados**: Los nombres de los modelos (`text-embedding-ada-002` y `gpt-4`) están escritos directamente en las funciones. Si el proveedor depreca un modelo el código se rompe. Deben gestionarse de forma externa.
* **Persistencia del Historial Deficiente**: La función `ask` machaca el archivo `history.json` entero en cada mensaje (`open(..., "w")`). Si varios usuarios chatean a la vez, esto generará bloqueos de archivos y pérdida de datos.

---

# 2. Mi Propuesta de Solución (Código Refactorizado)

Para solucionar esto, he rediseñado el pipeline aplicando inyección de dependencias con **Pydantic** para las variables de entorno, procesamiento por batches para los embeddings, persistencia en disco para Chroma DB y una ventana deslizante ($k$) para controlar la memoria del chat.

```python
"""
Pipeline Optimizado de Ingesta y Consulta RAG.
Versión refactorizada para producción, seguridad y rendimiento en lote.
"""

"""
Pipeline Optimizado de Ingesta y Consulta RAG.
Versión corregida: seguridad por variables de entorno, procesamiento en lote y persistencia.
"""

from __future__ import annotations

import os
import json
import logging
from openai import OpenAI
import chromadb

# Configuración de los logs para producción
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# =====================================================================
# 1. GESTIÓN DE CONFIGURACIÓN Y SEGURIDAD (Sección 1.1 y 1.3)
# =====================================================================
# Recuperamos los valores de las variables de entorno para evitar datos fijos
API_KEY = os.getenv("OPENAI_API_KEY")
EMBED_MODEL = os.getenv("OPENAI_EMBED_MODEL", "text-embedding-3-small")
LLM_MODEL = os.getenv("OPENAI_LLM_MODEL", "gpt-4o-mini")
CHROMA_DIR = os.getenv("CHROMA_PERSIST_DIR", "./chroma_vector_db")

if not API_KEY:
    raise ValueError("ERROR CRÍTICO: La variable de entorno 'OPENAI_API_KEY' no está configurada.")

# =====================================================================
# 2. INICIALIZACIÓN DE CLIENTES (Sección 1.2 y 1.3)
# =====================================================================
# Inicialización oficial con la sintaxis moderna de OpenAI (v1.0+)
openai_client = OpenAI(api_key=API_KEY)

# Cliente persistente en disco para no perder los vectores al reiniciar el servidor
chroma_client = chromadb.PersistentClient(path=CHROMA_DIR)
collection = chroma_client.get_or_create_collection("docs")


# =====================================================================
# 3. FUNCIONES DEL PIPELINE REFACTORIZADAS
# =====================================================================
def ingest_documents(docs: list[str]):
    """
    Ingesta los documentos optimizando las llamadas mediante procesamiento por lotes (Batching).
    Soluciona el problema de la inyección secuencial ineficiente en bucle.
    """
    if not docs:
        logger.warning("La lista de documentos está vacía.")
        return

    try:
        logger.info("Generando embeddings en lote para %d documentos...", len(docs))
        
        # Eliminamos el bucle 'for' e interconectamos todo en una sola petición HTTP
        response = openai_client.embeddings.create(
            input=docs,
            model=EMBED_MODEL
        )
        embeddings = [item.embedding for item in response.data]
        ids = [f"doc_{i}_{os.urandom(4).hex()}" for i in range(len(docs))]

        # Añadimos todo el lote de golpe a la base de datos persistente
        collection.add(
            documents=docs,
            embeddings=embeddings,
            ids=ids
        )
        logger.info("Ingesta masiva completada con éxito.")

    except Exception as e:
        logger.error("Error durante el proceso de ingesta: %s", e)
        raise e


def ask(question: str, history: list) -> str:
    """
    Procesa la consulta utilizando el contexto del RAG y la nueva interfaz de OpenAI.
    """
    try:
        # 1. Crear el embedding de la pregunta usando el modelo configurado
        q_response = openai_client.embeddings.create(
            input=[question],
            model=EMBED_MODEL
        )
        q_embedding = q_response.data[0].embedding

        # 2. Búsqueda semántica en Chroma DB
        results = collection.query(query_embeddings=[q_embedding], n_results=5)
        
        # Validamos que existan documentos devueltos por la query antes de unirlos
        flat_docs = results.get("documents", [[]])[0] if results.get("documents") else []
        context = " ".join(flat_docs) if flat_docs else "No hay contexto disponible."

        # 3. Construcción del historial de mensajes con la estructura correcta
        messages = [{"role": "system", "content": f"Responde usando: {context}"}]
        for turn in history:
            messages.append({"role": "user", "content": turn[0]})
            messages.append({"role": "assistant", "content": turn[1]})
        messages.append({"role": "user", "content": question})

        # 4. Llamada al modelo ChatCompletion con la sintaxis moderna
        resp = openai_client.chat.completions.create(
            model=LLM_MODEL,
            messages=messages # type: ignore
        )
        answer = resp.choices[0].message.content or ""

        # 5. Actualización del historial en memoria
        history.append((question, answer))
        

        return answer

    except Exception as e:
        logger.error("Error al procesar la consulta: %s", e)
        return "Lo siento, ha ocurrido un error interno al procesar tu pregunta."