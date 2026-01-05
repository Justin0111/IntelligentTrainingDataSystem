"""
设计方案生成器模块
场景2：为给定的需求生成基于本地代码仓架构的设计方案
"""

import json
import logging
from pathlib import Path
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime

from ..config import get_config, GeneratorConfig
from ..analyzers.structure_analyzer import StructureAnalyzer, StructureAnalysis
from ..analyzers.dependency_analyzer import DependencyAnalyzer, DependencyGraph
from ..parsers.repo_scanner import RepoScanner
from .llm_client import LLMClient, PromptTemplate, create_llm_client
from ..utils.helpers import generate_id

logger = logging.getLogger(__name__)


@dataclass
class ReasoningStep:
    """推理步骤"""
    step: int
    thought: str
    
    def to_dict(self) -> Dict:
        return {"step": self.step, "thought": self.thought}


@dataclass 
class ComponentDesign:
    """组件设计"""
    name: str
    component_type: str  # class, module, service
    responsibility: str
    interfaces: List[Dict[str, str]] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "type": self.component_type,
            "responsibility": self.responsibility,
            "interfaces": self.interfaces
        }


@dataclass
class DataStructure:
    """数据结构设计"""
    name: str
    fields: List[Dict[str, str]]
    description: str = ""
    
    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "fields": self.fields,
            "description": self.description
        }


@dataclass
class IntegrationPoint:
    """集成点"""
    target_module: str
    integration_type: str  # extend, modify, call
    description: str
    
    def to_dict(self) -> Dict:
        return {
            "target_module": self.target_module,
            "integration_type": self.integration_type,
            "description": self.description
        }


@dataclass
class TradeOff:
    """设计权衡"""
    decision: str
    pros: List[str]
    cons: List[str]
    
    def to_dict(self) -> Dict:
        return {
            "decision": self.decision,
            "pros": self.pros,
            "cons": self.cons
        }


@dataclass
class DesignProposal:
    """设计方案"""
    id: str
    requirement: str
    overview: str
    components: List[ComponentDesign]
    data_structures: List[DataStructure]
    integration_points: List[IntegrationPoint]
    reasoning_trace: List[ReasoningStep]
    design_patterns_used: List[str] = field(default_factory=list)
    trade_offs: List[TradeOff] = field(default_factory=list)
    estimated_complexity: str = "medium"
    affected_files: List[str] = field(default_factory=list)
    architecture_context: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "type": "architecture_design",
            "requirement": self.requirement,
            "design_proposal": {
                "overview": self.overview,
                "components": [c.to_dict() for c in self.components],
                "data_structures": [d.to_dict() for d in self.data_structures],
                "integration_points": [i.to_dict() for i in self.integration_points]
            },
            "reasoning_trace": [r.to_dict() for r in self.reasoning_trace],
            "design_patterns_used": self.design_patterns_used,
            "trade_offs": [t.to_dict() for t in self.trade_offs],
            "estimated_complexity": self.estimated_complexity,
            "affected_files": self.affected_files,
            "architecture_context": self.architecture_context,
            "metadata": self.metadata,
            "created_at": self.created_at
        }
    
    def to_training_format(self) -> Dict:
        """转换为训练数据格式"""
        # 构建推理过程文本
        reasoning_text = "\n".join([
            f"步骤{r.step}: {r.thought}" for r in self.reasoning_trace
        ])
        
        # 构建组件设计文本
        components_text = "\n".join([
            f"- {c.name} ({c.component_type}): {c.responsibility}"
            for c in self.components
        ])
        
        # 构建集成点文本
        integration_text = "\n".join([
            f"- {i.target_module}: {i.description}"
            for i in self.integration_points
        ])
        
        full_answer = f"""# 设计方案

## 分析过程
{reasoning_text}

## 方案概述
{self.overview}

## 组件设计
{components_text}

## 集成方案
{integration_text}

## 使用的设计模式
{', '.join(self.design_patterns_used)}

## 复杂度评估
{self.estimated_complexity}
"""
        
        return {
            "instruction": f"请为以下需求设计一个基于现有代码架构的解决方案：{self.requirement}",
            "input": f"代码架构信息：\n{json.dumps(self.architecture_context, ensure_ascii=False, indent=2)}",
            "output": full_answer
        }


class DesignGenerator:
    """
    设计方案生成器
    
    分析代码仓库架构，为新需求生成设计方案
    """
    
    # 常见需求类型和对应的设计模式建议
    REQUIREMENT_PATTERNS = {
        "authentication": ["Strategy", "Factory", "Singleton"],
        "authorization": ["Strategy", "Decorator", "Chain of Responsibility"],
        "caching": ["Proxy", "Decorator", "Singleton"],
        "logging": ["Decorator", "Observer", "Singleton"],
        "notification": ["Observer", "Mediator", "Strategy"],
        "payment": ["Strategy", "Factory", "State"],
        "search": ["Strategy", "Iterator", "Composite"],
        "upload": ["Strategy", "Factory", "Template Method"],
        "api": ["Facade", "Adapter", "Factory"],
        "database": ["Repository", "Unit of Work", "Factory"],
    }
    
    def __init__(
        self,
        llm_client: Optional[LLMClient] = None,
        config: Optional[GeneratorConfig] = None
    ):
        """
        初始化设计方案生成器
        
        Args:
            llm_client: LLM 客户端
            config: 生成器配置
        """
        self.config = config or get_config().generator
        self.llm_client = llm_client or create_llm_client()
        self.prompt_template = PromptTemplate()
        self.structure_analyzer = StructureAnalyzer()
        self.dependency_analyzer = DependencyAnalyzer()
        self.scanner = RepoScanner()
    
    def generate_design(
        self,
        repo_path: Path,
        requirement: str,
        context: Optional[Dict] = None
    ) -> DesignProposal:
        """
        为需求生成设计方案
        
        Args:
            repo_path: 仓库路径
            requirement: 需求描述
            context: 附加上下文信息
            
        Returns:
            DesignProposal 设计方案
        """
        repo_path = Path(repo_path).resolve()
        logger.info(f"开始为需求生成设计方案: {requirement[:50]}...")
        
        # 分析代码结构
        structure_analysis = self.structure_analyzer.analyze(repo_path)
        
        # 分析依赖关系
        dependency_graph = self.dependency_analyzer.analyze_repository(repo_path)
        
        # 获取项目结构
        project_structure = self.scanner.get_project_structure(repo_path)
        
        # 构建架构上下文
        architecture_context = self._build_architecture_context(
            structure_analysis, dependency_graph, project_structure
        )
        
        # 识别相关设计模式
        suggested_patterns = self._suggest_patterns(requirement)
        
        # 使用 LLM 生成设计方案
        try:
            design = self._generate_with_llm(
                requirement,
                architecture_context,
                suggested_patterns
            )
        except Exception as e:
            logger.warning(f"LLM 生成失败: {e}，使用模板生成")
            design = self._generate_template_design(
                requirement,
                architecture_context,
                suggested_patterns
            )
        
        # 更新元数据
        design.architecture_context = architecture_context
        design.metadata = {
            "repo_path": str(repo_path),
            "generated_at": datetime.now().isoformat(),
            "structure_summary": {
                "total_files": structure_analysis.total_files,
                "total_classes": structure_analysis.total_classes,
                "modules": [m.name for m in structure_analysis.modules]
            }
        }
        
        logger.info(f"设计方案生成完成，包含 {len(design.components)} 个组件")
        return design
    
    def _build_architecture_context(
        self,
        structure: StructureAnalysis,
        dependencies: DependencyGraph,
        project_structure: str
    ) -> Dict[str, Any]:
        """构建架构上下文信息"""
        # 模块描述
        module_descriptions = {}
        for module in structure.modules:
            module_descriptions[module.name] = {
                "description": module.description or "无描述",
                "classes": module.classes[:10],
                "functions": module.functions[:10]
            }
        
        # 现有设计模式
        existing_patterns = [
            p.name for p in structure.architecture_patterns
            if p.confidence > 0.5
        ]
        
        # 依赖关系摘要
        dependency_summary = {
            "internal_modules": list(dependencies.nodes)[:20],
            "external_dependencies": dependencies.external_dependencies[:20],
            "has_circular_dependencies": len(dependencies.circular_dependencies) > 0
        }
        
        return {
            "project_structure": project_structure[:2000],  # 限制长度
            "module_descriptions": module_descriptions,
            "existing_patterns": existing_patterns,
            "dependencies": dependency_summary,
            "entry_points": structure.entry_points,
            "layer_structure": structure.layer_structure
        }
    
    def _suggest_patterns(self, requirement: str) -> List[str]:
        """根据需求建议设计模式"""
        requirement_lower = requirement.lower()
        suggested = []
        
        for keyword, patterns in self.REQUIREMENT_PATTERNS.items():
            if keyword in requirement_lower:
                suggested.extend(patterns)
        
        # 去重并限制数量
        return list(dict.fromkeys(suggested))[:5]
    
    def _generate_with_llm(
        self,
        requirement: str,
        architecture_context: Dict,
        suggested_patterns: List[str]
    ) -> DesignProposal:
        """使用 LLM 生成设计方案"""
        # 渲染 prompt
        prompt = self.prompt_template.render(
            "design_prompt",
            project_structure=architecture_context.get("project_structure", ""),
            module_descriptions=json.dumps(
                architecture_context.get("module_descriptions", {}),
                ensure_ascii=False,
                indent=2
            ),
            existing_patterns=", ".join(architecture_context.get("existing_patterns", [])),
            dependencies=json.dumps(
                architecture_context.get("dependencies", {}),
                ensure_ascii=False,
                indent=2
            ),
            requirement=requirement
        )
        
        # 调用 LLM
        response = self.llm_client.generate_with_json(prompt)
        
        # 解析响应
        return self._parse_design_response(response, requirement)
    
    def _parse_design_response(
        self,
        response: Dict,
        requirement: str
    ) -> DesignProposal:
        """解析 LLM 响应为 DesignProposal"""
        # 解析组件
        components = []
        for comp in response.get("components", []):
            interfaces = comp.get("interfaces", [])
            components.append(ComponentDesign(
                name=comp.get("name", "Unknown"),
                component_type=comp.get("type", "class"),
                responsibility=comp.get("responsibility", ""),
                interfaces=interfaces if isinstance(interfaces, list) else []
            ))
        
        # 解析数据结构
        data_structures = []
        for ds in response.get("data_structures", []):
            data_structures.append(DataStructure(
                name=ds.get("name", "Unknown"),
                fields=ds.get("fields", []),
                description=ds.get("description", "")
            ))
        
        # 解析集成点
        integration_points = []
        for ip in response.get("integration_points", []):
            integration_points.append(IntegrationPoint(
                target_module=ip.get("target_module", ""),
                integration_type=ip.get("integration_type", "call"),
                description=ip.get("description", "")
            ))
        
        # 解析推理步骤
        reasoning_trace = []
        for item in response.get("reasoning_trace", []):
            reasoning_trace.append(ReasoningStep(
                step=item.get("step", len(reasoning_trace) + 1),
                thought=item.get("thought", "")
            ))
        
        # 解析权衡
        trade_offs = []
        for to in response.get("trade_offs", []):
            trade_offs.append(TradeOff(
                decision=to.get("decision", ""),
                pros=to.get("pros", []),
                cons=to.get("cons", [])
            ))
        
        return DesignProposal(
            id=generate_id("design"),
            requirement=requirement,
            overview=response.get("overview", ""),
            components=components,
            data_structures=data_structures,
            integration_points=integration_points,
            reasoning_trace=reasoning_trace,
            design_patterns_used=response.get("design_patterns_used", []),
            trade_offs=trade_offs,
            estimated_complexity=response.get("estimated_complexity", "medium"),
            affected_files=response.get("affected_files", [])
        )
    
    def _generate_template_design(
        self,
        requirement: str,
        architecture_context: Dict,
        suggested_patterns: List[str]
    ) -> DesignProposal:
        """使用模板生成备用设计方案"""
        # 生成推理步骤
        reasoning_trace = [
            ReasoningStep(1, f"分析需求：{requirement}"),
            ReasoningStep(2, f"检查现有架构，识别可复用的模块"),
            ReasoningStep(3, f"确定需要新增的组件"),
            ReasoningStep(4, f"设计组件接口和交互方式"),
            ReasoningStep(5, f"评估集成方案和影响范围")
        ]
        
        # 根据需求推断组件
        components = []
        
        # 主要业务组件
        main_component_name = self._extract_component_name(requirement)
        components.append(ComponentDesign(
            name=f"{main_component_name}Service",
            component_type="class",
            responsibility=f"处理{requirement}的核心业务逻辑",
            interfaces=[
                {"name": "execute", "signature": "def execute(self, params: Dict) -> Result", "description": "执行主要操作"}
            ]
        ))
        
        # 如果有数据处理需求，添加数据访问组件
        if any(kw in requirement.lower() for kw in ["存储", "保存", "查询", "数据"]):
            components.append(ComponentDesign(
                name=f"{main_component_name}Repository",
                component_type="class",
                responsibility="数据访问层，处理数据的增删改查",
                interfaces=[
                    {"name": "save", "signature": "def save(self, entity) -> bool", "description": "保存数据"},
                    {"name": "find", "signature": "def find(self, id) -> Optional[Entity]", "description": "查询数据"}
                ]
            ))
        
        # 数据结构
        data_structures = [
            DataStructure(
                name=f"{main_component_name}Request",
                fields=[
                    {"name": "id", "type": "str", "description": "请求ID"},
                    {"name": "data", "type": "Dict", "description": "请求数据"}
                ],
                description="请求数据结构"
            ),
            DataStructure(
                name=f"{main_component_name}Response",
                fields=[
                    {"name": "success", "type": "bool", "description": "是否成功"},
                    {"name": "data", "type": "Optional[Dict]", "description": "响应数据"},
                    {"name": "error", "type": "Optional[str]", "description": "错误信息"}
                ],
                description="响应数据结构"
            )
        ]
        
        # 集成点
        integration_points = []
        modules = architecture_context.get("module_descriptions", {})
        
        # 根据现有模块确定集成点
        for module_name, module_info in list(modules.items())[:3]:
            integration_points.append(IntegrationPoint(
                target_module=module_name,
                integration_type="call",
                description=f"与 {module_name} 模块集成"
            ))
        
        # 权衡
        trade_offs = [
            TradeOff(
                decision="采用分层架构设计",
                pros=["代码结构清晰", "易于测试", "便于维护"],
                cons=["增加代码量", "可能存在过度设计"]
            )
        ]
        
        return DesignProposal(
            id=generate_id("design"),
            requirement=requirement,
            overview=f"为实现「{requirement}」，建议采用分层架构，新增 {len(components)} 个核心组件。",
            components=components,
            data_structures=data_structures,
            integration_points=integration_points,
            reasoning_trace=reasoning_trace,
            design_patterns_used=suggested_patterns[:3] if suggested_patterns else ["Service Layer"],
            trade_offs=trade_offs,
            estimated_complexity="medium"
        )
    
    def _extract_component_name(self, requirement: str) -> str:
        """从需求中提取组件名称"""
        # 简单的名称提取逻辑
        keywords = ["添加", "实现", "创建", "开发", "设计"]
        
        for kw in keywords:
            if kw in requirement:
                # 取关键词后面的名词
                idx = requirement.find(kw) + len(kw)
                remaining = requirement[idx:idx+10].strip()
                # 提取中文或英文单词
                name = ""
                for char in remaining:
                    if char.isalnum() or '\u4e00' <= char <= '\u9fff':
                        name += char
                    else:
                        break
                if name:
                    return name
        
        return "Feature"
    
    def generate_batch_designs(
        self,
        repo_path: Path,
        requirements: List[str]
    ) -> List[DesignProposal]:
        """
        批量生成设计方案
        
        Args:
            repo_path: 仓库路径
            requirements: 需求列表
            
        Returns:
            设计方案列表
        """
        designs = []
        
        for req in requirements:
            try:
                design = self.generate_design(repo_path, req)
                designs.append(design)
            except Exception as e:
                logger.error(f"生成设计方案失败: {req[:30]}..., 错误: {e}")
        
        return designs
    
    def generate_design_document(self, design: DesignProposal) -> str:
        """
        生成设计文档
        
        Args:
            design: 设计方案
            
        Returns:
            Markdown 格式的设计文档
        """
        doc = [
            f"# 设计方案: {design.requirement}\n",
            f"**生成时间**: {design.created_at}",
            f"**复杂度评估**: {design.estimated_complexity}\n",
            
            "## 方案概述\n",
            design.overview + "\n",
            
            "## 设计推理过程\n"
        ]
        
        for step in design.reasoning_trace:
            doc.append(f"{step.step}. {step.thought}")
        
        doc.append("\n## 组件设计\n")
        for comp in design.components:
            doc.append(f"### {comp.name}")
            doc.append(f"- **类型**: {comp.component_type}")
            doc.append(f"- **职责**: {comp.responsibility}")
            if comp.interfaces:
                doc.append("- **接口**:")
                for iface in comp.interfaces:
                    doc.append(f"  - `{iface.get('signature', iface.get('name', ''))}`: {iface.get('description', '')}")
            doc.append("")
        
        if design.data_structures:
            doc.append("## 数据结构\n")
            for ds in design.data_structures:
                doc.append(f"### {ds.name}")
                if ds.description:
                    doc.append(ds.description)
                doc.append("| 字段 | 类型 | 描述 |")
                doc.append("|------|------|------|")
                for field in ds.fields:
                    doc.append(f"| {field.get('name', '')} | {field.get('type', '')} | {field.get('description', '')} |")
                doc.append("")
        
        if design.integration_points:
            doc.append("## 集成方案\n")
            for ip in design.integration_points:
                doc.append(f"- **{ip.target_module}** ({ip.integration_type}): {ip.description}")
            doc.append("")
        
        if design.design_patterns_used:
            doc.append("## 使用的设计模式\n")
            doc.append(", ".join(design.design_patterns_used) + "\n")
        
        if design.trade_offs:
            doc.append("## 设计权衡\n")
            for to in design.trade_offs:
                doc.append(f"### {to.decision}")
                doc.append(f"- **优点**: {', '.join(to.pros)}")
                doc.append(f"- **缺点**: {', '.join(to.cons)}")
                doc.append("")
        
        if design.affected_files:
            doc.append("## 可能受影响的文件\n")
            for f in design.affected_files:
                doc.append(f"- {f}")
        
        return '\n'.join(doc)

