import os
from typing import List, Tuple


def select_files(subdir_path: str, current_suffix: str, all_suffixes: List[str]) -> Tuple[List[str], str]:
    """
    根据处理后缀选择要处理的文件。

    Args:
        subdir_path (str): 要扫描的子目录。
        current_suffix (str): 当前处理步骤的后缀。
        all_suffixes (List[str]): 流水线中所有已知的后缀。

    Returns:
        A tuple containing:
        - list[str]: The list of file names to process.
        - str: A message describing the selection logic.
    """
    all_files = [f for f in os.listdir(subdir_path) if f.lower().endswith((".pcap", ".pcapng"))]

    # 1. 检查是否存在当前处理类型的产物文件
    # 文件名示例: capture.pcap -> capture-Deduped.pcap
    has_current_product = any(current_suffix in f for f in all_files)

    if has_current_product:
        return [], f"Skipped: Files with '{current_suffix}' suffix already exist."

    # 2. 找出所有其他处理类型的产物文件
    # 我们应该从最"新"的产物开始处理，可以根据后缀在ALL_KNOWN_SUFFIXES中的顺位来判断
    # 这是一个简化的逻辑，假设后缀按处理顺序排列

    # 寻找已经存在的、非当前步骤的产物文件
    # 优先处理已经被处理过的文件
    files_to_process = []
    processed_files_found = False
    # 按后缀列表反向查找，优先处理更后步骤的产物
    for suffix in reversed(all_suffixes):
        if suffix == current_suffix:
            continue

        # 查找带有该后缀的文件
        intermediate_files = [f for f in all_files if suffix in f]

        if intermediate_files:
            files_to_process = intermediate_files
            processed_files_found = True
            msg = f"Processing files from a previous step ('{suffix}')."
            break

    if processed_files_found:
        return files_to_process, msg

    # 3. 如果没有找到任何中间产物文件，则处理原始文件
    # 原始文件是指不含任何已知后缀的文件
    raw_files = [f for f in all_files if not any(s in f for s in all_suffixes)]
    if raw_files:
        return raw_files, "Processing raw files."

    return [], "No suitable files found for processing."
