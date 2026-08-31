import ast
import re
import uuid
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger("jarvis.rag.chunker")


class DocumentChunkModel(BaseModel):
    """
    Structured syntax-aware document chunk complying with Build Plan Section 8.
    Preserves all necessary metadata for hybrid lexical, AST, and semantic retrieval.
    """
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    project_id: Optional[str] = None
    document_id: Optional[str] = None
    file_path: str
    file_name: str
    chunk_index: int
    start_line: int
    end_line: int
    content: str
    symbol_name: Optional[str] = None
    symbol_type: Optional[str] = None  # function, async_function, class, struct, module, section, block
    namespace: Optional[str] = None
    imports: list[str] = Field(default_factory=list)
    language: Optional[str] = None
    git_commit_hash: Optional[str] = None
    modified_timestamp: datetime = Field(default_factory=datetime.utcnow)


class SyntaxAwareChunker:
    """
    Codebase and document chunker with AST parsing for Python,
    macro/syntax block parsing for C++ (Unreal Engine), and sliding-window fallback.
    """

    def __init__(self, chunk_size: int = 1024, chunk_overlap: int = 128):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def detect_language(self, file_path: str) -> str:
        """Infer programming language from file extension."""
        ext = Path(file_path).suffix.lower()
        mapping = {
            ".py": "python",
            ".cpp": "cpp",
            ".cxx": "cpp",
            ".cc": "cpp",
            ".c": "c",
            ".h": "cpp",
            ".hpp": "cpp",
            ".cs": "csharp",
            ".ts": "typescript",
            ".tsx": "typescriptreact",
            ".js": "javascript",
            ".jsx": "javascriptreact",
            ".json": "json",
            ".yaml": "yaml",
            ".yml": "yaml",
            ".ini": "ini",
            ".md": "markdown",
            ".txt": "text",
            ".uproject": "unreal_project",
        }
        return mapping.get(ext, "unknown")

    def chunk_file(
        self,
        file_path: str,
        content: str,
        project_id: Optional[str] = None,
        git_commit_hash: Optional[str] = None,
        modified_timestamp: Optional[datetime] = None
    ) -> list[DocumentChunkModel]:
        """
        Main entrypoint: parses file content into structured DocumentChunkModel chunks
        using the best syntax-aware chunker for the language.
        """
        language = self.detect_language(file_path)
        mtime = modified_timestamp or datetime.utcnow()
        fname = Path(file_path).name

        if language == "python":
            chunks = self._chunk_python(content, file_path, fname, project_id, git_commit_hash, mtime)
            if chunks:
                return chunks

        elif language in ("cpp", "c", "csharp"):
            chunks = self._chunk_cpp(content, file_path, fname, project_id, language, git_commit_hash, mtime)
            if chunks:
                return chunks

        # Fallback to recursive sliding-window chunking
        return self._chunk_recursive(content, file_path, fname, project_id, language, git_commit_hash, mtime)

    def _chunk_python(
        self,
        code: str,
        file_path: str,
        file_name: str,
        project_id: Optional[str],
        git_commit_hash: Optional[str],
        mtime: datetime
    ) -> list[DocumentChunkModel]:
        """
        Extract classes, functions, async functions, decorators, and imports using Python AST.
        """
        try:
            tree = ast.parse(code, filename=file_path)
        except Exception as e:
            logger.debug("Python AST parse failed for %s: %s. Using recursive chunker.", file_path, e)
            return []

        lines = code.splitlines()
        total_lines = len(lines)
        if total_lines == 0:
            return []

        # 1. Collect module-level imports and docstring
        module_imports = []
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.Import):
                module_imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                module_name = node.module or ""
                for alias in node.names:
                    module_imports.append(f"{module_name}.{alias.name}")

        chunks: list[DocumentChunkModel] = []
        chunk_idx = 0

        # Helper to slice lines safely (1-indexed)
        def get_snippet(s_line: int, e_line: int) -> str:
            s_idx = max(0, s_line - 1)
            e_idx = min(total_lines, e_line)
            return "\n".join(lines[s_idx:e_idx])

        # 2. Iterate top-level AST nodes
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                start_line = node.lineno
                end_line = getattr(node, "end_lineno", start_line)
                symbol_type = (
                    "class" if isinstance(node, ast.ClassDef)
                    else "async_function" if isinstance(node, ast.AsyncFunctionDef)
                    else "function"
                )
                symbol_name = node.name
                content = get_snippet(start_line, end_line)

                chunks.append(
                    DocumentChunkModel(
                        project_id=project_id,
                        file_path=file_path,
                        file_name=file_name,
                        chunk_index=chunk_idx,
                        start_line=start_line,
                        end_line=end_line,
                        content=content,
                        symbol_name=symbol_name,
                        symbol_type=symbol_type,
                        imports=module_imports,
                        language="python",
                        git_commit_hash=git_commit_hash,
                        modified_timestamp=mtime,
                    )
                )
                chunk_idx += 1

        # If no classes or functions were found (e.g. script/config), chunk top-level body
        if not chunks and total_lines > 0:
            chunks.append(
                DocumentChunkModel(
                    project_id=project_id,
                    file_path=file_path,
                    file_name=file_name,
                    chunk_index=0,
                    start_line=1,
                    end_line=total_lines,
                    content=code,
                    symbol_name=file_name,
                    symbol_type="module",
                    imports=module_imports,
                    language="python",
                    git_commit_hash=git_commit_hash,
                    modified_timestamp=mtime,
                )
            )

        return chunks

    def _chunk_cpp(
        self,
        code: str,
        file_path: str,
        file_name: str,
        project_id: Optional[str],
        language: str,
        git_commit_hash: Optional[str],
        mtime: datetime
    ) -> list[DocumentChunkModel]:
        """
        C++ / Unreal Engine macro & block syntax chunker.
        Identifies UCLASS, USTRUCT, UFUNCTION, namespaces, classes, and methods.
        """
        lines = code.splitlines()
        total_lines = len(lines)
        if total_lines == 0:
            return []

        # 1. Collect #includes
        includes = []
        for line in lines:
            if line.strip().startswith("#include"):
                includes.append(line.strip())

        chunks: list[DocumentChunkModel] = []
        chunk_idx = 0

        # Pattern for C++ / UE Class, Struct, and Function declarations
        class_pattern = re.compile(
            r'(?:class|struct)\s+(?:[A-Za-z0-9_]+_API\s+)?([A-Za-z0-9_]+)'
        )
        func_pattern = re.compile(
            r'^\s*(?:UFUNCTION\s*\(.*?\)|FORCEINLINE|virtual|static)?\s*[\w:<>&*]+\s+([A-Za-z0-9_]+::[A-Za-z0-9_]+|[A-Za-z0-9_]+)\s*\([^)]*\)'
        )

        # Scan line by line detecting block boundaries
        i = 0
        while i < total_lines:
            line = lines[i]
            # Check for Unreal Engine decorator on previous or current line
            is_ue_macro = line.strip().startswith(("UCLASS", "USTRUCT", "UFUNCTION", "UPROPERTY"))
            match_class = class_pattern.search(line)
            match_func = func_pattern.search(line) if not match_class else None

            # If current line is UCLASS/USTRUCT and next line is class/struct, advance
            if is_ue_macro and not match_class and i + 1 < total_lines:
                next_line = lines[i + 1]
                match_class = class_pattern.search(next_line)

            if match_class or match_func:
                symbol_name = match_class.group(1) if match_class else match_func.group(1)
                symbol_type = "class" if match_class else "function"
                start_line = i + 1

                # Find closing brace or block end
                brace_count = line.count("{") - line.count("}")
                if is_ue_macro and i + 1 < total_lines:
                    brace_count += lines[i + 1].count("{") - lines[i + 1].count("}")

                end_line = start_line
                j = i + 1
                while j < total_lines:
                    brace_count += lines[j].count("{") - lines[j].count("}")
                    if brace_count <= 0 and ("}" in lines[j] or ";" in lines[j]):
                        end_line = j + 1
                        break
                    j += 1
                else:
                    end_line = min(total_lines, i + 40)

                snippet = "\n".join(lines[i:end_line])
                chunks.append(
                    DocumentChunkModel(
                        project_id=project_id,
                        file_path=file_path,
                        file_name=file_name,
                        chunk_index=chunk_idx,
                        start_line=start_line,
                        end_line=end_line,
                        content=snippet,
                        symbol_name=symbol_name,
                        symbol_type=symbol_type,
                        imports=includes,
                        language=language,
                        git_commit_hash=git_commit_hash,
                        modified_timestamp=mtime,
                    )
                )
                chunk_idx += 1
                i = max(i + 1, end_line)
            else:
                i += 1


        # Fallback if no matching blocks found
        if not chunks:
            return self._chunk_recursive(code, file_path, file_name, project_id, language, git_commit_hash, mtime)

        return chunks

    def _chunk_recursive(
        self,
        text: str,
        file_path: str,
        file_name: str,
        project_id: Optional[str],
        language: str,
        git_commit_hash: Optional[str],
        mtime: datetime
    ) -> list[DocumentChunkModel]:
        """
        Sliding-window recursive character chunking for generic text, Markdown, JSON, YAML.
        """
        lines = text.splitlines()
        total_lines = len(lines)
        if total_lines == 0:
            return []

        chunks: list[DocumentChunkModel] = []
        chunk_idx = 0
        current_lines: list[str] = []
        current_char_count = 0
        start_line = 1

        for idx, line in enumerate(lines, start=1):
            line_len = len(line) + 1  # include newline
            if current_char_count + line_len > self.chunk_size and current_lines:
                chunk_content = "\n".join(current_lines)
                end_line = idx - 1
                chunks.append(
                    DocumentChunkModel(
                        project_id=project_id,
                        file_path=file_path,
                        file_name=file_name,
                        chunk_index=chunk_idx,
                        start_line=start_line,
                        end_line=end_line,
                        content=chunk_content,
                        symbol_name=f"{file_name}#L{start_line}-L{end_line}",
                        symbol_type="block",
                        language=language,
                        git_commit_hash=git_commit_hash,
                        modified_timestamp=mtime,
                    )
                )
                chunk_idx += 1

                # Calculate overlap lines
                overlap_chars = 0
                overlap_lines: list[str] = []
                for prev_line in reversed(current_lines):
                    if overlap_chars + len(prev_line) + 1 <= self.chunk_overlap:
                        overlap_lines.insert(0, prev_line)
                        overlap_chars += len(prev_line) + 1
                    else:
                        break

                current_lines = overlap_lines + [line]
                current_char_count = sum(len(l) + 1 for l in current_lines)
                start_line = idx - len(overlap_lines)
            else:
                current_lines.append(line)
                current_char_count += line_len

        if current_lines:
            chunk_content = "\n".join(current_lines)
            chunks.append(
                DocumentChunkModel(
                    project_id=project_id,
                    file_path=file_path,
                    file_name=file_name,
                    chunk_index=chunk_idx,
                    start_line=start_line,
                    end_line=total_lines,
                    content=chunk_content,
                    symbol_name=f"{file_name}#L{start_line}-L{total_lines}",
                    symbol_type="block",
                    language=language,
                    git_commit_hash=git_commit_hash,
                    modified_timestamp=mtime,
                )
            )

        return chunks
