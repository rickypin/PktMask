# Scripts Directory Reorganization - 2024

## Overview

This document records the reorganization of the `scripts/` directory to improve maintainability and clarity.

## Date

2024-11-06

## Motivation

The `scripts/` root directory contained several miscellaneous scripts that should be organized into appropriate subdirectories based on their purpose. This reorganization improves:

1. **Discoverability**: Developers can easily find scripts by category
2. **Maintainability**: Clear organization makes it easier to maintain scripts
3. **Documentation**: Better structure enables better documentation
4. **Consistency**: Aligns with the project's overall organization principles

## Changes Made

### 1. Created New Directory

- **`scripts/adhoc/`** - For temporary, one-time, and experimental scripts
  - Added comprehensive `README.md` with cleanup policy
  - Established naming conventions for temporary scripts
  - Defined guidelines for when to use this directory

### 2. Moved Scripts to Appropriate Subdirectories

| Original Location | New Location | Purpose |
|-------------------|--------------|---------|
| `scripts/pyinstaller_common.py` | `scripts/build/pyinstaller_common.py` | PyInstaller shared configuration |
| `scripts/check_tshark_dependencies.py` | `scripts/maintenance/check_tshark_dependencies.py` | TShark dependency verification |
| `scripts/docs_quality_check.sh` | `scripts/docs/docs_quality_check.sh` | Documentation quality assurance |
| `scripts/test_unified_functionality.py` | `scripts/test/test_unified_functionality.py` | Unified functionality testing |
| `scripts/run_http_auto_e2e.py` | `scripts/validation/run_http_auto_e2e.py` | HTTP auto protocol E2E testing |
| `scripts/verify_http_zero_body.py` | `scripts/validation/verify_http_zero_body.py` | HTTP zero-body verification |

### 3. Kept in Root Directory

- **`scripts/pktmask_launcher.py`** - Must remain in root for PyInstaller spec files
- **`scripts/__init__.py`** - Python package marker
- **`scripts/README.md`** - Directory documentation

### 4. Updated References

Updated all references to moved scripts in:

- `PktMask.spec` - Updated import path for `pyinstaller_common`
- `PktMask-Windows.spec` - Updated import path for `pyinstaller_common`
- `scripts/README.md` - Updated directory structure documentation
- `docs/DEPLOYMENT_CHECKLIST.md` - Updated script paths

## Final Directory Structure

```
scripts/
├── README.md                           # Directory documentation
├── __init__.py                         # Python package marker
├── pktmask_launcher.py                 # PyInstaller launcher (must stay in root)
│
├── adhoc/                              # Temporary and experimental scripts
│   └── README.md                       # Cleanup policy and guidelines
│
├── build/                              # Build and packaging
│   ├── build_app.sh
│   └── pyinstaller_common.py
│
├── docs/                               # Documentation management
│   ├── docs_quality_check.sh
│   └── manage-docs.sh
│
├── git-hooks/                          # Git hooks for code quality
│   ├── install-hooks.sh
│   └── pre-commit-chinese-check
│
├── maintenance/                        # Maintenance and audit tools
│   ├── audit_dependencies.py
│   ├── check_chinese_text.py
│   ├── check_doc_sync.py
│   ├── check_tshark_dependencies.py
│   ├── cleanup_deprecated_files.sh
│   └── verify_naming_conventions.py
│
├── test/                               # Testing assistance
│   ├── test_all_entrypoints.sh
│   ├── test_cli_comprehensive.sh
│   ├── test_ip_anonymization_fix.py
│   └── test_unified_functionality.py
│
└── validation/                         # Validation and analysis
    ├── __init__.py
    ├── run_http_auto_e2e.py
    ├── tls23_e2e_validator.py
    ├── tls23_maskstage_e2e_validator.py
    └── verify_http_zero_body.py
```

## Benefits

### Before Reorganization
- ❌ 6 miscellaneous scripts in root directory
- ❌ Unclear purpose and categorization
- ❌ Difficult to find specific scripts
- ❌ No clear policy for temporary scripts

### After Reorganization
- ✅ Clean root directory with only essential files
- ✅ Clear categorization by purpose
- ✅ Easy to discover and locate scripts
- ✅ Established `adhoc/` directory with cleanup policy
- ✅ Comprehensive documentation in `scripts/README.md`

## Migration Guide

### For Developers

If you have local scripts or documentation that reference the old paths, update them as follows:

```bash
# Old paths → New paths
scripts/pyinstaller_common.py → scripts/build/pyinstaller_common.py
scripts/check_tshark_dependencies.py → scripts/maintenance/check_tshark_dependencies.py
scripts/docs_quality_check.sh → scripts/docs/docs_quality_check.sh
scripts/test_unified_functionality.py → scripts/test/test_unified_functionality.py
scripts/run_http_auto_e2e.py → scripts/validation/run_http_auto_e2e.py
scripts/verify_http_zero_body.py → scripts/validation/verify_http_zero_body.py
```

### For CI/CD Pipelines

If your CI/CD pipelines reference these scripts, update the paths accordingly. All scripts maintain the same functionality and command-line interface.

### For PyInstaller Builds

The PyInstaller spec files have been updated automatically. No action required.

## Verification

All changes have been verified:

1. ✅ PyInstaller imports work correctly
2. ✅ All script references updated in documentation
3. ✅ Directory structure is clean and organized
4. ✅ `adhoc/` directory created with guidelines
5. ✅ `scripts/README.md` updated with new structure

## Future Recommendations

1. **Regular Cleanup**: Review `scripts/adhoc/` quarterly and remove outdated scripts
2. **Documentation**: Keep `scripts/README.md` updated when adding new scripts
3. **Naming Conventions**: Follow established naming patterns for consistency
4. **Categorization**: Place new scripts in appropriate subdirectories from the start

## Related Documents

- `scripts/README.md` - Main scripts directory documentation
- `scripts/adhoc/README.md` - Temporary scripts guidelines
- `src/pktmask/tools/README.md` - Production tools documentation
- `docs/DOCS_DIRECTORY_STRUCTURE_GUIDE.md` - Overall documentation structure

## Notes

This reorganization maintains backward compatibility for all script functionality. Only file paths have changed; the scripts themselves remain unchanged.

