"""
Tests de RAGService.

El LLM/embeddings/vector store reales NO se invocan: se mockean
`HuggingFaceEmbeddings`, `Chroma` y `PyPDFLoader` (sección 2.13 del
documento de arquitectura: "Vector store: para testear el service en
aislamiento puro").
"""

from __future__ import annotations

import os

import pytest
from langchain_core.documents import Document

from src.config.constant import METADATA_SECTION_KEY
from src.services.rag_service import RAGService


@pytest.fixture
def rag_service(mocker, test_settings):
    """RAGService con HuggingFaceEmbeddings mockeado (sin descargar modelo)."""
    mocker.patch("src.services.rag_service.HuggingFaceEmbeddings")
    return RAGService(test_settings)


class TestIndexExists:
    def test_returns_false_for_missing_directory(self, rag_service, tmp_path):
        missing_dir = str(tmp_path / "does_not_exist")
        assert rag_service._index_exists(missing_dir) is False

    def test_returns_false_for_empty_directory(self, rag_service, tmp_path):
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        assert rag_service._index_exists(str(empty_dir)) is False

    def test_returns_true_when_directory_has_files(self, rag_service, tmp_path):
        populated_dir = tmp_path / "populated"
        populated_dir.mkdir()
        (populated_dir / "chroma.sqlite3").write_text("fake")
        assert rag_service._index_exists(str(populated_dir)) is True


class TestLoadAndSplitPdf:
    def test_raises_if_pdf_missing(self, rag_service):
        with pytest.raises(FileNotFoundError):
            rag_service._load_and_split_pdf()

    def test_splits_and_tags_section_metadata(self, rag_service, mocker, tmp_path):
        # El PDF "existe" (solo necesitamos que exista el fichero).
        pdf_path = tmp_path / "magic_rules.pdf"
        pdf_path.write_text("fake pdf content")
        rag_service._settings.rules_pdf_path = str(pdf_path)

        long_text = "Frase. " * 200  # contenido suficiente para varios chunks
        fake_docs = [
            Document(page_content=long_text, metadata={"page": 0}),
            Document(page_content=long_text, metadata={"page": 1}),
        ]

        mock_loader = mocker.patch("src.services.rag_service.PyPDFLoader")
        mock_loader.return_value.load.return_value = fake_docs

        chunks = rag_service._load_and_split_pdf()

        assert len(chunks) > len(fake_docs)  # se ha fragmentado
        for chunk in chunks:
            assert METADATA_SECTION_KEY in chunk.metadata
            assert "pág." in chunk.metadata[METADATA_SECTION_KEY]


class TestRetrieve:
    def test_raises_if_index_not_loaded(self, rag_service):
        with pytest.raises(RuntimeError):
            rag_service.retrieve("¿qué fases tiene un turno?")

    def test_retrieve_delegates_to_vectorstore(self, rag_service):
        fake_vectorstore = type(
            "FakeVS",
            (),
            {
                "similarity_search": lambda self, query, k: [
                    Document(page_content="contenido", metadata={"section": "S1"})
                ]
            },
        )()
        rag_service._vectorstore = fake_vectorstore

        results = rag_service.retrieve("pregunta", k=2)

        assert len(results) == 1
        assert results[0].page_content == "contenido"


class TestLoadOrBuildIndex:
    def test_loads_existing_index(self, rag_service, mocker, tmp_path):
        persist_dir = tmp_path / "chroma_db"
        persist_dir.mkdir()
        (persist_dir / "chroma.sqlite3").write_text("fake")
        rag_service._settings.chroma_persist_dir = str(persist_dir)

        mock_chroma_cls = mocker.patch("src.services.rag_service.Chroma")

        rag_service.load_or_build_index()

        mock_chroma_cls.assert_called_once()
        mock_chroma_cls.from_documents.assert_not_called()
        assert rag_service.is_ready() is True

    def test_builds_index_when_missing(self, rag_service, mocker, tmp_path):
        persist_dir = tmp_path / "chroma_db_new"
        rag_service._settings.chroma_persist_dir = str(persist_dir)

        pdf_path = tmp_path / "magic_rules.pdf"
        pdf_path.write_text("fake pdf content")
        rag_service._settings.rules_pdf_path = str(pdf_path)

        mocker.patch.object(
            rag_service,
            "_load_and_split_pdf",
            return_value=[Document(page_content="contenido", metadata={})],
        )
        mock_chroma_cls = mocker.patch("src.services.rag_service.Chroma")

        rag_service.load_or_build_index()

        mock_chroma_cls.from_documents.assert_called_once()
        assert rag_service.is_ready() is True