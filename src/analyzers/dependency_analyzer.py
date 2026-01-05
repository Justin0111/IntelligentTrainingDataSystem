"""
依赖分析器
分析代码的模块依赖、函数调用关系和数据流
"""

from pathlib import Path
from typing import List, Dict, Optional, Set, Tuple
from dataclasses import dataclass, field
from collections import defaultdict
import logging
import re

from ..parsers.repo_scanner import RepoScanner, FileInfo
from ..parsers.ast_parser import ParseResult, get_parser_for_language, ImportInfo

logger = logging.getLogger(__name__)


@dataclass
class Dependency:
    """依赖关系"""
    source: str  # 源模块/文件
    target: str  # 目标模块/文件
    dependency_type: str  # import, call, inherit, implement
    details: str = ""
    
    def to_dict(self) -> Dict:
        return {
            "source": self.source,
            "target": self.target,
            "dependency_type": self.dependency_type,
            "details": self.details
        }


@dataclass
class CallRelation:
    """函数调用关系"""
    caller: str  # 调用者 (文件:函数名)
    callee: str  # 被调用者
    call_count: int = 1
    call_sites: List[int] = field(default_factory=list)  # 调用位置行号
    
    def to_dict(self) -> Dict:
        return {
            "caller": self.caller,
            "callee": self.callee,
            "call_count": self.call_count,
            "call_sites": self.call_sites
        }


@dataclass
class DependencyGraph:
    """依赖图"""
    nodes: Set[str] = field(default_factory=set)
    edges: List[Dependency] = field(default_factory=list)
    call_relations: List[CallRelation] = field(default_factory=list)
    external_dependencies: List[str] = field(default_factory=list)
    circular_dependencies: List[Tuple[str, str]] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            "nodes": list(self.nodes),
            "edges": [e.to_dict() for e in self.edges],
            "call_relations": [c.to_dict() for c in self.call_relations],
            "external_dependencies": self.external_dependencies,
            "circular_dependencies": [list(c) for c in self.circular_dependencies]
        }
    
    def get_dependencies_of(self, module: str) -> List[str]:
        """获取模块的直接依赖"""
        return [e.target for e in self.edges if e.source == module]
    
    def get_dependents_of(self, module: str) -> List[str]:
        """获取依赖该模块的模块"""
        return [e.source for e in self.edges if e.target == module]


class DependencyAnalyzer:
    """
    依赖分析器
    
    分析代码仓库中的依赖关系、调用图和模块耦合
    """
    
    # 标准库/常见第三方库 (用于识别外部依赖)
    COMMON_STDLIB = {
        "python": {
            "os", "sys", "re", "json", "time", "datetime", "collections",
            "typing", "pathlib", "logging", "functools", "itertools",
            "dataclasses", "abc", "asyncio", "concurrent", "threading",
            "unittest", "pytest", "numpy", "pandas", "requests"
        },
        "javascript": {
            "fs", "path", "http", "https", "crypto", "util", "events",
            "stream", "buffer", "os", "child_process", "react", "vue",
            "express", "lodash", "axios", "moment"
        },
        "java": {
            "java.lang", "java.util", "java.io", "java.net", "java.time",
            "java.sql", "java.nio", "javax", "org.springframework",
            "org.apache", "com.google"
        }
    }
    
    def __init__(self):
        self.scanner = RepoScanner()
    
    def analyze_repository(self, repo_path: Path) -> DependencyGraph:
        """
        分析整个仓库的依赖关系
        
        Args:
            repo_path: 仓库路径
            
        Returns:
            DependencyGraph 依赖图
        """
        repo_path = Path(repo_path).resolve()
        logger.info(f"开始分析依赖: {repo_path}")
        
        graph = DependencyGraph()
        
        # 扫描仓库
        repo_info = self.scanner.scan_repository(repo_path, load_content=True)
        
        # 收集所有模块名
        internal_modules: Set[str] = set()
        for file_info in repo_info.files:
            module_name = self._file_to_module(file_info.relative_path)
            internal_modules.add(module_name)
            graph.nodes.add(module_name)
        
        # 分析每个文件的依赖
        for file_info in repo_info.files:
            if file_info.language and file_info.content:
                self._analyze_file_dependencies(
                    file_info, internal_modules, graph
                )
        
        # 检测循环依赖
        graph.circular_dependencies = self._detect_circular_dependencies(graph)
        
        logger.info(
            f"依赖分析完成: {len(graph.nodes)} 模块, "
            f"{len(graph.edges)} 依赖关系, "
            f"{len(graph.circular_dependencies)} 循环依赖"
        )
        
        return graph
    
    def _file_to_module(self, file_path: str) -> str:
        """将文件路径转换为模块名"""
        # 移除扩展名
        module = re.sub(r'\.(py|js|ts|java)$', '', file_path)
        # 替换路径分隔符
        module = module.replace('/', '.').replace('\\', '.')
        # 移除 __init__
        module = re.sub(r'\.__init__$', '', module)
        return module
    
    def _analyze_file_dependencies(
        self,
        file_info: FileInfo,
        internal_modules: Set[str],
        graph: DependencyGraph
    ):
        """分析单个文件的依赖"""
        parser = get_parser_for_language(file_info.language)
        if not parser:
            return
        
        try:
            parse_result = parser.parse(file_info.content, str(file_info.path))
        except Exception as e:
            logger.warning(f"解析失败: {file_info.path}, 错误: {e}")
            return
        
        source_module = self._file_to_module(file_info.relative_path)
        
        # 分析导入依赖
        for imp in parse_result.imports:
            target_module = imp.module if imp.is_from_import else ', '.join(imp.names)
            
            # 判断是否是内部依赖
            is_internal = self._is_internal_module(target_module, internal_modules)
            
            if is_internal:
                graph.edges.append(Dependency(
                    source=source_module,
                    target=target_module,
                    dependency_type="import",
                    details=imp.code
                ))
            else:
                if target_module not in graph.external_dependencies:
                    graph.external_dependencies.append(target_module)
        
        # 分析类继承关系
        for cls in parse_result.classes:
            for base in cls.bases:
                # 检查是否是内部类
                if self._find_class_module(base, internal_modules, parse_result):
                    graph.edges.append(Dependency(
                        source=source_module,
                        target=base,
                        dependency_type="inherit",
                        details=f"class {cls.name}({base})"
                    ))
        
        # 分析函数调用关系
        call_relations = self._analyze_call_relations(
            parse_result, file_info.content, source_module
        )
        graph.call_relations.extend(call_relations)
    
    def _is_internal_module(self, module_name: str, internal_modules: Set[str]) -> bool:
        """判断是否是内部模块"""
        if not module_name:
            return False
        
        # 直接匹配
        if module_name in internal_modules:
            return True
        
        # 检查是否是内部模块的子模块
        for internal in internal_modules:
            if module_name.startswith(internal + '.') or internal.startswith(module_name + '.'):
                return True
        
        # 检查相对导入
        if module_name.startswith('.'):
            return True
        
        return False
    
    def _find_class_module(
        self, 
        class_name: str, 
        internal_modules: Set[str],
        parse_result: ParseResult
    ) -> Optional[str]:
        """找到类所在的模块"""
        # 检查导入
        for imp in parse_result.imports:
            if class_name in imp.names:
                return imp.module
        
        return None
    
    def _analyze_call_relations(
        self,
        parse_result: ParseResult,
        code: str,
        source_module: str
    ) -> List[CallRelation]:
        """分析函数调用关系"""
        relations = []
        all_functions = parse_result.get_all_functions()
        
        # 收集当前文件中定义的函数名
        local_functions = {f.name for f in all_functions}
        local_functions.update({c.name for c in parse_result.classes})
        
        for func in all_functions:
            caller = f"{source_module}:{func.name}"
            
            # 在函数体中查找函数调用
            call_pattern = r'\b(\w+)\s*\('
            calls: Dict[str, List[int]] = defaultdict(list)
            
            for i, line in enumerate(func.code.split('\n'), func.start_line):
                for match in re.finditer(call_pattern, line):
                    callee = match.group(1)
                    # 过滤关键字和内置函数
                    if callee not in {"if", "for", "while", "return", "print", "len", "str", "int", "list", "dict", "set", "type", "isinstance", "hasattr", "getattr"}:
                        calls[callee].append(i)
            
            for callee, sites in calls.items():
                relations.append(CallRelation(
                    caller=caller,
                    callee=callee,
                    call_count=len(sites),
                    call_sites=sites
                ))
        
        return relations
    
    def _detect_circular_dependencies(
        self, 
        graph: DependencyGraph
    ) -> List[Tuple[str, str]]:
        """检测循环依赖"""
        circular = []
        
        # 构建邻接表
        adj: Dict[str, Set[str]] = defaultdict(set)
        for edge in graph.edges:
            adj[edge.source].add(edge.target)
        
        # 检测双向依赖（最简单的循环）
        checked: Set[Tuple[str, str]] = set()
        for edge in graph.edges:
            pair = tuple(sorted([edge.source, edge.target]))
            if pair in checked:
                continue
            checked.add(pair)
            
            if edge.target in adj and edge.source in adj[edge.target]:
                circular.append((edge.source, edge.target))
        
        return circular
    
    def get_module_coupling(self, graph: DependencyGraph) -> Dict[str, Dict]:
        """计算模块耦合度"""
        coupling = {}
        
        for node in graph.nodes:
            # 传入耦合度 (被依赖的数量)
            afferent = len(graph.get_dependents_of(node))
            # 传出耦合度 (依赖的数量)
            efferent = len(graph.get_dependencies_of(node))
            
            # 不稳定度 I = Ce / (Ca + Ce)
            total = afferent + efferent
            instability = efferent / total if total > 0 else 0
            
            coupling[node] = {
                "afferent_coupling": afferent,  # 被依赖
                "efferent_coupling": efferent,  # 依赖
                "instability": round(instability, 2)
            }
        
        return coupling
    
    def generate_dependency_report(self, graph: DependencyGraph) -> str:
        """生成依赖分析报告"""
        lines = ["# 依赖分析报告\n"]
        
        # 概述
        lines.append("## 概述")
        lines.append(f"- 内部模块数: {len(graph.nodes)}")
        lines.append(f"- 依赖关系数: {len(graph.edges)}")
        lines.append(f"- 外部依赖数: {len(graph.external_dependencies)}")
        lines.append(f"- 循环依赖数: {len(graph.circular_dependencies)}")
        lines.append("")
        
        # 外部依赖
        if graph.external_dependencies:
            lines.append("## 外部依赖")
            for dep in sorted(graph.external_dependencies)[:20]:
                lines.append(f"- {dep}")
            lines.append("")
        
        # 循环依赖警告
        if graph.circular_dependencies:
            lines.append("## ⚠️ 循环依赖")
            for a, b in graph.circular_dependencies:
                lines.append(f"- {a} ↔ {b}")
            lines.append("")
        
        # 耦合度分析
        coupling = self.get_module_coupling(graph)
        if coupling:
            lines.append("## 模块耦合度")
            # 按不稳定度排序
            sorted_modules = sorted(
                coupling.items(), 
                key=lambda x: x[1]["instability"],
                reverse=True
            )
            for module, metrics in sorted_modules[:10]:
                lines.append(
                    f"- **{module}**: 被依赖={metrics['afferent_coupling']}, "
                    f"依赖={metrics['efferent_coupling']}, "
                    f"不稳定度={metrics['instability']}"
                )
            lines.append("")
        
        return '\n'.join(lines)
    
    def get_dependency_tree(self, graph: DependencyGraph, root: str, max_depth: int = 3) -> Dict:
        """获取模块的依赖树"""
        def build_tree(module: str, depth: int, visited: Set[str]) -> Dict:
            if depth > max_depth or module in visited:
                return {"name": module, "truncated": True}
            
            visited.add(module)
            deps = graph.get_dependencies_of(module)
            
            return {
                "name": module,
                "dependencies": [
                    build_tree(dep, depth + 1, visited.copy())
                    for dep in deps[:10]  # 限制每层数量
                ]
            }
        
        return build_tree(root, 0, set())

