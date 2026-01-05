"""
GitHub 仓库自动发现和下载模块
根据指定的场景、技术栈等维度自动搜索和筛选 GitHub 仓库
"""

import os
import json
import logging
import subprocess
import time
from pathlib import Path
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
import requests

logger = logging.getLogger(__name__)


@dataclass
class RepoSearchCriteria:
    """仓库搜索条件"""
    keywords: List[str]  # 搜索关键词
    language: Optional[str] = None  # 编程语言
    min_stars: int = 50  # 最小 star 数（降低门槛）
    min_forks: int = 10  # 最小 fork 数（降低门槛）
    max_age_days: Optional[int] = 1825  # 最大年龄（天），默认5年（放宽限制）
    topics: List[str] = None  # GitHub topics
    size_range: tuple = (50, 100000)  # 仓库大小范围（KB），放宽限制
    max_results: int = 10  # 最大结果数


@dataclass
class GitHubRepo:
    """GitHub 仓库信息"""
    name: str
    full_name: str
    url: str
    clone_url: str
    description: str
    stars: int
    forks: int
    language: str
    size: int  # KB
    created_at: str
    updated_at: str
    topics: List[str]
    score: float  # 综合评分


# 预定义场景配置
SCENARIO_CONFIGS = {
    "金融科技": {
        "keywords": ["payment", "fintech", "trading", "blockchain", "wallet"],
        "topics": ["finance", "payment"],  # 减少topic数量
        "language": None,  # 不限制语言
        "description": "支付系统、交易平台、区块链、钱包服务"
    },
    "电商系统": {
        "keywords": ["ecommerce", "shop", "shopping", "marketplace"],
        "topics": ["ecommerce", "marketplace"],
        "language": None,
        "description": "电商平台、购物车、订单系统、商品管理"
    },
    "微服务架构": {
        "keywords": ["microservices", "microservice", "api-gateway"],
        "topics": ["microservices", "kubernetes"],
        "language": None,
        "description": "微服务、API网关、服务网格、容器化"
    },
    "数据处理": {
        "keywords": ["data-pipeline", "etl", "data-processing"],
        "topics": ["data-engineering", "data-science"],
        "language": None,  # 不限制语言
        "description": "ETL、数据管道、数据分析、数据仓库"
    },
    "Web框架": {
        "keywords": ["web-framework", "api", "rest", "graphql"],
        "topics": ["web", "api", "rest-api", "backend"],
        "language": None,
        "description": "Web框架、REST API、GraphQL、后端服务"
    },
    "机器学习": {
        "keywords": ["machine-learning", "deep-learning", "ml"],
        "topics": ["machine-learning", "deep-learning"],
        "language": None,  # 不限制语言
        "description": "机器学习、深度学习、神经网络"
    },
    "DevOps工具": {
        "keywords": ["devops", "ci-cd", "automation"],
        "topics": ["devops", "automation"],
        "language": None,
        "description": "CI/CD、监控、日志、自动化部署"
    },
    "认证授权": {
        "keywords": ["authentication", "authorization", "oauth", "jwt"],
        "topics": ["authentication", "oauth2", "security"],
        "language": None,
        "description": "用户认证、OAuth、JWT、权限管理"
    },
    "消息队列": {
        "keywords": ["message-queue", "kafka", "rabbitmq", "redis"],
        "topics": ["message-queue", "event-driven"],
        "language": None,
        "description": "消息队列、事件驱动、发布订阅"
    },
    "API服务": {
        "keywords": ["api-server", "rest-api", "http-server"],
        "topics": ["api", "rest-api", "backend"],
        "language": None,
        "description": "API服务器、HTTP服务、RESTful接口"
    }
}

# 技术栈配置
TECH_STACK_CONFIGS = {
    "Python Web": {
        "keywords": ["django", "flask", "fastapi"],
        "language": "python",
        "topics": ["django", "flask", "fastapi"]
    },
    "JavaScript/Node.js": {
        "keywords": ["nodejs", "express", "nestjs"],
        "language": "javascript",
        "topics": ["nodejs", "express", "typescript"]
    },
    "Java企业应用": {
        "keywords": ["spring-boot", "spring-cloud", "mybatis"],
        "language": "java",
        "topics": ["spring-boot", "spring-framework"]
    },
    "Go微服务": {
        "keywords": ["go", "microservices", "grpc"],
        "language": "go",
        "topics": ["golang", "microservices"]
    },
    "React前端": {
        "keywords": ["react", "frontend", "ui"],
        "language": "javascript",
        "topics": ["react", "frontend"]
    },
    "Vue前端": {
        "keywords": ["vue", "vuejs", "frontend"],
        "language": "javascript",
        "topics": ["vue", "vuejs"]
    }
}


class GitHubDiscovery:
    """
    GitHub 仓库自动发现器
    
    使用 GitHub API 搜索和筛选符合条件的仓库
    """
    
    def __init__(self, github_token: Optional[str] = None):
        """
        初始化发现器
        
        Args:
            github_token: GitHub Personal Access Token（可选，但推荐使用以提高 API 限额）
        """
        self.github_token = github_token or os.getenv("GITHUB_TOKEN")
        self.api_base = "https://api.github.com"
        self.session = requests.Session()
        
        if self.github_token:
            self.session.headers["Authorization"] = f"token {self.github_token}"
        
        self.session.headers["Accept"] = "application/vnd.github.v3+json"
    
    def search_repositories(
        self,
        criteria: RepoSearchCriteria
    ) -> List[GitHubRepo]:
        """
        搜索符合条件的仓库
        
        Args:
            criteria: 搜索条件
            
        Returns:
            仓库列表
        """
        logger.info(f"开始搜索仓库，关键词: {criteria.keywords}")
        
        # 构建搜索查询
        query_parts = []
        
        # 关键词
        if criteria.keywords:
            keyword_query = " OR ".join(criteria.keywords)
            query_parts.append(f"({keyword_query})")
        
        # 语言
        if criteria.language:
            query_parts.append(f"language:{criteria.language}")
        
        # Stars
        query_parts.append(f"stars:>={criteria.min_stars}")
        
        # Forks（可选，不是必需）
        if criteria.min_forks and criteria.min_forks > 0:
            query_parts.append(f"forks:>={criteria.min_forks}")
        
        # 创建时间
        if criteria.max_age_days:
            cutoff_date = datetime.now() - timedelta(days=criteria.max_age_days)
            query_parts.append(f"created:>={cutoff_date.strftime('%Y-%m-%d')}")
        
        # Topics - 暂时移除，因为 GitHub API 不支持 (topic:A OR topic:B) 括号语法
        # 改为依赖关键词搜索，已经足够精准
        # if criteria.topics:
        #     topics_to_use = criteria.topics[:2]
        #     if topics_to_use:
        #         topic_query = " OR ".join([f"topic:{t}" for t in topics_to_use])
        #         query_parts.append(f"({topic_query})")
        
        # 仓库大小（可选，不强制）
        # 注释掉大小限制，因为太严格
        # if criteria.size_range:
        #     min_size, max_size = criteria.size_range
        #     query_parts.append(f"size:{min_size}..{max_size}")
        
        query = " ".join(query_parts)
        logger.info(f"搜索查询: {query}")
        
        # 调用 GitHub API
        url = f"{self.api_base}/search/repositories"
        params = {
            "q": query,
            "sort": "stars",
            "order": "desc",
            "per_page": criteria.max_results
        }
        
        try:
            response = self.session.get(url, params=params, timeout=10)
            
            # 详细的错误信息
            if response.status_code != 200:
                logger.error(f"API 请求失败: HTTP {response.status_code}")
                logger.error(f"响应内容: {response.text[:500]}")
                
                if response.status_code == 403:
                    logger.error("可能是 API 限额问题，请配置 GITHUB_TOKEN")
                elif response.status_code == 422:
                    logger.error("搜索查询格式错误")
                
                return []
            
            data = response.json()
            
            # 检查是否有结果
            total_count = data.get("total_count", 0)
            logger.info(f"GitHub 搜索结果总数: {total_count}")
            
            if total_count == 0:
                logger.warning(f"搜索查询未找到结果: {query}")
                return []
            
            repositories = []
            
            for item in data.get("items", []):
                repo = GitHubRepo(
                    name=item["name"],
                    full_name=item["full_name"],
                    url=item["html_url"],
                    clone_url=item["clone_url"],
                    description=item["description"] or "",
                    stars=item["stargazers_count"],
                    forks=item["forks_count"],
                    language=item["language"] or "unknown",
                    size=item["size"],
                    created_at=item["created_at"],
                    updated_at=item["updated_at"],
                    topics=item.get("topics", []),
                    score=self._calculate_score(item)
                )
                repositories.append(repo)
            
            logger.info(f"找到 {len(repositories)} 个仓库")
            return repositories
            
        except requests.Timeout:
            logger.error("API 请求超时，请检查网络连接")
            return []
        except requests.RequestException as e:
            logger.error(f"搜索仓库失败: {type(e).__name__}: {e}")
            return []
        except Exception as e:
            logger.error(f"未预期的错误: {type(e).__name__}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return []
    
    def _calculate_score(self, repo_data: Dict) -> float:
        """
        计算仓库综合评分
        
        考虑因素：
        - Stars 数量
        - Forks 数量
        - 最近更新时间
        - Issues 解决率
        """
        stars = repo_data["stargazers_count"]
        forks = repo_data["forks_count"]
        
        # 时间衰减因子
        updated_at = datetime.strptime(
            repo_data["updated_at"], 
            "%Y-%m-%dT%H:%M:%SZ"
        )
        days_since_update = (datetime.now() - updated_at).days
        recency_score = max(0, 1 - days_since_update / 365)  # 1年内更新=1.0
        
        # 综合评分
        score = (
            stars * 1.0 +
            forks * 2.0 +
            recency_score * 500
        )
        
        return score
    
    def search_by_scenario(
        self,
        scenario: str,
        max_results: int = 10
    ) -> List[GitHubRepo]:
        """
        根据预定义场景搜索
        
        Args:
            scenario: 场景名称（如"金融科技"、"电商系统"）
            max_results: 最大结果数
            
        Returns:
            仓库列表
        """
        if scenario not in SCENARIO_CONFIGS:
            logger.error(f"未知场景: {scenario}")
            logger.info(f"可用场景: {list(SCENARIO_CONFIGS.keys())}")
            return []
        
        config = SCENARIO_CONFIGS[scenario]
        logger.info(f"搜索场景: {scenario} - {config['description']}")
        
        criteria = RepoSearchCriteria(
            keywords=config["keywords"],
            language=config.get("language"),
            topics=config.get("topics", []),
            max_results=max_results
        )
        
        return self.search_repositories(criteria)
    
    def search_by_tech_stack(
        self,
        tech_stack: str,
        max_results: int = 10
    ) -> List[GitHubRepo]:
        """
        根据技术栈搜索
        
        Args:
            tech_stack: 技术栈名称
            max_results: 最大结果数
            
        Returns:
            仓库列表
        """
        if tech_stack not in TECH_STACK_CONFIGS:
            logger.error(f"未知技术栈: {tech_stack}")
            logger.info(f"可用技术栈: {list(TECH_STACK_CONFIGS.keys())}")
            return []
        
        config = TECH_STACK_CONFIGS[tech_stack]
        
        criteria = RepoSearchCriteria(
            keywords=config["keywords"],
            language=config.get("language"),
            topics=config.get("topics", []),
            max_results=max_results
        )
        
        return self.search_repositories(criteria)
    
    def get_available_scenarios(self) -> List[Dict[str, str]]:
        """获取所有可用场景"""
        return [
            {
                "name": name,
                "description": config["description"],
                "language": config.get("language", "不限")
            }
            for name, config in SCENARIO_CONFIGS.items()
        ]
    
    def get_available_tech_stacks(self) -> List[str]:
        """获取所有可用技术栈"""
        return list(TECH_STACK_CONFIGS.keys())


class RepoDownloader:
    """
    仓库下载器
    
    负责克隆 GitHub 仓库到本地
    """
    
    def __init__(self, download_dir: Path):
        """
        初始化下载器
        
        Args:
            download_dir: 下载目录
        """
        self.download_dir = Path(download_dir)
        self.download_dir.mkdir(parents=True, exist_ok=True)
    
    def clone_repository(
        self,
        repo: GitHubRepo,
        shallow: bool = True,
        depth: int = 1
    ) -> Optional[Path]:
        """
        克隆仓库
        
        Args:
            repo: 仓库信息
            shallow: 是否浅克隆（只下载最新代码）
            depth: 克隆深度
            
        Returns:
            克隆后的本地路径
        """
        repo_dir = self.download_dir / repo.name
        
        # 如果已存在，跳过
        if repo_dir.exists():
            logger.info(f"仓库已存在，跳过: {repo.name}")
            return repo_dir
        
        logger.info(f"开始克隆: {repo.full_name} -> {repo_dir}")
        
        try:
            # 构建 git clone 命令
            cmd = ["git", "clone"]
            
            if shallow:
                cmd.extend(["--depth", str(depth)])
            
            cmd.extend([repo.clone_url, str(repo_dir)])
            
            # 执行克隆
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5分钟超时
            )
            
            if result.returncode == 0:
                logger.info(f"克隆成功: {repo.name}")
                return repo_dir
            else:
                logger.error(f"克隆失败: {repo.name}, 错误: {result.stderr}")
                return None
                
        except subprocess.TimeoutExpired:
            logger.error(f"克隆超时: {repo.name}")
            return None
        except Exception as e:
            logger.error(f"克隆异常: {repo.name}, 错误: {e}")
            return None
    
    def clone_multiple(
        self,
        repos: List[GitHubRepo],
        max_concurrent: int = 3
    ) -> Dict[str, Optional[Path]]:
        """
        批量克隆仓库
        
        Args:
            repos: 仓库列表
            max_concurrent: 最大并发数（暂时串行实现）
            
        Returns:
            仓库名 -> 本地路径的映射
        """
        results = {}
        
        for i, repo in enumerate(repos):
            logger.info(f"克隆进度: {i+1}/{len(repos)}")
            path = self.clone_repository(repo)
            results[repo.full_name] = path
            
            # 避免请求过快
            if i < len(repos) - 1:
                time.sleep(2)
        
        return results


def save_repo_metadata(
    repos: List[GitHubRepo],
    output_file: Path
):
    """
    保存仓库元数据
    
    Args:
        repos: 仓库列表
        output_file: 输出文件路径
    """
    data = [asdict(repo) for repo in repos]
    
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    logger.info(f"元数据已保存: {output_file}")


def create_repos_config(
    local_paths: Dict[str, Path],
    output_file: Path
):
    """
    创建批量处理的仓库配置文件
    
    Args:
        local_paths: 仓库名 -> 本地路径的映射
        output_file: 输出配置文件路径
    """
    repositories = []
    
    for repo_name, path in local_paths.items():
        if path:  # 只包含成功克隆的
            repositories.append({
                "path": str(path),
                "name": repo_name.split("/")[-1]  # 只保留仓库名
            })
    
    config = {"repositories": repositories}
    
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    
    logger.info(f"仓库配置已保存: {output_file}")

