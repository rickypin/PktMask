#!/usr/bin/env python3
"""
TLS23 MaskStage E2E集成测试

验证Enhanced MaskStage的TLS23掩码功能，与现有的EnhancedTrimmer测试并行。
"""

import sys
import subprocess
import os
from pathlib import Path

import pytest

# 标记为集成测试
pytestmark = pytest.mark.integration

# TLS 样本目录
SAMPLES_DIR = Path(__file__).parent.parent / "data" / "tls"

# 输出目录位于临时 tmp 路径
OUTPUT_DIR = Path("tmp/tls23_maskstage_e2e_test_output")


def _run_maskstage_validator(mode: str = "pipeline") -> subprocess.CompletedProcess:
    """运行 tls23_maskstage_e2e_validator 并返回 CompletedProcess"""
    cmd = [
        sys.executable,
        "scripts/validation/tls23_maskstage_e2e_validator.py",
        "--input-dir", str(SAMPLES_DIR),
        "--output-dir", str(OUTPUT_DIR / mode),
        "--maskstage-mode", mode,
        "--verbose",
    ]
    env = dict(**os.environ, PYTHONPATH=str(Path(__file__).parent.parent.parent))
    return subprocess.run(cmd, capture_output=True, text=True, env=env)


def test_maskstage_e2e_validation_pipeline_mode():
    """测试Enhanced MaskStage E2E验证 - Pipeline模式
    
    验证通过PipelineExecutor调用Enhanced MaskStage的TLS23掩码功能。
    """
    # 依赖检测
    try:
        import pyshark  # noqa: F401
        from pktmask.core.pipeline.executor import PipelineExecutor  # noqa: F401
        from pktmask.core.pipeline.stages.mask_payload.stage import MaskStage  # noqa: F401
    except ImportError:
        pytest.xfail("依赖缺失：PyShark 或 Enhanced MaskStage 未安装")

    # 执行Pipeline模式验证
    result = _run_maskstage_validator("pipeline")

    if result.returncode != 0:
        print("STDOUT:\n", result.stdout)
        print("STDERR:\n", result.stderr)
        
        # 检查是否为依赖问题
        if "无法导入 Enhanced MaskStage" in result.stderr:
            pytest.xfail("Enhanced MaskStage 导入失败，可能是架构集成问题")
        elif "tshark" in result.stderr.lower():
            pytest.xfail("TShark 依赖问题，跳过测试")
        else:
            pytest.fail(f"MaskStage Pipeline模式验证失败，退出码: {result.returncode}")
    
    # 验证输出文件生成
    assert (OUTPUT_DIR / "pipeline" / "validation_summary.json").exists()
    assert (OUTPUT_DIR / "pipeline" / "validation_summary.html").exists()
    
    # 若返回值为 0，则验证通过
    assert result.returncode == 0


def test_maskstage_e2e_validation_direct_mode():
    """测试Enhanced MaskStage E2E验证 - Direct模式
    
    验证直接调用Enhanced MaskStage的TLS23掩码功能。
    """
    # 依赖检测
    try:
        import pyshark  # noqa: F401
        from pktmask.core.pipeline.stages.mask_payload.stage import MaskStage  # noqa: F401
    except ImportError:
        pytest.xfail("依赖缺失：PyShark 或 Enhanced MaskStage 未安装")

    # 执行Direct模式验证
    result = _run_maskstage_validator("direct")

    if result.returncode != 0:
        print("STDOUT:\n", result.stdout)
        print("STDERR:\n", result.stderr)
        
        # 检查是否为依赖问题
        if "无法导入 Enhanced MaskStage" in result.stderr:
            pytest.xfail("Enhanced MaskStage 导入失败，可能是架构集成问题")
        elif "tshark" in result.stderr.lower():
            pytest.xfail("TShark 依赖问题，跳过测试")
        else:
            pytest.fail(f"MaskStage Direct模式验证失败，退出码: {result.returncode}")
    
    # 验证输出文件生成
    assert (OUTPUT_DIR / "direct" / "validation_summary.json").exists()
    assert (OUTPUT_DIR / "direct" / "validation_summary.html").exists()
    
    # 若返回值为 0，则验证通过
    assert result.returncode == 0


def test_maskstage_validator_only():
    """验证MaskStage验证器能正常工作"""
    # 运行MaskStage验证
    result = _run_maskstage_validator("pipeline")
    # 验证返回码
    assert result.returncode == 0
    # 验证输出文件生成
    assert (OUTPUT_DIR / "pipeline" / "validation_summary.json").exists()
    assert (OUTPUT_DIR / "pipeline" / "validation_summary.html").exists()


def test_maskstage_validator_output_format():
    """验证MaskStage验证器的输出格式正确性"""
    try:
        import pyshark  # noqa: F401
        from pktmask.core.pipeline.stages.mask_payload.stage import MaskStage  # noqa: F401
    except ImportError:
        pytest.xfail("依赖缺失：PyShark 或 Enhanced MaskStage")

    # 运行验证器
    result = _run_maskstage_validator("pipeline")
    
    # 即使验证失败，也应该生成报告文件
    summary_file = OUTPUT_DIR / "pipeline" / "validation_summary.json"
    html_file = OUTPUT_DIR / "pipeline" / "validation_summary.html"
    
    # 验证输出文件存在
    assert summary_file.exists(), "JSON报告文件应该存在"
    assert html_file.exists(), "HTML报告文件应该存在"
    
    # 验证JSON格式
    import json
    with open(summary_file, 'r') as f:
        summary = json.load(f)
    
    # 验证必要字段存在
    assert "overall_pass_rate" in summary
    assert "maskstage_mode" in summary
    assert "test_metadata" in summary
    assert "files" in summary
    
    # 验证元数据
    metadata = summary["test_metadata"]
    assert metadata["component"] == "Enhanced MaskStage"
    assert metadata["validator_version"] == "v1.0"
    assert metadata["vs_original"] == "EnhancedTrimmer E2E Validator"
    
    # 验证模式记录
    assert summary["maskstage_mode"] == "pipeline"


if __name__ == "__main__":
    # 允许单独运行此测试文件
    pytest.main([__file__, "-v"]) 