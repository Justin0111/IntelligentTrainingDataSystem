"""
基础测试模块
测试各个核心组件的基本功能
"""

import pytest
from pathlib import Path
import tempfile
import os

# 获取项目根目录
PROJECT_ROOT = Path(__file__).parent.parent


class TestRepoScanner:
    """测试仓库扫描器"""
    
    def test_scan_directory(self):
        """测试目录扫描"""
        from src.parsers import RepoScanner
        
        scanner = RepoScanner()
        
        # 扫描项目自身
        files = list(scanner.scan_directory(PROJECT_ROOT / "src"))
        
        assert len(files) > 0
        assert any(f.extension == "py" for f in files)
    
    def test_get_project_structure(self):
        """测试获取项目结构"""
        from src.parsers import RepoScanner
        
        scanner = RepoScanner()
        structure = scanner.get_project_structure(PROJECT_ROOT, max_depth=2)
        
        assert "src" in structure
        assert isinstance(structure, str)


class TestASTParser:
    """测试 AST 解析器"""
    
    def test_python_parser(self):
        """测试 Python 解析器"""
        from src.parsers import get_parser_for_language
        
        parser = get_parser_for_language("python")
        assert parser is not None
        
        code = '''
def hello(name: str) -> str:
    """Say hello"""
    return f"Hello, {name}!"

class Greeter:
    def greet(self):
        pass
'''
        
        result = parser.parse(code, "test.py")
        
        assert len(result.functions) == 1
        assert result.functions[0].name == "hello"
        assert len(result.classes) == 1
        assert result.classes[0].name == "Greeter"
    
    def test_javascript_parser(self):
        """测试 JavaScript 解析器"""
        from src.parsers import get_parser_for_language
        
        parser = get_parser_for_language("javascript")
        assert parser is not None
        
        code = '''
import { foo } from 'bar';

function greet(name) {
    return `Hello, ${name}!`;
}

class Calculator {
    add(a, b) {
        return a + b;
    }
}
'''
        
        result = parser.parse(code, "test.js")
        
        assert len(result.imports) >= 1
        assert len(result.functions) >= 1
        assert len(result.classes) >= 1


class TestStructureAnalyzer:
    """测试结构分析器"""
    
    def test_analyze(self):
        """测试代码结构分析"""
        from src.analyzers import StructureAnalyzer
        
        analyzer = StructureAnalyzer()
        result = analyzer.analyze(PROJECT_ROOT)
        
        assert result.repo_name == PROJECT_ROOT.name
        assert result.total_files > 0
        assert result.total_functions > 0


class TestLogicAnalyzer:
    """测试业务逻辑分析器"""
    
    def test_analyze_file(self):
        """测试文件分析"""
        from src.analyzers import LogicAnalyzer
        
        analyzer = LogicAnalyzer()
        
        code = '''
def validate_email(email: str) -> bool:
    """验证邮箱格式"""
    if not email:
        return False
    return "@" in email and "." in email

def process_order(order_data: dict) -> dict:
    """处理订单"""
    # 验证订单数据
    if not order_data.get("items"):
        raise ValueError("订单项不能为空")
    
    # 计算总价
    total = sum(item["price"] * item["quantity"] for item in order_data["items"])
    
    return {"status": "processed", "total": total}
'''
        
        result = analyzer.analyze_file(code, "test.py", "python")
        
        assert len(result.business_rules) >= 1
        # 应该识别出 validate_email 是验证函数
        rule_names = [r.name for r in result.business_rules]
        assert "validate_email" in rule_names


class TestDataValidator:
    """测试数据验证器"""
    
    def test_validate_qa_pair(self):
        """测试问答对验证"""
        from src.processors import DataValidator
        from src.generators.qa_generator import QAPair, ReasoningStep
        
        validator = DataValidator()
        
        # 创建有效的问答对
        qa = QAPair(
            id="test_001",
            question="这个函数的作用是什么？请详细解释。",
            answer="这个函数用于处理用户认证，首先验证token的有效性，然后检查用户权限，最后返回认证结果。",
            question_type="function_explanation",
            code_context={
                "file_path": "test.py",
                "code_snippet": "def auth(token): pass",
                "start_line": 1,
                "end_line": 1
            },
            reasoning_trace=[
                ReasoningStep(1, "首先分析函数签名"),
                ReasoningStep(2, "然后查看函数体"),
                ReasoningStep(3, "最后总结功能")
            ]
        )
        
        result = validator.validate_qa_pair(qa)
        
        assert result.is_valid
        assert result.score > 0.5
    
    def test_validate_invalid_qa(self):
        """测试无效问答对验证"""
        from src.processors import DataValidator
        from src.generators.qa_generator import QAPair
        
        validator = DataValidator()
        
        # 创建无效的问答对（问题太短）
        qa = QAPair(
            id="test_002",
            question="?",
            answer="",
            question_type="general",
            code_context={},
            reasoning_trace=[]
        )
        
        result = validator.validate_qa_pair(qa)
        
        assert not result.is_valid
        assert len(result.issues) > 0


class TestDataCleaner:
    """测试数据清洗器"""
    
    def test_clean_text(self):
        """测试文本清洗"""
        from src.processors import DataCleaner
        from src.generators.qa_generator import QAPair, ReasoningStep
        
        cleaner = DataCleaner()
        
        # 创建需要清洗的问答对
        qa = QAPair(
            id="test_003",
            question="这个函数   有什么  作用？",  # 多余空格
            answer="这是答案。\n\n\n\n这是更多内容。",  # 多余空行
            question_type="general",
            code_context={"file_path": "test.py", "code_snippet": "def foo(): pass"},
            reasoning_trace=[ReasoningStep(1, "  思考过程  ")]
        )
        
        cleaned, stats = cleaner.clean_qa_pairs([qa])
        
        assert len(cleaned) == 1
        assert "   " not in cleaned[0].question  # 多余空格被清理


class TestDataFormatter:
    """测试数据格式化器"""
    
    def test_format_alpaca(self):
        """测试 Alpaca 格式输出"""
        from src.processors import DataFormatter
        from src.generators.qa_generator import QAPair, ReasoningStep
        
        formatter = DataFormatter()
        
        qa = QAPair(
            id="test_004",
            question="解释这段代码",
            answer="这段代码实现了...",
            question_type="function_explanation",
            code_context={
                "file_path": "test.py",
                "code_snippet": "def foo(): pass"
            },
            reasoning_trace=[ReasoningStep(1, "分析代码")]
        )
        
        formatted = formatter.format_qa_pairs([qa], "alpaca")
        
        assert len(formatted) == 1
        assert "instruction" in formatted[0]
        assert "output" in formatted[0]
    
    def test_format_sharegpt(self):
        """测试 ShareGPT 格式输出"""
        from src.processors import DataFormatter
        from src.generators.qa_generator import QAPair, ReasoningStep
        
        formatter = DataFormatter()
        
        qa = QAPair(
            id="test_005",
            question="解释这段代码",
            answer="这段代码实现了...",
            question_type="function_explanation",
            code_context={"file_path": "test.py", "code_snippet": "def foo(): pass"},
            reasoning_trace=[ReasoningStep(1, "分析代码")]
        )
        
        formatted = formatter.format_qa_pairs([qa], "sharegpt")
        
        assert len(formatted) == 1
        assert "conversations" in formatted[0]
        assert len(formatted[0]["conversations"]) == 2


class TestConfig:
    """测试配置模块"""
    
    def test_default_config(self):
        """测试默认配置"""
        from src.config import get_config
        
        config = get_config()
        
        assert config.llm.provider == "qwen"
        assert config.parser.max_file_size > 0
        assert config.generator.qa_per_file > 0
    
    def test_ensure_directories(self):
        """测试目录创建"""
        from src.config import AppConfig
        
        with tempfile.TemporaryDirectory() as tmpdir:
            config = AppConfig(output_dir=Path(tmpdir) / "output")
            config.ensure_directories()
            
            assert (Path(tmpdir) / "output" / "datasets").exists()


class TestHelpers:
    """测试工具函数"""
    
    def test_generate_id(self):
        """测试 ID 生成"""
        from src.utils.helpers import generate_id
        
        id1 = generate_id("qa")
        id2 = generate_id("qa")
        
        assert id1.startswith("qa_")
        assert id1 != id2  # 应该是唯一的
    
    def test_generate_content_hash_id(self):
        """测试基于内容的 ID 生成"""
        from src.utils.helpers import generate_id
        
        id1 = generate_id("qa", "same content")
        id2 = generate_id("qa", "same content")
        
        assert id1 == id2  # 相同内容应该生成相同 ID
    
    def test_language_detection(self):
        """测试语言检测"""
        from src.utils.helpers import get_language_from_extension
        
        assert get_language_from_extension("py") == "python"
        assert get_language_from_extension("js") == "javascript"
        assert get_language_from_extension("ts") == "typescript"
        assert get_language_from_extension("java") == "java"
        assert get_language_from_extension("xyz") is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

