"""
仓库扫描器模块
负责扫描和遍历代码仓库，收集文件信息
"""

import os
import fnmatch
from pathlib import Path
from typing import List, Dict, Optional, Generator, Set
from dataclasses import dataclass, field
from datetime import datetime
import logging

from ..config import get_config, ParserConfig
from ..utils.helpers import get_file_extension, get_language_from_extension


logger = logging.getLogger(__name__)


@dataclass
class FileInfo:
    """文件信息数据类"""
    path: Path
    relative_path: str
    extension: str
    language: Optional[str]
    size: int
    modified_time: datetime
    content: Optional[str] = None
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            "path": str(self.path),
            "relative_path": self.relative_path,
            "extension": self.extension,
            "language": self.language,
            "size": self.size,
            "modified_time": self.modified_time.isoformat(),
        }


@dataclass
class RepoInfo:
    """仓库信息数据类"""
    root_path: Path
    name: str
    total_files: int = 0
    total_size: int = 0
    languages: Dict[str, int] = field(default_factory=dict)
    files: List[FileInfo] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            "root_path": str(self.root_path),
            "name": self.name,
            "total_files": self.total_files,
            "total_size": self.total_size,
            "languages": self.languages,
            "file_count_by_language": {
                lang: len([f for f in self.files if f.language == lang])
                for lang in self.languages
            }
        }


class RepoScanner:
    """
    代码仓库扫描器
    
    负责扫描本地代码仓库，收集文件信息，
    支持文件过滤和多语言检测
    """
    
    def __init__(self, config: Optional[ParserConfig] = None):
        """
        初始化扫描器
        
        Args:
            config: 解析器配置，如果为None则使用默认配置
        """
        self.config = config or get_config().parser
        self._ignore_patterns = self._compile_ignore_patterns()
        
    def _compile_ignore_patterns(self) -> Set[str]:
        """编译忽略模式"""
        return set(self.config.ignore_patterns)
    
    def _should_ignore(self, path: Path, root_path: Path) -> bool:
        """
        检查路径是否应该被忽略
        
        Args:
            path: 要检查的路径
            root_path: 仓库根路径
            
        Returns:
            是否应该忽略
        """
        # 获取相对路径
        try:
            rel_path = path.relative_to(root_path)
        except ValueError:
            rel_path = path
            
        path_str = str(rel_path)
        name = path.name
        
        for pattern in self._ignore_patterns:
            # 检查文件/目录名是否匹配模式
            if fnmatch.fnmatch(name, pattern):
                return True
            # 检查路径是否包含匹配的部分
            if fnmatch.fnmatch(path_str, f"*{pattern}*"):
                return True
            # 检查是否是需要忽略的目录
            if pattern in path.parts:
                return True
                
        return False
    
    def _is_valid_file(self, file_path: Path) -> bool:
        """
        检查文件是否有效（应该被处理）
        
        Args:
            file_path: 文件路径
            
        Returns:
            是否是有效文件
        """
        # 检查文件大小
        try:
            size = file_path.stat().st_size
            if size > self.config.max_file_size:
                logger.debug(f"文件过大，跳过: {file_path} ({size} bytes)")
                return False
            if size == 0:
                logger.debug(f"空文件，跳过: {file_path}")
                return False
        except OSError:
            return False
            
        # 检查是否是支持的语言
        ext = get_file_extension(file_path)
        language = get_language_from_extension(ext)
        
        if language and language not in self.config.supported_languages:
            return False
            
        return True
    
    def scan_directory(
        self, 
        root_path: Path, 
        load_content: bool = False
    ) -> Generator[FileInfo, None, None]:
        """
        扫描目录，生成文件信息
        
        Args:
            root_path: 要扫描的根目录
            load_content: 是否加载文件内容
            
        Yields:
            FileInfo 对象
        """
        root_path = Path(root_path).resolve()
        
        if not root_path.exists():
            raise FileNotFoundError(f"路径不存在: {root_path}")
            
        if not root_path.is_dir():
            raise NotADirectoryError(f"不是目录: {root_path}")
        
        logger.info(f"开始扫描目录: {root_path}")
        
        file_count = 0
        error_count = 0
        
        try:
            for current_dir, dirs, files in os.walk(root_path):
                current_path = Path(current_dir)
                
                # 计算当前深度
                try:
                    depth = len(current_path.relative_to(root_path).parts)
                except ValueError:
                    depth = 0
                    
                if depth > self.config.max_depth:
                    logger.debug(f"超过最大深度，跳过: {current_path}")
                    dirs.clear()  # 停止向下遍历
                    continue
                
                # 过滤要忽略的目录
                dirs[:] = [
                    d for d in dirs 
                    if not self._should_ignore(current_path / d, root_path)
                ]
                
                # 处理文件
                for filename in files:
                    file_path = current_path / filename
                    
                    # 检查是否应该忽略
                    if self._should_ignore(file_path, root_path):
                        continue
                        
                    # 检查文件是否有效
                    if not self._is_valid_file(file_path):
                        continue
                    
                    # 创建文件信息
                    try:
                        file_info = self._create_file_info(
                            file_path, root_path, load_content
                        )
                        if file_info:
                            file_count += 1
                            # 每处理100个文件记录一次进度
                            if file_count % 100 == 0:
                                logger.debug(f"已处理 {file_count} 个文件...")
                            yield file_info
                    except KeyboardInterrupt:
                        logger.info("扫描被用户中断")
                        raise
                    except Exception as e:
                        error_count += 1
                        logger.warning(f"处理文件失败: {file_path}, 错误: {e}")
                        # 如果错误太多，记录警告但继续
                        if error_count > 100:
                            logger.error(f"错误过多 ({error_count})，停止扫描")
                            break
        except KeyboardInterrupt:
            logger.info("扫描被用户中断")
            raise
        except Exception as e:
            logger.error(f"扫描过程中发生错误: {e}")
            raise
        
        logger.info(f"扫描完成: 处理了 {file_count} 个文件，{error_count} 个错误")
    
    def _create_file_info(
        self, 
        file_path: Path, 
        root_path: Path,
        load_content: bool
    ) -> Optional[FileInfo]:
        """
        创建文件信息对象
        
        Args:
            file_path: 文件路径
            root_path: 仓库根路径
            load_content: 是否加载内容
            
        Returns:
            FileInfo 对象或 None
        """
        try:
            stat = file_path.stat()
            ext = get_file_extension(file_path)
            language = get_language_from_extension(ext)
            
            content = None
            if load_content:
                try:
                    # 限制读取大小，避免读取超大文件导致卡住
                    max_read_size = min(self.config.max_file_size, 10 * 1024 * 1024)  # 最多10MB
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        # 先读取一小部分检查
                        first_chunk = f.read(1024)
                        if len(first_chunk) == 1024:
                            # 文件可能很大，检查大小
                            if stat.st_size > max_read_size:
                                logger.warning(f"文件过大 ({stat.st_size} bytes)，跳过内容加载: {file_path}")
                                content = None
                            else:
                                # 重新读取完整内容
                                f.seek(0)
                                content = f.read(max_read_size)
                        else:
                            content = first_chunk
                except UnicodeDecodeError:
                    # 尝试其他编码
                    try:
                        with open(file_path, 'r', encoding='latin-1', errors='ignore') as f:
                            max_read_size = min(self.config.max_file_size, 10 * 1024 * 1024)
                            content = f.read(max_read_size)
                    except Exception as e:
                        logger.warning(f"无法读取文件内容: {file_path}, 错误: {e}")
                except Exception as e:
                    logger.warning(f"读取文件时出错: {file_path}, 错误: {e}")
                        
            return FileInfo(
                path=file_path,
                relative_path=str(file_path.relative_to(root_path)),
                extension=ext,
                language=language,
                size=stat.st_size,
                modified_time=datetime.fromtimestamp(stat.st_mtime),
                content=content
            )
        except Exception as e:
            logger.error(f"创建文件信息失败: {file_path}, 错误: {e}")
            return None
    
    def scan_repository(
        self, 
        repo_path: Path,
        load_content: bool = False
    ) -> RepoInfo:
        """
        扫描整个仓库，返回仓库信息
        
        Args:
            repo_path: 仓库路径
            load_content: 是否加载文件内容
            
        Returns:
            RepoInfo 对象
        """
        repo_path = Path(repo_path).resolve()
        
        repo_info = RepoInfo(
            root_path=repo_path,
            name=repo_path.name
        )
        
        languages: Dict[str, int] = {}
        
        try:
            logger.info(f"开始扫描仓库: {repo_path} (load_content={load_content})")
            file_count = 0
            
            for file_info in self.scan_directory(repo_path, load_content):
                repo_info.files.append(file_info)
                repo_info.total_files += 1
                repo_info.total_size += file_info.size
                
                if file_info.language:
                    languages[file_info.language] = languages.get(file_info.language, 0) + 1
                
                file_count += 1
                # 每处理500个文件记录一次进度
                if file_count % 500 == 0:
                    logger.info(
                        f"扫描进度: {file_count} 个文件, "
                        f"{repo_info.total_size / 1024:.2f} KB"
                    )
        except KeyboardInterrupt:
            logger.info("扫描被用户中断")
            raise
        except Exception as e:
            logger.error(f"扫描仓库时发生错误: {e}")
            raise
        
        repo_info.languages = languages
        
        logger.info(
            f"扫描完成: {repo_info.total_files} 个文件, "
            f"{repo_info.total_size / 1024:.2f} KB, "
            f"语言分布: {languages}"
        )
        
        return repo_info
    
    def get_files_by_language(
        self, 
        repo_path: Path, 
        language: str,
        load_content: bool = True
    ) -> List[FileInfo]:
        """
        获取指定语言的所有文件
        
        Args:
            repo_path: 仓库路径
            language: 编程语言
            load_content: 是否加载内容
            
        Returns:
            文件信息列表
        """
        files = []
        for file_info in self.scan_directory(repo_path, load_content):
            if file_info.language == language:
                files.append(file_info)
        return files
    
    def get_project_structure(self, repo_path: Path, max_depth: int = 3) -> str:
        """
        获取项目目录结构的文本表示
        
        Args:
            repo_path: 仓库路径
            max_depth: 最大深度
            
        Returns:
            目录结构字符串
        """
        repo_path = Path(repo_path).resolve()
        lines = [repo_path.name + "/"]
        
        def _add_tree(path: Path, prefix: str, depth: int):
            if depth > max_depth:
                return
                
            try:
                entries = sorted(path.iterdir(), key=lambda x: (x.is_file(), x.name))
            except PermissionError:
                return
                
            # 过滤忽略的项目
            entries = [
                e for e in entries 
                if not self._should_ignore(e, repo_path)
            ]
            
            for i, entry in enumerate(entries):
                is_last = i == len(entries) - 1
                connector = "└── " if is_last else "├── "
                
                if entry.is_dir():
                    lines.append(f"{prefix}{connector}{entry.name}/")
                    extension = "    " if is_last else "│   "
                    _add_tree(entry, prefix + extension, depth + 1)
                else:
                    lines.append(f"{prefix}{connector}{entry.name}")
        
        _add_tree(repo_path, "", 1)
        return "\n".join(lines)

