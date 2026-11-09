import json
import time
from typing import Any, Dict, List, Optional
from app.core.security_guards import ensure_safe_storage_path
from app.services.document.document_service import document_intelligence_service
from app.services.multimodal.image_service import image_intelligence_service
from app.services.multimodal.video_service import video_intelligence_service
from app.services.research.research_service import web_research_service
from app.services.tools.base import BaseTool, ToolExecutionContext, ToolExecutionResult, ToolPermissionLevel
from app.services.tools.sandbox import isolated_sandbox


class WebSearchTool(BaseTool):
    tool_id = "web_search"
    name = "Web Search"
    description = "Search the public web for real-time information, documentation, and technical references."
    permission_level = ToolPermissionLevel.READ
    requires_approval = False
    input_schema = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "The search keywords or query."},
            "max_results": {"type": "integer", "default": 5, "description": "Maximum number of results to return."}
        },
        "required": ["query"]
    }
    output_schema = {
        "type": "object",
        "properties": {
            "results": {"type": "array"}
        }
    }

    async def execute(self, params: Dict[str, Any], context: ToolExecutionContext) -> ToolExecutionResult:
        start = time.time()
        query = params.get("query", "")
        max_results = params.get("max_results", 5)
        try:
            results = await web_research_service.search_web(query, max_results=max_results)
            return ToolExecutionResult(
                tool_id=self.tool_id,
                status="completed",
                output={"query": query, "results": [r.dict() for r in results]},
                execution_time_ms=(time.time() - start) * 1000,
                permission_level=self.permission_level
            )
        except Exception as e:
            return ToolExecutionResult(
                tool_id=self.tool_id,
                status="failed",
                error=str(e),
                execution_time_ms=(time.time() - start) * 1000,
                permission_level=self.permission_level
            )


class WebExtractTool(BaseTool):
    tool_id = "web_extract"
    name = "Web Page Extractor"
    description = "Safely retrieve and extract text from an external web page with strict SSRF defense."
    permission_level = ToolPermissionLevel.READ
    requires_approval = False
    input_schema = {
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "The public HTTP/HTTPS URL to fetch."}
        },
        "required": ["url"]
    }
    output_schema = {"type": "object"}

    async def execute(self, params: Dict[str, Any], context: ToolExecutionContext) -> ToolExecutionResult:
        start = time.time()
        url = params.get("url", "")
        try:
            page_data = await web_research_service.fetch_page(url)
            return ToolExecutionResult(
                tool_id=self.tool_id,
                status="completed" if page_data.get("success") else "failed",
                output=page_data,
                error=page_data.get("error"),
                execution_time_ms=(time.time() - start) * 1000,
                permission_level=self.permission_level
            )
        except Exception as e:
            return ToolExecutionResult(
                tool_id=self.tool_id,
                status="failed",
                error=str(e),
                execution_time_ms=(time.time() - start) * 1000,
                permission_level=self.permission_level
            )


class DocumentExtractTool(BaseTool):
    tool_id = "document_extract"
    name = "Document Parser"
    description = "Extract text, metadata, and structured tables from PDF, DOCX, XLSX, CSV, PPTX, TXT, or JSON."
    permission_level = ToolPermissionLevel.ANALYZE
    requires_approval = False
    input_schema = {
        "type": "object",
        "properties": {
            "file_path": {"type": "string", "description": "Absolute path to the document file."},
            "file_name": {"type": "string", "description": "Original file name."}
        },
        "required": ["file_path"]
    }
    output_schema = {"type": "object"}

    async def execute(self, params: Dict[str, Any], context: ToolExecutionContext) -> ToolExecutionResult:
        start = time.time()
        path = params.get("file_path", "")
        name = params.get("file_name")
        try:
            safe_path = ensure_safe_storage_path(path)
            doc = document_intelligence_service.parse_file(safe_path, name)
            return ToolExecutionResult(
                tool_id=self.tool_id,
                status="completed",
                output={
                    "file_name": doc.file_name,
                    "file_type": doc.file_type,
                    "page_count": doc.page_count,
                    "total_words": doc.total_words,
                    "table_count": len(doc.tables),
                    "text_preview": doc.text_content[:2000],
                    "tables": [t.dict() for t in doc.tables]
                },
                execution_time_ms=(time.time() - start) * 1000,
                permission_level=self.permission_level
            )
        except Exception as e:
            return ToolExecutionResult(
                tool_id=self.tool_id,
                status="failed",
                error=str(e),
                execution_time_ms=(time.time() - start) * 1000,
                permission_level=self.permission_level
            )


class DocumentCompareTool(BaseTool):
    tool_id = "document_compare"
    name = "Document Comparator"
    description = "Compare two documents side-by-side, analyze similarities, differences, and structural metrics."
    permission_level = ToolPermissionLevel.ANALYZE
    requires_approval = False
    input_schema = {
        "type": "object",
        "properties": {
            "file_path_1": {"type": "string", "description": "Path to first document."},
            "file_path_2": {"type": "string", "description": "Path to second document."},
            "focus_topic": {"type": "string", "description": "Optional focus area for comparison."}
        },
        "required": ["file_path_1", "file_path_2"]
    }
    output_schema = {"type": "object"}

    async def execute(self, params: Dict[str, Any], context: ToolExecutionContext) -> ToolExecutionResult:
        start = time.time()
        try:
            safe_p1 = ensure_safe_storage_path(params["file_path_1"])
            safe_p2 = ensure_safe_storage_path(params["file_path_2"])
            doc1 = document_intelligence_service.parse_file(safe_p1)
            doc2 = document_intelligence_service.parse_file(safe_p2)
            comp = document_intelligence_service.compare_documents(doc1, doc2, params.get("focus_topic"))
            return ToolExecutionResult(
                tool_id=self.tool_id,
                status="completed",
                output=comp.dict(),
                execution_time_ms=(time.time() - start) * 1000,
                permission_level=self.permission_level
            )
        except Exception as e:
            return ToolExecutionResult(
                tool_id=self.tool_id,
                status="failed",
                error=str(e),
                execution_time_ms=(time.time() - start) * 1000,
                permission_level=self.permission_level
            )


class DataVisualizerTool(BaseTool):
    tool_id = "data_visualizer"
    name = "Data Visualizer & Chart Generator"
    description = "Analyze structured tabular records and produce interactive chart configuration specifications."
    permission_level = ToolPermissionLevel.ANALYZE
    requires_approval = False
    input_schema = {
        "type": "object",
        "properties": {
            "chart_type": {"type": "string", "enum": ["bar", "line", "pie", "scatter", "table"]},
            "title": {"type": "string"},
            "labels": {"type": "array", "items": {"type": "string"}},
            "datasets": {"type": "array", "items": {"type": "object"}}
        },
        "required": ["chart_type", "title", "labels", "datasets"]
    }
    output_schema = {"type": "object"}

    async def execute(self, params: Dict[str, Any], context: ToolExecutionContext) -> ToolExecutionResult:
        start = time.time()
        chart_spec = {
            "chart_type": params.get("chart_type", "bar"),
            "title": params.get("title", "Dataset Visualization"),
            "labels": params.get("labels", []),
            "datasets": params.get("datasets", []),
            "rendered_at": time.time()
        }
        return ToolExecutionResult(
            tool_id=self.tool_id,
            status="completed",
            output=chart_spec,
            execution_time_ms=(time.time() - start) * 1000,
            permission_level=self.permission_level
        )


class OCRImageTool(BaseTool):
    tool_id = "ocr_image_reader"
    name = "Image OCR & Vision Reader"
    description = "Read text, analyze charts, diagrams, or UI screenshots from an image file."
    permission_level = ToolPermissionLevel.ANALYZE
    requires_approval = False
    input_schema = {
        "type": "object",
        "properties": {
            "file_path": {"type": "string", "description": "Absolute path to the image file."},
            "analysis_type": {"type": "string", "enum": ["general", "ocr", "chart", "diagram", "screenshot"]},
            "prompt": {"type": "string"}
        },
        "required": ["file_path"]
    }
    output_schema = {"type": "object"}

    async def execute(self, params: Dict[str, Any], context: ToolExecutionContext) -> ToolExecutionResult:
        start = time.time()
        try:
            safe_path = ensure_safe_storage_path(params["file_path"])
            res = await image_intelligence_service.analyze_image(
                file_path=safe_path,
                prompt=params.get("prompt", "Analyze this image."),
                analysis_type=params.get("analysis_type", "general")
            )
            return ToolExecutionResult(
                tool_id=self.tool_id,
                status="completed",
                output=res.dict(),
                execution_time_ms=(time.time() - start) * 1000,
                permission_level=self.permission_level
            )
        except Exception as e:
            return ToolExecutionResult(
                tool_id=self.tool_id,
                status="failed",
                error=str(e),
                execution_time_ms=(time.time() - start) * 1000,
                permission_level=self.permission_level
            )


class PythonInterpreterTool(BaseTool):
    tool_id = "python_interpreter"
    name = "Isolated Python Interpreter"
    description = "Execute trusted mathematical, data processing, and analytical Python code in a safe sandbox."
    permission_level = ToolPermissionLevel.EXECUTE
    requires_approval = True
    input_schema = {
        "type": "object",
        "properties": {
            "code": {"type": "string", "description": "Python source code to execute."},
            "timeout_seconds": {"type": "number", "default": 10.0}
        },
        "required": ["code"]
    }
    output_schema = {"type": "object"}

    async def execute(self, params: Dict[str, Any], context: ToolExecutionContext) -> ToolExecutionResult:
        start = time.time()
        code = params.get("code", "")
        timeout = float(params.get("timeout_seconds", 10.0))

        # Check explicit approval gate if configured
        if self.requires_approval and not context.is_approved:
            return ToolExecutionResult(
                tool_id=self.tool_id,
                status="pending_approval",
                output={"code_preview": code[:300], "message": "Sensitive execution requires explicit user authorization."},
                execution_time_ms=(time.time() - start) * 1000,
                permission_level=self.permission_level,
                requires_approval=True
            )

        # Run safely inside isolated sandbox
        res = isolated_sandbox.run_code(code, timeout_seconds=timeout)
        return ToolExecutionResult(
            tool_id=self.tool_id,
            status="completed" if res.success else "failed",
            output={
                "stdout": res.stdout,
                "stderr": res.stderr,
                "return_code": res.return_code,
                "output_files": res.output_files
            },
            error=res.error,
            execution_time_ms=res.execution_time_ms,
            permission_level=self.permission_level,
            requires_approval=False
        )
