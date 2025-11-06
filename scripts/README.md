# Scripts Directory Description

This directory contains script tools related to project development, testing, and maintenance. These scripts are primarily for developers, not end users.

## Directory Structure

### `adhoc/`
Temporary scripts and one-time tools, including:
- Backup version tools
- Quick verification scripts
- Experimental code
- See `adhoc/README.md` for cleanup policy and guidelines

### `build/`
Build and packaging related scripts:
- `build_app.sh` - Application build script
- `pyinstaller_common.py` - Shared PyInstaller configuration

### `docs/`
Documentation management scripts:
- `manage-docs.sh` - Documentation management script
- `docs_quality_check.sh` - Documentation quality assurance

### `git-hooks/`
Git hooks for code quality control:
- `install-hooks.sh` - Git hooks installation script
- `pre-commit-chinese-check` - Pre-commit Chinese text check

### `maintenance/`
System maintenance and audit scripts:
- `audit_dependencies.py` - Dependency audit tool
- `check_chinese_text.py` - Chinese text detection in codebase
- `check_doc_sync.py` - Documentation synchronization check
- `check_tshark_dependencies.py` - TShark dependency verification
- `cleanup_deprecated_files.sh` - Cleanup deprecated files
- `verify_naming_conventions.py` - Naming convention verification

### `test/`
Testing assistance scripts:
- `test_all_entrypoints.sh` - Entry point testing
- `test_cli_comprehensive.sh` - Comprehensive CLI testing
- `test_ip_anonymization_fix.py` - IP anonymization fix testing
- `test_unified_functionality.py` - Unified functionality testing

### `validation/`
Data validation and analysis scripts:
- `tls23_e2e_validator.py` - TLS-23 end-to-end validation
- `tls23_maskstage_e2e_validator.py` - TLS-23 mask stage validation
- `run_http_auto_e2e.py` - HTTP auto protocol E2E testing
- `verify_http_zero_body.py` - HTTP zero-body verification

## Usage Instructions

### Build Scripts
```bash
# Build application with PyInstaller
bash scripts/build/build_app.sh
```

### Maintenance Scripts
```bash
# Audit dependencies
python scripts/maintenance/audit_dependencies.py

# Check for Chinese text in codebase
python scripts/maintenance/check_chinese_text.py

# Verify TShark dependencies
python scripts/maintenance/check_tshark_dependencies.py

# Check documentation synchronization
python scripts/maintenance/check_doc_sync.py

# Verify naming conventions
python scripts/maintenance/verify_naming_conventions.py
```

### Test Scripts
```bash
# Run all entry point tests
bash scripts/test/test_all_entrypoints.sh

# Run comprehensive CLI tests
bash scripts/test/test_cli_comprehensive.sh

# Test unified functionality
python scripts/test/test_unified_functionality.py
```

### Validation Scripts
```bash
# TLS-23 end-to-end validation
python scripts/validation/tls23_e2e_validator.py --input samples/tls --output output/validation

# TLS-23 mask stage validation
python scripts/validation/tls23_maskstage_e2e_validator.py --input samples/tls --output output/validation

# HTTP auto protocol E2E testing
python scripts/validation/run_http_auto_e2e.py --input samples/http --output output/http_e2e

# Verify HTTP zero-body masking
python scripts/validation/verify_http_zero_body.py --input output/http_e2e
```

### Documentation Scripts
```bash
# Manage documentation
bash scripts/docs/manage-docs.sh

# Check documentation quality
bash scripts/docs/docs_quality_check.sh
```

## Guidelines

### Script Organization
1. **Production tools** → `src/pktmask/tools/` (for end users)
2. **Development scripts** → `scripts/` subdirectories (for developers)
3. **Temporary scripts** → `scripts/adhoc/` (with cleanup policy)

### Naming Conventions
- Use descriptive names with underscores: `check_tshark_dependencies.py`
- Avoid prefixes like `debug_`, `test_`, `backup_` in permanent scripts
- For temporary scripts in `adhoc/`, use date prefixes: `2024-01-15_description.py`

### Adding New Scripts
1. Choose the appropriate subdirectory based on purpose
2. Follow existing naming conventions
3. Add documentation header with purpose and usage
4. Update this README with the new script
5. If temporary, place in `adhoc/` and add cleanup date

## Notes

1. These scripts are for **development and maintenance**, not production use
2. For production-grade tools, see `src/pktmask/tools/` directory
3. Temporary scripts in `adhoc/` should be reviewed and cleaned up regularly
4. All scripts should follow the project's coding standards

## Related Resources

- **Production Tools**: `src/pktmask/tools/` - User-facing command-line tools
- **Project Documentation**: `docs/` - Comprehensive project documentation
- **Test Cases**: `tests/` - Unit, integration, and E2E tests
- **Build Configuration**: `pyproject.toml` - Project dependencies and metadata
