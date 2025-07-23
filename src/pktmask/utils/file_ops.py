#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
文件操作工具模块
提供统一的文件和目录操作功能
"""

import os
import shutil
from pathlib import Path
from typing import List, Optional, Tuple, Union
from ..common.constants import (
    ValidationConstants,
    FileConstants,
    SystemConstants,
    ProcessingConstants,
)
from ..common.exceptions import FileError, ValidationError
from ..infrastructure.logging import get_logger


logger = get_logger("file_ops")


def ensure_directory(path: Union[str, Path], create_if_missing: bool = True) -> bool:
    """
    确保目录存在

    Args:
        path: 目录路径
        create_if_missing: 如果目录不存在是否创建

    Returns:
        目录是否存在

    Raises:
        FileError: 创建目录失败时
    """
    path = Path(path)

    if path.exists():
        if not path.is_dir():
            raise FileError(
                f"Path exists but is not a directory: {path}", file_path=str(path)
            )
        return True

    if create_if_missing:
        try:
            path.mkdir(parents=True, exist_ok=True)
            logger.debug(f"Created directory: {path}")
            return True
        except Exception as e:
            raise FileError(
                f"Failed to create directory: {path}", file_path=str(path)
            ) from e

    return False


def safe_join(*paths) -> str:
    """
    安全地拼接路径，处理各种边界情况

    Args:
        *paths: 要拼接的路径组件

    Returns:
        拼接后的路径字符串
    """
    return str(Path(*[str(p) for p in paths if p]))


def get_file_extension(filepath: Union[str, Path]) -> str:
    """
    获取文件扩展名（小写）

    Args:
        filepath: 文件路径

    Returns:
        小写的文件扩展名（包含点号）
    """
    return Path(filepath).suffix.lower()


def get_file_base_name(filepath: Union[str, Path]) -> str:
    """
    获取文件基础名称（不含扩展名）

    Args:
        filepath: 文件路径

    Returns:
        文件基础名称
    """
    return Path(filepath).stem


def get_file_size(filepath: Union[str, Path]) -> int:
    """
    获取文件大小

    Args:
        filepath: 文件路径

    Returns:
        文件大小（字节）

    Raises:
        FileError: 文件不存在或无法访问时
    """
    try:
        return Path(filepath).stat().st_size
    except Exception as e:
        raise FileError(
            f"Cannot get file size: {filepath}", file_path=str(filepath)
        ) from e


def validate_file_size(filepath: Union[str, Path]) -> bool:
    """
    验证文件大小是否在允许范围内

    Args:
        filepath: 文件路径

    Returns:
        文件大小是否有效

    Raises:
        ValidationError: 文件大小超出限制时
    """
    file_size = get_file_size(filepath)

    if file_size > ValidationConstants.MAX_FILE_SIZE:
        raise ValidationError(
            f"File too large: {file_size} bytes > {ValidationConstants.MAX_FILE_SIZE} bytes"
        )

    if file_size < ValidationConstants.MIN_FILE_SIZE:
        raise ValidationError(
            f"File too small: {file_size} bytes < {ValidationConstants.MIN_FILE_SIZE} bytes"
        )

    return True


def is_supported_file(filepath: Union[str, Path]) -> bool:
    """
    检查文件是否为支持的格式

    Args:
        filepath: 文件路径

    Returns:
        是否为支持的文件格式
    """
    ext = get_file_extension(filepath)
    return ext in ProcessingConstants.SUPPORTED_EXTENSIONS


def find_files_by_extension(
    directory: Union[str, Path], extensions: List[str], recursive: bool = False
) -> List[str]:
    """
    Find files with specified extensions in a directory

    Args:
        directory: Search directory
        extensions: List of extensions
        recursive: Whether to recursively search subdirectories

    Returns:
        List of found file paths
    """
    directory = Path(directory)
    found_files = []

    extensions = [
        ext.lower() if ext.startswith(".") else f".{ext.lower()}" for ext in extensions
    ]

    if recursive:
        for ext in extensions:
            found_files.extend([str(p) for p in directory.rglob(f"*{ext}")])
    else:
        for file_path in directory.iterdir():
            if file_path.is_file() and file_path.suffix.lower() in extensions:
                found_files.append(str(file_path))

    return sorted(found_files)


def find_pcap_files(directory: Union[str, Path]) -> List[str]:
    """
    在目录中查找PCAP文件

    Args:
        directory: 搜索目录

    Returns:
        找到的PCAP文件路径列表
    """
    return find_files_by_extension(directory, ProcessingConstants.SUPPORTED_EXTENSIONS)


def copy_file_safely(
    src: Union[str, Path], dst: Union[str, Path], overwrite: bool = False
) -> bool:
    """
    Safely copy a file

    Args:
        src: Source file path
        dst: Destination file path
        overwrite: Whether to overwrite existing file

    Returns:
        Whether copy was successful

    Raises:
        FileError: When copy fails
    """
    src_path = Path(src)
    dst_path = Path(dst)

    if not src_path.exists():
        raise FileError(f"Source file does not exist: {src}", file_path=str(src))

    if dst_path.exists() and not overwrite:
        raise FileError(
            f"Destination file exists and overwrite is disabled: {dst}",
            file_path=str(dst),
        )

    try:
        # Ensure destination directory exists
        ensure_directory(dst_path.parent)

        # Copy file
        shutil.copy2(src_path, dst_path)
        logger.debug(f"Copied file: {src} -> {dst}")
        return True

    except Exception as e:
        raise FileError(
            f"Failed to copy file: {src} -> {dst}", file_path=str(src)
        ) from e


def delete_file_safely(filepath: Union[str, Path]) -> bool:
    """
    Safely delete a file

    Args:
        filepath: File path to delete

    Returns:
        Whether deletion was successful
    """
    path = Path(filepath)

    if not path.exists():
        logger.debug(f"File does not exist, nothing to delete: {filepath}")
        return True

    try:
        path.unlink()
        logger.debug(f"Deleted file: {filepath}")
        return True
    except Exception as e:
        logger.warning(f"Failed to delete file: {filepath}, error: {e}")
        return False


def open_directory_in_system(directory: Union[str, Path]) -> bool:
    """
    Open directory in system file manager

    Args:
        directory: Directory path to open

    Returns:
        Whether successfully opened
    """
    # Use the new hidden subprocess utility to prevent cmd window popup on Windows
    from .subprocess_utils import open_directory_hidden

    return open_directory_hidden(directory)


def generate_output_filename(
    input_filename: str, suffix: str, directory: Optional[Union[str, Path]] = None
) -> str:
    """
    Generate output filename based on input filename

    Args:
        input_filename: Input filename
        suffix: Suffix to add
        directory: Output directory, if None use input file's directory

    Returns:
        Generated output file path
    """
    input_path = Path(input_filename)
    base_name = input_path.stem
    extension = input_path.suffix

    output_filename = f"{base_name}{suffix}{extension}"

    if directory:
        return safe_join(directory, output_filename)
    else:
        return safe_join(input_path.parent, output_filename)


def get_directory_size(directory: Union[str, Path]) -> int:
    """
    Calculate total size of directory

    Args:
        directory: Directory path

    Returns:
        Total directory size (bytes)
    """
    total_size = 0
    directory = Path(directory)

    try:
        for file_path in directory.rglob("*"):
            if file_path.is_file():
                total_size += file_path.stat().st_size
    except Exception as e:
        logger.warning(f"Error calculating directory size: {directory}, error: {e}")

    return total_size


def cleanup_temp_files(directory: Union[str, Path], pattern: str = "*.tmp") -> int:
    """
    Clean up temporary files in directory

    Args:
        directory: Directory to clean
        pattern: File pattern, default is "*.tmp"

    Returns:
        Number of files cleaned
    """
    directory = Path(directory)
    cleaned_count = 0

    try:
        for temp_file in directory.glob(pattern):
            if temp_file.is_file():
                try:
                    temp_file.unlink()
                    cleaned_count += 1
                    logger.debug(f"Cleaned temp file: {temp_file}")
                except Exception as e:
                    logger.warning(
                        f"Failed to clean temp file: {temp_file}, error: {e}"
                    )
    except Exception as e:
        logger.warning(f"Error during temp file cleanup: {directory}, error: {e}")

    if cleaned_count > 0:
        logger.info(f"Cleaned {cleaned_count} temporary files from {directory}")

    return cleaned_count
