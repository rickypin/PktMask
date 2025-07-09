"""
Unified ProcessorStage base class

Combines the best of StageBase and BaseProcessor interfaces to eliminate
the need for adapter layers in desktop applications.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Union
from pathlib import Path
from dataclasses import dataclass

from .models import StageStats


@dataclass
class StageResult:
    """Unified stage processing result"""
    success: bool
    stats: Dict[str, Any]
    error: Optional[str] = None

    def __bool__(self):
        return self.success


class ProcessorStage(ABC):
    """Unified processor stage base class
    
    This class combines the interfaces of StageBase and BaseProcessor
    to eliminate the need for adapter layers. It's optimized for desktop
    applications with:
    - Lazy initialization for faster startup
    - Minimal overhead
    - Direct integration
    - Simple error handling
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self._initialized = False
        self._stats = {}
    
    @property
    def name(self) -> str:
        """Get processor name"""
        return self.__class__.__name__
    
    @property
    def is_initialized(self) -> bool:
        """Check if processor is initialized"""
        return self._initialized
    
    @abstractmethod
    def initialize(self) -> bool:
        """Initialize processor
        
        Returns:
            bool: True if initialization successful, False otherwise
        """
        pass
    
    @abstractmethod
    def process_file(self, input_path: Union[str, Path], output_path: Union[str, Path]) -> Union[StageResult, StageStats]:
        """Process file - core method

        Args:
            input_path: Input file path
            output_path: Output file path

        Returns:
            StageResult or StageStats: Processing result
        """
        pass
    
    def get_required_tools(self) -> List[str]:
        """Get required tools list
        
        Returns:
            List[str]: List of required external tools
        """
        return []
    
    def get_display_name(self) -> str:
        """Get user-friendly display name"""
        return self.name
    
    def get_description(self) -> str:
        """Get processor description"""
        return f"{self.get_display_name()} processor"
    
    def validate_inputs(self, input_path: Union[str, Path], output_path: Union[str, Path]) -> bool:
        """Validate input parameters"""
        input_file = Path(input_path)
        if not input_file.exists():
            raise FileNotFoundError(f"Input file does not exist: {input_path}")
        
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        return True
    
    def get_stats(self) -> Dict[str, Any]:
        """Get processing statistics"""
        return self._stats.copy()
    
    def reset_stats(self):
        """Reset statistics"""
        self._stats.clear()
    
    def stop(self) -> None:
        """Stop processing (for cancellation)"""
        pass
    
    # StageBase compatibility methods
    def prepare_for_directory(self, directory: Union[str, Path], all_files: List[str]) -> None:
        """Prepare for directory processing (StageBase compatibility)"""
        pass
    
    def finalize_directory_processing(self) -> Optional[Dict]:
        """Finalize directory processing (StageBase compatibility)"""
        return None
    
    # Helper methods for result conversion
    def _create_stage_stats(self, packets_processed: int = 0, packets_modified: int = 0, 
                           duration_ms: float = 0.0, extra_metrics: Optional[Dict] = None) -> StageStats:
        """Create StageStats from processing results"""
        return StageStats(
            stage_name=self.name,
            packets_processed=packets_processed,
            packets_modified=packets_modified,
            duration_ms=duration_ms,
            extra_metrics=extra_metrics or {}
        )
    
    def _create_stage_result(self, success: bool, stats: Optional[Dict] = None,
                              error: Optional[str] = None) -> StageResult:
        """Create StageResult from processing results"""
        return StageResult(
            success=success,
            stats=stats or {},
            error=error
        )


class DirectProcessorStage(ProcessorStage):
    """Direct processor stage implementation
    
    This class provides a direct implementation that can wrap existing
    processors without the need for adapters.
    """
    
    def __init__(self, processor_class, config: Dict[str, Any]):
        super().__init__(config)
        self._processor_class = processor_class
        self._processor = None
    
    def initialize(self) -> bool:
        """Initialize the wrapped processor"""
        if self._initialized:
            return True
        
        try:
            # Import processor config if needed
            from ..processors.base_processor import ProcessorConfig
            processor_config = ProcessorConfig(
                enabled=True,
                name=self.config.get('name', self.name),
                priority=self.config.get('priority', 1)
            )
            
            self._processor = self._processor_class(processor_config)
            self._initialized = self._processor.initialize()
            return self._initialized
        except Exception as e:
            print(f"Failed to initialize {self.name}: {e}")
            return False
    
    def process_file(self, input_path: Union[str, Path], output_path: Union[str, Path]) -> StageStats:
        """Process file using the wrapped processor"""
        if not self._initialized and not self.initialize():
            raise RuntimeError(f"{self.name} not initialized")
        
        self.validate_inputs(input_path, output_path)
        
        # Call the wrapped processor
        result = self._processor.process_file(str(input_path), str(output_path))
        
        if not result.success:
            raise RuntimeError(f"Processing failed: {result.error}")
        
        # Convert to StageStats
        return self._create_stage_stats(
            packets_processed=result.stats.get('packets_processed', 0),
            packets_modified=result.stats.get('packets_modified', 0),
            duration_ms=result.stats.get('duration_ms', 0.0),
            extra_metrics=result.stats
        )
    
    def get_required_tools(self) -> List[str]:
        """Get required tools from wrapped processor"""
        if self._processor and hasattr(self._processor, 'get_required_tools'):
            return self._processor.get_required_tools()
        return []
    
    def get_display_name(self) -> str:
        """Get display name from wrapped processor"""
        if self._processor and hasattr(self._processor, 'get_display_name'):
            return self._processor.get_display_name()
        return super().get_display_name()
    
    def get_description(self) -> str:
        """Get description from wrapped processor"""
        if self._processor and hasattr(self._processor, 'get_description'):
            return self._processor.get_description()
        return super().get_description()
    
    def stop(self) -> None:
        """Stop the wrapped processor"""
        if self._processor and hasattr(self._processor, 'stop'):
            self._processor.stop()
        super().stop()


# Factory function for easy creation
def create_processor_stage(processor_class, config: Dict[str, Any]) -> ProcessorStage:
    """Create a ProcessorStage from a processor class
    
    Args:
        processor_class: The processor class to wrap
        config: Configuration dictionary
        
    Returns:
        ProcessorStage: A unified processor stage
    """
    return DirectProcessorStage(processor_class, config)
