"""
Pytest 配置和共享 fixtures
"""

import sys
from pathlib import Path

import pytest

# 确保项目根目录在 Python 路径中
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


@pytest.fixture
def sample_python_code():
    """返回用于测试的示例 Python 代码"""
    return '''
def calculate_total(items: list, discount: float = 0.0) -> float:
    """
    计算订单总价
    
    Args:
        items: 商品列表，每个商品包含 price 和 quantity
        discount: 折扣比例 (0-1)
    
    Returns:
        折扣后的总价
    """
    subtotal = sum(item["price"] * item["quantity"] for item in items)
    return subtotal * (1 - discount)


class OrderProcessor:
    """订单处理器"""
    
    def __init__(self, tax_rate: float = 0.1):
        self.tax_rate = tax_rate
    
    def process(self, order_data: dict) -> dict:
        """处理订单"""
        total = calculate_total(order_data["items"])
        tax = total * self.tax_rate
        return {
            "subtotal": total,
            "tax": tax,
            "total": total + tax
        }
'''


@pytest.fixture
def sample_javascript_code():
    """返回用于测试的示例 JavaScript 代码"""
    return '''
/**
 * 计算购物车总价
 * @param {Array} items - 商品列表
 * @param {number} discount - 折扣比例
 * @returns {number} 总价
 */
function calculateCartTotal(items, discount = 0) {
    const subtotal = items.reduce((sum, item) => {
        return sum + item.price * item.quantity;
    }, 0);
    return subtotal * (1 - discount);
}

class ShoppingCart {
    constructor() {
        this.items = [];
    }
    
    addItem(item) {
        this.items.push(item);
    }
    
    getTotal() {
        return calculateCartTotal(this.items);
    }
}

export { calculateCartTotal, ShoppingCart };
'''


@pytest.fixture
def temp_repo(tmp_path):
    """创建临时代码仓库用于测试"""
    # 创建目录结构
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    
    # 创建 Python 文件
    (src_dir / "main.py").write_text('''
def hello():
    """Say hello"""
    return "Hello, World!"

def add(a, b):
    """Add two numbers"""
    return a + b
''')
    
    (src_dir / "utils.py").write_text('''
def format_name(first, last):
    """Format full name"""
    return f"{first} {last}"
''')
    
    return tmp_path


@pytest.fixture
def mock_llm_response():
    """模拟 LLM 响应"""
    return {
        "question": "这个函数的作用是什么？",
        "answer": "这是一个计算总价的函数...",
        "reasoning": [
            {"step": 1, "thought": "首先分析函数签名"},
            {"step": 2, "thought": "然后查看函数实现"},
            {"step": 3, "thought": "最后总结功能"}
        ]
    }


# 标记需要 LLM API 的测试
def pytest_configure(config):
    """添加自定义标记"""
    config.addinivalue_line(
        "markers", "requires_llm: mark test as requiring LLM API"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )


# 跳过没有 API Key 的 LLM 测试
def pytest_collection_modifyitems(config, items):
    """自动跳过需要 LLM 但没有配置的测试"""
    import os
    
    skip_llm = pytest.mark.skip(reason="LLM_API_KEY not set")
    
    for item in items:
        if "requires_llm" in item.keywords:
            if not os.getenv("LLM_API_KEY"):
                item.add_marker(skip_llm)

