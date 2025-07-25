# PktMask CLI Refactor Design Document

## Executive Summary

This document outlines the refactoring of PktMask CLI argument structure to address inconsistencies and limitations in the current parameter design, implementing a unified, flexible command interface that maintains backward compatibility.

## Current Issues Analysis

### Problem 1: Inconsistent Parameter Design

**Current Structure Issues:**
- `mask` command uses optional flags (`--remove-dupes`, `--anonymize-ips`)
- `dedup`/`anon` commands are standalone with no combination options
- `batch` command uses enable/disable toggles (`--remove-dupes/--no-remove-dupes`)
- Different parameter forms create high learning curve

### Problem 2: Limited Parameter Combinations

**Current Limitations:**
- Cannot execute `dedup` + `anon` without also running `mask`
- No direct way to combine operations flexibly
- `batch` command defaults all operations to enabled

### Problem 3: Validation Inconsistencies

**Current Issues:**
- Config service validates "at least one stage enabled" but CLI allows empty operations
- `pktmask mask input.pcap -o output.pcap` runs with no actual processing

## Proposed Solution

### Design Principles

1. **Unified Parameter Format**: Consistent flag-based approach for all operations
2. **Flexible Combinations**: Any combination of operations can be specified
3. **Mandatory Selection**: At least one operation must be specified
4. **Backward Compatibility**: Existing commands work with deprecation warnings
5. **GUI Consistency**: Maintain identical functionality between CLI and GUI

### New Unified Command Structure

#### Primary Command: `process`
```bash
pktmask process <input> -o <output> [--dedup] [--anon] [--mask] [options]
```

**Operation Flags:**
- `--dedup`: Enable Remove Dupes processing
- `--anon`: Enable Anonymize IPs processing  
- `--mask`: Enable Mask Payloads processing

**Additional Options:**
- `--protocol <tls|http>`: Protocol for masking (default: tls)
- `--verbose`, `--format`, `--pattern`, etc.: Existing options

#### Usage Examples
```bash
# Single operations
pktmask process input.pcap -o output.pcap --dedup
pktmask process input.pcap -o output.pcap --anon
pktmask process input.pcap -o output.pcap --mask

# Combinations
pktmask process input.pcap -o output.pcap --dedup --anon
pktmask process input.pcap -o output.pcap --anon --mask --protocol tls
pktmask process input.pcap -o output.pcap --dedup --anon --mask --verbose

# Directory processing
pktmask process /data/pcaps -o /data/output --dedup --anon --mask
```

### Backward Compatibility Strategy

#### Legacy Commands (Deprecated)
```bash
# These continue to work with deprecation warnings
pktmask mask input.pcap -o output.pcap --remove-dupes --anonymize-ips
pktmask dedup input.pcap -o output.pcap
pktmask anon input.pcap -o output.pcap
pktmask batch /data/pcaps -o /data/output
```

#### Migration Path
1. **Phase 1**: Implement new `process` command alongside existing commands
2. **Phase 2**: Add deprecation warnings to legacy commands
3. **Phase 3**: Update documentation to recommend new syntax
4. **Phase 4**: (Future) Remove legacy commands in major version update

## Implementation Plan

### Phase 1: Core Implementation

#### 1. New Command Structure
```python
@app.command("process")
def cmd_process(
    input_path: Path = typer.Argument(..., exists=True, help="Input PCAP/PCAPNG file or directory"),
    output_path: Path = typer.Option(..., "-o", "--output", help="Output file/directory path"),
    dedup: bool = typer.Option(False, "--dedup", help="Enable Remove Dupes processing"),
    anon: bool = typer.Option(False, "--anon", help="Enable Anonymize IPs processing"),
    mask: bool = typer.Option(False, "--mask", help="Enable Mask Payloads processing"),
    protocol: str = typer.Option("tls", "--protocol", help="Protocol type: tls|http"),
    # ... other options
):
```

#### 2. Parameter Validation
```python
def validate_process_parameters(dedup: bool, anon: bool, mask: bool) -> Tuple[bool, Optional[str]]:
    """Validate that at least one operation is selected"""
    if not any([dedup, anon, mask]):
        return False, "At least one operation must be specified: --dedup, --anon, or --mask"
    return True, None
```

#### 3. Configuration Integration
```python
def build_config_from_unified_args(
    dedup: bool = False,
    anon: bool = False, 
    mask: bool = False,
    protocol: str = "tls"
) -> Dict[str, Any]:
    """Build configuration from unified CLI arguments"""
    return build_config_from_cli_args(
        remove_dupes=dedup,
        anonymize_ips=anon,
        mask_payloads=mask,
        mask_protocol=protocol
    )
```

### Phase 2: Legacy Command Updates

#### Add Deprecation Warnings
```python
def _show_deprecation_warning(command: str, new_syntax: str):
    """Show deprecation warning for legacy commands"""
    typer.echo(
        f"⚠️  Warning: '{command}' command is deprecated. "
        f"Use: {new_syntax}",
        err=True
    )
```

#### Update Legacy Commands
```python
@app.command("mask")
def cmd_mask_legacy(...):
    """Legacy mask command with deprecation warning"""
    _show_deprecation_warning(
        "pktmask mask", 
        "pktmask process <input> -o <output> --mask [--dedup] [--anon]"
    )
    # ... existing implementation
```

## Technical Specifications

### Parameter Mapping

| New Unified | Legacy Equivalent | Description |
|-------------|-------------------|-------------|
| `--dedup` | `--remove-dupes` | Enable deduplication |
| `--anon` | `--anonymize-ips` | Enable IP anonymization |
| `--mask` | (mask command) | Enable payload masking |

### Configuration Compatibility

The new structure maintains full compatibility with existing configuration service:

```python
# Both approaches produce identical configuration
config1 = build_config_from_cli_args(remove_dupes=True, anonymize_ips=True, mask_payloads=True)
config2 = build_config_from_unified_args(dedup=True, anon=True, mask=True)
assert config1 == config2
```

### GUI Integration

No changes required to GUI - the configuration service abstraction ensures GUI continues to work identically.

## Risk Assessment

### Low Risk
- **Configuration compatibility**: Existing config service handles parameter mapping
- **GUI functionality**: No GUI changes required
- **Core processing**: No changes to processing pipeline

### Medium Risk  
- **User adoption**: Users need to learn new command syntax
- **Documentation updates**: Extensive documentation changes required

### Mitigation Strategies
- **Gradual migration**: Maintain legacy commands with warnings
- **Clear documentation**: Provide migration guide and examples
- **Comprehensive testing**: Validate all parameter combinations

## Success Criteria

1. **Functional Requirements**
   - ✅ Any combination of dedup/anon/mask operations can be executed
   - ✅ At least one operation must be specified
   - ✅ Identical results between CLI and GUI for same operations
   - ✅ Backward compatibility maintained

2. **Technical Requirements**
   - ✅ Consistent parameter naming across all commands
   - ✅ Unified validation logic
   - ✅ No breaking changes to existing functionality

3. **User Experience Requirements**
   - ✅ Intuitive command structure
   - ✅ Clear error messages for invalid combinations
   - ✅ Smooth migration path from legacy commands

## Next Steps

1. Implement new `process` command with unified parameters
2. Add parameter validation logic
3. Update configuration service integration
4. Add deprecation warnings to legacy commands
5. Update tests and documentation
6. Validate backward compatibility

This design addresses all identified issues while maintaining the pragmatic, non-over-engineered approach preferred for this lightweight desktop application.
