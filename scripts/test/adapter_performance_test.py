#!/usr/bin/env python3
"""
适配器性能基准测试

比较迁移前后的性能指标。
"""

import sys
import time
import statistics
from pathlib import Path
from typing import List, Tuple, Callable

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / 'src'))


def measure_import_time(module_name: str, iterations: int = 10) -> Tuple[float, float]:
    """测量模块导入时间"""
    times = []
    
    for _ in range(iterations):
        # 清除已导入的模块
        if module_name in sys.modules:
            del sys.modules[module_name]
        
        start = time.perf_counter()
        try:
            __import__(module_name)
        except Exception:
            return -1, -1
        end = time.perf_counter()
        
        times.append(end - start)
    
    return statistics.mean(times), statistics.stdev(times)


def measure_exception_creation(iterations: int = 10000) -> Tuple[float, float]:
    """测量异常创建性能"""
    from pktmask.adapters.adapter_exceptions import AdapterError, MissingConfigError
    
    times = []
    
    for _ in range(10):  # 10轮测试
        start = time.perf_counter()
        for i in range(iterations // 10):
            error = AdapterError(f"Test error {i}")
            config_error = MissingConfigError("key", "adapter")
        end = time.perf_counter()
        
        times.append(end - start)
    
    return statistics.mean(times), statistics.stdev(times)


def measure_adapter_access() -> dict:
    """测量适配器访问性能"""
    results = {}
    
    # 测试直接导入（新位置）
    mean_new, std_new = measure_import_time("pktmask.adapters")
    results["新位置导入"] = {"mean": mean_new, "std": std_new}
    
    # 测试代理导入（旧位置）
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        mean_old, std_old = measure_import_time("pktmask.core.adapters.processor_adapter")
        results["代理文件导入"] = {"mean": mean_old, "std": std_old}
    
    # 计算开销
    if mean_new > 0 and mean_old > 0:
        overhead = ((mean_old - mean_new) / mean_new) * 100
        results["代理开销"] = {"percent": overhead}
    
    return results


def format_time(seconds: float) -> str:
    """格式化时间显示"""
    if seconds < 0:
        return "N/A"
    elif seconds < 0.001:
        return f"{seconds * 1000000:.2f} μs"
    elif seconds < 1:
        return f"{seconds * 1000:.2f} ms"
    else:
        return f"{seconds:.2f} s"


def main():
    """主函数"""
    print("适配器性能基准测试")
    print("=" * 60)
    
    # 运行性能测试
    print("\n1. 测量导入性能...")
    import_results = measure_adapter_access()
    
    print("\n2. 测量异常创建性能...")
    exc_mean, exc_std = measure_exception_creation()
    
    # 显示结果
    print("\n\n=== 性能测试结果 ===")
    print("=" * 60)
    
    print("\n导入性能:")
    for test_name, result in import_results.items():
        if "mean" in result:
            mean_time = format_time(result["mean"])
            std_time = format_time(result["std"])
            print(f"  {test_name}: {mean_time} (±{std_time})")
        elif "percent" in result:
            print(f"  {test_name}: {result['percent']:.1f}%")
    
    print(f"\n异常创建性能:")
    print(f"  平均时间: {format_time(exc_mean)} (±{format_time(exc_std)})")
    print(f"  每秒操作数: {10000/exc_mean:.0f} ops/s")
    
    # 性能评估
    print("\n\n=== 性能评估 ===")
    print("=" * 60)
    
    if "代理开销" in import_results:
        overhead = import_results["代理开销"]["percent"]
        if overhead < 10:
            print("✅ 代理文件开销很小（<10%），对性能影响可忽略")
        elif overhead < 50:
            print("⚠️  代理文件有一定开销（10-50%），但在可接受范围内")
        else:
            print("❌ 代理文件开销较大（>50%），建议尽快迁移到新导入路径")
    
    if exc_mean < 0.01:  # 小于10ms
        print("✅ 异常创建性能良好")
    else:
        print("⚠️  异常创建性能需要优化")
    
    print("\n建议:")
    print("- 尽快将所有代码迁移到新的导入路径，避免代理文件开销")
    print("- 在下个主版本发布时移除代理文件")
    print("- 定期运行性能测试，确保重构不影响性能")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
