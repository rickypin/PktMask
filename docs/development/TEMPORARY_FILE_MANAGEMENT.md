# Temporary File Management Best Practices

## Overview

This document outlines the best practices for temporary file management in the PktMask project, based on the fixes implemented for issue RES-001.

## Core Principles

### 1. Use Context Managers
Always use `tempfile.TemporaryDirectory()` context manager instead of manual `tempfile.mkdtemp()`:

```python
# ✅ Recommended
with tempfile.TemporaryDirectory(prefix="pktmask_") as temp_dir_str:
    temp_dir = Path(temp_dir_str)
    # ... use temp_dir ...
# Automatic cleanup

# ❌ Avoid
temp_dir = Path(tempfile.mkdtemp(prefix="pktmask_"))
try:
    # ... use temp_dir ...
finally:
    shutil.rmtree(temp_dir, ignore_errors=True)  # Manual cleanup
```

### 2. Exception Safety
Context managers ensure cleanup even when exceptions occur:

```python
with tempfile.TemporaryDirectory(prefix="pktmask_") as temp_dir_str:
    temp_dir = Path(temp_dir_str)
    try:
        # ... processing that might raise exceptions ...
    except Exception as e:
        # ... error handling ...
        # temp_dir is still cleaned up automatically
```

### 3. Consistent Naming
Use consistent prefixes for temporary directories:
- `pktmask_pipeline_` - for pipeline execution
- `pktmask_stage_` - for individual stage processing
- `pktmask_test_` - for test fixtures

## Implementation Examples

### Pipeline Executor Pattern
```python
def run(self, input_path: Path, output_path: Path) -> ProcessResult:
    with tempfile.TemporaryDirectory(prefix="pktmask_pipeline_") as temp_dir_str:
        temp_dir = Path(temp_dir_str)
        
        try:
            # Pipeline execution logic
            for idx, stage in enumerate(self.stages):
                stage_output = output_path if is_last else temp_dir / f"stage_{idx}_{output_path.name}"
                # ... stage processing ...
        except Exception as e:
            # Error handling
            return ProcessResult(success=False, errors=[str(e)])
    # Automatic cleanup
```

### Resource Manager Integration
For complex scenarios, integrate with ResourceManager:

```python
def create_temp_hardlink(self, input_path: Path) -> Path:
    try:
        temp_dir = Path(tempfile.mkdtemp(prefix="pktmask_stage_"))
        temp_file = temp_dir / f"input_{input_path.name}"
        
        os.link(str(input_path), str(temp_file))
        
        # Register for cleanup tracking
        self.resource_manager.register_temp_file(temp_file)
        self.resource_manager.register_cleanup_callback(
            lambda: self._cleanup_temp_directory(temp_dir)
        )
        
        return temp_file
    except OSError as e:
        # Handle cross-device errors gracefully
        return input_path
```

## Testing Patterns

### Test Fixtures
```python
@pytest.fixture
def temp_output_dir():
    """Create temporary output directory for tests"""
    with tempfile.TemporaryDirectory(prefix="pktmask_test_") as temp_dir:
        yield Path(temp_dir)
```

### Verification Tests
```python
def test_temp_cleanup():
    """Verify temporary files are cleaned up"""
    temp_dirs_created = []
    
    def track_temp_dir(*args, **kwargs):
        temp_dir = tempfile.TemporaryDirectory(*args, **kwargs)
        temp_dirs_created.append(temp_dir.name)
        return temp_dir
    
    with patch('tempfile.TemporaryDirectory', side_effect=track_temp_dir):
        # ... execute code that creates temp directories ...
    
    # Verify cleanup
    for temp_dir_path in temp_dirs_created:
        assert not Path(temp_dir_path).exists()
```

## Error Handling

### Cross-Device Link Errors
When creating hardlinks, handle cross-device errors gracefully:

```python
try:
    os.link(str(source), str(target))
except OSError as e:
    logger.warning(f"Cannot create hardlink: {e}. Falling back to direct access.")
    # Clean up partial resources
    if temp_dir.exists():
        temp_dir.rmdir()
    return source  # Fallback to original file
```

### Partial Cleanup Failures
Handle cases where cleanup might partially fail:

```python
def cleanup_temp_directory(self, temp_dir: Path) -> None:
    """Clean up temporary directory safely"""
    if temp_dir and temp_dir.exists() and temp_dir.name.startswith("pktmask_"):
        try:
            temp_dir.rmdir()  # Only removes empty directories
            logger.debug(f"Cleaned up temporary directory: {temp_dir}")
        except OSError as e:
            # Expected if directory is not empty
            logger.debug(f"Could not remove directory {temp_dir}: {e}")
```

## Performance Considerations

### Large File Handling
For large files, consider using hardlinks to avoid copying:

```python
def optimize_large_file_access(self, input_path: Path) -> Path:
    """Create hardlink for large files to avoid I/O overhead"""
    file_size_mb = input_path.stat().st_size / (1024 * 1024)
    
    if file_size_mb > self.LARGE_FILE_THRESHOLD_MB:
        return self._create_temp_hardlink(input_path, file_size_mb)
    return input_path
```

### Memory Management
Integrate with ResourceManager for memory-aware cleanup:

```python
def should_cleanup_early(self) -> bool:
    """Check if early cleanup is needed due to memory pressure"""
    return self.resource_manager.is_memory_pressure()
```

## Migration Guide

### From Manual to Context Manager
1. Replace `tempfile.mkdtemp()` with `tempfile.TemporaryDirectory()`
2. Remove manual cleanup code in `finally` blocks
3. Adjust indentation for context manager scope
4. Update error handling to work within context

### Testing Migration
1. Update test fixtures to use context managers
2. Add verification tests for cleanup behavior
3. Test exception scenarios to ensure cleanup

## Common Pitfalls

### ❌ Forgetting Context Manager Scope
```python
# Wrong - temp_dir used outside context
temp_dir = None
with tempfile.TemporaryDirectory() as temp_dir_str:
    temp_dir = Path(temp_dir_str)
# temp_dir is now invalid!
```

### ❌ Manual Cleanup in Context Manager
```python
# Wrong - unnecessary manual cleanup
with tempfile.TemporaryDirectory() as temp_dir_str:
    temp_dir = Path(temp_dir_str)
    try:
        # ... processing ...
    finally:
        shutil.rmtree(temp_dir)  # Unnecessary!
```

### ❌ Ignoring Cross-Device Errors
```python
# Wrong - not handling cross-device link errors
os.link(source, target)  # May fail on different filesystems
```

## Monitoring and Debugging

### Logging Best Practices
```python
logger.debug(f"Created temporary directory: {temp_dir}")
logger.info(f"Created temporary hardlink for large file ({file_size_mb:.1f}MB): {temp_file}")
logger.warning(f"Cannot create hardlink: {e}. Falling back to direct access.")
```

### Resource Tracking
Use ResourceManager for centralized tracking:
```python
self.resource_manager.register_temp_file(temp_file)
self.resource_manager.register_cleanup_callback(cleanup_func)
```

## Summary

The temporary file management improvements in PktMask focus on:
1. **Automatic cleanup** using context managers
2. **Exception safety** in all scenarios
3. **Consistent patterns** across the codebase
4. **Proper error handling** for edge cases
5. **Comprehensive testing** of cleanup behavior

These practices ensure reliable resource management and prevent disk space leaks while maintaining code simplicity and readability.
