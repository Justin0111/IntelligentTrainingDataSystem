"""
代码结构分析器
分析代码的整体结构、模块组织和架构模式
"""

from pathlib import Path
from typing import List, Dict, Optional, Set
from dataclasses import dataclass, field
import logging
import re

from ..parsers.repo_scanner import RepoScanner, RepoInfo, FileInfo
from ..parsers.ast_parser import (
    ParseResult, ASTParser, get_parser_for_language,
    ClassInfo, FunctionInfo
)

logger = logging.getLogger(__name__)


@dataclass
class ModuleInfo:
    """模块信息"""
    name: str
    path: str
    description: Optional[str] = None
    files: List[str] = field(default_factory=list)
    classes: List[str] = field(default_factory=list)
    functions: List[str] = field(default_factory=list)
    exports: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "path": self.path,
            "description": self.description,
            "files": self.files,
            "classes": self.classes,
            "functions": self.functions,
            "exports": self.exports
        }


@dataclass
class ArchitecturePattern:
    """架构模式"""
    name: str
    confidence: float  # 0-1
    evidence: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "confidence": self.confidence,
            "evidence": self.evidence
        }


@dataclass
class StructureAnalysis:
    """结构分析结果"""
    repo_name: str
    total_files: int
    total_classes: int
    total_functions: int
    modules: List[ModuleInfo] = field(default_factory=list)
    architecture_patterns: List[ArchitecturePattern] = field(default_factory=list)
    entry_points: List[str] = field(default_factory=list)
    layer_structure: Dict[str, List[str]] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "repo_name": self.repo_name,
            "total_files": self.total_files,
            "total_classes": self.total_classes,
            "total_functions": self.total_functions,
            "modules": [m.to_dict() for m in self.modules],
            "architecture_patterns": [p.to_dict() for p in self.architecture_patterns],
            "entry_points": self.entry_points,
            "layer_structure": self.layer_structure
        }


class StructureAnalyzer:
    """
    代码结构分析器
    
    分析代码仓库的整体结构，识别模块、架构模式等
    """
    
    # 常见的分层目录名称
    LAYER_PATTERNS = {
        "presentation": ["views", "pages", "components", "ui", "frontend", "templates"],
        "api": ["api", "routes", "controllers", "handlers", "endpoints"],
        "service": ["services", "service", "business", "logic", "core"],
        "data": ["models", "entities", "schemas", "data", "repository", "dao"],
        "utils": ["utils", "helpers", "common", "shared", "lib"],
        "config": ["config", "settings", "configuration"],
        "tests": ["tests", "test", "__tests__", "spec"],
    }
    
    # 常见入口点文件
    ENTRY_POINT_PATTERNS = [
        "main.py", "app.py", "__main__.py", "index.py",
        "index.js", "index.ts", "main.js", "main.ts", "app.js", "app.ts",
        "Main.java", "Application.java", "App.java",
        "server.py", "server.js", "server.ts",
        "manage.py", "wsgi.py", "asgi.py",
    ]
    
    def __init__(self):
        self.scanner = RepoScanner()
        self._parse_cache: Dict[str, ParseResult] = {}
    
    def analyze(self, repo_path: Path) -> StructureAnalysis:
        """
        分析代码仓库结构
        
        Args:
            repo_path: 仓库路径
            
        Returns:
            StructureAnalysis 分析结果
        """
        repo_path = Path(repo_path).resolve()
        logger.info(f"开始分析代码结构: {repo_path}")
        
        # 扫描仓库
        repo_info = self.scanner.scan_repository(repo_path, load_content=True)
        
        # 解析所有代码文件
        all_classes: List[ClassInfo] = []
        all_functions: List[FunctionInfo] = []
        
        for file_info in repo_info.files:
            if file_info.language and file_info.content:
                parse_result = self._parse_file(file_info)
                if parse_result:
                    all_classes.extend(parse_result.classes)
                    all_functions.extend(parse_result.functions)
                    for cls in parse_result.classes:
                        all_functions.extend(cls.methods)
        
        # 创建分析结果
        analysis = StructureAnalysis(
            repo_name=repo_info.name,
            total_files=repo_info.total_files,
            total_classes=len(all_classes),
            total_functions=len(all_functions)
        )
        
        # 识别模块
        analysis.modules = self._identify_modules(repo_path, repo_info)
        
        # 识别架构模式
        analysis.architecture_patterns = self._identify_architecture_patterns(
            repo_path, repo_info, all_classes
        )
        
        # 识别入口点
        analysis.entry_points = self._find_entry_points(repo_path, repo_info)
        
        # 识别分层结构
        analysis.layer_structure = self._identify_layers(repo_path, repo_info)
        
        logger.info(
            f"结构分析完成: {analysis.total_classes} 类, "
            f"{analysis.total_functions} 函数, "
            f"{len(analysis.modules)} 模块"
        )
        
        return analysis
    
    def _parse_file(self, file_info: FileInfo) -> Optional[ParseResult]:
        """解析文件并缓存结果"""
        cache_key = str(file_info.path)
        
        if cache_key in self._parse_cache:
            return self._parse_cache[cache_key]
        
        parser = get_parser_for_language(file_info.language)
        if not parser:
            return None
        
        try:
            result = parser.parse(file_info.content, str(file_info.path))
            self._parse_cache[cache_key] = result
            return result
        except Exception as e:
            logger.warning(f"解析文件失败: {file_info.path}, 错误: {e}")
            return None
    
    def _identify_modules(
        self, 
        repo_path: Path, 
        repo_info: RepoInfo
    ) -> List[ModuleInfo]:
        """识别代码模块"""
        modules = []
        module_dirs: Set[str] = set()
        
        # 根据目录结构识别模块
        for file_info in repo_info.files:
            rel_path = Path(file_info.relative_path)
            parts = rel_path.parts
            
            # 取第一级或第二级目录作为模块
            if len(parts) > 1:
                module_path = parts[0]
                # 跳过常见的非模块目录
                if module_path not in ["tests", "test", "docs", "examples"]:
                    module_dirs.add(module_path)
        
        # 为每个模块收集信息
        for module_name in module_dirs:
            module_path = repo_path / module_name
            if not module_path.is_dir():
                continue
            
            module_files = []
            module_classes = []
            module_functions = []
            module_exports = []
            
            for file_info in repo_info.files:
                if file_info.relative_path.startswith(module_name + "/"):
                    module_files.append(file_info.relative_path)
                    
                    # 解析文件获取类和函数
                    if file_info.content and file_info.language:
                        parse_result = self._parse_file(file_info)
                        if parse_result:
                            module_classes.extend([c.name for c in parse_result.classes])
                            module_functions.extend([f.name for f in parse_result.functions])
                            
                            # 识别导出
                            for imp in parse_result.imports:
                                if "__all__" in imp.code:
                                    module_exports.extend(imp.names)
            
            # 尝试从 __init__.py 或 index 文件获取描述
            description = self._get_module_description(module_path)
            
            modules.append(ModuleInfo(
                name=module_name,
                path=str(module_path.relative_to(repo_path)),
                description=description,
                files=module_files,
                classes=module_classes,
                functions=module_functions,
                exports=module_exports
            ))
        
        return modules
    
    def _get_module_description(self, module_path: Path) -> Optional[str]:
        """获取模块描述"""
        # 尝试从 __init__.py 获取模块文档
        init_files = ["__init__.py", "index.py", "index.js", "index.ts"]
        
        for init_file in init_files:
            init_path = module_path / init_file
            if init_path.exists():
                try:
                    content = init_path.read_text(encoding='utf-8')
                    # 提取模块级文档字符串
                    docstring_match = re.search(
                        r'^["\'][\"\'][\"\'](.+?)["\'][\"\'][\"\']',
                        content, 
                        re.DOTALL
                    )
                    if docstring_match:
                        return docstring_match.group(1).strip().split('\n')[0]
                    
                    # 提取首行注释
                    comment_match = re.search(r'^#\s*(.+)$', content, re.MULTILINE)
                    if comment_match:
                        return comment_match.group(1).strip()
                except Exception:
                    pass
        
        return None
    
    def _identify_architecture_patterns(
        self, 
        repo_path: Path,
        repo_info: RepoInfo,
        all_classes: List[ClassInfo]
    ) -> List[ArchitecturePattern]:
        """识别架构模式"""
        patterns = []
        
        # 检测 MVC/MVP/MVVM 模式
        mvc_evidence = []
        has_models = any("model" in f.relative_path.lower() for f in repo_info.files)
        has_views = any("view" in f.relative_path.lower() for f in repo_info.files)
        has_controllers = any(
            any(kw in f.relative_path.lower() for kw in ["controller", "handler", "presenter"])
            for f in repo_info.files
        )
        
        if has_models:
            mvc_evidence.append("存在 models 目录/文件")
        if has_views:
            mvc_evidence.append("存在 views 目录/文件")
        if has_controllers:
            mvc_evidence.append("存在 controllers/handlers 目录/文件")
        
        if len(mvc_evidence) >= 2:
            patterns.append(ArchitecturePattern(
                name="MVC/MVP",
                confidence=len(mvc_evidence) / 3,
                evidence=mvc_evidence
            ))
        
        # 检测分层架构
        layer_evidence = []
        for layer, keywords in self.LAYER_PATTERNS.items():
            for keyword in keywords:
                if any(keyword in f.relative_path.lower() for f in repo_info.files):
                    layer_evidence.append(f"存在 {layer} 层 ({keyword})")
                    break
        
        if len(layer_evidence) >= 3:
            patterns.append(ArchitecturePattern(
                name="分层架构",
                confidence=min(len(layer_evidence) / 5, 1.0),
                evidence=layer_evidence
            ))
        
        # 检测微服务/模块化架构
        service_dirs = [
            d for d in repo_path.iterdir() 
            if d.is_dir() and "service" in d.name.lower()
        ]
        if len(service_dirs) >= 2:
            patterns.append(ArchitecturePattern(
                name="微服务/模块化",
                confidence=min(len(service_dirs) / 5, 1.0),
                evidence=[f"包含 {len(service_dirs)} 个服务模块"]
            ))
        
        # 检测工厂模式
        factory_classes = [c for c in all_classes if "factory" in c.name.lower()]
        if factory_classes:
            patterns.append(ArchitecturePattern(
                name="工厂模式",
                confidence=0.8,
                evidence=[f"发现 {len(factory_classes)} 个工厂类"]
            ))
        
        # 检测单例模式
        singleton_evidence = []
        for cls in all_classes:
            if any("singleton" in d.lower() for d in cls.decorators):
                singleton_evidence.append(f"{cls.name} 使用单例装饰器")
            elif any(m.name in ["__new__", "get_instance", "getInstance"] for m in cls.methods):
                singleton_evidence.append(f"{cls.name} 可能是单例")
        
        if singleton_evidence:
            patterns.append(ArchitecturePattern(
                name="单例模式",
                confidence=0.7,
                evidence=singleton_evidence[:5]
            ))
        
        return patterns
    
    def _find_entry_points(
        self, 
        repo_path: Path, 
        repo_info: RepoInfo
    ) -> List[str]:
        """找到项目入口点"""
        entry_points = []
        
        for file_info in repo_info.files:
            filename = Path(file_info.relative_path).name
            
            # 检查是否是常见入口点文件
            if filename in self.ENTRY_POINT_PATTERNS:
                entry_points.append(file_info.relative_path)
                continue
            
            # 检查文件内容是否包含入口代码
            if file_info.content:
                # Python main block
                if 'if __name__ == "__main__"' in file_info.content:
                    entry_points.append(file_info.relative_path)
                # JavaScript/TypeScript exports
                elif 'module.exports' in file_info.content or 'export default' in file_info.content:
                    if filename in ["index.js", "index.ts", "app.js", "app.ts"]:
                        entry_points.append(file_info.relative_path)
        
        return list(set(entry_points))
    
    def _identify_layers(
        self, 
        repo_path: Path, 
        repo_info: RepoInfo
    ) -> Dict[str, List[str]]:
        """识别代码分层结构"""
        layers = {layer: [] for layer in self.LAYER_PATTERNS.keys()}
        
        for file_info in repo_info.files:
            rel_path = file_info.relative_path.lower()
            
            for layer, keywords in self.LAYER_PATTERNS.items():
                if any(keyword in rel_path for keyword in keywords):
                    layers[layer].append(file_info.relative_path)
                    break
        
        # 过滤空层
        return {k: v for k, v in layers.items() if v}
    
    def get_module_summary(self, analysis: StructureAnalysis) -> str:
        """生成模块摘要文本"""
        lines = [f"# {analysis.repo_name} 代码结构分析\n"]
        
        # 概述
        lines.append(f"## 概述")
        lines.append(f"- 文件总数: {analysis.total_files}")
        lines.append(f"- 类总数: {analysis.total_classes}")
        lines.append(f"- 函数总数: {analysis.total_functions}")
        lines.append("")
        
        # 模块
        if analysis.modules:
            lines.append("## 模块")
            for module in analysis.modules:
                desc = f" - {module.description}" if module.description else ""
                lines.append(f"- **{module.name}**{desc}")
                lines.append(f"  - 文件数: {len(module.files)}")
                if module.classes:
                    lines.append(f"  - 主要类: {', '.join(module.classes[:5])}")
            lines.append("")
        
        # 架构模式
        if analysis.architecture_patterns:
            lines.append("## 识别到的架构模式")
            for pattern in analysis.architecture_patterns:
                lines.append(f"- **{pattern.name}** (置信度: {pattern.confidence:.0%})")
                for evidence in pattern.evidence[:3]:
                    lines.append(f"  - {evidence}")
            lines.append("")
        
        # 入口点
        if analysis.entry_points:
            lines.append("## 入口点")
            for ep in analysis.entry_points:
                lines.append(f"- {ep}")
            lines.append("")
        
        return '\n'.join(lines)

