# E2E CLI Blackbox Test Log Capture Fix

> **Issue**: HTML test reports showed "No log output captured"  
> **Status**: ✅ **FIXED**  
> **Date**: 2025-10-09

---

## 📋 Problem Description

### Issue
When running E2E CLI blackbox tests, the HTML test report displayed "No log output captured" for all tests, making it difficult to debug failures or understand test execution.

### Root Cause
The CLI blackbox tests use `subprocess.run()` to execute PktMask CLI commands. While the subprocess output (stdout/stderr) was captured using `capture_output=True`, this output was **not being passed to pytest's logging system**, which is what the HTML report displays.

### Impact
- No visibility into CLI execution in test reports
- Difficult to debug test failures
- Missing important execution details (command, output, errors)

---

## ✅ Solution Implemented

### Changes Made

#### 1. Added Logging Infrastructure
Added Python's `logging` module to capture and forward CLI output to pytest:

```python
import logging

# Configure logger for CLI output capture
logger = logging.getLogger(__name__)
```

#### 2. Enhanced `_run_cli_command()` Method
Modified the CLI command execution method to log all output:

**Before**:
```python
def _run_cli_command(...):
    # Run command
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    return result
```

**After**:
```python
def _run_cli_command(...):
    # Log command being executed
    logger.info(f"Executing CLI command: {' '.join(cmd)}")
    
    # Run command
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    
    # Log output to pytest capture
    if result.stdout:
        logger.info(f"CLI STDOUT:\n{result.stdout}")
        print(f"\n=== CLI STDOUT ===\n{result.stdout}")
    
    if result.stderr:
        logger.warning(f"CLI STDERR:\n{result.stderr}")
        print(f"\n=== CLI STDERR ===\n{result.stderr}")
    
    logger.info(f"CLI exit code: {result.returncode}")
    print(f"\n=== CLI Exit Code: {result.returncode} ===")
    
    return result
```

#### 3. Enhanced Test Methods
Added detailed logging to all three test methods:

```python
def test_cli_core_functionality_consistency(...):
    logger.info(f"Starting test {test_id}: dedup={dedup}, anon={anon}, mask={mask}")
    print(f"\n{'='*60}\nTest {test_id}: Core Functionality Test\n{'='*60}")
    
    # ... test execution ...
    
    logger.info(f"Output file created successfully: {output_path.stat().st_size} bytes")
    print(f"Output file size: {output_path.stat().st_size} bytes")
    
    logger.info(f"Test {test_id} PASSED: Hash matches baseline")
    print(f"✅ Test {test_id} PASSED\n")
```

---

## 📊 Results

### Before Fix
```
Test Details
Test ID:    E2E-001
Duration:   0.358s
Status:     PASSED

No log output captured.
```

### After Fix (with Metrics)
```
Test Details
Test ID:    E2E-001
Duration:   0.423s
Status:     PASSED

============================================================
Test E2E-001: Core Functionality Test
============================================================
Input:  /Users/ricky/Downloads/code/PktMask/tests/data/tls/tls_1_2-2.pcap (2,721 bytes)

=== CLI STDOUT ===
🚀 🚀 Processing started...
2025-10-09 22:16:20 - pktmask.dedup_stage - INFO - Starting deduplication...
2025-10-09 22:16:20 - pktmask.dedup_stage - INFO - Loaded 14 packets...
2025-10-09 22:16:20 - pktmask.dedup_stage - INFO - Deduplication completed: removed 0/14 duplicate packets
✅ Processed 1 stages in 0.01s
✅ ✅ Processing completed successfully

=== CLI Exit Code: 0 ===

────────────────────────────────────────────────────────────
📊 File Metrics:
  Input size:        2,721 bytes
  Output size:       2,721 bytes
  Change:               +0 bytes (+0.00%)
────────────────────────────────────────────────────────────

🔐 Hash Verification:
  Expected: baf39e4018711111...
  Actual:   baf39e4018711111...
  Status:   ✅ MATCH

✅ Test E2E-001 PASSED
```

---

## 🎯 Benefits

### 1. **Improved Debugging**
- Full visibility into CLI execution
- Can see exact commands being run
- Can see all output and errors

### 2. **Better Test Reports**
- HTML reports now contain rich execution details
- Easy to identify what went wrong in failures
- Complete audit trail of test execution

### 3. **Enhanced Monitoring**
- Can track performance metrics (file sizes, durations)
- Can verify expected behavior from logs
- Can identify patterns in test execution

---

## 📝 Files Modified

### Modified Files
1. **tests/e2e/test_e2e_cli_blackbox.py**
   - Added `logging` import
   - Enhanced `_run_cli_command()` method
   - Enhanced all three test methods:
     - `test_cli_core_functionality_consistency()`
     - `test_cli_protocol_coverage_consistency()`
     - `test_cli_encapsulation_consistency()`

### Documentation Created
1. **docs/dev/E2E_LOG_CAPTURE_FIX.md** (this file)

---

## 🧪 Verification

### Test Execution
```bash
# Run single test with logs
pytest 'tests/e2e/test_e2e_cli_blackbox.py::TestE2ECLIBlackbox::test_cli_core_functionality_consistency[E2E-001-True-False-False-tls_1_2-2.pcap]' -v -s

# Run all tests with HTML report
pytest tests/e2e/test_e2e_cli_blackbox.py -v --html=tests/e2e/cli_blackbox_with_logs.html --self-contained-html
```

### Results
```
Total Tests:     16
Passed:          16 (100.0%)
Failed:          0 (0.0%)
Total Duration:  37.63s

✅ All tests passed with full log capture
```

---

## 💡 Technical Details

### Why Both `logger` and `print()`?

We use both logging methods to ensure maximum compatibility:

1. **`logger.info()`**: 
   - Captured by pytest's logging system
   - Appears in HTML reports
   - Structured and filterable

2. **`print()`**: 
   - Captured by pytest's stdout capture
   - Appears in console output with `-s` flag
   - Always visible in live test runs

### Log Levels Used

- `logger.info()`: Normal execution flow
- `logger.warning()`: CLI stderr output
- `logger.debug()`: Detailed debugging (not used in this fix)

---

## 🔍 Example Log Output

### Test Start
```
============================================================
Test E2E-001: Core Functionality Test
============================================================
Input:  /path/to/input.pcap
Output: /path/to/output.pcap
```

### CLI Execution
```
Executing CLI command: python pktmask process input.pcap -o output.pcap --dedup

=== CLI STDOUT ===
🚀 🚀 Processing started...
[... full CLI output ...]
✅ ✅ Processing completed successfully

=== CLI Exit Code: 0 ===
```

### Test Completion
```
Output file size: 2721 bytes
Expected hash: baf39e4018711111...
Actual hash:   baf39e4018711111...
✅ Test E2E-001 PASSED
```

---

## 📚 Related Documentation

- **Test Guide**: `tests/e2e/E2E_QUICK_REFERENCE.md`
- **Test Implementation**: `tests/e2e/test_e2e_cli_blackbox.py`
- **HTML Report**: `tests/e2e/cli_blackbox_with_logs.html`

---

## ✅ Acceptance Criteria

- [x] Logs appear in HTML test reports
- [x] CLI commands are logged
- [x] CLI stdout is captured
- [x] CLI stderr is captured
- [x] Exit codes are logged
- [x] Test progress is visible
- [x] All 16 tests pass with logs

---

## 🎓 Lessons Learned

### Key Insights
1. **Subprocess output doesn't auto-capture**: Need to explicitly forward to pytest
2. **Dual logging is best**: Use both `logger` and `print()` for maximum visibility
3. **Structured logging helps**: Clear sections (STDOUT, STDERR, Exit Code) improve readability

### Best Practices
1. Always log command execution in subprocess-based tests
2. Log both input and output for traceability
3. Use visual separators (===) for clarity
4. Include success indicators (✅) for quick scanning

---

**Fixed by**: AI Assistant  
**Verified by**: E2E Test Suite (16/16 passed)  
**Date**: 2025-10-09  
**Status**: ✅ **RESOLVED**

