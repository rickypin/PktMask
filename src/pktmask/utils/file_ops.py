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
from ..common.constants import ValidationConstants, FileConstants, SystemConstants, ProcessingConstants
from ..common.exceptions import FileError, ValidationError
from ..infrastructure.logging import get_logger


logger = get_logger('file_ops')


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
            raise FileError(f"Path exists but is not a directory: {path}", file_path=str(path))
        return True
    
    if create_if_missing:
        try:
            import os
            import platform

            # Enhanced Windows-specific directory creation logging
            if platform.system() == "Windows":
                logger.debug(f"Windows directory creation attempt: {path}")

                # Check parent directory permissions
                parent_path = path.parent
                if parent_path.exists():
                    parent_writable = os.access(parent_path, os.W_OK)
                    logger.debug(f"Parent directory writable: {parent_writable}")
                    if not parent_writable:
                        logger.warning(f"Parent directory not writable: {parent_path}")

                # Check for path length issues on Windows
                path_str = str(path)
                if len(path_str) > 260:
                    logger.warning(f"Path length ({len(path_str)}) exceeds Windows limit (260): {path_str[:100]}...")

                # Check for invalid characters in Windows paths
                invalid_chars = '<>:"|?*'
                if any(char in path_str for char in invalid_chars):
                    logger.warning(f"Path contains invalid Windows characters: {path_str}")

            path.mkdir(parents=True, exist_ok=True)
            logger.debug(f"Created directory: {path}")

            # Verify directory creation on Windows
            if platform.system() == "Windows" and path.exists():
                logger.debug(f"Windows directory creation verified: {path}")
                # Test write access
                try:
                    test_file = path / ".pktmask_write_test"
                    test_file.touch()
                    test_file.unlink()
                    logger.debug(f"Windows directory write access confirmed: {path}")
                except Exception as write_test_e:
                    logger.warning(f"Windows directory write test failed: {write_test_e}")

            return True

        except PermissionError as e:
            # Enhanced Windows-specific fallback for permission issues
            import os
            if os.name == 'nt':
                logger.warning(f"Windows permission error, attempting fallback: {e}")
                try:
                    # Try alternative Windows directory creation method
                    os.makedirs(str(path), exist_ok=True)
                    logger.debug(f"Created directory (Windows fallback): {path}")

                    # Verify fallback creation
                    if path.exists():
                        logger.debug(f"Windows fallback directory creation verified: {path}")
                    else:
                        logger.error(f"Windows fallback directory creation failed - directory does not exist: {path}")

                    return True
                except Exception as fallback_e:
                    logger.error(f"Windows fallback directory creation failed: {fallback_e}")
                    raise FileError(f"Failed to create directory (Windows): {path}", file_path=str(path)) from fallback_e
            else:
                logger.error(f"Permission denied creating directory: {path}")
                raise FileError(f"Permission denied creating directory: {path}", file_path=str(path)) from e
        except Exception as e:
            logger.error(f"Failed to create directory: {path}, error: {e}")
            raise FileError(f"Failed to create directory: {path}", file_path=str(path)) from e
    
    return False


def safe_join(*paths) -> str:
    """
    安全地拼接路径，处理各种边界情况

    Args:
        *paths: 要拼接的路径组件

    Returns:
        拼接后的路径字符串
    """
    import os
    result = Path(*[str(p) for p in paths if p])
    # Normalize path separators for current platform
    return str(result).replace('/', os.sep) if os.name == 'nt' else str(result)


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
        raise FileError(f"Cannot get file size: {filepath}", file_path=str(filepath)) from e


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
        raise ValidationError(f"File too large: {file_size} bytes > {ValidationConstants.MAX_FILE_SIZE} bytes")
    
    if file_size < ValidationConstants.MIN_FILE_SIZE:
        raise ValidationError(f"File too small: {file_size} bytes < {ValidationConstants.MIN_FILE_SIZE} bytes")
    
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


def find_files_by_extension(directory: Union[str, Path], 
                          extensions: List[str], 
                          recursive: bool = False) -> List[str]:
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
    
    extensions = [ext.lower() if ext.startswith('.') else f'.{ext.lower()}' for ext in extensions]
    
    if recursive:
        for ext in extensions:
            found_files.extend([str(p) for p in directory.rglob(f'*{ext}')])
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


def copy_file_safely(src: Union[str, Path], dst: Union[str, Path],
                     overwrite: bool = False) -> bool:
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
        raise FileError(f"Destination file exists and overwrite is disabled: {dst}", file_path=str(dst))
    
    try:
        import platform
        import os

        # Enhanced Windows-specific file copy logging
        if platform.system() == "Windows":
            logger.debug(f"Windows file copy operation: {src} -> {dst}")

            # Check source file details
            src_size = src_path.stat().st_size
            logger.debug(f"Source file size: {src_size} bytes ({src_size / (1024*1024):.2f} MB)")

            # Check source file permissions
            if not os.access(src_path, os.R_OK):
                logger.error(f"Source file not readable: {src}")
                raise FileError(f"Source file not readable: {src}", file_path=str(src))

            # Check for file locks (Windows-specific)
            try:
                with open(src_path, 'rb') as test_file:
                    test_file.read(1)
                logger.debug(f"Source file access test passed: {src}")
            except Exception as lock_e:
                logger.warning(f"Source file may be locked: {lock_e}")

            # Check destination path encoding
            try:
                dst_str = str(dst_path)
                dst_str.encode('utf-8').decode('utf-8')
                logger.debug(f"Destination path encoding check passed: {dst}")
            except UnicodeError as enc_e:
                logger.error(f"Destination path encoding error: {enc_e}")
                raise FileError(f"Destination path encoding error: {dst}", file_path=str(dst)) from enc_e

        # Ensure destination directory exists
        ensure_directory(dst_path.parent)

        # Enhanced file copy with Windows-specific error handling
        if platform.system() == "Windows":
            try:
                # Use shutil.copy2 for metadata preservation
                shutil.copy2(src_path, dst_path)
                logger.debug(f"Windows file copy completed: {src} -> {dst}")

                # Verify copy on Windows
                if dst_path.exists():
                    dst_size = dst_path.stat().st_size
                    src_size = src_path.stat().st_size
                    if dst_size == src_size:
                        logger.debug(f"Windows file copy verification passed: sizes match ({dst_size} bytes)")
                    else:
                        logger.warning(f"Windows file copy size mismatch: src={src_size}, dst={dst_size}")
                else:
                    logger.error(f"Windows file copy failed: destination file does not exist")
                    raise FileError(f"Copy failed - destination file not created: {dst}", file_path=str(dst))

            except PermissionError as perm_e:
                logger.error(f"Windows file copy permission error: {perm_e}")
                raise FileError(f"Permission denied copying file (Windows): {src} -> {dst}", file_path=str(src)) from perm_e
            except OSError as os_e:
                logger.error(f"Windows file copy OS error: {os_e}")
                raise FileError(f"OS error copying file (Windows): {src} -> {dst}", file_path=str(src)) from os_e
        else:
            # Standard copy for non-Windows platforms
            shutil.copy2(src_path, dst_path)
            logger.debug(f"Copied file: {src} -> {dst}")

        return True

    except FileError:
        # Re-raise FileError as-is
        raise
    except Exception as e:
        logger.error(f"Unexpected error copying file: {src} -> {dst}, error: {e}")
        raise FileError(f"Failed to copy file: {src} -> {dst}", file_path=str(src)) from e


def delete_file_safely(filepath: Union[str, Path]) -> bool:
    """
    Safely delete a file with enhanced Windows-specific logging

    Args:
        filepath: File path to delete

    Returns:
        Whether deletion was successful
    """
    import platform
    import os

    path = Path(filepath)

    if not path.exists():
        logger.debug(f"File does not exist, nothing to delete: {filepath}")
        return True

    # Enhanced Windows-specific file deletion logging
    if platform.system() == "Windows":
        logger.debug(f"Windows file deletion attempt: {filepath}")

        try:
            # Check file properties before deletion
            file_size = path.stat().st_size
            logger.debug(f"File to delete size: {file_size} bytes")

            # Check if file is read-only
            if not os.access(path, os.W_OK):
                logger.warning(f"File is read-only, attempting to change permissions: {filepath}")
                try:
                    # Try to remove read-only attribute on Windows
                    import stat
                    path.chmod(stat.S_IWRITE)
                    logger.debug(f"Successfully changed file permissions: {filepath}")
                except Exception as chmod_e:
                    logger.warning(f"Failed to change file permissions: {chmod_e}")

            # Check for file locks (Windows-specific)
            try:
                with open(path, 'r+b') as test_file:
                    pass  # Just test if we can open for writing
                logger.debug(f"File lock check passed: {filepath}")
            except Exception as lock_e:
                logger.warning(f"File may be locked or in use: {lock_e}")

        except Exception as check_e:
            logger.warning(f"Pre-deletion checks failed: {check_e}")

    try:
        if platform.system() == "Windows":
            # Windows-specific deletion with retry logic
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    path.unlink()
                    logger.debug(f"Windows file deletion successful (attempt {attempt + 1}): {filepath}")

                    # Verify deletion on Windows
                    if path.exists():
                        logger.warning(f"File still exists after deletion attempt: {filepath}")
                        if attempt < max_retries - 1:
                            import time
                            time.sleep(0.1)  # Brief delay before retry
                            continue
                        else:
                            logger.error(f"File deletion verification failed: {filepath}")
                            return False
                    else:
                        logger.debug(f"Windows file deletion verified: {filepath}")
                        return True

                except PermissionError as perm_e:
                    logger.warning(f"Windows file deletion permission error (attempt {attempt + 1}): {perm_e}")
                    if attempt < max_retries - 1:
                        import time
                        time.sleep(0.1)  # Brief delay before retry
                        continue
                    else:
                        logger.error(f"Windows file deletion failed after {max_retries} attempts: {filepath}")
                        return False

                except Exception as del_e:
                    logger.warning(f"Windows file deletion error (attempt {attempt + 1}): {del_e}")
                    if attempt < max_retries - 1:
                        import time
                        time.sleep(0.1)  # Brief delay before retry
                        continue
                    else:
                        logger.error(f"Windows file deletion failed after {max_retries} attempts: {filepath}")
                        return False
        else:
            # Standard deletion for non-Windows platforms
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
    import platform
    import subprocess
    
    directory = Path(directory)
    
    if not directory.exists() or not directory.is_dir():
        logger.warning(f"Directory does not exist: {directory}")
        return False
    
    try:
        system = platform.system()
        
        if system == SystemConstants.MACOS_SYSTEM_NAME:
            subprocess.run([SystemConstants.MACOS_OPEN_COMMAND, str(directory)])
        elif system == SystemConstants.WINDOWS_SYSTEM_NAME:
            subprocess.run([SystemConstants.WINDOWS_OPEN_COMMAND, str(directory)])
        else:  # Linux and others
            subprocess.run([SystemConstants.LINUX_OPEN_COMMAND, str(directory)])
        
        logger.debug(f"Opened directory in system file manager: {directory}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to open directory: {directory}, error: {e}")
        return False


def generate_output_filename(input_filename: str, suffix: str,
                           directory: Optional[Union[str, Path]] = None) -> str:
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
        for file_path in directory.rglob('*'):
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
                    logger.warning(f"Failed to clean temp file: {temp_file}, error: {e}")
    except Exception as e:
        logger.warning(f"Error during temp file cleanup: {directory}, error: {e}")
    
    if cleaned_count > 0:
        logger.info(f"Cleaned {cleaned_count} temporary files from {directory}")
    
    return cleaned_count 