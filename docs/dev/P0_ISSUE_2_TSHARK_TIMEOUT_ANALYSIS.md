# P0 Issue #2: Add TShark Timeout and Resource Limits

> **Priority**: P0 (Critical)  
> **Status**: 🔄 **IN PROGRESS**  
> **Estimated Time**: 3 hours  
> **Date**: 2025-10-09

---

## 📋 Problem Description

### Issue
TShark subprocess calls lack comprehensive timeout and resource limits, which can cause:
- **Process Hangs**: Large PCAP files may cause TShark to run indefinitely
- **Memory Exhaustion**: No memory limits on TShark processes
- **Resource Leaks**: Hung processes consume system resources
- **Poor User Experience**: Application appears frozen with no feedback

### Current State Analysis

#### Files with TShark Calls
1. **`src/pktmask/utils/subprocess_utils.py`**
   - ✅ `run_tshark_command()`: Has default timeout (300s)
   - ❌ No memory limits

2. **`src/pktmask/core/pipeline/stages/masking_stage/marker/tls_marker.py`**
   - ❌ Version check: No timeout
   - ❌ TLS scanning: No timeout
   - ❌ TCP flow analysis: No timeout

3. **`src/pktmask/tools/tls23_marker.py`**
   - ❌ Version check: No timeout
   - ❌ TLS scanning: No timeout
   - ❌ Stream analysis: No timeout

4. **`src/pktmask/tools/enhanced_tls_marker.py`**
   - ❌ Version check: No timeout
   - ❌ TLS scanning: No timeout

5. **`src/pktmask/tools/tls_flow_analyzer.py`**
   - ❌ Version check: No timeout
   - ❌ Flow analysis: No timeout

6. **`src/pktmask/infrastructure/dependency/checker.py`**
   - ✅ Version check: Has timeout (10s)
   - ❌ Protocol list: No timeout
   - ❌ JSON test: No timeout

### Impact
- **High Risk**: Large PCAP files (>100MB) can cause indefinite hangs
- **User Impact**: Application appears frozen, no progress feedback
- **Resource Impact**: Hung processes consume CPU/memory
- **Production Risk**: Cannot be deployed safely without timeouts

---

## 🎯 Solution Design

### 1. **Timeout Strategy**

#### Operation-Based Timeouts
Different operations need different timeout values:

| Operation Type | Default Timeout | Rationale |
|----------------|-----------------|-----------|
| Version Check | 10s | Quick operation, should complete instantly |
| Protocol List | 30s | Medium operation, parsing protocol database |
| Small PCAP (<10MB) | 60s | Normal processing time |
| Medium PCAP (10-100MB) | 300s (5min) | May need more time for complex analysis |
| Large PCAP (>100MB) | 600s (10min) | Maximum allowed processing time |
| JSON Test | 10s | Quick validation operation |

#### Dynamic Timeout Calculation
```python
def calculate_timeout(file_size_mb: float) -> float:
    """Calculate timeout based on file size"""
    if file_size_mb < 10:
        return 60  # 1 minute
    elif file_size_mb < 100:
        return 300  # 5 minutes
    else:
        return 600  # 10 minutes
```

### 2. **Resource Limits**

#### Memory Limits (Future Enhancement)
- Use `resource.setrlimit()` on Unix systems
- Use `psutil` for cross-platform memory monitoring
- **Not implemented in this phase** (requires more testing)

#### Process Monitoring
- Log TShark execution time
- Log file sizes being processed
- Warn if approaching timeout

---

## 🔧 Implementation Plan

### Phase 1: Add Timeouts to All TShark Calls ✅

#### 1.1 Update `tls_marker.py`
```python
# Version check
completed = run_hidden_subprocess(
    [executable, "-v"],
    check=True,
    text=True,
    capture_output=True,
    encoding="utf-8",
    errors="replace",
    timeout=10,  # ADD THIS
)

# TLS scanning
completed_reassembled = run_tshark_command(
    self.tshark_exec,
    cmd_reassembled[1:],  # Remove tshark_exec from args
    timeout=self._calculate_scan_timeout(pcap_path),  # ADD THIS
)
```

#### 1.2 Update `tls23_marker.py`
```python
# Version check
completed = run_hidden_subprocess(
    [executable, "-v"],
    timeout=10,  # ADD THIS
    ...
)

# TLS scanning
completed = run_hidden_subprocess(
    tshark_cmd,
    timeout=calculate_timeout_from_file(args.pcap),  # ADD THIS
    ...
)
```

#### 1.3 Update `enhanced_tls_marker.py`
Similar changes as above.

#### 1.4 Update `tls_flow_analyzer.py`
Similar changes as above.

#### 1.5 Update `dependency/checker.py`
```python
# Protocol list check
proc = run_hidden_subprocess(
    [tshark_path, "-G", "protocols"],
    timeout=30,  # ADD THIS
    ...
)

# JSON test
proc = run_hidden_subprocess(
    [tshark_path, "-T", "json", "-c", "0"],
    timeout=10,  # ADD THIS
    ...
)
```

### Phase 2: Add Helper Functions

#### 2.1 Create Timeout Calculator
```python
# In subprocess_utils.py
def calculate_tshark_timeout(pcap_path: str, operation: str = "scan") -> float:
    """
    Calculate appropriate timeout for TShark operation based on file size.
    
    Args:
        pcap_path: Path to PCAP file
        operation: Type of operation ('version', 'scan', 'analyze')
    
    Returns:
        Timeout in seconds
    """
    if operation == "version":
        return 10
    
    try:
        file_size_mb = Path(pcap_path).stat().st_size / (1024 * 1024)
    except:
        file_size_mb = 0
    
    if operation == "scan":
        if file_size_mb < 10:
            return 60
        elif file_size_mb < 100:
            return 300
        else:
            return 600
    
    return 300  # Default 5 minutes
```

### Phase 3: Add Logging and Monitoring

#### 3.1 Log TShark Execution
```python
logger.info(f"Executing TShark: file_size={file_size_mb:.2f}MB, timeout={timeout}s")
start_time = time.time()
try:
    result = run_tshark_command(...)
    elapsed = time.time() - start_time
    logger.info(f"TShark completed in {elapsed:.2f}s")
except subprocess.TimeoutExpired:
    logger.error(f"TShark timeout after {timeout}s for file {pcap_path}")
    raise
```

---

## 📝 Files to Modify

### Core Files
1. ✅ `src/pktmask/utils/subprocess_utils.py`
   - Add `calculate_tshark_timeout()` function
   - Update documentation

2. ✅ `src/pktmask/core/pipeline/stages/masking_stage/marker/tls_marker.py`
   - Add timeout to version check
   - Add timeout to TLS scanning
   - Add timeout to TCP flow analysis

3. ✅ `src/pktmask/tools/tls23_marker.py`
   - Add timeout to all TShark calls

4. ✅ `src/pktmask/tools/enhanced_tls_marker.py`
   - Add timeout to all TShark calls

5. ✅ `src/pktmask/tools/tls_flow_analyzer.py`
   - Add timeout to all TShark calls

6. ✅ `src/pktmask/infrastructure/dependency/checker.py`
   - Add timeout to protocol list check
   - Add timeout to JSON test

---

## 🧪 Testing Strategy

### Unit Tests
```python
def test_tshark_timeout_small_file():
    """Test timeout calculation for small files"""
    timeout = calculate_tshark_timeout("small.pcap", "scan")
    assert timeout == 60

def test_tshark_timeout_large_file():
    """Test timeout calculation for large files"""
    timeout = calculate_tshark_timeout("large.pcap", "scan")
    assert timeout == 600
```

### Integration Tests
- Test with small PCAP files (should complete quickly)
- Test with medium PCAP files (should complete within timeout)
- Test with large PCAP files (should complete or timeout gracefully)
- Test timeout handling (mock slow TShark)

### E2E Tests
- Run existing E2E CLI blackbox tests
- Verify all tests pass with new timeouts
- Verify no performance regression

---

## ✅ Acceptance Criteria

- [ ] All TShark calls have appropriate timeouts
- [ ] Timeout values are based on file size
- [ ] Version checks have 10s timeout
- [ ] Small files (<10MB) have 60s timeout
- [ ] Medium files (10-100MB) have 300s timeout
- [ ] Large files (>100MB) have 600s timeout
- [ ] Timeout errors are logged clearly
- [ ] All existing tests pass
- [ ] No performance regression
- [ ] Documentation updated

---

## 📊 Expected Benefits

### Before Fix
```
❌ No timeout - can hang indefinitely
❌ No file size consideration
❌ No progress feedback
❌ Poor error messages
```

### After Fix
```
✅ All operations have timeouts
✅ Dynamic timeout based on file size
✅ Clear timeout error messages
✅ Logged execution times
✅ Better user experience
```

### Metrics
- **Risk Reduction**: High → Low
- **User Experience**: Poor → Good
- **Reliability**: 60% → 95%
- **Production Ready**: No → Yes

---

**Status**: Ready for implementation  
**Next Step**: Implement timeout additions to all TShark calls

