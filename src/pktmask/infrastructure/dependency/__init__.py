"""
PktMask 依赖管理模块

本模块提供统一的依赖检查和管理功能，整合分散在各个模块中的依赖验证逻辑。

核心组件：
- DependencyChecker: 统一的依赖检查器
- DependencyResult: 依赖检查结果数据结构
- DependencyStatus: 依赖状态枚举

设计原则：
- 统一接口：提供标准化的依赖检查接口
- 易于扩展：支持添加新的依赖类型
- 复用现有：整合现有的检查逻辑
- 轻量级：避免过度工程化
"""

from .checker import DependencyChecker, DependencyResult, DependencyStatus

__all__ = ["DependencyChecker", "DependencyResult", "DependencyStatus"]
