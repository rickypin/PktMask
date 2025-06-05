import os
from scapy.all import PcapReader, PcapNgReader

def process_file_dedup(file_path, error_log):
    """
    处理单个 pcap/pcapng 文件，去除完全重复的报文。
    参数：
      file_path：待处理的文件路径；
      error_log：用于记录错误信息的列表。
    返回：
      去重后的报文列表，以及原文件中报文的总数与去重后报文的数量。
    """
    packets = []
    total_count = 0
    try:
        ext = os.path.splitext(file_path)[1].lower()
        if ext == ".pcap":
            reader_cls = PcapReader
        elif ext == ".pcapng":
            reader_cls = PcapNgReader
        else:
            raise ValueError("不支持的文件扩展名")
        seen = set()
        with reader_cls(file_path) as reader:
            for pkt in reader:
                total_count += 1
                raw_bytes = bytes(pkt)
                if raw_bytes in seen:
                    continue
                seen.add(raw_bytes)
                packets.append(pkt)
        return packets, total_count, len(packets)
    except Exception as e:
        error_log.append(f"处理文件 {file_path} 出错：{str(e)}")
        return None, total_count, 0

def select_files_for_processing(subdir_path, all_known_suffixes, current_suffix):
    """
    选择要处理的文件：
    1. 如果目录下没有该处理类型的产物文件：
       - 如果目录下仅有原始文件，则处理原始文件
       - 如果目录下已有其它处理类型的产物文件，则仅处理这些产物文件
    2. 如果目录下已有产物文件带有该处理类型的后缀标记，则跳过处理
    """
    all_files = [f for f in os.listdir(subdir_path) if f.endswith('.pcap') or f.endswith('.pcapng')]
    
    # 1. 检查是否存在当前处理类型的产物文件（包括复合标记）
    has_current_product = False
    for f in all_files:
        if current_suffix in f:  # 检查文件名中是否包含当前处理类型的后缀
            has_current_product = True
            break
    
    if has_current_product:
        return [], 'Skipped: files with current processing type already exist.'
    
    # 2. 找出所有其他处理类型的产物文件
    other_product_files = []
    for suffix in all_known_suffixes:
        if suffix != current_suffix:
            other_product_files.extend([f for f in all_files if f.endswith(f'{suffix}.pcap') or f.endswith(f'{suffix}.pcapng')])
    
    # 3. 如果存在其他处理类型的产物文件，则只处理这些文件
    if other_product_files:
        return other_product_files, 'Processing files from other processing steps.'
    
    # 4. 如果只有原始文件，则处理原始文件
    raw_files = [f for f in all_files if not any(f.endswith(f'{s}.pcap') or f.endswith(f'{s}.pcapng') for s in all_known_suffixes if s)]
    return raw_files, 'Processing raw files.' 