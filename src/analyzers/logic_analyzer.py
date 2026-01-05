"""
业务逻辑分析器
分析代码中的业务流程、规则和关键路径
"""

from pathlib import Path
from typing import List, Dict, Optional, Set, Tuple
from dataclasses import dataclass, field
import logging
import re

from ..parsers.ast_parser import (
    ParseResult, get_parser_for_language,
    FunctionInfo, ClassInfo
)
from ..parsers.doc_extractor import DocExtractor

logger = logging.getLogger(__name__)


@dataclass
class BusinessRule:
    """业务规则"""
    name: str
    description: str
    location: str  # 文件路径:行号
    code_snippet: str
    rule_type: str  # validation, calculation, workflow, permission, etc.
    conditions: List[str] = field(default_factory=list)
    actions: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "description": self.description,
            "location": self.location,
            "code_snippet": self.code_snippet,
            "rule_type": self.rule_type,
            "conditions": self.conditions,
            "actions": self.actions
        }


@dataclass
class CodeFlow:
    """代码执行流程"""
    name: str
    entry_point: str
    steps: List[Dict[str, str]] = field(default_factory=list)
    branches: List[Dict[str, str]] = field(default_factory=list)
    called_functions: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "entry_point": self.entry_point,
            "steps": self.steps,
            "branches": self.branches,
            "called_functions": self.called_functions
        }


@dataclass
class LogicAnalysis:
    """业务逻辑分析结果"""
    file_path: str
    business_rules: List[BusinessRule] = field(default_factory=list)
    code_flows: List[CodeFlow] = field(default_factory=list)
    key_functions: List[FunctionInfo] = field(default_factory=list)
    error_handlers: List[Dict] = field(default_factory=list)
    api_endpoints: List[Dict] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            "file_path": self.file_path,
            "business_rules": [r.to_dict() for r in self.business_rules],
            "code_flows": [f.to_dict() for f in self.code_flows],
            "key_functions": [f.to_dict() for f in self.key_functions],
            "error_handlers": self.error_handlers,
            "api_endpoints": self.api_endpoints
        }


class LogicAnalyzer:
    """
    业务逻辑分析器
    
    分析代码中的业务规则、流程和关键路径
    """
    
    # 业务规则关键词
    RULE_KEYWORDS = {
        "validation": ["validate", "check", "verify", "assert", "ensure", "is_valid"],
        "calculation": ["calculate", "compute", "sum", "total", "average", "count"],
        "workflow": ["process", "handle", "execute", "run", "perform", "flow"],
        "permission": ["authorize", "authenticate", "permission", "role", "access", "can_"],
        "transform": ["convert", "transform", "parse", "format", "serialize", "map"],
    }
    
    # API 装饰器/注解模式
    API_PATTERNS = {
        "python": [
            r'@app\.(get|post|put|delete|patch)\s*\(\s*[\'"]([^\'"]+)[\'"]',
            r'@router\.(get|post|put|delete|patch)\s*\(\s*[\'"]([^\'"]+)[\'"]',
            r'@blueprint\.(route)\s*\(\s*[\'"]([^\'"]+)[\'"]',
        ],
        "javascript": [
            r'(get|post|put|delete|patch)\s*\(\s*[\'"]([^\'"]+)[\'"]',
            r'@(Get|Post|Put|Delete|Patch)\s*\(\s*[\'"]?([^\'")\s]+)[\'"]?\s*\)',
        ],
        "java": [
            r'@(GetMapping|PostMapping|PutMapping|DeleteMapping|RequestMapping)\s*\(\s*[\'"]?([^\'")\s]+)[\'"]?\s*\)',
        ]
    }
    
    def __init__(self):
        self.doc_extractor = DocExtractor()
    
    def analyze_file(
        self, 
        code: str, 
        file_path: str, 
        language: str
    ) -> LogicAnalysis:
        """
        分析单个文件的业务逻辑
        
        Args:
            code: 源代码
            file_path: 文件路径
            language: 编程语言
            
        Returns:
            LogicAnalysis 分析结果
        """
        analysis = LogicAnalysis(file_path=file_path)
        
        # 解析代码
        parser = get_parser_for_language(language)
        if not parser:
            logger.warning(f"不支持的语言: {language}")
            return analysis
        
        try:
            parse_result = parser.parse(code, file_path)
        except Exception as e:
            logger.error(f"解析失败: {file_path}, 错误: {e}")
            return analysis
        
        # 分析业务规则
        analysis.business_rules = self._extract_business_rules(
            parse_result, code, file_path, language
        )
        
        # 分析代码流程
        analysis.code_flows = self._extract_code_flows(parse_result, code)
        
        # 识别关键函数
        analysis.key_functions = self._identify_key_functions(parse_result)
        
        # 分析错误处理
        analysis.error_handlers = self._extract_error_handlers(code, language)
        
        # 提取 API 端点
        analysis.api_endpoints = self._extract_api_endpoints(code, language)
        
        return analysis
    
    def _extract_business_rules(
        self, 
        parse_result: ParseResult,
        code: str,
        file_path: str,
        language: str
    ) -> List[BusinessRule]:
        """提取业务规则"""
        rules = []
        all_functions = parse_result.get_all_functions()
        
        for func in all_functions:
            # 根据函数名识别规则类型
            rule_type = self._identify_rule_type(func.name)
            
            if rule_type:
                # 提取条件和动作
                conditions, actions = self._extract_conditions_actions(func.code, language)
                
                # 生成规则描述
                description = func.docstring or self._generate_rule_description(
                    func.name, rule_type
                )
                
                rules.append(BusinessRule(
                    name=func.name,
                    description=description,
                    location=f"{file_path}:{func.start_line}",
                    code_snippet=func.code,
                    rule_type=rule_type,
                    conditions=conditions,
                    actions=actions
                ))
        
        return rules
    
    def _identify_rule_type(self, func_name: str) -> Optional[str]:
        """根据函数名识别业务规则类型"""
        func_name_lower = func_name.lower()
        
        for rule_type, keywords in self.RULE_KEYWORDS.items():
            if any(kw in func_name_lower for kw in keywords):
                return rule_type
        
        return None
    
    def _extract_conditions_actions(
        self, 
        code: str, 
        language: str
    ) -> Tuple[List[str], List[str]]:
        """提取代码中的条件和动作"""
        conditions = []
        actions = []
        
        # 提取 if 条件
        if_pattern = r'if\s+(.+?):'  # Python
        if language in ["javascript", "typescript", "java"]:
            if_pattern = r'if\s*\((.+?)\)'
        
        for match in re.finditer(if_pattern, code):
            condition = match.group(1).strip()
            if len(condition) < 200:  # 过滤过长的条件
                conditions.append(condition)
        
        # 提取函数调用作为动作
        call_pattern = r'(\w+)\s*\('
        for match in re.finditer(call_pattern, code):
            func_name = match.group(1)
            # 过滤常见的非业务函数
            if func_name not in ["if", "for", "while", "print", "len", "str", "int", "float"]:
                if func_name not in actions:
                    actions.append(func_name)
        
        return conditions[:10], actions[:10]
    
    def _generate_rule_description(self, func_name: str, rule_type: str) -> str:
        """生成规则描述"""
        # 将函数名转换为可读描述
        words = re.sub(r'([A-Z])', r' \1', func_name)
        words = words.replace('_', ' ').strip().lower()
        
        type_descriptions = {
            "validation": "验证规则",
            "calculation": "计算逻辑",
            "workflow": "业务流程",
            "permission": "权限控制",
            "transform": "数据转换",
        }
        
        return f"{type_descriptions.get(rule_type, '业务规则')}: {words}"
    
    def _extract_code_flows(
        self, 
        parse_result: ParseResult,
        code: str
    ) -> List[CodeFlow]:
        """提取代码执行流程"""
        flows = []
        
        for func in parse_result.functions:
            # 分析较复杂的函数
            if func.complexity > 2 or len(func.code.split('\n')) > 10:
                flow = self._analyze_function_flow(func, code)
                if flow.steps:
                    flows.append(flow)
        
        # 分析类中的重要方法
        for cls in parse_result.classes:
            for method in cls.methods:
                # 重点分析入口方法
                if method.name in ["__init__", "__call__", "run", "execute", "process", "handle"]:
                    flow = self._analyze_function_flow(method, code)
                    flow.name = f"{cls.name}.{method.name}"
                    if flow.steps:
                        flows.append(flow)
        
        return flows
    
    def _analyze_function_flow(self, func: FunctionInfo, code: str) -> CodeFlow:
        """分析函数执行流程"""
        flow = CodeFlow(
            name=func.name,
            entry_point=f"line {func.start_line}"
        )
        
        lines = func.code.split('\n')
        step_num = 0
        
        for i, line in enumerate(lines):
            stripped = line.strip()
            
            # 跳过空行和注释
            if not stripped or stripped.startswith('#') or stripped.startswith('//'):
                continue
            
            # 识别分支
            if stripped.startswith(('if ', 'elif ', 'else:', 'else {', 'switch')):
                flow.branches.append({
                    "line": i + func.start_line,
                    "condition": stripped
                })
            
            # 识别函数调用
            call_match = re.search(r'(\w+)\s*\(', stripped)
            if call_match:
                called = call_match.group(1)
                if called not in ["if", "for", "while", "return", "print"]:
                    if called not in flow.called_functions:
                        flow.called_functions.append(called)
            
            # 识别关键步骤
            if any(kw in stripped.lower() for kw in ['return', '=', 'await', 'yield']):
                step_num += 1
                flow.steps.append({
                    "step": step_num,
                    "line": i + func.start_line,
                    "description": self._summarize_line(stripped)
                })
        
        return flow
    
    def _summarize_line(self, line: str) -> str:
        """生成代码行的简短描述"""
        line = line.strip()
        
        if line.startswith('return'):
            return "返回结果"
        elif '=' in line and not any(op in line for op in ['==', '!=', '<=', '>=']):
            var_name = line.split('=')[0].strip()
            return f"赋值 {var_name}"
        elif 'await' in line:
            return "异步调用"
        elif line.startswith('raise') or line.startswith('throw'):
            return "抛出异常"
        
        return line[:50] + "..." if len(line) > 50 else line
    
    def _identify_key_functions(self, parse_result: ParseResult) -> List[FunctionInfo]:
        """识别关键函数"""
        key_functions = []
        all_functions = parse_result.get_all_functions()
        
        for func in all_functions:
            # 基于多个因素评分
            score = 0
            
            # 复杂度
            if func.complexity > 3:
                score += 2
            
            # 有文档字符串
            if func.docstring:
                score += 1
            
            # 函数名表明重要性
            important_keywords = ["main", "process", "handle", "execute", "run", "create", "update", "delete"]
            if any(kw in func.name.lower() for kw in important_keywords):
                score += 2
            
            # 参数数量
            if len(func.parameters) >= 3:
                score += 1
            
            # 代码行数
            lines = len(func.code.split('\n'))
            if lines > 20:
                score += 1
            
            if score >= 3:
                key_functions.append(func)
        
        # 按复杂度排序，返回前10个
        key_functions.sort(key=lambda f: f.complexity, reverse=True)
        return key_functions[:10]
    
    def _extract_error_handlers(self, code: str, language: str) -> List[Dict]:
        """提取错误处理代码"""
        handlers = []
        
        if language == "python":
            # Python try-except
            pattern = r'except\s+(\w+(?:\s+as\s+\w+)?)\s*:'
            for match in re.finditer(pattern, code):
                line_num = code[:match.start()].count('\n') + 1
                handlers.append({
                    "type": "exception_handler",
                    "exception": match.group(1),
                    "line": line_num
                })
        
        elif language in ["javascript", "typescript"]:
            # JavaScript try-catch
            pattern = r'catch\s*\(\s*(\w+)\s*\)'
            for match in re.finditer(pattern, code):
                line_num = code[:match.start()].count('\n') + 1
                handlers.append({
                    "type": "exception_handler",
                    "exception": match.group(1),
                    "line": line_num
                })
        
        elif language == "java":
            # Java try-catch
            pattern = r'catch\s*\(\s*(\w+(?:\s*\|\s*\w+)*)\s+(\w+)\s*\)'
            for match in re.finditer(pattern, code):
                line_num = code[:match.start()].count('\n') + 1
                handlers.append({
                    "type": "exception_handler",
                    "exception": match.group(1),
                    "variable": match.group(2),
                    "line": line_num
                })
        
        return handlers
    
    def _extract_api_endpoints(self, code: str, language: str) -> List[Dict]:
        """提取 API 端点"""
        endpoints = []
        patterns = self.API_PATTERNS.get(language, [])
        
        for pattern in patterns:
            for match in re.finditer(pattern, code):
                method = match.group(1).upper()
                path = match.group(2)
                line_num = code[:match.start()].count('\n') + 1
                
                endpoints.append({
                    "method": method,
                    "path": path,
                    "line": line_num
                })
        
        return endpoints
    
    def generate_logic_summary(self, analysis: LogicAnalysis) -> str:
        """生成业务逻辑摘要"""
        lines = [f"# 业务逻辑分析: {analysis.file_path}\n"]
        
        if analysis.business_rules:
            lines.append("## 业务规则")
            for rule in analysis.business_rules:
                lines.append(f"### {rule.name}")
                lines.append(f"- 类型: {rule.rule_type}")
                lines.append(f"- 描述: {rule.description}")
                if rule.conditions:
                    lines.append(f"- 条件: {', '.join(rule.conditions[:3])}")
                lines.append("")
        
        if analysis.api_endpoints:
            lines.append("## API 端点")
            for ep in analysis.api_endpoints:
                lines.append(f"- {ep['method']} {ep['path']} (line {ep['line']})")
            lines.append("")
        
        if analysis.key_functions:
            lines.append("## 关键函数")
            for func in analysis.key_functions[:5]:
                lines.append(f"- **{func.name}** (复杂度: {func.complexity})")
                if func.docstring:
                    lines.append(f"  {func.docstring.split(chr(10))[0]}")
            lines.append("")
        
        return '\n'.join(lines)

