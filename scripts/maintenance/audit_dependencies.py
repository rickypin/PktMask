#!/usr/bin/env python3
"""
依赖审计脚本 - 分析主项目和子包的依赖差异
"""

import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple

try:
    import toml
except ImportError:
    print("需要安装 toml 包: pip install toml")
    sys.exit(1)


def parse_requirement(req_str: str) -> Tuple[str, str]:
    """解析依赖字符串，返回包名和版本约束"""
    # 处理带有环境标记的依赖，如 'typing-extensions>=4.0.0;python_version<"3.8"'
    req_str = req_str.split(";")[0].strip()

    # 使用正则表达式分离包名和版本
    match = re.match(r"^([a-zA-Z0-9_-]+)(.*)$", req_str)
    if match:
        pkg_name = match.group(1).lower()
        version_spec = match.group(2).strip()
        return pkg_name, version_spec
    return req_str.lower(), ""


def read_pyproject_deps(filepath: Path) -> Dict[str, str]:
    """读取 pyproject.toml 中的依赖"""
    with open(filepath, "r", encoding="utf-8") as f:
        data = toml.load(f)

    deps = {}

    # 主依赖
    for dep in data.get("project", {}).get("dependencies", []):
        pkg_name, version = parse_requirement(dep)
        deps[pkg_name] = version

    return deps


def read_requirements_txt(filepath: Path) -> Dict[str, str]:
    """读取 requirements.txt 中的依赖"""
    deps = {}

    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            # 跳过空行和注释
            if line and not line.startswith("#"):
                pkg_name, version = parse_requirement(line)
                deps[pkg_name] = version

    return deps


def read_setup_py_deps(filepath: Path) -> Dict[str, str]:
    """从 setup.py 中提取依赖（简单解析）"""
    deps = {}

    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    # 查找 install_requires
    install_requires_match = re.search(
        r"install_requires\s*=\s*\[(.*?)\]", content, re.DOTALL
    )

    if install_requires_match:
        requires_content = install_requires_match.group(1)
        # 提取所有引号中的内容
        for match in re.findall(r'[\'"]([^\'",]+)[\'"]', requires_content):
            pkg_name, version = parse_requirement(match)
            deps[pkg_name] = version

    return deps


def compare_versions(v1: str, v2: str) -> bool:
    """比较两个版本约束是否兼容"""
    # 简单比较，实际可能需要更复杂的版本比较逻辑
    return v1 != v2


def main():
    """主函数"""
    project_root = Path.cwd()

    print("=== PktMask 依赖审计报告 ===\n")

    # 1. 读取主项目依赖
    pyproject_path = project_root / "pyproject.toml"
    if not pyproject_path.exists():
        print(f"错误: 找不到 {pyproject_path}")
        return

    main_deps = read_pyproject_deps(pyproject_path)
    print(f"主项目依赖 (pyproject.toml): {len(main_deps)} 个包")

    # 2. 读取子包依赖
    tcp_masker_path = project_root / "src/pktmask/core/tcp_payload_masker"

    # 2.1 requirements.txt
    req_txt_path = tcp_masker_path / "requirements.txt"
    req_txt_deps = {}
    if req_txt_path.exists():
        req_txt_deps = read_requirements_txt(req_txt_path)
        print(f"子包依赖 (requirements.txt): {len(req_txt_deps)} 个包")

    # 2.2 setup.py
    setup_py_path = tcp_masker_path / "setup.py"
    setup_py_deps = {}
    if setup_py_path.exists():
        setup_py_deps = read_setup_py_deps(setup_py_path)
        print(f"子包依赖 (setup.py): {len(setup_py_deps)} 个包")

    # 3. 合并子包依赖
    sub_deps = {**req_txt_deps, **setup_py_deps}

    print("\n=== 依赖对比分析 ===\n")

    # 4. 查找版本冲突
    conflicts = []
    for pkg, sub_version in sub_deps.items():
        if pkg in main_deps:
            main_version = main_deps[pkg]
            if compare_versions(main_version, sub_version):
                conflicts.append(
                    {"package": pkg, "main": main_version, "sub": sub_version}
                )

    if conflicts:
        print("⚠️  发现版本冲突:\n")
        for conflict in conflicts:
            print(f"  📦 {conflict['package']}:")
            print(f"     主项目: {conflict['main']}")
            print(f"     子包:   {conflict['sub']}")
            print()
    else:
        print("✅ 未发现版本冲突\n")

    # 5. 查找子包独有的依赖
    sub_only = []
    for pkg, version in sub_deps.items():
        if pkg not in main_deps:
            sub_only.append((pkg, version))

    if sub_only:
        print("📋 子包独有的依赖:\n")
        for pkg, version in sub_only:
            print(f"  - {pkg}{version}")

    # 6. 建议
    print("\n=== 建议 ===\n")

    if conflicts or sub_only:
        print("1. 更新 pyproject.toml:")
        print("   - 解决版本冲突，使用兼容的版本范围")
        if sub_only:
            print("   - 添加子包独有的依赖到主项目")
        print()

    print("2. 清理子包配置文件:")
    print(f"   - 备份并删除 {req_txt_path.relative_to(project_root)}")
    print(f"   - 备份并删除 {setup_py_path.relative_to(project_root)}")
    print()

    print("3. 更新文档:")
    print("   - 在 CHANGELOG.md 中记录依赖管理变更")
    print("   - 更新开发者文档说明新的依赖管理方式")

    # 7. 生成迁移脚本
    print("\n=== 生成迁移命令 ===\n")
    print("# 备份子包配置文件")
    if req_txt_path.exists():
        print(f"mv {req_txt_path} {req_txt_path}.bak")
    if setup_py_path.exists():
        print(f"mv {setup_py_path} {setup_py_path}.bak")

    print("\n# 更新依赖")
    print("pip install -e .")

    print("\n# 验证导入")
    print("python -c 'from pktmask.core.tcp_payload_masker import TCPPayloadMasker'")


if __name__ == "__main__":
    main()
