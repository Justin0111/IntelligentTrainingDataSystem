#!/usr/bin/env python3
"""
智能训练数据生成与处理系统 - 主入口

用于从本地代码仓库自动生成高质量的训练数据集
支持问答对生成和设计方案生成两种场景
"""

import sys
import logging
import json
from pathlib import Path
from typing import Optional, List
from datetime import datetime

import click
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.panel import Panel

from src.config import get_config, load_config
from src.utils.helpers import setup_logging, save_json, save_jsonl
from src.parsers import RepoScanner
from src.analyzers import StructureAnalyzer, LogicAnalyzer, DependencyAnalyzer
from src.generators import QAGenerator, DesignGenerator, create_llm_client
from src.processors import DataValidator, DataCleaner, DataFormatter, BatchManager

console = Console()


def print_banner():
    """打印欢迎横幅"""
    banner = """
╔══════════════════════════════════════════════════════════════╗
║     智能训练数据生成与处理系统 v0.1.0                        ║
║     Code Repository Training Data Generator                   ║
╚══════════════════════════════════════════════════════════════╝
    """
    console.print(Panel(banner, style="bold blue"))


@click.group()
@click.option('--config', '-c', default=None, help='配置文件路径')
@click.option('--verbose', '-v', is_flag=True, help='显示详细日志')
def cli(config: Optional[str], verbose: bool):
    """智能训练数据生成与处理系统
    
    从本地代码仓库自动生成高质量的训练数据集
    """
    # 加载配置
    if config:
        load_config(config)
    
    # 设置日志
    log_level = "DEBUG" if verbose else "INFO"
    setup_logging(log_level)
    
    print_banner()


@cli.command()
@click.argument('repo_path', type=click.Path(exists=True))
@click.option('--output', '-o', default='output/datasets', help='输出目录')
@click.option('--max-files', '-m', default=50, help='最大处理文件数')
@click.option('--languages', '-l', multiple=True, help='指定编程语言')
@click.option('--format', '-f', default='jsonl', 
              type=click.Choice(['jsonl', 'json', 'alpaca', 'sharegpt']),
              help='输出格式')
@click.option('--split', is_flag=True, help='是否划分训练/验证/测试集')
def generate_qa(
    repo_path: str,
    output: str,
    max_files: int,
    languages: tuple,
    format: str,
    split: bool
):
    """场景1: 生成问答对数据集
    
    根据代码仓库的业务流程和规则，自动生成问答对
    """
    repo_path = Path(repo_path).resolve()
    output_dir = Path(output)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    console.print(f"\n[bold green]开始处理代码仓库:[/bold green] {repo_path}")
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        # 初始化生成器
        task = progress.add_task("初始化生成器...", total=None)
        try:
            generator = QAGenerator()
        except Exception as e:
            console.print(f"[red]初始化失败:[/red] {e}")
            console.print("[yellow]提示: 请确保已设置 LLM API 密钥[/yellow]")
            return
        
        progress.update(task, description="扫描代码仓库...")
        
        # 生成问答对
        lang_list = list(languages) if languages else None
        qa_pairs = generator.generate_for_repository(
            repo_path,
            max_files=max_files,
            languages=lang_list
        )
        
        progress.update(task, description="验证和清洗数据...")
        
        # 验证数据
        validator = DataValidator()
        valid_pairs, invalid_pairs = validator.validate_batch(qa_pairs, "qa")
        
        # 清洗数据
        cleaner = DataCleaner()
        cleaned_pairs, stats = cleaner.clean_qa_pairs(valid_pairs)
        
        progress.update(task, description="格式化输出...")
        
        # 格式化并保存
        formatter = DataFormatter()
        
        if split:
            split_ratio = {"train": 0.8, "valid": 0.1, "test": 0.1}
        else:
            split_ratio = None
        
        output_path = output_dir / f"qa_dataset.{format if format != 'jsonl' else 'jsonl'}"
        output_files = formatter.save_qa_dataset(
            cleaned_pairs,
            output_path,
            format_type=format,
            split_ratio=split_ratio
        )
        
        progress.update(task, description="完成!")
    
    # 显示结果统计
    table = Table(title="生成结果统计")
    table.add_column("指标", style="cyan")
    table.add_column("数值", style="green")
    
    table.add_row("原始问答对数", str(len(qa_pairs)))
    table.add_row("有效问答对数", str(len(valid_pairs)))
    table.add_row("清洗后数量", str(len(cleaned_pairs)))
    table.add_row("去重数量", str(stats.duplicates_removed))
    table.add_row("输出格式", format)
    
    console.print(table)
    
    console.print(f"\n[bold green]数据集已保存:[/bold green]")
    for name, path in output_files.items():
        console.print(f"  - {name}: {path}")


@cli.command()
@click.argument('repo_path', type=click.Path(exists=True))
@click.argument('requirements', nargs=-1)
@click.option('--output', '-o', default='output/datasets', help='输出目录')
@click.option('--format', '-f', default='jsonl', 
              type=click.Choice(['jsonl', 'json', 'alpaca', 'sharegpt']),
              help='输出格式')
@click.option('--requirements-file', '-r', type=click.Path(exists=True),
              help='需求列表文件（每行一个需求）')
def generate_design(
    repo_path: str,
    requirements: tuple,
    output: str,
    format: str,
    requirements_file: Optional[str]
):
    """场景2: 生成设计方案数据集
    
    为给定的需求生成基于代码仓架构的设计方案
    """
    repo_path = Path(repo_path).resolve()
    output_dir = Path(output)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 收集需求
    all_requirements = list(requirements)
    
    if requirements_file:
        with open(requirements_file, 'r', encoding='utf-8') as f:
            all_requirements.extend([
                line.strip() for line in f 
                if line.strip() and not line.startswith('#')
            ])
    
    if not all_requirements:
        console.print("[red]错误: 请提供至少一个需求描述[/red]")
        console.print("用法: python main.py generate-design <repo_path> '需求描述'")
        return
    
    console.print(f"\n[bold green]开始处理代码仓库:[/bold green] {repo_path}")
    console.print(f"[bold]需求数量:[/bold] {len(all_requirements)}")
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("初始化生成器...", total=None)
        
        try:
            generator = DesignGenerator()
        except Exception as e:
            console.print(f"[red]初始化失败:[/red] {e}")
            return
        
        designs = []
        for i, req in enumerate(all_requirements):
            progress.update(task, description=f"生成设计方案 ({i+1}/{len(all_requirements)})...")
            
            try:
                design = generator.generate_design(repo_path, req)
                designs.append(design)
            except Exception as e:
                console.print(f"[yellow]警告: 生成失败 - {req[:30]}... : {e}[/yellow]")
        
        progress.update(task, description="验证和格式化...")
        
        # 验证数据
        validator = DataValidator()
        valid_designs, _ = validator.validate_batch(designs, "design")
        
        # 格式化并保存
        formatter = DataFormatter()
        output_path = output_dir / f"design_dataset.{format if format != 'jsonl' else 'jsonl'}"
        formatter.save_design_dataset(valid_designs, output_path, format_type=format)
        
        # 生成设计文档
        docs_dir = output_dir / "design_docs"
        docs_dir.mkdir(exist_ok=True)
        
        for design in valid_designs:
            doc_content = generator.generate_design_document(design)
            doc_path = docs_dir / f"{design.id}.md"
            doc_path.write_text(doc_content, encoding='utf-8')
        
        progress.update(task, description="完成!")
    
    # 显示结果
    table = Table(title="生成结果统计")
    table.add_column("指标", style="cyan")
    table.add_column("数值", style="green")
    
    table.add_row("需求总数", str(len(all_requirements)))
    table.add_row("成功生成", str(len(designs)))
    table.add_row("有效方案", str(len(valid_designs)))
    
    console.print(table)
    console.print(f"\n[bold green]数据集已保存:[/bold green] {output_path}")
    console.print(f"[bold green]设计文档目录:[/bold green] {docs_dir}")


@cli.command()
@click.argument('repo_path', type=click.Path(exists=True))
def analyze(repo_path: str):
    """分析代码仓库结构
    
    不生成数据，仅分析并显示代码仓库的结构信息
    """
    repo_path = Path(repo_path).resolve()
    
    console.print(f"\n[bold green]分析代码仓库:[/bold green] {repo_path}")
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("扫描仓库...", total=None)
        
        # 扫描仓库
        scanner = RepoScanner()
        repo_info = scanner.scan_repository(repo_path)
        
        progress.update(task, description="分析代码结构...")
        structure_analyzer = StructureAnalyzer()
        structure = structure_analyzer.analyze(repo_path)
        
        progress.update(task, description="分析依赖关系...")
        dep_analyzer = DependencyAnalyzer()
        dependencies = dep_analyzer.analyze_repository(repo_path)
        
        progress.update(task, description="完成!")
    
    # 显示基本信息
    console.print("\n[bold]基本信息[/bold]")
    table = Table()
    table.add_column("属性", style="cyan")
    table.add_column("值", style="green")
    
    table.add_row("仓库名称", repo_info.name)
    table.add_row("文件总数", str(repo_info.total_files))
    table.add_row("总大小", f"{repo_info.total_size / 1024:.2f} KB")
    table.add_row("类数量", str(structure.total_classes))
    table.add_row("函数数量", str(structure.total_functions))
    
    console.print(table)
    
    # 语言分布
    if repo_info.languages:
        console.print("\n[bold]语言分布[/bold]")
        lang_table = Table()
        lang_table.add_column("语言", style="cyan")
        lang_table.add_column("文件数", style="green")
        
        for lang, count in sorted(repo_info.languages.items(), key=lambda x: x[1], reverse=True):
            lang_table.add_row(lang, str(count))
        
        console.print(lang_table)
    
    # 模块信息
    if structure.modules:
        console.print("\n[bold]模块结构[/bold]")
        for module in structure.modules[:10]:
            console.print(f"  • [cyan]{module.name}[/cyan]: {len(module.files)} 文件")
    
    # 架构模式
    if structure.architecture_patterns:
        console.print("\n[bold]识别到的架构模式[/bold]")
        for pattern in structure.architecture_patterns:
            console.print(f"  • [yellow]{pattern.name}[/yellow] (置信度: {pattern.confidence:.0%})")
    
    # 依赖信息
    console.print(f"\n[bold]依赖分析[/bold]")
    console.print(f"  • 内部模块: {len(dependencies.nodes)}")
    console.print(f"  • 外部依赖: {len(dependencies.external_dependencies)}")
    if dependencies.circular_dependencies:
        console.print(f"  • [red]循环依赖: {len(dependencies.circular_dependencies)}[/red]")


@cli.command()
@click.argument('data_path', type=click.Path(exists=True))
@click.option('--output', '-o', default='output/models', help='模型输出目录')
@click.option('--epochs', '-e', default=1, help='训练轮数')
@click.option('--samples', '-s', default=100, help='最大样本数')
def validate(data_path: str, output: str, epochs: int, samples: int):
    """快速验证数据集效果
    
    使用小模型快速微调，验证数据集质量
    """
    from src.finetuning import FineTuner
    
    data_path = Path(data_path)
    output_dir = Path(output)
    
    console.print(f"\n[bold green]快速验证数据集:[/bold green] {data_path}")
    console.print(f"[bold]参数:[/bold] epochs={epochs}, max_samples={samples}")
    
    console.print("\n[yellow]注意: 此功能需要 GPU 支持和足够的显存[/yellow]")
    console.print("[yellow]依赖: torch, transformers, peft, datasets[/yellow]\n")
    
    try:
        trainer = FineTuner()
        result = trainer.quick_validate(
            data_path,
            output_dir,
            num_epochs=epochs,
            max_samples=samples
        )
        
        # 显示结果
        console.print("\n[bold]验证结果[/bold]")
        table = Table()
        table.add_column("指标", style="cyan")
        table.add_column("值", style="green")
        
        eval_result = result.get("evaluation", {})
        table.add_row("困惑度", f"{eval_result.get('perplexity', 0):.4f}")
        table.add_row("平均损失", f"{eval_result.get('metrics', {}).get('avg_loss', 0):.4f}")
        
        console.print(table)
        
        # 显示样本输出
        if eval_result.get("sample_outputs"):
            console.print("\n[bold]样本输出[/bold]")
            for i, sample in enumerate(eval_result["sample_outputs"][:3]):
                console.print(f"\n[cyan]样本 {i+1}:[/cyan]")
                console.print(f"  提示: {sample['prompt'][:100]}...")
                console.print(f"  生成: {sample['generated'][:200]}...")
        
        console.print(f"\n[bold green]完整结果已保存至:[/bold green] {output_dir}/validation_result.json")
        
    except Exception as e:
        console.print(f"[red]验证失败:[/red] {e}")
        console.print("\n[yellow]请确保已安装必要的依赖并有足够的计算资源[/yellow]")


@cli.command()
@click.argument('repo_path', type=click.Path(exists=True))
@click.option('--output', '-o', default='output', help='输出目录')
@click.option('--max-files', '-m', default=30, help='最大处理文件数')
@click.option('--requirements', '-r', multiple=True, help='需求描述（可多次指定）')
def full_pipeline(
    repo_path: str,
    output: str,
    max_files: int,
    requirements: tuple
):
    """完整流程: 分析 + QA生成 + 设计方案生成
    
    执行完整的数据生成流程
    """
    repo_path = Path(repo_path).resolve()
    output_dir = Path(output)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    console.print(f"\n[bold green]执行完整数据生成流程[/bold green]")
    console.print(f"代码仓库: {repo_path}")
    console.print(f"输出目录: {output_dir}")
    
    results = {"timestamp": timestamp, "repo_path": str(repo_path)}
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        # 1. 分析代码仓库
        task = progress.add_task("[1/4] 分析代码仓库...", total=None)
        
        scanner = RepoScanner()
        repo_info = scanner.scan_repository(repo_path)
        
        structure_analyzer = StructureAnalyzer()
        structure = structure_analyzer.analyze(repo_path)
        
        results["analysis"] = {
            "total_files": repo_info.total_files,
            "languages": repo_info.languages,
            "total_classes": structure.total_classes,
            "total_functions": structure.total_functions,
            "modules": [m.name for m in structure.modules]
        }
        
        # 2. 生成问答对
        progress.update(task, description="[2/4] 生成问答对...")
        
        try:
            qa_generator = QAGenerator()
            qa_pairs = qa_generator.generate_for_repository(repo_path, max_files=max_files)
            
            validator = DataValidator()
            valid_qa, _ = validator.validate_batch(qa_pairs, "qa")
            
            cleaner = DataCleaner()
            cleaned_qa, qa_stats = cleaner.clean_qa_pairs(valid_qa)
            
            formatter = DataFormatter()
            qa_output = output_dir / "datasets" / f"qa_dataset_{timestamp}.jsonl"
            formatter.save_qa_dataset(cleaned_qa, qa_output)
            
            results["qa_generation"] = {
                "total_generated": len(qa_pairs),
                "valid": len(valid_qa),
                "cleaned": len(cleaned_qa),
                "output_file": str(qa_output)
            }
        except Exception as e:
            console.print(f"[yellow]QA生成跳过: {e}[/yellow]")
            results["qa_generation"] = {"error": str(e)}
        
        # 3. 生成设计方案
        progress.update(task, description="[3/4] 生成设计方案...")
        
        # 如果没有提供需求，生成一些默认需求
        if not requirements:
            requirements = [
                f"为{repo_info.name}项目添加用户认证功能",
                f"为{repo_info.name}项目添加日志记录模块",
            ]
        
        try:
            design_generator = DesignGenerator()
            designs = []
            
            for req in requirements:
                try:
                    design = design_generator.generate_design(repo_path, req)
                    designs.append(design)
                except Exception as e:
                    console.print(f"[yellow]设计方案生成失败: {req[:30]}...[/yellow]")
            
            if designs:
                valid_designs, _ = validator.validate_batch(designs, "design")
                
                design_output = output_dir / "datasets" / f"design_dataset_{timestamp}.jsonl"
                formatter.save_design_dataset(valid_designs, design_output)
                
                results["design_generation"] = {
                    "total_generated": len(designs),
                    "valid": len(valid_designs),
                    "output_file": str(design_output)
                }
        except Exception as e:
            console.print(f"[yellow]设计方案生成跳过: {e}[/yellow]")
            results["design_generation"] = {"error": str(e)}
        
        # 4. 生成报告
        progress.update(task, description="[4/4] 生成报告...")
        
        report_path = output_dir / f"generation_report_{timestamp}.json"
        save_json(results, report_path)
        
        # 生成数据集说明
        if cleaned_qa or designs:
            formatter.create_dataset_card(
                cleaned_qa if 'cleaned_qa' in dir() else [],
                valid_designs if 'valid_designs' in dir() else [],
                output_dir / "datasets"
            )
        
        progress.update(task, description="完成!")
    
    # 显示总结
    console.print("\n[bold]生成总结[/bold]")
    table = Table()
    table.add_column("类型", style="cyan")
    table.add_column("数量", style="green")
    table.add_column("状态", style="yellow")
    
    qa_info = results.get("qa_generation", {})
    if "error" in qa_info:
        table.add_row("问答对", "-", f"失败: {qa_info['error'][:30]}")
    else:
        table.add_row("问答对", str(qa_info.get("cleaned", 0)), "✓")
    
    design_info = results.get("design_generation", {})
    if "error" in design_info:
        table.add_row("设计方案", "-", f"失败: {design_info['error'][:30]}")
    else:
        table.add_row("设计方案", str(design_info.get("valid", 0)), "✓")
    
    console.print(table)
    console.print(f"\n[bold green]报告已保存:[/bold green] {report_path}")


@cli.command()
@click.argument('repos_file', type=click.Path(exists=True))
@click.option('--output', '-o', default='output/batch', help='输出目录')
@click.option('--max-files', '-m', default=30, help='每个仓库最大处理文件数')
@click.option('--max-qa-per-repo', default=None, type=int, help='每个仓库最大QA数量')
@click.option('--max-design-per-repo', default=None, type=int, help='每个仓库最大设计方案数量')
@click.option('--balance-strategy', '-b', 
              type=click.Choice(['proportional', 'uniform', 'weighted']),
              default='proportional',
              help='数据平衡策略')
@click.option('--format', '-f', default='jsonl',
              type=click.Choice(['jsonl', 'json', 'alpaca', 'sharegpt']),
              help='输出格式')
@click.option('--requirements-file', '-r', type=click.Path(exists=True),
              help='设计需求列表文件')
@click.option('--split', is_flag=True, help='是否划分训练/验证/测试集')
@click.option('--design-only', is_flag=True, help='只生成设计方案数据，跳过QA生成')
def batch_generate(
    repos_file: str,
    output: str,
    max_files: int,
    max_qa_per_repo: Optional[int],
    max_design_per_repo: Optional[int],
    balance_strategy: str,
    format: str,
    requirements_file: Optional[str],
    split: bool,
    design_only: bool
):
    """批量处理多个代码仓库
    
    从配置文件读取多个仓库路径，批量生成训练数据
    
    配置文件格式 (repos.txt):
    /path/to/repo1
    /path/to/repo2
    /path/to/repo3
    
    或 JSON 格式 (repos.json):
    {
      "repositories": [
        {"path": "/path/to/repo1", "name": "repo1"},
        {"path": "/path/to/repo2", "name": "repo2"}
      ]
    }
    """
    import time
    from collections import defaultdict
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(output)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 读取仓库列表
    repos_file_path = Path(repos_file)
    if repos_file_path.suffix == '.json':
        with open(repos_file_path, 'r', encoding='utf-8') as f:
            repos_config = json.load(f)
            repo_list = [
                (item['path'], item.get('name', Path(item['path']).name))
                for item in repos_config.get('repositories', [])
            ]
    else:
        # 纯文本格式，每行一个路径
        with open(repos_file_path, 'r', encoding='utf-8') as f:
            repo_paths = [line.strip() for line in f if line.strip() and not line.startswith('#')]
            repo_list = [(path, Path(path).name) for path in repo_paths]
    
    if not repo_list:
        console.print("[red]错误: 没有找到有效的仓库路径[/red]")
        return
    
    console.print(f"\n[bold green]批量处理 {len(repo_list)} 个代码仓库[/bold green]")
    console.print(f"输出目录: {output_dir}")
    console.print(f"平衡策略: {balance_strategy}")
    if design_only:
        console.print(f"[yellow]模式: 只生成设计方案数据（跳过QA）[/yellow]")
    if max_qa_per_repo and not design_only:
        console.print(f"每个仓库最大QA数: {max_qa_per_repo}")
    if max_design_per_repo:
        console.print(f"每个仓库最大设计方案数: {max_design_per_repo}")
    
    start_time = time.time()
    
    # 读取设计需求
    design_requirements = []
    if requirements_file:
        with open(requirements_file, 'r', encoding='utf-8') as f:
            design_requirements = [
                line.strip() for line in f 
                if line.strip() and not line.startswith('#')
            ]
    
    # 存储所有仓库的数据
    repo_qa_map = {}
    repo_design_map = {}
    processing_errors = defaultdict(list)
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        # 初始化生成器
        task = progress.add_task("初始化生成器...", total=None)
        try:
            if not design_only:
                qa_generator = QAGenerator()
            design_generator = DesignGenerator()
        except Exception as e:
            console.print(f"[red]初始化失败:[/red] {e}")
            return
        
        validator = DataValidator()
        cleaner = DataCleaner()
        
        # 处理每个仓库
        for i, (repo_path, repo_name) in enumerate(repo_list):
            progress.update(
                task,
                description=f"[{i+1}/{len(repo_list)}] 处理 {repo_name}..."
            )
            
            repo_path_obj = Path(repo_path)
            if not repo_path_obj.exists():
                console.print(f"[yellow]跳过不存在的仓库: {repo_path}[/yellow]")
                processing_errors[repo_name].append(f"路径不存在: {repo_path}")
                continue
            
            try:
                # 生成问答对 (如果不是 design-only 模式)
                if not design_only:
                    progress.update(task, description=f"[{i+1}/{len(repo_list)}] {repo_name} - 生成QA...")
                    qa_pairs = qa_generator.generate_for_repository(
                        repo_path_obj,
                        max_files=max_files
                    )
                    
                    if qa_pairs:
                        valid_qa, _ = validator.validate_batch(qa_pairs, "qa")
                        cleaned_qa, _ = cleaner.clean_qa_pairs(valid_qa)
                        repo_qa_map[repo_name] = cleaned_qa
                        console.print(f"  ✓ {repo_name}: 生成 {len(cleaned_qa)} 个QA")
                    else:
                        repo_qa_map[repo_name] = []
                        console.print(f"  • {repo_name}: 未生成QA")
                else:
                    # design-only 模式，跳过 QA 生成
                    repo_qa_map[repo_name] = []
                
            except Exception as e:
                console.print(f"[yellow]  ✗ {repo_name} QA生成失败: {e}[/yellow]")
                processing_errors[repo_name].append(f"QA生成错误: {str(e)}")
                repo_qa_map[repo_name] = []
            
            try:
                # 生成设计方案
                if design_requirements:
                    progress.update(task, description=f"[{i+1}/{len(repo_list)}] {repo_name} - 生成设计方案...")
                    designs = []
                    
                    # 为每个需求生成设计方案
                    for req in design_requirements[:3]:  # 限制每个仓库最多3个需求
                        try:
                            design = design_generator.generate_design(repo_path_obj, req)
                            designs.append(design)
                        except Exception as e:
                            console.print(f"[yellow]  • 设计方案生成失败: {req[:30]}...[/yellow]")
                    
                    if designs:
                        valid_designs, _ = validator.validate_batch(designs, "design")
                        repo_design_map[repo_name] = valid_designs
                        console.print(f"  ✓ {repo_name}: 生成 {len(valid_designs)} 个设计方案")
                    else:
                        repo_design_map[repo_name] = []
                else:
                    repo_design_map[repo_name] = []
                    
            except Exception as e:
                console.print(f"[yellow]  ✗ {repo_name} 设计方案生成失败: {e}[/yellow]")
                processing_errors[repo_name].append(f"设计方案错误: {str(e)}")
                repo_design_map[repo_name] = []
        
        # 批量处理和合并数据
        progress.update(task, description="合并和平衡数据...")
        
        batch_manager = BatchManager(
            max_qa_per_repo=max_qa_per_repo,
            max_design_per_repo=max_design_per_repo,
            balance_strategy=balance_strategy,
            shuffle=True,
            deduplicate=True
        )
        
        merged_qa, merged_designs, batch_stats = batch_manager.process_repositories(
            repo_qa_map,
            repo_design_map
        )
        
        # 保存数据
        progress.update(task, description="保存数据集...")
        
        formatter = DataFormatter()
        
        # 保存 QA 数据集
        if merged_qa:
            qa_output = output_dir / f"merged_qa_dataset_{timestamp}.{format if format != 'jsonl' else 'jsonl'}"
            
            if split:
                split_ratio = {"train": 0.8, "valid": 0.1, "test": 0.1}
            else:
                split_ratio = None
            
            qa_files = formatter.save_qa_dataset(
                merged_qa,
                qa_output,
                format_type=format,
                split_ratio=split_ratio
            )
        
        # 保存设计方案数据集
        if merged_designs:
            design_output = output_dir / f"merged_design_dataset_{timestamp}.{format if format != 'jsonl' else 'jsonl'}"
            
            # 如果指定了 split，也划分 Design 数据集
            if split:
                split_ratio = {"train": 0.8, "valid": 0.1, "test": 0.1}
            else:
                split_ratio = None
            
            design_files = formatter.save_design_dataset(
                merged_designs, 
                design_output, 
                format_type=format,
                split_ratio=split_ratio
            )
            
            # 生成设计文档
            docs_dir = output_dir / "design_docs"
            docs_dir.mkdir(exist_ok=True)
            for design in merged_designs[:10]:  # 只保存前10个作为示例
                doc_content = design_generator.generate_design_document(design)
                doc_path = docs_dir / f"{design.id}.md"
                doc_path.write_text(doc_content, encoding='utf-8')
        
        # 生成数据集说明
        if merged_qa or merged_designs:
            formatter.create_dataset_card(
                merged_qa,
                merged_designs,
                output_dir
            )
        
        # 保存批处理报告
        progress.update(task, description="生成报告...")
        
        batch_stats["processing_errors"] = dict(processing_errors)
        batch_stats["timestamp"] = timestamp
        batch_stats["config"] = {
            "max_files_per_repo": max_files,
            "max_qa_per_repo": max_qa_per_repo,
            "max_design_per_repo": max_design_per_repo,
            "balance_strategy": balance_strategy,
            "output_format": format
        }
        
        report_path = output_dir / f"batch_report_{timestamp}.json"
        batch_manager.save_batch_report(batch_stats, report_path)
        
        progress.update(task, description="完成!")
    
    end_time = time.time()
    duration = end_time - start_time
    
    # 显示结果摘要
    console.print("\n[bold]批量处理完成![/bold]\n")
    
    summary_table = Table(title="数据统计")
    summary_table.add_column("类型", style="cyan")
    summary_table.add_column("原始数据", style="yellow")
    summary_table.add_column("最终数据", style="green")
    summary_table.add_column("移除数据", style="red")
    
    summary = batch_stats["summary"]
    summary_table.add_row(
        "问答对",
        str(summary["total_qa_original"]),
        str(summary["total_qa_final"]),
        str(summary["qa_removed"])
    )
    summary_table.add_row(
        "设计方案",
        str(summary["total_design_original"]),
        str(summary["total_design_final"]),
        str(summary["design_removed"])
    )
    
    console.print(summary_table)
    
    # 仓库贡献表
    repo_table = Table(title="各仓库贡献")
    repo_table.add_column("仓库", style="cyan")
    repo_table.add_column("QA数量", style="green")
    repo_table.add_column("设计方案", style="green")
    
    for repo_name, stats in batch_stats["by_repo"].items():
        repo_table.add_row(
            repo_name,
            f"{stats['qa']['balanced']} ({stats['qa']['original']})",
            f"{stats['design']['balanced']} ({stats['design']['original']})"
        )
    
    console.print("\n")
    console.print(repo_table)
    
    # 平衡度指标
    balance = batch_stats["balance_metrics"]
    console.print("\n[bold]数据平衡度[/bold]")
    console.print(f"  • QA 平衡比: {balance['qa_balance_ratio']:.1%}")
    console.print(f"  • Design 平衡比: {balance['design_balance_ratio']:.1%}")
    
    console.print(f"\n[bold]处理时间:[/bold] {duration:.2f} 秒")
    console.print(f"\n[bold green]输出文件:[/bold green]")
    console.print(f"  • 数据集: {output_dir}")
    console.print(f"  • 报告: {report_path}")
    console.print(f"  • Markdown报告: {report_path.with_suffix('.md')}")


@cli.command()
@click.option('--scenario', '-s', multiple=True, help='业务场景（可多次指定）')
@click.option('--tech-stack', '-t', multiple=True, help='技术栈（可多次指定）')
@click.option('--language', '-l', help='编程语言')
@click.option('--max-repos', '-n', default=10, help='每个场景最大仓库数')
@click.option('--min-stars', default=100, help='最小 Star 数')
@click.option('--download-dir', '-d', default='downloaded_repos', help='下载目录')
@click.option('--output', '-o', default='output/auto_discovered', help='数据输出目录')
@click.option('--list-scenarios', is_flag=True, help='列出所有可用场景')
@click.option('--list-tech-stacks', is_flag=True, help='列出所有可用技术栈')
@click.option('--auto-generate', is_flag=True, help='自动执行批量数据生成')
@click.option('--max-qa-per-repo', default=50, help='每个仓库最大QA数')
@click.option('--format', '-f', default='alpaca', 
              type=click.Choice(['jsonl', 'json', 'alpaca', 'sharegpt']),
              help='输出格式')
@click.option('--split', is_flag=True, help='是否划分训练/验证/测试集')
def auto_discover(
    scenario: tuple,
    tech_stack: tuple,
    language: Optional[str],
    max_repos: int,
    min_stars: int,
    download_dir: str,
    output: str,
    list_scenarios: bool,
    list_tech_stacks: bool,
    auto_generate: bool,
    max_qa_per_repo: int,
    format: str,
    split: bool
):
    """自动发现和下载 GitHub 优质代码仓库
    
    根据业务场景、技术栈等维度自动搜索 GitHub 上的高质量仓库，
    下载后可选择自动执行批量数据生成。
    
    示例:
      # 列出所有可用场景
      python main.py auto-discover --list-scenarios
      
      # 搜索金融科技和电商系统的仓库（仅搜索）
      python main.py auto-discover -s 金融科技 -s 电商系统 -n 5
      
      # 搜索并自动生成训练数据
      python main.py auto-discover -s 微服务架构 -t "Python Web" --auto-generate
      
      # 搜索、生成并划分数据集
      python main.py auto-discover -s 金融科技 --auto-generate --split
      
      # 指定编程语言
      python main.py auto-discover -s API服务 -l python --auto-generate --split
    """
    from src.utils.github_discovery import (
        GitHubDiscovery, RepoDownloader, SCENARIO_CONFIGS, 
        TECH_STACK_CONFIGS, save_repo_metadata, create_repos_config,
        RepoSearchCriteria
    )
    
    discovery = GitHubDiscovery()
    
    # 列出可用选项
    if list_scenarios:
        console.print("\n[bold]可用业务场景:[/bold]\n")
        table = Table()
        table.add_column("场景名称", style="cyan")
        table.add_column("描述", style="green")
        table.add_column("语言", style="yellow")
        
        for name, config in SCENARIO_CONFIGS.items():
            table.add_row(
                name,
                config["description"],
                config.get("language", "不限")
            )
        
        console.print(table)
        return
    
    if list_tech_stacks:
        console.print("\n[bold]可用技术栈:[/bold]\n")
        table = Table()
        table.add_column("技术栈", style="cyan")
        table.add_column("关键词", style="green")
        
        for name, config in TECH_STACK_CONFIGS.items():
            keywords = ", ".join(config["keywords"][:3])
            table.add_row(name, keywords)
        
        console.print(table)
        return
    
    # 检查是否指定了搜索条件
    if not scenario and not tech_stack:
        console.print("[yellow]请指定至少一个场景或技术栈[/yellow]")
        console.print("\n提示:")
        console.print("  python main.py auto-discover --list-scenarios")
        console.print("  python main.py auto-discover -s 金融科技")
        return
    
    console.print("\n[bold green]开始自动发现 GitHub 仓库[/bold green]\n")
    
    all_repos = []
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        # 按场景搜索
        if scenario:
            for sc in scenario:
                task = progress.add_task(f"搜索场景: {sc}...", total=None)
                repos = discovery.search_by_scenario(sc, max_results=max_repos)
                all_repos.extend(repos)
                progress.update(task, description=f"✓ {sc}: 找到 {len(repos)} 个仓库")
        
        # 按技术栈搜索
        if tech_stack:
            for ts in tech_stack:
                task = progress.add_task(f"搜索技术栈: {ts}...", total=None)
                repos = discovery.search_by_tech_stack(ts, max_results=max_repos)
                all_repos.extend(repos)
                progress.update(task, description=f"✓ {ts}: 找到 {len(repos)} 个仓库")
        
        # 自定义语言过滤
        if language:
            all_repos = [r for r in all_repos if r.language.lower() == language.lower()]
        
        # 去重（基于 full_name）
        seen = set()
        unique_repos = []
        for repo in all_repos:
            if repo.full_name not in seen:
                seen.add(repo.full_name)
                unique_repos.append(repo)
        
        all_repos = unique_repos
        
        # 按评分排序
        all_repos.sort(key=lambda r: r.score, reverse=True)
        
        console.print(f"\n[bold]共找到 {len(all_repos)} 个唯一仓库[/bold]\n")
    
    # 显示仓库列表
    if all_repos:
        table = Table(title="发现的仓库")
        table.add_column("仓库", style="cyan")
        table.add_column("描述", style="green", max_width=40)
        table.add_column("Stars", style="yellow")
        table.add_column("语言", style="blue")
        table.add_column("评分", style="magenta")
        
        for repo in all_repos[:20]:  # 显示前20个
            table.add_row(
                repo.full_name,
                repo.description[:50] + "..." if len(repo.description) > 50 else repo.description,
                str(repo.stars),
                repo.language,
                f"{repo.score:.0f}"
            )
        
        console.print(table)
        
        if len(all_repos) > 20:
            console.print(f"\n[dim]...还有 {len(all_repos) - 20} 个仓库未显示[/dim]")
    else:
        console.print("[yellow]未找到符合条件的仓库[/yellow]")
        return
    
    # 保存元数据
    download_dir_path = Path(download_dir)
    metadata_file = download_dir_path / "repos_metadata.json"
    save_repo_metadata(all_repos, metadata_file)
    
    # 询问是否下载
    if not auto_generate:
        console.print(f"\n[bold]元数据已保存:[/bold] {metadata_file}")
        console.print("\n要下载这些仓库并生成训练数据，请使用:")
        console.print(f"  python main.py auto-discover -s {scenario[0] if scenario else tech_stack[0]} --auto-generate")
        return
    
    # 下载仓库
    console.print("\n[bold green]开始下载仓库...[/bold green]")
    
    downloader = RepoDownloader(download_dir_path)
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("下载中...", total=len(all_repos))
        
        local_paths = {}
        for i, repo in enumerate(all_repos):
            progress.update(task, description=f"克隆 {repo.name}...")
            path = downloader.clone_repository(repo)
            if path:
                local_paths[repo.full_name] = path
            progress.advance(task)
    
    successful = len([p for p in local_paths.values() if p])
    console.print(f"\n[green]成功下载 {successful}/{len(all_repos)} 个仓库[/green]")
    
    if successful == 0:
        console.print("[red]没有成功下载任何仓库，退出[/red]")
        return
    
    # 创建批量处理配置
    repos_config_file = download_dir_path / "repos_config.json"
    create_repos_config(local_paths, repos_config_file)
    console.print(f"[green]配置文件已创建:[/green] {repos_config_file}")
    
    # 自动执行批量生成
    console.print("\n[bold green]开始批量生成训练数据...[/bold green]")
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(output)
    
    try:
        from collections import defaultdict
        from src.generators import QAGenerator, DesignGenerator
        from src.processors import DataValidator, DataCleaner, DataFormatter, BatchManager
        
        qa_generator = QAGenerator()
        validator = DataValidator()
        cleaner = DataCleaner()
        
        repo_qa_map = {}
        repo_design_map = {}
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("生成数据...", total=len(local_paths))
            
            for repo_name, repo_path in local_paths.items():
                if not repo_path:
                    continue
                
                short_name = repo_name.split("/")[-1]
                progress.update(task, description=f"处理 {short_name}...")
                
                try:
                    # 生成 QA
                    qa_pairs = qa_generator.generate_for_repository(
                        repo_path,
                        max_files=20  # 限制文件数以加快速度
                    )
                    
                    if qa_pairs:
                        valid_qa, _ = validator.validate_batch(qa_pairs, "qa")
                        cleaned_qa, _ = cleaner.clean_qa_pairs(valid_qa)
                        repo_qa_map[short_name] = cleaned_qa
                    else:
                        repo_qa_map[short_name] = []
                        
                except Exception as e:
                    console.print(f"[yellow]处理失败 {short_name}: {e}[/yellow]")
                    repo_qa_map[short_name] = []
                    repo_design_map[short_name] = []
                
                progress.advance(task)
        
        # 批量处理和合并
        batch_manager = BatchManager(
            max_qa_per_repo=max_qa_per_repo,
            balance_strategy="proportional"
        )
        
        merged_qa, merged_designs, batch_stats = batch_manager.process_repositories(
            repo_qa_map,
            {}  # 暂不生成设计方案以节省时间
        )
        
        # 保存数据
        formatter = DataFormatter()
        
        if merged_qa:
            qa_output = output_dir / f"auto_discovered_qa_{timestamp}.{format if format != 'jsonl' else 'jsonl'}"
            
            # 划分数据集
            if split:
                split_ratio = {"train": 0.8, "valid": 0.1, "test": 0.1}
            else:
                split_ratio = None
            
            output_files = formatter.save_qa_dataset(
                merged_qa, 
                qa_output, 
                format_type=format,
                split_ratio=split_ratio
            )
            
            console.print(f"\n[bold green]✓ 数据集已保存:[/bold green]")
            for split_name, file_path in output_files.items():
                console.print(f"  - {split_name}: {file_path}")
            console.print(f"[bold]总数据量:[/bold] {len(merged_qa)} 条")
        
        # 保存报告
        report_path = output_dir / f"discovery_report_{timestamp}.json"
        batch_manager.save_batch_report(batch_stats, report_path)
        
        console.print(f"[bold green]✓ 报告已保存:[/bold green] {report_path}")
        
    except Exception as e:
        console.print(f"[red]批量生成失败:[/red] {e}")
        import traceback
        console.print(traceback.format_exc())


@cli.command()
def version():
    """显示版本信息"""
    from src import __version__
    console.print(f"智能训练数据生成系统 v{__version__}")
    console.print("作者: IntelligentTrainingDataSystem Team")


if __name__ == "__main__":
    cli()

