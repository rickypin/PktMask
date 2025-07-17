#!/usr/bin/env python3
"""
Application Startup Dependency Validator

Validates all required dependencies during application initialization
and provides user-friendly error messages and installation guidance.
"""

import sys
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

from pktmask.infrastructure.logging import get_logger
from pktmask.infrastructure.dependency.checker import DependencyChecker, DependencyStatus
from pktmask.infrastructure.tshark import TSharkManager


@dataclass
class ValidationResult:
    """Dependency validation result"""
    success: bool
    missing_dependencies: List[str]
    error_messages: List[str]
    installation_guides: Dict[str, any]
    can_continue: bool = False  # Whether app can continue with warnings


class StartupDependencyValidator:
    """Validates dependencies during application startup"""
    
    def __init__(self, custom_tshark_path: Optional[str] = None):
        """Initialize dependency validator
        
        Args:
            custom_tshark_path: Custom TShark executable path
        """
        self.logger = get_logger('startup_validator')
        self.dependency_checker = DependencyChecker(custom_tshark_path=custom_tshark_path)
    
    def validate_all_dependencies(self, strict_mode: bool = True) -> ValidationResult:
        """Validate all required dependencies
        
        Args:
            strict_mode: If True, all dependencies must be satisfied
                        If False, some dependencies can be missing with warnings
        
        Returns:
            Validation result with detailed information
        """
        self.logger.info("Starting application dependency validation...")
        
        # Check all dependencies
        dependency_results = self.dependency_checker.check_all_dependencies()
        
        missing_dependencies = []
        error_messages = []
        installation_guides = {}
        
        for name, result in dependency_results.items():
            if not result.is_satisfied:
                missing_dependencies.append(name)
                error_messages.append(self._format_dependency_error(result))
                
                # Get installation guide for missing dependencies
                if name == 'tshark':
                    installation_guides[name] = self.dependency_checker.get_tshark_installation_guide()
        
        # Determine if validation passed
        success = len(missing_dependencies) == 0
        can_continue = not strict_mode or success
        
        if success:
            self.logger.info("All dependencies validated successfully")
        else:
            self.logger.warning(f"Missing dependencies: {', '.join(missing_dependencies)}")
        
        return ValidationResult(
            success=success,
            missing_dependencies=missing_dependencies,
            error_messages=error_messages,
            installation_guides=installation_guides,
            can_continue=can_continue
        )
    
    def validate_tshark_only(self) -> ValidationResult:
        """Validate only TShark dependency (for quick checks)
        
        Returns:
            TShark-specific validation result
        """
        self.logger.info("Validating TShark dependency...")
        
        tshark_result = self.dependency_checker.check_tshark()
        
        if tshark_result.is_satisfied:
            self.logger.info("TShark dependency validated successfully")
            return ValidationResult(
                success=True,
                missing_dependencies=[],
                error_messages=[],
                installation_guides={},
                can_continue=True
            )
        else:
            error_message = self._format_dependency_error(tshark_result)
            installation_guide = self.dependency_checker.get_tshark_installation_guide()
            
            self.logger.error(f"TShark validation failed: {error_message}")
            
            return ValidationResult(
                success=False,
                missing_dependencies=['tshark'],
                error_messages=[error_message],
                installation_guides={'tshark': installation_guide},
                can_continue=False
            )
    
    def _format_dependency_error(self, result) -> str:
        """Format dependency error message for user display
        
        Args:
            result: DependencyResult object
            
        Returns:
            Formatted error message
        """
        if result.status == DependencyStatus.MISSING:
            return f"❌ {result.name.upper()} not found: {result.error_message}"
        elif result.status == DependencyStatus.VERSION_MISMATCH:
            return (f"⚠️  {result.name.upper()} version mismatch: "
                   f"Found {result.version_found}, required ≥{result.version_required}")
        elif result.status == DependencyStatus.PERMISSION_ERROR:
            return f"🔒 {result.name.upper()} permission error: {result.error_message}"
        elif result.status == DependencyStatus.EXECUTION_ERROR:
            return f"💥 {result.name.upper()} execution error: {result.error_message}"
        else:
            return f"❓ {result.name.upper()} unknown error: {result.error_message}"
    
    def get_installation_instructions(self, dependency_name: str) -> Optional[str]:
        """Get formatted installation instructions for a dependency
        
        Args:
            dependency_name: Name of the dependency
            
        Returns:
            Formatted installation instructions or None
        """
        if dependency_name == 'tshark':
            guide = self.dependency_checker.get_tshark_installation_guide()
            return self._format_tshark_installation_guide(guide)
        
        return None
    
    def _format_tshark_installation_guide(self, guide: Dict[str, any]) -> str:
        """Format TShark installation guide for display
        
        Args:
            guide: Installation guide dictionary
            
        Returns:
            Formatted installation instructions
        """
        if not guide:
            return "No installation guide available for this platform."
        
        platform = guide.get('platform', 'Unknown')
        methods = guide.get('methods', [])
        
        instructions = [f"📋 TShark Installation Guide for {platform}:\n"]
        
        for i, method in enumerate(methods, 1):
            instructions.append(f"{i}. {method['name']}:")
            instructions.append(f"   {method['description']}")
            
            if method.get('commands'):
                instructions.append("   Commands:")
                for cmd in method['commands']:
                    instructions.append(f"   $ {cmd}")
            
            if method.get('url'):
                instructions.append(f"   URL: {method['url']}")
            
            instructions.append("")  # Empty line between methods
        
        # Add common paths information
        common_paths = guide.get('common_paths', [])
        if common_paths:
            instructions.append("🔍 Common installation paths to check:")
            for path in common_paths:
                instructions.append(f"   • {path}")
        
        return "\n".join(instructions)
    
    def print_validation_summary(self, result: ValidationResult) -> None:
        """Print validation summary to console
        
        Args:
            result: Validation result to display
        """
        if result.success:
            print("✅ All dependencies validated successfully!")
            return
        
        print("❌ Dependency validation failed!")
        print(f"Missing dependencies: {', '.join(result.missing_dependencies)}")
        print()
        
        # Print error messages
        for error in result.error_messages:
            print(error)
        print()
        
        # Print installation guides
        for dep_name, guide in result.installation_guides.items():
            instructions = self.get_installation_instructions(dep_name)
            if instructions:
                print(instructions)
                print()
        
        if not result.can_continue:
            print("⚠️  Application cannot continue without these dependencies.")
            print("Please install the missing dependencies and try again.")
        else:
            print("⚠️  Application can continue with limited functionality.")


def validate_startup_dependencies(custom_tshark_path: Optional[str] = None, 
                                strict_mode: bool = True) -> ValidationResult:
    """Convenience function for startup dependency validation
    
    Args:
        custom_tshark_path: Custom TShark executable path
        strict_mode: Whether to require all dependencies
        
    Returns:
        Validation result
    """
    validator = StartupDependencyValidator(custom_tshark_path=custom_tshark_path)
    return validator.validate_all_dependencies(strict_mode=strict_mode)


def validate_tshark_dependency(custom_tshark_path: Optional[str] = None) -> ValidationResult:
    """Convenience function for TShark-only validation
    
    Args:
        custom_tshark_path: Custom TShark executable path
        
    Returns:
        TShark validation result
    """
    validator = StartupDependencyValidator(custom_tshark_path=custom_tshark_path)
    return validator.validate_tshark_only()


if __name__ == "__main__":
    # Command-line validation for testing
    import argparse
    
    parser = argparse.ArgumentParser(description="Validate PktMask dependencies")
    parser.add_argument("--tshark-path", help="Custom TShark executable path")
    parser.add_argument("--strict", action="store_true", help="Strict mode (all deps required)")
    parser.add_argument("--tshark-only", action="store_true", help="Validate TShark only")
    
    args = parser.parse_args()
    
    if args.tshark_only:
        result = validate_tshark_dependency(custom_tshark_path=args.tshark_path)
    else:
        result = validate_startup_dependencies(
            custom_tshark_path=args.tshark_path,
            strict_mode=args.strict
        )
    
    validator = StartupDependencyValidator()
    validator.print_validation_summary(result)
    
    sys.exit(0 if result.success else 1)
