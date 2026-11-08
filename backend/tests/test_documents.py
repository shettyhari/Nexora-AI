import csv
import json
import os
import tempfile
import pytest
from app.services.document.document_service import document_intelligence_service


@pytest.mark.asyncio
async def test_parse_csv_and_extract_tables():
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".csv", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Model", "Provider", "Context Window", "Price per 1M"])
        writer.writerow(["nexora-flagship", "Nexora", "128000", "$2.50"])
        writer.writerow(["gpt-4o", "OpenAI", "128000", "$5.00"])
        writer.writerow(["claude-3-5-sonnet", "Anthropic", "200000", "$3.00"])
        tmp_path = f.name

    try:
        doc = document_intelligence_service.parse_file(tmp_path, "ai_models.csv")
        assert doc.file_name == "ai_models.csv"
        assert doc.file_type == "csv"
        assert len(doc.tables) == 1
        table = doc.tables[0]
        assert table.headers == ["Model", "Provider", "Context Window", "Price per 1M"]
        assert len(table.rows) == 3
        assert "| Model | Provider |" in table.markdown
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


@pytest.mark.asyncio
async def test_parse_json_document():
    data = {
        "project": "NEXORA AI",
        "version": "1.0.0",
        "agents": ["research", "coding", "vision", "orchestrator"],
        "active": True
    }
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json", encoding="utf-8") as f:
        json.dump(data, f)
        tmp_path = f.name

    try:
        doc = document_intelligence_service.parse_file(tmp_path, "config.json")
        assert doc.file_type == "json"
        assert "NEXORA AI" in doc.text_content
        assert doc.metadata.get("key_count") == 4
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


@pytest.mark.asyncio
async def test_compare_two_documents():
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt", encoding="utf-8") as f1:
        f1.write("Nexora AI architecture provides high-performance model routing, semantic memory, and RAG search.")
        doc1_path = f1.name

    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt", encoding="utf-8") as f2:
        f2.write("Nexora multimodal engine provides image OCR, video timestamp analysis, and multi-agent coordination.")
        doc2_path = f2.name

    try:
        doc1 = document_intelligence_service.parse_file(doc1_path, "architecture.txt")
        doc2 = document_intelligence_service.parse_file(doc2_path, "multimodal.txt")
        comp = document_intelligence_service.compare_documents(doc1, doc2, focus_topic="Architecture Evolution")

        assert comp.document_1_name == "architecture.txt"
        assert comp.document_2_name == "multimodal.txt"
        assert len(comp.key_similarities) >= 2
        assert len(comp.key_differences) >= 2
        assert len(comp.metric_comparisons) == 3
    finally:
        if os.path.exists(doc1_path):
            os.remove(doc1_path)
        if os.path.exists(doc2_path):
            os.remove(doc2_path)
