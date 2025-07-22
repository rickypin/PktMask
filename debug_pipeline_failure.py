#!/usr/bin/env python3
"""
Debug script to investigate intermittent pipeline processing failures.

This script will:
1. Create a test environment with sample files
2. Run the pipeline multiple times to reproduce the issue
3. Add detailed logging to identify where processing stops
4. Analyze the stage execution flow
"""

import os
import sys
import tempfile
import shutil
import logging
from pathlib import Path
from typing import Dict, Any

# Add the src directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Configure detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('debug_pipeline.log', mode='w')
    ]
)

logger = logging.getLogger('PipelineDebug')

def create_test_environment():
    """Create a temporary test environment with sample files"""
    test_dir = Path(tempfile.mkdtemp(prefix="pktmask_debug_"))
    logger.info(f"Created test directory: {test_dir}")

    # Look for real PCAP files in test samples
    sample_locations = [
        "tests/samples/tls-single/tls_sample.pcap",
        "tests/samples/http-single",
        "tests/samples/dups",
        "tests/samples/http",
        "tests/samples/tls-collector"
    ]

    copied_files = []

    # Copy individual files
    for sample_path in sample_locations:
        if os.path.isfile(sample_path) and sample_path.endswith(('.pcap', '.pcapng')):
            dest_file = test_dir / os.path.basename(sample_path)
            shutil.copy2(sample_path, dest_file)
            copied_files.append(str(dest_file))
            logger.info(f"Copied {sample_path} -> {dest_file}")

    # Copy files from directories
    for sample_dir in sample_locations:
        if os.path.isdir(sample_dir):
            for file_path in Path(sample_dir).glob("*.pcap*"):
                if file_path.is_file():
                    dest_file = test_dir / file_path.name
                    shutil.copy2(file_path, dest_file)
                    copied_files.append(str(dest_file))
                    logger.info(f"Copied {file_path} -> {dest_file}")
                    # Limit to 2 files to avoid too many test files
                    if len(copied_files) >= 2:
                        break
        if len(copied_files) >= 2:
            break

    if not copied_files:
        logger.error("No real PCAP files found in test samples")
        raise RuntimeError("Cannot run debug without real PCAP files")

    return test_dir, copied_files

def create_test_config():
    """Create test configuration for all three stages"""
    return {
        "remove_dupes": {"enabled": True},
        "anonymize_ips": {"enabled": True}, 
        "mask_payloads": {"enabled": True, "protocol": "tls", "mode": "enhanced"}
    }

def debug_pipeline_executor(config: Dict[str, Any]):
    """Debug the PipelineExecutor creation and stage initialization"""
    logger.info("=== DEBUGGING PIPELINE EXECUTOR ===")
    
    try:
        from pktmask.core.pipeline.executor import PipelineExecutor
        logger.info("Successfully imported PipelineExecutor")
        
        # Create executor
        executor = PipelineExecutor(config)
        logger.info(f"Created PipelineExecutor with {len(executor.stages)} stages")
        
        # Debug each stage
        for i, stage in enumerate(executor.stages):
            logger.info(f"Stage {i}: {stage.__class__.__name__} - {stage.name}")
            logger.info(f"  Initialized: {stage._initialized}")
            logger.info(f"  Config: {getattr(stage, 'config', 'N/A')}")
        
        return executor
        
    except Exception as e:
        logger.error(f"Failed to create PipelineExecutor: {e}")
        import traceback
        traceback.print_exc()
        return None

def debug_single_file_processing(executor, input_file: str, output_dir: str):
    """Debug processing of a single file"""
    logger.info(f"=== DEBUGGING SINGLE FILE: {input_file} ===")
    
    try:
        input_path = Path(input_file)
        output_path = Path(output_dir) / f"{input_path.stem}_processed{input_path.suffix}"
        
        logger.info(f"Input: {input_path}")
        logger.info(f"Output: {output_path}")
        logger.info(f"Input exists: {input_path.exists()}")
        logger.info(f"Input size: {input_path.stat().st_size if input_path.exists() else 'N/A'} bytes")
        
        # Add progress callback for detailed monitoring
        def progress_callback(stage, stats):
            logger.info(f"PROGRESS: Stage {stage.name} completed")
            logger.info(f"  Stats: {stats}")
        
        # Execute pipeline
        result = executor.run(input_file, str(output_path), progress_cb=progress_callback)
        
        logger.info(f"Pipeline result: {result}")
        logger.info(f"Success: {result.success}")
        logger.info(f"Errors: {result.errors}")
        logger.info(f"Stage count: {len(result.stage_stats)}")
        
        for i, stage_stats in enumerate(result.stage_stats):
            logger.info(f"  Stage {i}: {stage_stats.stage_name}")
            logger.info(f"    Processed: {stage_stats.packets_processed}")
            logger.info(f"    Modified: {stage_stats.packets_modified}")
            logger.info(f"    Duration: {stage_stats.duration_ms}ms")
            logger.info(f"    Extra: {stage_stats.extra_metrics}")
        
        # Check output file
        if output_path.exists():
            logger.info(f"Output file created: {output_path}")
            logger.info(f"Output size: {output_path.stat().st_size} bytes")
        else:
            logger.warning(f"Output file NOT created: {output_path}")
        
        return result
        
    except Exception as e:
        logger.error(f"Failed to process file {input_file}: {e}")
        import traceback
        traceback.print_exc()
        return None

def run_multiple_iterations(executor, test_files: list, output_dir: str, iterations: int = 3):
    """Run multiple iterations to reproduce intermittent issues"""
    logger.info(f"=== RUNNING {iterations} ITERATIONS ===")
    
    results = []
    for iteration in range(iterations):
        logger.info(f"\n--- ITERATION {iteration + 1} ---")
        
        iteration_results = []
        for test_file in test_files:
            result = debug_single_file_processing(executor, test_file, output_dir)
            iteration_results.append({
                'file': test_file,
                'result': result,
                'success': result.success if result else False,
                'stage_count': len(result.stage_stats) if result else 0
            })
        
        results.append(iteration_results)
        
        # Brief pause between iterations
        import time
        time.sleep(1)
    
    # Analyze results
    logger.info("\n=== ITERATION ANALYSIS ===")
    for i, iteration_results in enumerate(results):
        logger.info(f"Iteration {i + 1}:")
        for file_result in iteration_results:
            logger.info(f"  {os.path.basename(file_result['file'])}: "
                       f"Success={file_result['success']}, "
                       f"Stages={file_result['stage_count']}")
    
    return results

def main():
    """Main debug function"""
    logger.info("Starting PktMask Pipeline Debug Session")
    
    try:
        # Create test environment
        test_dir, test_files = create_test_environment()
        output_dir = test_dir / "output"
        output_dir.mkdir(exist_ok=True)
        
        # Create test configuration
        config = create_test_config()
        logger.info(f"Test config: {config}")
        
        # Debug executor creation
        executor = debug_pipeline_executor(config)
        if not executor:
            logger.error("Failed to create executor, aborting")
            return
        
        # Run multiple iterations
        results = run_multiple_iterations(executor, test_files, str(output_dir))
        
        # Summary
        logger.info("\n=== FINAL SUMMARY ===")
        logger.info(f"Test directory: {test_dir}")
        logger.info(f"Log file: debug_pipeline.log")
        logger.info("Check the log file for detailed execution traces")
        
    except Exception as e:
        logger.error(f"Debug session failed: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Keep test directory for manual inspection
        logger.info(f"Test directory preserved: {test_dir}")

if __name__ == "__main__":
    main()
