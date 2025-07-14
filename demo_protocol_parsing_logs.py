#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
演示协议栈解析日志控制功能的使用方法
"""

import sys
import os
from pathlib import Path

# 添加 src 目录到 Python 路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from pktmask.config import get_app_config, save_app_config


def show_current_config():
    """显示当前配置"""
    print("=== 当前日志配置 ===")
    config = get_app_config()
    print(f"日志级别: {config.logging.log_level}")
    print(f"协议栈解析日志: {'启用' if config.logging.enable_protocol_parsing_logs else '禁用'}")
    print(f"配置文件位置: {config.get_default_config_path()}")
    print()


def enable_protocol_parsing_logs():
    """启用协议栈解析日志"""
    print("=== 启用协议栈解析日志 ===")
    config = get_app_config()
    config.logging.enable_protocol_parsing_logs = True
    config.logging.log_level = "INFO"  # 确保日志级别足够低以显示INFO消息
    
    if save_app_config(config):
        print("✓ 协议栈解析日志已启用")
        print("现在启动PktMask GUI时，您将看到详细的协议栈解析日志")
    else:
        print("❌ 配置保存失败")
    print()


def disable_protocol_parsing_logs():
    """禁用协议栈解析日志"""
    print("=== 禁用协议栈解析日志 ===")
    config = get_app_config()
    config.logging.enable_protocol_parsing_logs = False
    
    if save_app_config(config):
        print("✓ 协议栈解析日志已禁用")
        print("现在启动PktMask GUI时，将不会看到重复的协议栈解析日志")
    else:
        print("❌ 配置保存失败")
    print()


def show_config_file_example():
    """显示配置文件示例"""
    print("=== 配置文件示例 ===")
    print("您也可以直接编辑配置文件来控制协议栈解析日志：")
    print()
    config_path = get_app_config().get_default_config_path()
    print(f"配置文件位置: {config_path}")
    print()
    print("启用协议栈解析日志的配置：")
    print("```yaml")
    print("logging:")
    print("  log_level: \"INFO\"")
    print("  enable_protocol_parsing_logs: true")
    print("```")
    print()
    print("禁用协议栈解析日志的配置：")
    print("```yaml")
    print("logging:")
    print("  log_level: \"INFO\"")
    print("  enable_protocol_parsing_logs: false")
    print("```")
    print()


def show_usage_instructions():
    """显示使用说明"""
    print("=== 使用说明 ===")
    print("协议栈解析日志控制功能可以帮助您：")
    print()
    print("1. 减少控制台输出的噪音")
    print("   - 默认情况下，协议栈解析日志是关闭的")
    print("   - 这避免了在处理大量数据包时产生过多的日志输出")
    print()
    print("2. 调试协议栈解析问题")
    print("   - 当需要调试协议栈解析相关问题时，可以启用详细日志")
    print("   - 启用后会显示每个数据包的解析结果，如：")
    print("     '协议栈解析完成: 4层, 1个IP层'")
    print()
    print("3. 灵活的日志级别控制")
    print("   - 协议栈解析日志使用INFO级别")
    print("   - 您可以通过调整log_level来进一步控制日志输出")
    print("   - DEBUG: 显示所有调试信息")
    print("   - INFO: 显示一般信息（包括协议栈解析日志）")
    print("   - WARNING: 只显示警告和错误")
    print("   - ERROR: 只显示错误")
    print()
    print("4. 配置变更立即生效")
    print("   - 修改配置后重新启动PktMask即可生效")
    print("   - 无需重新安装或重新编译")
    print()


def interactive_demo():
    """交互式演示"""
    print("=== 交互式演示 ===")
    print("请选择要执行的操作：")
    print("1. 查看当前配置")
    print("2. 启用协议栈解析日志")
    print("3. 禁用协议栈解析日志")
    print("4. 显示配置文件示例")
    print("5. 显示使用说明")
    print("6. 退出")
    print()
    
    while True:
        try:
            choice = input("请输入选项 (1-6): ").strip()
            print()
            
            if choice == '1':
                show_current_config()
            elif choice == '2':
                enable_protocol_parsing_logs()
            elif choice == '3':
                disable_protocol_parsing_logs()
            elif choice == '4':
                show_config_file_example()
            elif choice == '5':
                show_usage_instructions()
            elif choice == '6':
                print("感谢使用PktMask协议栈解析日志控制功能！")
                break
            else:
                print("无效选项，请输入1-6之间的数字")
                print()
                
        except KeyboardInterrupt:
            print("\n\n感谢使用PktMask协议栈解析日志控制功能！")
            break
        except Exception as e:
            print(f"发生错误: {e}")
            print()


def main():
    """主函数"""
    print("PktMask 协议栈解析日志控制功能演示")
    print("="*50)
    print()
    
    try:
        # 显示当前配置
        show_current_config()
        
        # 显示使用说明
        show_usage_instructions()
        
        # 交互式演示
        interactive_demo()
        
    except Exception as e:
        print(f"演示过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
