"""
AST解析器模块
支持多种编程语言的抽象语法树解析
"""

import ast
import re
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Dict, Optional, Any, Type
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)


@dataclass
class CodeElement:
    """代码元素基类"""
    name: str
    element_type: str  # function, class, method, variable, import
    start_line: int
    end_line: int
    code: str
    docstring: Optional[str] = None
    decorators: List[str] = field(default_factory=list)
    parent: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "element_type": self.element_type,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "code": self.code,
            "docstring": self.docstring,
            "decorators": self.decorators,
            "parent": self.parent
        }


@dataclass
class FunctionInfo(CodeElement):
    """函数信息"""
    parameters: List[Dict[str, Any]] = field(default_factory=list)
    return_type: Optional[str] = None
    is_async: bool = False
    is_method: bool = False
    complexity: int = 1  # 圈复杂度估计
    
    def to_dict(self) -> Dict:
        base = super().to_dict()
        base.update({
            "parameters": self.parameters,
            "return_type": self.return_type,
            "is_async": self.is_async,
            "is_method": self.is_method,
            "complexity": self.complexity
        })
        return base


@dataclass 
class ClassInfo(CodeElement):
    """类信息"""
    bases: List[str] = field(default_factory=list)
    methods: List[FunctionInfo] = field(default_factory=list)
    attributes: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        base = super().to_dict()
        base.update({
            "bases": self.bases,
            "methods": [m.to_dict() for m in self.methods],
            "attributes": self.attributes
        })
        return base


@dataclass
class ImportInfo(CodeElement):
    """导入信息"""
    module: str = ""
    names: List[str] = field(default_factory=list)
    is_from_import: bool = False
    
    def to_dict(self) -> Dict:
        base = super().to_dict()
        base.update({
            "module": self.module,
            "names": self.names,
            "is_from_import": self.is_from_import
        })
        return base


@dataclass
class ParseResult:
    """解析结果"""
    file_path: str
    language: str
    imports: List[ImportInfo] = field(default_factory=list)
    classes: List[ClassInfo] = field(default_factory=list)
    functions: List[FunctionInfo] = field(default_factory=list)
    global_variables: List[CodeElement] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            "file_path": self.file_path,
            "language": self.language,
            "imports": [i.to_dict() for i in self.imports],
            "classes": [c.to_dict() for c in self.classes],
            "functions": [f.to_dict() for f in self.functions],
            "global_variables": [v.to_dict() for v in self.global_variables],
            "errors": self.errors
        }
    
    def get_all_functions(self) -> List[FunctionInfo]:
        """获取所有函数（包括类方法）"""
        all_funcs = list(self.functions)
        for cls in self.classes:
            all_funcs.extend(cls.methods)
        return all_funcs


class ASTParser(ABC):
    """AST解析器抽象基类"""
    
    @property
    @abstractmethod
    def language(self) -> str:
        """返回支持的语言名称"""
        pass
    
    @abstractmethod
    def parse(self, code: str, file_path: str = "") -> ParseResult:
        """
        解析代码
        
        Args:
            code: 源代码字符串
            file_path: 文件路径（用于错误报告）
            
        Returns:
            ParseResult 解析结果
        """
        pass
    
    def parse_file(self, file_path: Path) -> ParseResult:
        """
        解析文件
        
        Args:
            file_path: 文件路径
            
        Returns:
            ParseResult 解析结果
        """
        file_path = Path(file_path)
        try:
            code = file_path.read_text(encoding='utf-8')
        except UnicodeDecodeError:
            code = file_path.read_text(encoding='latin-1')
        
        return self.parse(code, str(file_path))


class PythonASTParser(ASTParser):
    """Python AST 解析器"""
    
    @property
    def language(self) -> str:
        return "python"
    
    def parse(self, code: str, file_path: str = "") -> ParseResult:
        """解析 Python 代码"""
        result = ParseResult(file_path=file_path, language=self.language)
        lines = code.split('\n')
        
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            result.errors.append(f"语法错误: {e}")
            return result
        
        # 遍历AST节点
        for node in ast.walk(tree):
            # 只处理模块级别的节点
            pass
        
        # 处理顶层节点
        for node in ast.iter_child_nodes(tree):
            try:
                if isinstance(node, ast.Import):
                    result.imports.append(self._parse_import(node, lines))
                elif isinstance(node, ast.ImportFrom):
                    result.imports.append(self._parse_import_from(node, lines))
                elif isinstance(node, ast.ClassDef):
                    result.classes.append(self._parse_class(node, lines))
                elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    result.functions.append(self._parse_function(node, lines))
                elif isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            result.global_variables.append(
                                self._parse_variable(target, node, lines)
                            )
            except Exception as e:
                result.errors.append(f"解析节点失败: {type(node).__name__}, 错误: {e}")
        
        return result
    
    def _get_code_segment(self, node: ast.AST, lines: List[str]) -> str:
        """获取节点对应的代码段"""
        start = node.lineno - 1
        end = getattr(node, 'end_lineno', node.lineno)
        return '\n'.join(lines[start:end])
    
    def _get_docstring(self, node: ast.AST) -> Optional[str]:
        """获取文档字符串"""
        return ast.get_docstring(node)
    
    def _parse_import(self, node: ast.Import, lines: List[str]) -> ImportInfo:
        """解析 import 语句"""
        names = [alias.name for alias in node.names]
        return ImportInfo(
            name=', '.join(names),
            element_type="import",
            start_line=node.lineno,
            end_line=node.lineno,
            code=self._get_code_segment(node, lines),
            module="",
            names=names,
            is_from_import=False
        )
    
    def _parse_import_from(self, node: ast.ImportFrom, lines: List[str]) -> ImportInfo:
        """解析 from ... import 语句"""
        module = node.module or ""
        names = [alias.name for alias in node.names]
        return ImportInfo(
            name=f"from {module} import {', '.join(names)}",
            element_type="import",
            start_line=node.lineno,
            end_line=node.lineno,
            code=self._get_code_segment(node, lines),
            module=module,
            names=names,
            is_from_import=True
        )
    
    def _parse_function(
        self, 
        node: ast.FunctionDef | ast.AsyncFunctionDef, 
        lines: List[str],
        parent: Optional[str] = None
    ) -> FunctionInfo:
        """解析函数定义"""
        # 解析参数
        parameters = []
        for arg in node.args.args:
            param = {"name": arg.arg, "type": None}
            if arg.annotation:
                param["type"] = ast.unparse(arg.annotation)
            parameters.append(param)
        
        # 解析返回类型
        return_type = None
        if node.returns:
            return_type = ast.unparse(node.returns)
        
        # 解析装饰器
        decorators = [ast.unparse(d) for d in node.decorator_list]
        
        # 估计圈复杂度
        complexity = self._estimate_complexity(node)
        
        return FunctionInfo(
            name=node.name,
            element_type="method" if parent else "function",
            start_line=node.lineno,
            end_line=node.end_lineno or node.lineno,
            code=self._get_code_segment(node, lines),
            docstring=self._get_docstring(node),
            decorators=decorators,
            parent=parent,
            parameters=parameters,
            return_type=return_type,
            is_async=isinstance(node, ast.AsyncFunctionDef),
            is_method=parent is not None,
            complexity=complexity
        )
    
    def _parse_class(self, node: ast.ClassDef, lines: List[str]) -> ClassInfo:
        """解析类定义"""
        # 解析基类
        bases = [ast.unparse(base) for base in node.bases]
        
        # 解析装饰器
        decorators = [ast.unparse(d) for d in node.decorator_list]
        
        # 解析方法和属性
        methods = []
        attributes = []
        
        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                methods.append(self._parse_function(item, lines, parent=node.name))
            elif isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name):
                        attributes.append(target.id)
            elif isinstance(item, ast.AnnAssign):
                if isinstance(item.target, ast.Name):
                    attributes.append(item.target.id)
        
        return ClassInfo(
            name=node.name,
            element_type="class",
            start_line=node.lineno,
            end_line=node.end_lineno or node.lineno,
            code=self._get_code_segment(node, lines),
            docstring=self._get_docstring(node),
            decorators=decorators,
            bases=bases,
            methods=methods,
            attributes=attributes
        )
    
    def _parse_variable(
        self, 
        target: ast.Name, 
        node: ast.Assign, 
        lines: List[str]
    ) -> CodeElement:
        """解析变量定义"""
        return CodeElement(
            name=target.id,
            element_type="variable",
            start_line=node.lineno,
            end_line=node.end_lineno or node.lineno,
            code=self._get_code_segment(node, lines)
        )
    
    def _estimate_complexity(self, node: ast.AST) -> int:
        """估计圈复杂度"""
        complexity = 1
        for child in ast.walk(node):
            if isinstance(child, (ast.If, ast.While, ast.For, ast.ExceptHandler)):
                complexity += 1
            elif isinstance(child, ast.BoolOp):
                complexity += len(child.values) - 1
            elif isinstance(child, (ast.ListComp, ast.DictComp, ast.SetComp, ast.GeneratorExp)):
                complexity += 1
        return complexity


class JavaScriptASTParser(ASTParser):
    """JavaScript/TypeScript 简化解析器 (基于正则表达式)"""
    
    @property
    def language(self) -> str:
        return "javascript"
    
    def parse(self, code: str, file_path: str = "") -> ParseResult:
        """解析 JavaScript/TypeScript 代码"""
        result = ParseResult(file_path=file_path, language=self.language)
        lines = code.split('\n')
        
        # 解析导入
        result.imports = self._parse_imports(code, lines)
        
        # 解析函数
        result.functions = self._parse_functions(code, lines)
        
        # 解析类
        result.classes = self._parse_classes(code, lines)
        
        return result
    
    def _parse_imports(self, code: str, lines: List[str]) -> List[ImportInfo]:
        """解析导入语句"""
        imports = []
        
        # ES6 import
        import_pattern = r'import\s+(?:{([^}]+)}|(\*\s+as\s+\w+)|(\w+))\s+from\s+[\'"]([^\'"]+)[\'"]'
        for match in re.finditer(import_pattern, code):
            line_num = code[:match.start()].count('\n') + 1
            names = []
            if match.group(1):
                names = [n.strip() for n in match.group(1).split(',')]
            elif match.group(2):
                names = [match.group(2)]
            elif match.group(3):
                names = [match.group(3)]
            
            imports.append(ImportInfo(
                name=match.group(0),
                element_type="import",
                start_line=line_num,
                end_line=line_num,
                code=match.group(0),
                module=match.group(4),
                names=names,
                is_from_import=True
            ))
        
        # require
        require_pattern = r'(?:const|let|var)\s+(?:{([^}]+)}|(\w+))\s*=\s*require\([\'"]([^\'"]+)[\'"]\)'
        for match in re.finditer(require_pattern, code):
            line_num = code[:match.start()].count('\n') + 1
            names = []
            if match.group(1):
                names = [n.strip() for n in match.group(1).split(',')]
            elif match.group(2):
                names = [match.group(2)]
            
            imports.append(ImportInfo(
                name=match.group(0),
                element_type="import",
                start_line=line_num,
                end_line=line_num,
                code=match.group(0),
                module=match.group(3),
                names=names,
                is_from_import=False
            ))
        
        return imports
    
    def _parse_functions(self, code: str, lines: List[str]) -> List[FunctionInfo]:
        """解析函数定义"""
        functions = []
        
        # 普通函数和箭头函数
        patterns = [
            # function declaration
            r'(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*\(([^)]*)\)',
            # const/let/var arrow function
            r'(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s*)?\(([^)]*)\)\s*=>',
            # method definition  
            r'(?:async\s+)?(\w+)\s*\(([^)]*)\)\s*{'
        ]
        
        for pattern in patterns:
            for match in re.finditer(pattern, code):
                line_num = code[:match.start()].count('\n') + 1
                name = match.group(1)
                params_str = match.group(2) if len(match.groups()) > 1 else ""
                
                # 解析参数
                parameters = []
                if params_str.strip():
                    for param in params_str.split(','):
                        param = param.strip()
                        if param:
                            # 处理 TypeScript 类型注解
                            param_name = param.split(':')[0].strip()
                            param_type = param.split(':')[1].strip() if ':' in param else None
                            parameters.append({"name": param_name, "type": param_type})
                
                # 查找函数体结束位置
                end_line = self._find_block_end(code, match.end(), lines)
                
                functions.append(FunctionInfo(
                    name=name,
                    element_type="function",
                    start_line=line_num,
                    end_line=end_line,
                    code='\n'.join(lines[line_num-1:end_line]),
                    parameters=parameters,
                    is_async='async' in match.group(0)
                ))
        
        return functions
    
    def _parse_classes(self, code: str, lines: List[str]) -> List[ClassInfo]:
        """解析类定义"""
        classes = []
        
        class_pattern = r'(?:export\s+)?class\s+(\w+)(?:\s+extends\s+(\w+))?'
        for match in re.finditer(class_pattern, code):
            line_num = code[:match.start()].count('\n') + 1
            name = match.group(1)
            base = match.group(2)
            
            end_line = self._find_block_end(code, match.end(), lines)
            
            classes.append(ClassInfo(
                name=name,
                element_type="class",
                start_line=line_num,
                end_line=end_line,
                code='\n'.join(lines[line_num-1:end_line]),
                bases=[base] if base else []
            ))
        
        return classes
    
    def _find_block_end(self, code: str, start_pos: int, lines: List[str]) -> int:
        """找到代码块结束位置"""
        # 简化实现：查找匹配的大括号
        brace_count = 0
        in_string = False
        string_char = None
        
        for i, char in enumerate(code[start_pos:], start_pos):
            if char in '"\'`' and (i == 0 or code[i-1] != '\\'):
                if not in_string:
                    in_string = True
                    string_char = char
                elif char == string_char:
                    in_string = False
            elif not in_string:
                if char == '{':
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        return code[:i+1].count('\n') + 1
        
        return len(lines)


class JavaASTParser(ASTParser):
    """Java 简化解析器 (基于正则表达式)"""
    
    @property
    def language(self) -> str:
        return "java"
    
    def parse(self, code: str, file_path: str = "") -> ParseResult:
        """解析 Java 代码"""
        result = ParseResult(file_path=file_path, language=self.language)
        lines = code.split('\n')
        
        # 解析导入
        result.imports = self._parse_imports(code, lines)
        
        # 解析类
        result.classes = self._parse_classes(code, lines)
        
        return result
    
    def _parse_imports(self, code: str, lines: List[str]) -> List[ImportInfo]:
        """解析 import 语句"""
        imports = []
        import_pattern = r'import\s+(static\s+)?([^;]+);'
        
        for match in re.finditer(import_pattern, code):
            line_num = code[:match.start()].count('\n') + 1
            module = match.group(2).strip()
            
            imports.append(ImportInfo(
                name=match.group(0),
                element_type="import",
                start_line=line_num,
                end_line=line_num,
                code=match.group(0),
                module=module,
                names=[module.split('.')[-1]],
                is_from_import=False
            ))
        
        return imports
    
    def _parse_classes(self, code: str, lines: List[str]) -> List[ClassInfo]:
        """解析类定义"""
        classes = []
        
        class_pattern = r'(?:public|private|protected)?\s*(?:abstract|final)?\s*class\s+(\w+)(?:\s+extends\s+(\w+))?(?:\s+implements\s+([^{]+))?'
        
        for match in re.finditer(class_pattern, code):
            line_num = code[:match.start()].count('\n') + 1
            name = match.group(1)
            extends = match.group(2)
            implements = match.group(3)
            
            bases = []
            if extends:
                bases.append(extends)
            if implements:
                bases.extend([i.strip() for i in implements.split(',')])
            
            # 查找类体结束
            end_line = self._find_block_end(code, match.end(), lines)
            class_code = '\n'.join(lines[line_num-1:end_line])
            
            # 解析方法
            methods = self._parse_methods(class_code, line_num - 1, name)
            
            classes.append(ClassInfo(
                name=name,
                element_type="class",
                start_line=line_num,
                end_line=end_line,
                code=class_code,
                bases=bases,
                methods=methods
            ))
        
        return classes
    
    def _parse_methods(self, class_code: str, offset: int, class_name: str) -> List[FunctionInfo]:
        """解析类方法"""
        methods = []
        
        method_pattern = r'(?:public|private|protected)?\s*(?:static|final|abstract|synchronized)?\s*(\w+(?:<[^>]+>)?)\s+(\w+)\s*\(([^)]*)\)'
        
        for match in re.finditer(method_pattern, class_code):
            line_num = class_code[:match.start()].count('\n') + 1 + offset
            return_type = match.group(1)
            name = match.group(2)
            params_str = match.group(3)
            
            # 跳过构造函数的返回类型
            if name == class_name:
                return_type = None
            
            # 解析参数
            parameters = []
            if params_str.strip():
                for param in params_str.split(','):
                    param = param.strip()
                    if param:
                        parts = param.split()
                        if len(parts) >= 2:
                            parameters.append({
                                "name": parts[-1],
                                "type": ' '.join(parts[:-1])
                            })
            
            methods.append(FunctionInfo(
                name=name,
                element_type="method",
                start_line=line_num,
                end_line=line_num + class_code[match.end():].split('}')[0].count('\n'),
                code=match.group(0),
                parameters=parameters,
                return_type=return_type,
                is_method=True,
                parent=class_name
            ))
        
        return methods
    
    def _find_block_end(self, code: str, start_pos: int, lines: List[str]) -> int:
        """找到代码块结束位置"""
        brace_count = 0
        in_string = False
        string_char = None
        
        for i, char in enumerate(code[start_pos:], start_pos):
            if char in '"\'':
                if not in_string:
                    in_string = True
                    string_char = char
                elif char == string_char and code[i-1] != '\\':
                    in_string = False
            elif not in_string:
                if char == '{':
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        return code[:i+1].count('\n') + 1
        
        return len(lines)


# 解析器工厂
_PARSER_REGISTRY: Dict[str, Type[ASTParser]] = {
    "python": PythonASTParser,
    "javascript": JavaScriptASTParser,
    "typescript": JavaScriptASTParser,
    "java": JavaASTParser,
}


def get_parser_for_language(language: str) -> Optional[ASTParser]:
    """
    获取指定语言的解析器
    
    Args:
        language: 编程语言名称
        
    Returns:
        对应的解析器实例，如果不支持则返回 None
    """
    parser_class = _PARSER_REGISTRY.get(language.lower())
    if parser_class:
        return parser_class()
    return None


def register_parser(language: str, parser_class: Type[ASTParser]):
    """
    注册新的解析器
    
    Args:
        language: 语言名称
        parser_class: 解析器类
    """
    _PARSER_REGISTRY[language.lower()] = parser_class

