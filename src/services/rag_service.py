from __future__ import annotations

import logging
import os
from typing import Optional

from langchain_chroma import Chroma
from langchain_community.document_loaders import PyPDFLoader
from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from src.config.config import Settings
from src.config.constant import DEFAULT_SOURCE_LABEL, METADATA_SECTION_KEY

logger = logging.getLogger(__name__)


class RAGService:
    """
    Encapsula el índice vectorial del reglamento de Magic: The Gathering.

    Uso:
        rag = RAGService(settings)
        rag.load_or_build_index()
        docs = rag.retrieve("¿Cómo funciona la fase de combate?")
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._embeddings = HuggingFaceEmbeddings(
            model_name=settings.embedding_model
        )
        self._vectorstore: Optional[Chroma] = None

    # ------------------------------------------------------------------
    # Ciclo de vida del índice
    # ------------------------------------------------------------------
    def load_or_build_index(self) -> None:
        """
        Carga el índice persistido si existe; si no, lo construye desde
        el PDF de reglas y lo persiste en disco.

        Este método se llama una sola vez, durante el lifespan/startup
        de la app FastAPI (ver src/main.py).
        """
        persist_dir = self._settings.chroma_persist_dir

        if self._index_exists(persist_dir):
            logger.info("Cargando índice Chroma existente desde '%s'", persist_dir)
            self._vectorstore = Chroma(
                persist_directory=persist_dir,
                embedding_function=self._embeddings,
                collection_name=self._settings.chroma_collection_name,
            )
            return

        logger.info(
            "No se encontró índice en '%s'. Construyendo desde '%s'...",
            persist_dir,
            self._settings.rules_pdf_path,
        )
        documents = self._load_and_split_pdf()
        self._vectorstore = Chroma.from_documents(
            documents=documents,
            embedding=self._embeddings,
            persist_directory=persist_dir,
            collection_name=self._settings.chroma_collection_name,
        )
        logger.info("Índice construido con %d chunks.", len(documents))

    @staticmethod
    def _index_exists(persist_dir: str) -> bool:
        """Comprueba si ya existe un índice Chroma persistido en disco."""
        return os.path.isdir(persist_dir) and len(os.listdir(persist_dir)) > 0

    # ------------------------------------------------------------------
    # Indexación
    # ------------------------------------------------------------------
    def _load_and_split_pdf(self) -> list[Document]:
        """
        Carga el PDF de reglas y lo divide en chunks con overlap.

        `chunk_overlap=50` garantiza que una regla situada en el límite
        entre dos chunks aparezca en ambos, reduciendo el riesgo de que
        el LLM pierda contexto relevante.
        """
        pdf_path = self._settings.rules_pdf_path
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(
                f"No se encontró el PDF de reglas en '{pdf_path}'. "
                "Coloca el reglamento en esa ruta o ajusta RULES_PDF_PATH."
            )

        loader = PyPDFLoader(pdf_path)
        raw_documents = loader.load()

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=self._settings.chunk_size,
            chunk_overlap=self._settings.chunk_overlap,
        )
        chunks = splitter.split_documents(raw_documents)

        # Normalizamos metadatos: cada chunk debe poder identificar su
        # fuente para que el endpoint /chat pueda rellenar `sources`.
        for chunk in chunks:
            page = chunk.metadata.get("page")
            section_label = DEFAULT_SOURCE_LABEL
            if page is not None:
                section_label = f"{DEFAULT_SOURCE_LABEL} (pág. {page + 1})"
            chunk.metadata[METADATA_SECTION_KEY] = section_label

        return chunks

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------
    def retrieve(self, query: str, k: Optional[int] = None) -> list[Document]:
        """
        Recupera los `k` chunks más relevantes para la query dada.

        `k=4` (configurable) es suficiente contexto sin saturar el prompt
        del LLM (ver sección 2.4 del documento de arquitectura).
        """
        if self._vectorstore is None:
            raise RuntimeError(
                "El índice RAG no está inicializado. "
                "Llama a load_or_build_index() primero."
            )

        top_k = k or self._settings.retrieval_k
        return self._vectorstore.similarity_search(query, k=top_k)

    def is_ready(self) -> bool:
        """Indica si el índice está cargado y listo para servir queries."""
        return self._vectorstore is not None