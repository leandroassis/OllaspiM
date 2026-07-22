from pathlib import Path
from typing import Any, Dict, List
# pyrefly: ignore [missing-import]
# pyright: ignore [reportMissingImports]
from tree_sitter import Language, Parser
from src.ingestion.base_parser import BaseParser
from src.utils.exceptions import ParsingException
from src.utils.logger import logger

class CodeParser(BaseParser):
    """Parser for source code using tree-sitter to slice functions and methods."""
    
    LANGUAGE_MAP = {
        ".c": "c",
        ".cpp": "cpp",
        ".java": "java",
        ".go": "go",
        ".py": "python",
        ".html": "html",
        ".js": "javascript",
        ".css": "css"
    }
    
    def __init__(self):
        self.languages: Dict[str, Language] = {}
        self._initialize_parsers()
        
    def _initialize_parsers(self):
        """Downloads and compiles parsers for supported languages if not present."""
        try:
            # pyrefly: ignore [missing-import]
            import tree_sitter_c
            # pyrefly: ignore [missing-import]
            import tree_sitter_cpp
            # pyrefly: ignore [missing-import]
            import tree_sitter_java
            # pyrefly: ignore [missing-import]
            import tree_sitter_go
            # pyrefly: ignore [missing-import]
            import tree_sitter_python
            # pyrefly: ignore [missing-import]
            import tree_sitter_html
            # pyrefly: ignore [missing-import]
            import tree_sitter_javascript
            # pyrefly: ignore [missing-import]
            import tree_sitter_css
            
            self.languages["c"] = Language(tree_sitter_c.language())
            self.languages["cpp"] = Language(tree_sitter_cpp.language())
            self.languages["java"] = Language(tree_sitter_java.language())
            self.languages["go"] = Language(tree_sitter_go.language())
            self.languages["python"] = Language(tree_sitter_python.language())
            self.languages["html"] = Language(tree_sitter_html.language())
            self.languages["javascript"] = Language(tree_sitter_javascript.language())
            self.languages["css"] = Language(tree_sitter_css.language())
            
            logger.info("Tree-sitter languages loaded successfully.")
        except ImportError as e:
            logger.warning(f"Alguns parsers tree-sitter não estão instalados: {e}.")
            
    def _get_functions_query(self, lang_name: str) -> str:
        """Returns the tree-sitter query string to find functions/methods based on language."""
        if lang_name in ["c", "cpp"]:
            return "(function_definition) @function"
        elif lang_name == "python":
            return "(function_definition) @function"
        elif lang_name == "java":
            return "(method_declaration) @function"
        elif lang_name == "go":
            return "(function_declaration) @function (method_declaration) @function"
        elif lang_name == "javascript":
            return "(function_declaration) @function (method_definition) @function (arrow_function) @function"
        else:
            return ""

    def parse(self, file_path: Path) -> Dict[str, Any]:
        ext = file_path.suffix.lower()
        if ext not in self.LANGUAGE_MAP:
            logger.warning(f"Linguagem não suportada para {file_path}")
            return {"source": str(file_path), "functions": []}
            
        lang_name = self.LANGUAGE_MAP[ext]
        if lang_name not in self.languages:
            raise ParsingException(f"Parser for {lang_name} not available.")
            
        language = self.languages[lang_name]
        parser = Parser(language)
        
        try:
            with open(file_path, "rb") as f:
                code_bytes = f.read()
        except Exception as e:
            raise ParsingException(f"Failed to read file {file_path}: {e}")
            
        tree = parser.parse(code_bytes)
        
        query_str = self._get_functions_query(lang_name)
        if not query_str:
            return {"source": str(file_path), "functions": []}
            
        try:
            import tree_sitter
            captures = []
            if hasattr(tree_sitter, "QueryCursor"):
                # tree-sitter >= 0.24 / 0.25
                query = tree_sitter.Query(language, query_str)
                cursor = tree_sitter.QueryCursor(query)
                matches = cursor.matches(tree.root_node)
                for m in matches:
                    match_dict = m[1] if isinstance(m, tuple) else m
                    if isinstance(match_dict, dict):
                        for name, node_or_nodes in match_dict.items():
                            if isinstance(node_or_nodes, list):
                                for n in node_or_nodes:
                                    captures.append((n, name))
                            else:
                                captures.append((node_or_nodes, name))
            else:
                # tree-sitter older versions
                query = language.query(query_str)
                if hasattr(query, "captures"):
                    captures = query.captures(tree.root_node)
                elif hasattr(query, "matches"):
                    matches = query.matches(tree.root_node)
                    for m in matches:
                        match_dict = m[1] if isinstance(m, tuple) else m
                        if isinstance(match_dict, dict):
                            for name, node_or_nodes in match_dict.items():
                                if isinstance(node_or_nodes, list):
                                    for n in node_or_nodes:
                                        captures.append((n, name))
                                else:
                                    captures.append((node_or_nodes, name))
        except Exception as e:
            logger.debug(f"A query tree-sitter falhou silenciosamente para {lang_name}: {e}")
            return {"source": str(file_path), "functions": []}
            
        functions = []
        for node, _ in captures:
            start_line = node.start_point.row + 1
            end_line = node.end_point.row + 1
            source_code = code_bytes[node.start_byte:node.end_byte].decode("utf-8", errors="replace")
            
            # Tentar extrair o nome da função pelo AST
            func_name = "UnknownFunction"
            name_node = node.child_by_field_name('name')
            
            if name_node:
                func_name = code_bytes[name_node.start_byte:name_node.end_byte].decode("utf-8", errors="replace")
            else:
                # Fallback para C/C++ onde o nome fica dentro de declarator
                declarator = node.child_by_field_name('declarator')
                while declarator and declarator.type != 'identifier' and hasattr(declarator, 'child_by_field_name'):
                    child_decl = declarator.child_by_field_name('declarator')
                    if not child_decl:
                        break
                    declarator = child_decl
                    
                if declarator and getattr(declarator, 'type', '') == 'identifier':
                    func_name = code_bytes[declarator.start_byte:declarator.end_byte].decode("utf-8", errors="replace")
                else:
                    # Regex fallback na assinatura da função
                    import re
                    match = re.search(r'\b([a-zA-Z_][a-zA-Z0-9_]*)\s*\(', source_code)
                    if match and match.group(1) not in ["if", "while", "for", "switch", "return"]:
                        func_name = match.group(1)
            
            functions.append({
                "name": func_name,
                "lines": f"{start_line}-{end_line}",
                "codigo_fonte_bruto": source_code
            })
            
        return {
            "source": str(file_path),
            "type": "code",
            "language": lang_name,
            "functions": functions
        }
