# Adhoc Scripts Directory

This directory contains temporary, one-time, and experimental scripts that are not part of the regular development workflow.

## Purpose

The `adhoc/` directory is designed for:

- **Temporary scripts**: Quick scripts created for specific, short-term tasks
- **One-time tools**: Scripts that solve a specific problem and won't be reused
- **Experimental code**: Proof-of-concept scripts and experimental features
- **Backup versions**: Temporary backups of scripts during refactoring
- **Quick verification**: Fast diagnostic or verification scripts

## Guidelines

### When to Use This Directory

✅ **DO** place scripts here when:
- You need a quick script for a one-time task
- You're experimenting with a new approach
- You're creating a temporary backup during refactoring
- The script is for personal use and not part of the project workflow

❌ **DON'T** place scripts here when:
- The script will be used regularly (use appropriate `scripts/` subdirectory)
- The script is production-ready (consider `src/pktmask/tools/`)
- The script is part of CI/CD pipeline (use `scripts/test/` or `scripts/validation/`)

### Naming Conventions

Use descriptive names with date prefixes for temporary scripts:
```
YYYY-MM-DD_description.py
temp_feature_name.py
backup_original_script_name.py
experiment_new_approach.py
```

Examples:
- `2024-01-15_quick_pcap_check.py`
- `temp_tls_parser_v2.py`
- `backup_old_validator.py`
- `experiment_async_processing.py`

### Cleanup Policy

⚠️ **Important**: This directory should be cleaned up regularly!

- Scripts older than **3 months** should be reviewed and either:
  - Moved to appropriate permanent location if still useful
  - Deleted if no longer needed
- Before major releases, review and clean up this directory
- Add a comment at the top of each script explaining its purpose and creation date

### Example Script Header

```python
#!/usr/bin/env python3
"""
Temporary script for [purpose]
Created: 2024-01-15
Author: [Your Name]
Status: Experimental / One-time use / Backup

Description:
[Brief description of what this script does and why it was created]

TODO:
- [ ] Review after [date] and decide if still needed
"""
```

## Current Contents

This directory is currently empty or contains temporary scripts that should be reviewed periodically.

## Related Directories

- **`scripts/build/`** - Build and packaging scripts
- **`scripts/maintenance/`** - Regular maintenance and audit tools
- **`scripts/test/`** - Testing helper scripts
- **`scripts/validation/`** - Validation and analysis tools
- **`src/pktmask/tools/`** - Production-grade user-facing tools

