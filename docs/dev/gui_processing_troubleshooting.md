# GUI Processing Troubleshooting Guide

## Problem: GUI Start Button Doesn't Process Files and Log Shows Nothing

### Enhanced Diagnostics Added

The GUI now includes comprehensive logging to help diagnose processing issues. When you click the Start button, you should immediately see diagnostic messages in the Log panel.

### Step-by-Step Troubleshooting

#### 1. Check Log Panel Immediately After Clicking Start

**Expected Behavior**: You should see these messages appear immediately:
```
🧪 Log system test - if you see this, logging is working
📂 Input directory: /path/to/your/directory
✅ Found X pcap/pcapng files:
   1. file1.pcap
   2. file2.pcapng
   ...
⚙️ Building pipeline configuration...
✅ Configuration built with X stages
🔧 Creating pipeline executor...
✅ Pipeline executor created successfully
🚀 Processing started...
```

**If you see NO messages**: There's a fundamental GUI issue
**If you see some but not all**: The issue is at a specific step

#### 2. Common Issues and Solutions

##### Issue: "No pcap/pcapng files found in input directory"
**Cause**: The selected directory doesn't contain valid pcap files
**Solution**: 
- Verify the directory contains .pcap or .pcapng files
- Check file extensions are correct (case-sensitive on some systems)
- Ensure files are not corrupted

##### Issue: "No processing steps selected"
**Cause**: All checkboxes (Remove Dupes, Anonymize IPs, Mask Payloads) are unchecked
**Solution**: Enable at least one processing feature

##### Issue: "Configuration error" or "Failed to create pipeline"
**Cause**: Internal configuration problem
**Solution**: Check console output for detailed error messages

##### Issue: "Failed to start processing thread"
**Cause**: Threading or executor creation problem
**Solution**: Check file permissions and available system resources

#### 3. Platform-Specific Issues

##### Windows-Specific Problems
- **Path Length**: Windows has a 260-character path limit
- **Permissions**: Try running as administrator
- **File Locks**: Ensure pcap files aren't open in other applications
- **Antivirus**: Some antivirus software may block file processing

##### macOS-Specific Problems
- **Gatekeeper**: Allow the application in Security & Privacy settings
- **File Permissions**: Ensure read access to input directory and write access to output location

##### Linux-Specific Problems
- **File Permissions**: Check directory and file permissions
- **Dependencies**: Ensure all required libraries are installed

#### 4. Advanced Diagnostics

##### Enable Debug Logging
Run PktMask from terminal to see detailed console output:
```bash
# macOS/Linux
cd /path/to/PktMask
python3 -m pktmask

# Windows
cd C:\path\to\PktMask
python -m pktmask
```

##### Check Log Files
PktMask creates detailed log files at:
- **macOS/Linux**: `~/.pktmask/pktmask.log`
- **Windows**: `%USERPROFILE%\.pktmask\pktmask.log`

##### Test Components Individually
Use the debug scripts:
```bash
# Test basic functionality
python3 debug_gui_processing.py

# Test GUI logging
python3 test_gui_logging.py
```

#### 5. What the Enhanced Logging Shows

##### Directory Scanning Phase
```
📂 Directory Scanning Started
 - Input Directory: /path/to/input
 - Output Directory: /path/to/output
 - Platform: Windows/macOS/Linux
 - Scanning for pcap/pcapng files...
 - Found: file1.pcap (2.45 MB)
 - Found: file2.pcapng (1.23 MB)
📊 Directory Scanning Completed
 - Total files found: 2
```

##### File Processing Phase
```
🔄 File Processing Pipeline Started
📄 Processing file 1/2: file1.pcap
 - Input size: 2.45 MB
 - Output path: file1_processed.pcap
 - Starting processing stages...
   🔧 Remove Dupes started
   ✅ Remove Dupes: processed 1,000 packets, removed 50 duplicates (5.0%) (0.05s)
 - ✅ Output created: 2.20 MB (reduction: 10.2%)
```

##### Error Reporting
```
❌ Error processing file sample.pcap: Permission denied
 - Windows Tip: Try running as administrator or check file permissions
```

#### 6. Quick Fixes

1. **Restart the Application**: Close and reopen PktMask
2. **Check File Permissions**: Ensure read access to input files
3. **Free Disk Space**: Ensure sufficient space for output files
4. **Close Other Applications**: Free up system resources
5. **Try Different Directory**: Test with a different input directory
6. **Enable Only Remove Dupes**: Start with the simplest processing option

#### 7. Reporting Issues

If problems persist, include this information when reporting:

1. **Operating System**: Windows/macOS/Linux version
2. **Log Messages**: Copy all messages from the Log panel
3. **Console Output**: Any error messages from terminal
4. **File Details**: Number and size of pcap files
5. **Configuration**: Which processing features were enabled
6. **Steps to Reproduce**: Exact steps that led to the problem

#### 8. Emergency Workaround

If GUI processing fails completely, use the command-line interface:
```bash
# Process single file
python3 -m pktmask mask input.pcap -o output.pcap --dedup --anon

# Process with verbose output
python3 -m pktmask mask input.pcap -o output.pcap --dedup --verbose
```

The enhanced logging should now provide clear visibility into where the processing pipeline fails, making it much easier to diagnose and resolve issues.
