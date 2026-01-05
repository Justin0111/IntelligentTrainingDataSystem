"""
文档提取器模块
从代码中提取注释、文档字符串和README等文档信息
"""

import re
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)


@dataclass
class DocComment:
    """文档注释"""
    content: str
    comment_type: str  # docstring, line_comment, block_comment, readme
    start_line: int
    end_line: int
    associated_element: Optional[str] = None  # 关联的代码元素名称
    
    def to_dict(self) -> Dict:
        return {
            "content": self.content,
            "comment_type": self.comment_type,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "associated_element": self.associated_element
        }


@dataclass
class DocSection:
    """文档章节（如README中的章节）"""
    title: str
    content: str
    level: int  # 标题级别 (1-6)
    
    def to_dict(self) -> Dict:
        return {
            "title": self.title,
            "content": self.content,
            "level": self.level
        }


@dataclass
class ProjectDocs:
    """项目文档信息"""
    readme: Optional[str] = None
    readme_sections: List[DocSection] = field(default_factory=list)
    changelog: Optional[str] = None
    contributing: Optional[str] = None
    license: Optional[str] = None
    api_docs: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            "readme": self.readme,
            "readme_sections": [s.to_dict() for s in self.readme_sections],
            "changelog": self.changelog,
            "contributing": self.contributing,
            "license": self.license,
            "api_docs": self.api_docs
        }


class DocExtractor:
    """
    文档提取器
    
    从代码和项目文件中提取文档信息
    """
    
    # 不同语言的注释模式
    COMMENT_PATTERNS = {
        "python": {
            "line": r'#\s*(.+)$',
            "docstring": r'"""([\s\S]*?)"""|\'\'\'([\s\S]*?)\'\'\'',
        },
        "javascript": {
            "line": r'//\s*(.+)$',
            "block": r'/\*\*([\s\S]*?)\*/',
        },
        "typescript": {
            "line": r'//\s*(.+)$',
            "block": r'/\*\*([\s\S]*?)\*/',
        },
        "java": {
            "line": r'//\s*(.+)$',
            "block": r'/\*\*([\s\S]*?)\*/',
        },
    }
    
    # 项目文档文件名
    DOC_FILES = {
        "readme": ["README.md", "README.rst", "README.txt", "README"],
        "changelog": ["CHANGELOG.md", "CHANGELOG.txt", "HISTORY.md", "CHANGES.md"],
        "contributing": ["CONTRIBUTING.md", "CONTRIBUTING.txt"],
        "license": ["LICENSE", "LICENSE.md", "LICENSE.txt"],
    }
    
    def __init__(self):
        pass
    
    def extract_comments(self, code: str, language: str) -> List[DocComment]:
        """
        从代码中提取注释
        
        Args:
            code: 源代码
            language: 编程语言
            
        Returns:
            注释列表
        """
        comments = []
        patterns = self.COMMENT_PATTERNS.get(language, {})
        lines = code.split('\n')
        
        # 提取文档字符串（Python）
        if "docstring" in patterns:
            for match in re.finditer(patterns["docstring"], code, re.MULTILINE):
                content = match.group(1) or match.group(2)
                if content:
                    start_line = code[:match.start()].count('\n') + 1
                    end_line = code[:match.end()].count('\n') + 1
                    comments.append(DocComment(
                        content=content.strip(),
                        comment_type="docstring",
                        start_line=start_line,
                        end_line=end_line
                    ))
        
        # 提取块注释
        if "block" in patterns:
            for match in re.finditer(patterns["block"], code, re.MULTILINE):
                content = match.group(1)
                if content:
                    start_line = code[:match.start()].count('\n') + 1
                    end_line = code[:match.end()].count('\n') + 1
                    # 清理 JSDoc 样式的 * 前缀
                    cleaned = self._clean_block_comment(content)
                    comments.append(DocComment(
                        content=cleaned,
                        comment_type="block_comment",
                        start_line=start_line,
                        end_line=end_line
                    ))
        
        # 提取行注释
        if "line" in patterns:
            # 收集连续的行注释
            current_block = []
            block_start = None
            
            for i, line in enumerate(lines, 1):
                match = re.search(patterns["line"], line)
                if match:
                    if block_start is None:
                        block_start = i
                    current_block.append(match.group(1).strip())
                else:
                    if current_block:
                        # 如果注释块足够长（>= 2行），则保存
                        if len(current_block) >= 2:
                            comments.append(DocComment(
                                content='\n'.join(current_block),
                                comment_type="line_comment",
                                start_line=block_start,
                                end_line=i - 1
                            ))
                        current_block = []
                        block_start = None
            
            # 处理最后一个块
            if current_block and len(current_block) >= 2:
                comments.append(DocComment(
                    content='\n'.join(current_block),
                    comment_type="line_comment",
                    start_line=block_start,
                    end_line=len(lines)
                ))
        
        return comments
    
    def _clean_block_comment(self, content: str) -> str:
        """清理块注释内容"""
        lines = content.split('\n')
        cleaned_lines = []
        for line in lines:
            # 移除开头的 * 和空格
            line = re.sub(r'^\s*\*\s?', '', line)
            cleaned_lines.append(line)
        return '\n'.join(cleaned_lines).strip()
    
    def extract_project_docs(self, repo_path: Path) -> ProjectDocs:
        """
        提取项目文档文件
        
        Args:
            repo_path: 仓库根目录
            
        Returns:
            ProjectDocs 对象
        """
        repo_path = Path(repo_path)
        docs = ProjectDocs()
        
        # 查找并读取各类文档文件
        for doc_type, filenames in self.DOC_FILES.items():
            for filename in filenames:
                file_path = repo_path / filename
                if file_path.exists():
                    try:
                        content = file_path.read_text(encoding='utf-8')
                        setattr(docs, doc_type, content)
                        
                        # 如果是 README，解析章节
                        if doc_type == "readme" and filename.endswith('.md'):
                            docs.readme_sections = self._parse_markdown_sections(content)
                        
                        logger.debug(f"读取文档文件: {file_path}")
                        break
                    except Exception as e:
                        logger.warning(f"读取文档文件失败: {file_path}, 错误: {e}")
        
        # 查找 API 文档目录
        for doc_dir in ["docs", "doc", "api", "documentation"]:
            doc_path = repo_path / doc_dir
            if doc_path.is_dir():
                for md_file in doc_path.glob("**/*.md"):
                    try:
                        docs.api_docs.append(md_file.read_text(encoding='utf-8'))
                    except Exception:
                        pass
        
        return docs
    
    def _parse_markdown_sections(self, content: str) -> List[DocSection]:
        """
        解析 Markdown 文档的章节结构
        
        Args:
            content: Markdown 内容
            
        Returns:
            章节列表
        """
        sections = []
        lines = content.split('\n')
        
        current_title = None
        current_level = 0
        current_content = []
        
        for line in lines:
            # 检查是否是标题行
            header_match = re.match(r'^(#{1,6})\s+(.+)$', line)
            
            if header_match:
                # 保存之前的章节
                if current_title is not None:
                    sections.append(DocSection(
                        title=current_title,
                        content='\n'.join(current_content).strip(),
                        level=current_level
                    ))
                
                # 开始新章节
                current_level = len(header_match.group(1))
                current_title = header_match.group(2).strip()
                current_content = []
            else:
                current_content.append(line)
        
        # 保存最后一个章节
        if current_title is not None:
            sections.append(DocSection(
                title=current_title,
                content='\n'.join(current_content).strip(),
                level=current_level
            ))
        
        return sections
    
    def extract_function_docs(
        self, 
        code: str, 
        language: str
    ) -> Dict[str, str]:
        """
        提取函数/方法的文档说明
        
        Args:
            code: 源代码
            language: 编程语言
            
        Returns:
            函数名到文档的映射
        """
        docs = {}
        
        if language == "python":
            # 匹配 def 后跟文档字符串
            pattern = r'def\s+(\w+)\s*\([^)]*\)\s*(?:->.*?)?\s*:\s*\n\s*(?:"""([\s\S]*?)"""|\'\'\'([\s\S]*?)\'\'\')'
            for match in re.finditer(pattern, code):
                func_name = match.group(1)
                docstring = match.group(2) or match.group(3)
                if docstring:
                    docs[func_name] = docstring.strip()
        
        elif language in ["javascript", "typescript", "java"]:
            # 匹配 JSDoc 风格注释后跟函数定义
            pattern = r'/\*\*([\s\S]*?)\*/\s*(?:async\s+)?(?:function\s+(\w+)|(?:const|let|var)\s+(\w+)\s*=)'
            for match in re.finditer(pattern, code):
                comment = self._clean_block_comment(match.group(1))
                func_name = match.group(2) or match.group(3)
                if func_name:
                    docs[func_name] = comment
        
        return docs
    
    def extract_inline_comments(
        self, 
        code: str, 
        start_line: int, 
        end_line: int,
        language: str
    ) -> List[str]:
        """
        提取指定行范围内的行内注释
        
        Args:
            code: 源代码
            start_line: 起始行
            end_line: 结束行
            language: 编程语言
            
        Returns:
            注释列表
        """
        comments = []
        lines = code.split('\n')
        patterns = self.COMMENT_PATTERNS.get(language, {})
        
        if "line" not in patterns:
            return comments
        
        for i in range(start_line - 1, min(end_line, len(lines))):
            line = lines[i]
            match = re.search(patterns["line"], line)
            if match:
                # 检查是否是行内注释（代码后面的注释）
                code_before = line[:match.start()].strip()
                if code_before:  # 如果注释前有代码，则是行内注释
                    comments.append(match.group(1).strip())
        
        return comments
    
    def summarize_docs(self, docs: ProjectDocs) -> str:
        """
        生成项目文档摘要
        
        Args:
            docs: 项目文档
            
        Returns:
            摘要文本
        """
        summary_parts = []
        
        if docs.readme:
            # 提取 README 的前几个段落作为摘要
            paragraphs = docs.readme.split('\n\n')[:3]
            readme_summary = '\n\n'.join(paragraphs)
            summary_parts.append(f"## 项目简介\n\n{readme_summary}")
        
        if docs.readme_sections:
            # 列出主要章节
            main_sections = [s for s in docs.readme_sections if s.level <= 2]
            if main_sections:
                section_list = '\n'.join([f"- {s.title}" for s in main_sections[:10]])
                summary_parts.append(f"## 文档结构\n\n{section_list}")
        
        return '\n\n'.join(summary_parts)

