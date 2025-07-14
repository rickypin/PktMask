#!/usr/bin/env python3
"""
PktMask GUI调试插桩脚本

本脚本用于在主程序代码的关键环节添加临时调试日志，
以便追踪GUI处理链条中的数据流和状态变化。

调试完成后，可以使用restore功能恢复原始代码。

使用方法：
    # 添加调试插桩
    python scripts/debug/gui_debug_instrumentation.py instrument
    
    # 恢复原始代码
    python scripts/debug/gui_debug_instrumentation.py restore
"""

import sys
import shutil
from pathlib import Path
from typing import List, Dict, Tuple

class GUIDebugInstrumentator:
    """GUI调试插桩器"""
    
    def __init__(self):
        self.project_root = Path(__file__).parent.parent.parent
        self.backup_dir = self.project_root / "scripts" / "debug" / "backups"
        self.backup_dir.mkdir(exist_ok=True)
        
        # 需要插桩的文件和位置
        self.instrumentation_targets = [
            {
                "file": "src/pktmask/core/pipeline/stages/mask_payload_v2/stage.py",
                "insertions": [
                    {
                        "after_line": "        # 阶段1: 调用Marker模块生成KeepRuleSet",
                        "code": """        # 🔍 DEBUG: Marker模块调用前状态
        self.logger.debug(f"🎯 [DEBUG] Marker调用前 - 输入文件: {input_path}")
        self.logger.debug(f"🎯 [DEBUG] Marker配置: {self.marker_config}")"""
                    },
                    {
                        "after_line": "        keep_rules = self.marker.analyze_file(str(input_path), self.config)",
                        "code": """        # 🔍 DEBUG: Marker模块调用后状态
        self.logger.debug(f"🎯 [DEBUG] Marker生成规则数量: {len(keep_rules.rules)}")
        for i, rule in enumerate(keep_rules.rules[:5]):  # 显示前5个规则
            self.logger.debug(f"🎯 [DEBUG] 规则{i}: {rule.stream_id} [{rule.seq_start}:{rule.seq_end}] 类型={getattr(rule, 'rule_type', 'unknown')}")"""
                    },
                    {
                        "after_line": "        # 阶段2: 调用Masker模块应用规则",
                        "code": """        # 🔍 DEBUG: Masker模块调用前状态
        self.logger.debug(f"⚙️ [DEBUG] Masker调用前 - 输出文件: {output_path}")
        self.logger.debug(f"⚙️ [DEBUG] Masker配置: {self.masker_config}")"""
                    },
                    {
                        "after_line": "        masking_stats = self.masker.apply_masking(str(input_path), str(output_path), keep_rules)",
                        "code": """        # 🔍 DEBUG: Masker模块调用后状态
        self.logger.debug(f"⚙️ [DEBUG] Masker处理结果: 成功={masking_stats.success}")
        self.logger.debug(f"⚙️ [DEBUG] Masker统计: 处理包={masking_stats.packets_processed}, 修改包={masking_stats.packets_modified}")"""
                    }
                ]
            },
            {
                "file": "src/pktmask/core/pipeline/stages/mask_payload_v2/marker/tls_marker.py",
                "insertions": [
                    {
                        "after_line": "    def analyze_file(self, pcap_file: str, config: Dict[str, Any]) -> KeepRuleSet:",
                        "code": """        # 🔍 DEBUG: TLS Marker分析开始
        self.logger.debug(f"🎯 [DEBUG] TLS Marker开始分析文件: {pcap_file}")
        self.logger.debug(f"🎯 [DEBUG] TLS Marker配置: {config}")"""
                    }
                ]
            },
            {
                "file": "src/pktmask/core/pipeline/stages/mask_payload_v2/masker/payload_masker.py",
                "insertions": [
                    {
                        "after_line": "    def apply_masking(self, input_path: str, output_path: str,",
                        "code": """        # 🔍 DEBUG: Payload Masker开始处理
        self.logger.debug(f"⚙️ [DEBUG] Payload Masker开始: {input_path} -> {output_path}")
        self.logger.debug(f"⚙️ [DEBUG] 接收到保留规则数量: {len(keep_rules.rules)}")"""
                    }
                ]
            }
        ]
    
    def instrument_code(self):
        """添加调试插桩"""
        print("🔧 开始添加调试插桩...")
        
        for target in self.instrumentation_targets:
            file_path = self.project_root / target["file"]
            
            if not file_path.exists():
                print(f"⚠️ 文件不存在，跳过: {file_path}")
                continue
            
            # 备份原始文件
            backup_path = self.backup_dir / f"{file_path.name}.backup"
            shutil.copy2(file_path, backup_path)
            print(f"📄 已备份: {file_path.name} -> {backup_path}")
            
            # 读取文件内容
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            # 应用插桩
            modified_lines = self._apply_insertions(lines, target["insertions"])
            
            # 写回文件
            with open(file_path, 'w', encoding='utf-8') as f:
                f.writelines(modified_lines)
            
            print(f"✅ 已插桩: {file_path}")
        
        print("🎯 调试插桩完成！")
        print("💡 运行GUI测试后，使用 'restore' 命令恢复原始代码")
    
    def restore_code(self):
        """恢复原始代码"""
        print("🔄 开始恢复原始代码...")
        
        for target in self.instrumentation_targets:
            file_path = self.project_root / target["file"]
            backup_path = self.backup_dir / f"{file_path.name}.backup"
            
            if not backup_path.exists():
                print(f"⚠️ 备份文件不存在，跳过: {backup_path}")
                continue
            
            # 恢复文件
            shutil.copy2(backup_path, file_path)
            print(f"✅ 已恢复: {file_path}")
        
        print("🎯 代码恢复完成！")
    
    def _apply_insertions(self, lines: List[str], insertions: List[Dict]) -> List[str]:
        """应用插桩代码"""
        modified_lines = lines.copy()
        
        # 从后往前处理，避免行号偏移问题
        for insertion in reversed(insertions):
            after_line = insertion["after_line"]
            code_to_insert = insertion["code"]
            
            # 查找目标行
            target_line_idx = None
            for i, line in enumerate(modified_lines):
                if after_line.strip() in line.strip():
                    target_line_idx = i
                    break
            
            if target_line_idx is not None:
                # 获取缩进
                indent = self._get_line_indent(modified_lines[target_line_idx])
                
                # 准备插入的代码行
                insert_lines = []
                for code_line in code_to_insert.split('\n'):
                    if code_line.strip():
                        insert_lines.append(indent + code_line + '\n')
                    else:
                        insert_lines.append('\n')
                
                # 插入代码
                modified_lines[target_line_idx+1:target_line_idx+1] = insert_lines
        
        return modified_lines
    
    def _get_line_indent(self, line: str) -> str:
        """获取行的缩进"""
        indent = ""
        for char in line:
            if char in [' ', '\t']:
                indent += char
            else:
                break
        return indent
    
    def clean_backups(self):
        """清理备份文件"""
        print("🧹 清理备份文件...")
        
        if self.backup_dir.exists():
            for backup_file in self.backup_dir.glob("*.backup"):
                backup_file.unlink()
                print(f"🗑️ 已删除: {backup_file}")
        
        print("✅ 备份清理完成！")


def main():
    """主函数"""
    if len(sys.argv) != 2:
        print("使用方法:")
        print("  python scripts/debug/gui_debug_instrumentation.py instrument  # 添加调试插桩")
        print("  python scripts/debug/gui_debug_instrumentation.py restore    # 恢复原始代码")
        print("  python scripts/debug/gui_debug_instrumentation.py clean      # 清理备份文件")
        sys.exit(1)
    
    command = sys.argv[1]
    instrumentator = GUIDebugInstrumentator()
    
    if command == "instrument":
        instrumentator.instrument_code()
    elif command == "restore":
        instrumentator.restore_code()
    elif command == "clean":
        instrumentator.clean_backups()
    else:
        print(f"❌ 未知命令: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
