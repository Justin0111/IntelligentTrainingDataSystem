#!/usr/bin/env python3
"""
智能训练数据生成与处理系统 - 安装配置
"""

from setuptools import setup, find_packages
from pathlib import Path

# 读取 README
readme_path = Path(__file__).parent / "README.md"
long_description = readme_path.read_text(encoding="utf-8") if readme_path.exists() else ""

# 读取依赖
requirements_path = Path(__file__).parent / "requirements.txt"
requirements = []
if requirements_path.exists():
    with open(requirements_path, 'r', encoding='utf-8') as f:
        requirements = [
            line.strip() 
            for line in f 
            if line.strip() and not line.startswith('#')
        ]

# 核心依赖（不包含可选的微调依赖）
core_requirements = [
    "pydantic>=2.5.0",
    "pydantic-settings>=2.1.0",
    "python-dotenv>=1.0.0",
    "dashscope>=1.14.0",
    "tree-sitter>=0.20.0",
    "tree-sitter-python>=0.20.0",
    "tree-sitter-javascript>=0.20.0",
    "tree-sitter-java>=0.20.0",
    "javalang>=0.13.0",
    "pandas>=2.1.0",
    "jsonlines>=4.0.0",
    "tqdm>=4.66.0",
    "rich>=13.7.0",
    "click>=8.1.0",
    "requests>=2.31.0",
]

# 可选依赖
extras_require = {
    "finetuning": [
        "torch>=2.1.0",
        "transformers>=4.36.0",
        "peft>=0.7.0",
        "datasets>=2.15.0",
        "accelerate>=0.25.0",
    ],
    "dev": [
        "pytest>=7.4.0",
        "pytest-asyncio>=0.21.0",
        "black>=23.0.0",
        "isort>=5.12.0",
        "flake8>=6.0.0",
    ],
}

setup(
    name="training-data-generator",
    version="0.2.0",
    author="IntelligentTrainingDataSystem Team",
    author_email="project@example.com",
    description="智能训练数据生成与处理系统",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/your-org/IntelligentTrainingDataSystem",
    packages=find_packages(exclude=["tests*", "examples*"]),
    python_requires=">=3.10",
    install_requires=core_requirements,
    extras_require=extras_require,
    entry_points={
        "console_scripts": [
            "training-data-gen=main:cli",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Software Development :: Code Generators",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
    ],
    keywords="training-data, code-generation, llm, fine-tuning, qwen",
    include_package_data=True,
    package_data={
        "": ["templates/*.txt"],
    },
)

