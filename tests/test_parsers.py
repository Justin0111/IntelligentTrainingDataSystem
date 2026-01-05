"""
解析器模块测试
"""

import pytest
from pathlib import Path


class TestRepoScanner:
    """仓库扫描器测试"""
    
    def test_scan_repository(self, temp_repo):
        """测试仓库扫描"""
        from src.parsers import RepoScanner
        
        scanner = RepoScanner()
        result = scanner.scan_repository(temp_repo)
        
        assert result.name == temp_repo.name
        assert result.total_files > 0
        assert "python" in result.languages or "Python" in result.languages
    
    def test_get_project_structure(self, temp_repo):
        """测试获取项目结构"""
        from src.parsers import RepoScanner
        
        scanner = RepoScanner()
        structure = scanner.get_project_structure(temp_repo, max_depth=2)
        
        assert isinstance(structure, str)
        assert "src" in structure


class TestASTParser:
    """AST 解析器测试"""
    
    def test_parse_python_code(self, sample_python_code):
        """测试 Python 代码解析"""
        from src.parsers import get_parser_for_language
        
        parser = get_parser_for_language("python")
        result = parser.parse(sample_python_code, "test.py")
        
        # 应该找到函数
        assert len(result.functions) > 0
        
        # 应该找到类
        assert len(result.classes) > 0
        
        # 检查函数名
        func_names = [f.name for f in result.functions]
        assert "calculate_total" in func_names
        
        # 检查类名
        class_names = [c.name for c in result.classes]
        assert "OrderProcessor" in class_names
    
    def test_parse_javascript_code(self, sample_javascript_code):
        """测试 JavaScript 代码解析"""
        from src.parsers import get_parser_for_language
        
        parser = get_parser_for_language("javascript")
        result = parser.parse(sample_javascript_code, "test.js")
        
        # 应该找到函数
        assert len(result.functions) >= 1
    
    def test_extract_docstrings(self, sample_python_code):
        """测试文档字符串提取"""
        from src.parsers import get_parser_for_language
        
        parser = get_parser_for_language("python")
        result = parser.parse(sample_python_code, "test.py")
        
        # calculate_total 函数应该有文档字符串
        calc_func = next((f for f in result.functions if f.name == "calculate_total"), None)
        assert calc_func is not None
        assert calc_func.docstring is not None
        assert "计算订单总价" in calc_func.docstring


class TestLanguageDetection:
    """语言检测测试"""
    
    def test_python_detection(self):
        """测试 Python 文件检测"""
        from src.parsers.repo_scanner import RepoScanner
        
        scanner = RepoScanner()
        lang = scanner._detect_language(Path("test.py"))
        assert lang == "python"
    
    def test_javascript_detection(self):
        """测试 JavaScript 文件检测"""
        from src.parsers.repo_scanner import RepoScanner
        
        scanner = RepoScanner()
        lang = scanner._detect_language(Path("test.js"))
        assert lang == "javascript"
    
    def test_typescript_detection(self):
        """测试 TypeScript 文件检测"""
        from src.parsers.repo_scanner import RepoScanner
        
        scanner = RepoScanner()
        lang = scanner._detect_language(Path("test.ts"))
        assert lang == "typescript"

