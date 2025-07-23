#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
错误处理注册表
管理错误处理器的注册和配置
"""

from typing import Dict, Any, Optional, List, Type, Callable
from dataclasses import dataclass
from ...common.exceptions import PktMaskError
from ...infrastructure.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ErrorHandlerConfig:
    """错误处理器配置"""

    handler_id: str
    handler_class: Type
    priority: int = 50  # 优先级，数字越小优先级越高
    enabled: bool = True
    config: Dict[str, Any] = None

    def __post_init__(self):
        if self.config is None:
            self.config = {}


class ErrorHandlerRegistry:
    """错误处理器注册表"""

    def __init__(self):
        self.handlers: Dict[str, ErrorHandlerConfig] = {}
        self.initialized_handlers: Dict[str, Any] = {}

        logger.debug("Error handler registry initialized")

    def register_handler(
        self,
        handler_id: str,
        handler_class: Type,
        priority: int = 50,
        enabled: bool = True,
        config: Optional[Dict[str, Any]] = None,
    ) -> None:
        """注册错误处理器"""

        handler_config = ErrorHandlerConfig(
            handler_id=handler_id,
            handler_class=handler_class,
            priority=priority,
            enabled=enabled,
            config=config or {},
        )

        self.handlers[handler_id] = handler_config

        logger.debug(f"Registered error handler: {handler_id} (priority: {priority})")

    def unregister_handler(self, handler_id: str) -> bool:
        """取消注册错误处理器"""
        if handler_id in self.handlers:
            del self.handlers[handler_id]

            # 清理已初始化的实例
            if handler_id in self.initialized_handlers:
                del self.initialized_handlers[handler_id]

            logger.debug(f"Unregistered error handler: {handler_id}")
            return True

        return False

    def get_handler(self, handler_id: str) -> Optional[Any]:
        """获取错误处理器实例"""
        if handler_id not in self.handlers:
            return None

        config = self.handlers[handler_id]

        if not config.enabled:
            return None

        # 懒加载实例
        if handler_id not in self.initialized_handlers:
            try:
                instance = config.handler_class(**config.config)
                self.initialized_handlers[handler_id] = instance
                logger.debug(f"Initialized error handler: {handler_id}")
            except Exception as e:
                logger.error(f"Failed to initialize error handler {handler_id}: {e}")
                return None

        return self.initialized_handlers[handler_id]

    def get_all_handlers(self, enabled_only: bool = True) -> List[Any]:
        """获取所有错误处理器实例"""
        handlers = []

        # 按优先级排序
        sorted_configs = sorted(self.handlers.values(), key=lambda x: x.priority)

        for config in sorted_configs:
            if enabled_only and not config.enabled:
                continue

            handler = self.get_handler(config.handler_id)
            if handler:
                handlers.append(handler)

        return handlers

    def enable_handler(self, handler_id: str) -> bool:
        """启用错误处理器"""
        if handler_id in self.handlers:
            self.handlers[handler_id].enabled = True
            logger.debug(f"Enabled error handler: {handler_id}")
            return True
        return False

    def disable_handler(self, handler_id: str) -> bool:
        """禁用错误处理器"""
        if handler_id in self.handlers:
            self.handlers[handler_id].enabled = False

            # 清理已初始化的实例
            if handler_id in self.initialized_handlers:
                del self.initialized_handlers[handler_id]

            logger.debug(f"Disabled error handler: {handler_id}")
            return True
        return False

    def update_handler_config(self, handler_id: str, config: Dict[str, Any]) -> bool:
        """更新错误处理器配置"""
        if handler_id in self.handlers:
            self.handlers[handler_id].config.update(config)

            # 如果已经初始化，需要重新初始化
            if handler_id in self.initialized_handlers:
                del self.initialized_handlers[handler_id]

            logger.debug(f"Updated config for error handler: {handler_id}")
            return True
        return False

    def set_handler_priority(self, handler_id: str, priority: int) -> bool:
        """设置错误处理器优先级"""
        if handler_id in self.handlers:
            self.handlers[handler_id].priority = priority
            logger.debug(f"Set priority for error handler {handler_id}: {priority}")
            return True
        return False

    def get_handler_info(self, handler_id: str) -> Optional[Dict[str, Any]]:
        """获取错误处理器信息"""
        if handler_id not in self.handlers:
            return None

        config = self.handlers[handler_id]
        is_initialized = handler_id in self.initialized_handlers

        return {
            "handler_id": handler_id,
            "handler_class": config.handler_class.__name__,
            "priority": config.priority,
            "enabled": config.enabled,
            "initialized": is_initialized,
            "config": config.config.copy(),
        }

    def list_handlers(self) -> List[Dict[str, Any]]:
        """列出所有注册的错误处理器"""
        return [
            self.get_handler_info(handler_id) for handler_id in self.handlers.keys()
        ]

    def clear_all(self) -> None:
        """清除所有注册的处理器"""
        self.handlers.clear()
        self.initialized_handlers.clear()
        logger.debug("Cleared all error handlers")

    def reload_handler(self, handler_id: str) -> bool:
        """重新加载错误处理器"""
        if handler_id not in self.handlers:
            return False

        # 清理旧实例
        if handler_id in self.initialized_handlers:
            del self.initialized_handlers[handler_id]

        # 重新获取实例（触发初始化）
        handler = self.get_handler(handler_id)
        return handler is not None

    def get_registry_stats(self) -> Dict[str, Any]:
        """获取注册表统计信息"""
        total_handlers = len(self.handlers)
        enabled_handlers = sum(1 for config in self.handlers.values() if config.enabled)
        initialized_handlers = len(self.initialized_handlers)

        priority_distribution = {}
        for config in self.handlers.values():
            priority_range = (
                f"{config.priority // 10 * 10}-{config.priority // 10 * 10 + 9}"
            )
            priority_distribution[priority_range] = (
                priority_distribution.get(priority_range, 0) + 1
            )

        return {
            "total_handlers": total_handlers,
            "enabled_handlers": enabled_handlers,
            "disabled_handlers": total_handlers - enabled_handlers,
            "initialized_handlers": initialized_handlers,
            "priority_distribution": priority_distribution,
        }


# 全局注册表实例
_error_handler_registry = ErrorHandlerRegistry()


def get_error_handler_registry() -> ErrorHandlerRegistry:
    """获取全局错误处理器注册表"""
    return _error_handler_registry


# 便利函数
def register_error_handler(
    handler_id: str,
    handler_class: Type,
    priority: int = 50,
    enabled: bool = True,
    config: Optional[Dict[str, Any]] = None,
) -> None:
    """注册错误处理器"""
    _error_handler_registry.register_handler(
        handler_id, handler_class, priority, enabled, config
    )


def get_error_handler_by_id(handler_id: str) -> Optional[Any]:
    """根据ID获取错误处理器"""
    return _error_handler_registry.get_handler(handler_id)


def enable_error_handler(handler_id: str) -> bool:
    """启用错误处理器"""
    return _error_handler_registry.enable_handler(handler_id)


def disable_error_handler(handler_id: str) -> bool:
    """禁用错误处理器"""
    return _error_handler_registry.disable_handler(handler_id)
