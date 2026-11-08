import csv
import io
import json
import os
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field

# Parsers
try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None

try:
    import docx
except ImportError:
    docx = None

try:
    import openpyxl
except ImportError:
    openpyxl = None

try:
    from pptx import Presentation
except ImportError:
    Presentation = None


class ExtractedTable(BaseModel):
    table_index: int
    headers: List[str] = Field(default_factory=list)
    rows: List[List[str]] = Field(default_factory=list)
    sheet_or_page: Optional[str] = None
    markdown: str = ""


class DocumentContent(BaseModel):
    file_name: str
    file_type: str
    text_content: str
    tables: List[ExtractedTable] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    page_count: int = 1
    total_words: int = 0


class DocumentComparisonResult(BaseModel):
    document_1_name: str
    document_2_name: str
    summary_doc_1: str
    summary_doc_2: str
    key_similarities: List[str] = Field(default_factory=list)
    key_differences: List[str] = Field(default_factory=list)
    metric_comparisons: List[Dict[str, Any]] = Field(default_factory=list)
    conclusion: str = ""


class DocumentIntelligenceService:
    """Enterprise document intelligence engine supporting multi-format parsing,

    table extraction, comparative analysis, and RAG ingestion.
    """

    SUPPORTED_EXTENSIONS = {"pdf", "docx", "xlsx", "csv", "pptx", "txt", "json", "md"}

    @classmethod
    def parse_file(cls, file_path: str, original_filename: Optional[str] = None) -> DocumentContent:
        """Parse file content and extract structured text, metadata, and tables."""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        name = original_filename or os.path.basename(file_path)
        ext = name.split(".")[-1].lower() if "." in name else "txt"

        if ext == "pdf":
            return cls._parse_pdf(file_path, name)
        elif ext == "docx":
            return cls._parse_docx(file_path, name)
        elif ext == "xlsx":
            return cls._parse_xlsx(file_path, name)
        elif ext == "csv":
            return cls._parse_csv(file_path, name)
        elif ext == "pptx":
            return cls._parse_pptx(file_path, name)
        elif ext == "json":
            return cls._parse_json(file_path, name)
        else:
            return cls._parse_text(file_path, name, ext)

    @classmethod
    def _parse_pdf(cls, file_path: str, name: str) -> DocumentContent:
        if not PdfReader:
            raise RuntimeError("pypdf library is not installed.")

        reader = PdfReader(file_path)
        pages_text = []
        for i, page in enumerate(reader.pages):
            text = page.extract_text() or ""
            pages_text.append(f"--- Page {i + 1} ---\n{text.strip()}")

        full_text = "\n\n".join(pages_text)
        metadata = {
            "title": reader.metadata.title if reader.metadata else None,
            "author": reader.metadata.author if reader.metadata else None,
            "total_pages": len(reader.pages)
        }

        return DocumentContent(
            file_name=name,
            file_type="pdf",
            text_content=full_text,
            metadata=metadata,
            page_count=len(reader.pages),
            total_words=len(full_text.split())
        )

    @classmethod
    def _parse_docx(cls, file_path: str, name: str) -> DocumentContent:
        if not docx:
            raise RuntimeError("python-docx library is not installed.")

        doc = docx.Document(file_path)
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        full_text = "\n\n".join(paragraphs)

        extracted_tables = []
        for idx, table in enumerate(doc.tables):
            rows_data = []
            for row in table.rows:
                rows_data.append([cell.text.strip() for cell in row.cells])
            if rows_data:
                headers = rows_data[0]
                body_rows = rows_data[1:] if len(rows_data) > 1 else []
                md_table = cls._rows_to_markdown(headers, body_rows)
                extracted_tables.append(ExtractedTable(
                    table_index=idx + 1,
                    headers=headers,
                    rows=body_rows,
                    markdown=md_table
                ))

        return DocumentContent(
            file_name=name,
            file_type="docx",
            text_content=full_text,
            tables=extracted_tables,
            page_count=max(1, len(paragraphs) // 10),
            total_words=len(full_text.split())
        )

    @classmethod
    def _parse_xlsx(cls, file_path: str, name: str) -> DocumentContent:
        if not openpyxl:
            raise RuntimeError("openpyxl library is not installed.")

        wb = openpyxl.load_workbook(file_path, data_only=True)
        extracted_tables = []
        all_text_sections = []

        for idx, sheet_name in enumerate(wb.sheetnames):
            sheet = wb[sheet_name]
            rows_data = []
            for row in sheet.iter_rows(values_only=True):
                # Filter rows that have at least one non-None cell
                str_row = [str(cell) if cell is not None else "" for cell in row]
                if any(c.strip() for c in str_row):
                    rows_data.append(str_row)

            if rows_data:
                headers = rows_data[0]
                body_rows = rows_data[1:] if len(rows_data) > 1 else []
                md_table = cls._rows_to_markdown(headers, body_rows[:50])  # preview top 50 in md
                extracted_tables.append(ExtractedTable(
                    table_index=idx + 1,
                    sheet_or_page=sheet_name,
                    headers=headers,
                    rows=body_rows,
                    markdown=md_table
                ))
                all_text_sections.append(f"Sheet: {sheet_name}\nHeaders: {', '.join(headers)}\nRows: {len(body_rows)}")

        full_text = "\n\n".join(all_text_sections)
        return DocumentContent(
            file_name=name,
            file_type="xlsx",
            text_content=full_text,
            tables=extracted_tables,
            page_count=len(wb.sheetnames),
            total_words=len(full_text.split())
        )

    @classmethod
    def _parse_csv(cls, file_path: str, name: str) -> DocumentContent:
        rows_data = []
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            reader = csv.reader(f)
            for row in reader:
                rows_data.append([c.strip() for c in row])

        headers = rows_data[0] if rows_data else []
        body_rows = rows_data[1:] if len(rows_data) > 1 else []
        md_table = cls._rows_to_markdown(headers, body_rows[:50])

        table = ExtractedTable(
            table_index=1,
            headers=headers,
            rows=body_rows,
            markdown=md_table
        )

        preview_text = f"CSV Document: {name}\nColumns: {', '.join(headers)}\nTotal Records: {len(body_rows)}"
        return DocumentContent(
            file_name=name,
            file_type="csv",
            text_content=preview_text,
            tables=[table],
            page_count=1,
            total_words=len(preview_text.split())
        )

    @classmethod
    def _parse_pptx(cls, file_path: str, name: str) -> DocumentContent:
        if not Presentation:
            raise RuntimeError("python-pptx library is not installed.")

        prs = Presentation(file_path)
        slides_text = []

        for i, slide in enumerate(prs.slides):
            slide_parts = [f"--- Slide {i + 1} ---"]
            for shape in slide.shapes:
                if shape.has_text_frame:
                    for paragraph in shape.text_frame.paragraphs:
                        if paragraph.text.strip():
                            slide_parts.append(paragraph.text.strip())
            slides_text.append("\n".join(slide_parts))

        full_text = "\n\n".join(slides_text)
        return DocumentContent(
            file_name=name,
            file_type="pptx",
            text_content=full_text,
            page_count=len(prs.slides),
            total_words=len(full_text.split())
        )

    @classmethod
    def _parse_json(cls, file_path: str, name: str) -> DocumentContent:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            data = json.load(f)
        formatted_json = json.dumps(data, indent=2)
        return DocumentContent(
            file_name=name,
            file_type="json",
            text_content=formatted_json,
            metadata={"is_array": isinstance(data, list), "key_count": len(data) if isinstance(data, dict) else len(data)},
            page_count=1,
            total_words=len(formatted_json.split())
        )

    @classmethod
    def _parse_text(cls, file_path: str, name: str, ext: str) -> DocumentContent:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            text = f.read()
        return DocumentContent(
            file_name=name,
            file_type=ext,
            text_content=text,
            page_count=max(1, len(text.splitlines()) // 40),
            total_words=len(text.split())
        )

    @classmethod
    def _rows_to_markdown(cls, headers: List[str], rows: List[List[str]]) -> str:
        """Convert rows to standard GitHub-flavored Markdown table."""
        if not headers and not rows:
            return ""

        clean_headers = [h.replace("|", "\\|") for h in (headers or [f"Col {i+1}" for i in range(len(rows[0]))])]
        lines = [
            "| " + " | ".join(clean_headers) + " |",
            "| " + " | ".join(["---"] * len(clean_headers)) + " |"
        ]

        for r in rows:
            # Pad row if shorter than headers
            padded = r + [""] * max(0, len(clean_headers) - len(r))
            clean_cells = [cell.replace("|", "\\|").replace("\n", " ") for cell in padded[:len(clean_headers)]]
            lines.append("| " + " | ".join(clean_cells) + " |")

        return "\n".join(lines)

    @classmethod
    def compare_documents(
        cls,
        doc1: DocumentContent,
        doc2: DocumentContent,
        focus_topic: Optional[str] = None
    ) -> DocumentComparisonResult:
        """Rule-based comparative analysis and metric comparison between two documents."""
        words1 = set(doc1.text_content.lower().split())
        words2 = set(doc2.text_content.lower().split())

        overlap = words1.intersection(words2)
        unique_1 = words1 - words2
        unique_2 = words2 - words1

        # Key metrics
        metrics = [
            {
                "metric": "Total Word Count",
                "doc_1": doc1.total_words,
                "doc_2": doc2.total_words,
                "difference": doc1.total_words - doc2.total_words
            },
            {
                "metric": "Page Count",
                "doc_1": doc1.page_count,
                "doc_2": doc2.page_count,
                "difference": doc1.page_count - doc2.page_count
            },
            {
                "metric": "Extracted Tables",
                "doc_1": len(doc1.tables),
                "doc_2": len(doc2.tables),
                "difference": len(doc1.tables) - len(doc2.tables)
            }
        ]

        similarities = [
            f"Both documents share core vocabulary of {len(overlap)} distinct terms.",
            f"Document formats: '{doc1.file_type.upper()}' and '{doc2.file_type.upper()}'.",
        ]
        if focus_topic:
            similarities.append(f"Comparative focus: {focus_topic}")

        differences = [
            f"'{doc1.file_name}' contains {len(unique_1)} terms unique to its context.",
            f"'{doc2.file_name}' contains {len(unique_2)} terms unique to its context.",
            f"Size delta: Document 1 has {doc1.total_words} words vs Document 2 with {doc2.total_words} words."
        ]

        summary_1 = f"Document 1 ({doc1.file_name}) has {doc1.page_count} page(s) and {len(doc1.tables)} table(s)."
        summary_2 = f"Document 2 ({doc2.file_name}) has {doc2.page_count} page(s) and {len(doc2.tables)} table(s)."
        conclusion = (
            f"Comparison completed between '{doc1.file_name}' and '{doc2.file_name}'. "
            f"Both documents show {len(overlap)} shared concepts with distinct structural layouts."
        )

        return DocumentComparisonResult(
            document_1_name=doc1.file_name,
            document_2_name=doc2.file_name,
            summary_doc_1=summary_1,
            summary_doc_2=summary_2,
            key_similarities=similarities,
            key_differences=differences,
            metric_comparisons=metrics,
            conclusion=conclusion
        )


document_intelligence_service = DocumentIntelligenceService()
