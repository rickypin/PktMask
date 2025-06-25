import os
import json
import logging
import sys
from pathlib import Path
from typing import Dict, Any, List

# --- Adjust sys.path to import from the src directory ---
# This allows the script to be run from the project root
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root / "src"))

try:
    from pktmask.core.trim.multi_stage_executor import MultiStageExecutor
    from pktmask.core.trim.stages.tshark_preprocessor import TSharkPreprocessor
    from pktmask.core.trim.stages.enhanced_pyshark_analyzer import EnhancedPySharkAnalyzer
    from pktmask.core.trim.stages.scapy_rewriter import ScapyRewriter
    from pktmask.core.trim.models.simple_execution_result import SimpleExecutionResult
except ImportError as e:
    print(f"Error: Failed to import PktMask components. Make sure the src directory is in your PYTHONPATH. Details: {e}")
    sys.exit(1)

# --- Configuration ---
SAMPLES_DIR = Path("tests/data/tls")
OUTPUT_DIR = Path(".tests_tls_trim/output")
TRIM_RESULTS_FILE = Path(".tests_tls_trim/output/trim_results.json")
TRIMMED_SUFFIX = "-TRIMMED"

# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s - %(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


def create_trim_pipeline(config: Dict[str, Any]) -> MultiStageExecutor:
    """Creates and configures the multi-stage trimming pipeline from a dictionary."""
    executor = MultiStageExecutor(work_dir=OUTPUT_DIR / "temp")

    trimming_config = config.get('payload_trimming', {})
    tshark_stage = TSharkPreprocessor(config=trimming_config.get('tshark_preprocessor', {}))
    pyshark_stage = EnhancedPySharkAnalyzer(config=trimming_config.get('pyshark_analyzer', {}))
    scapy_stage = ScapyRewriter(config=trimming_config.get('scapy_rewriter', {}))

    executor.register_stage(tshark_stage)
    executor.register_stage(pyshark_stage)
    executor.register_stage(scapy_stage)
    
    return executor


def run_trimming_process(sample_files: List[Path]) -> Dict[str, Any]:
    """
    Initializes and runs the multi-stage pipeline for a list of files.

    Args:
        sample_files: A list of pcap file paths to process.

    Returns:
        A dictionary containing the processing results for each file.
    """
    all_results: Dict[str, Any] = {}

    # Simplified dictionary-based configuration, bypassing AppConfig
    config = {
        "payload_trimming": {
            "enabled": True, 
            "mode": "enhanced", 
            "pyshark_analyzer": {"use_json": True, "default_mask_spec": "MaskAfter(5)"},
        }
    }

    try:
        pipeline = create_trim_pipeline(config)
    except Exception as e:
        logging.error(f"Failed to create trimming pipeline: {e}", exc_info=True)
        return {}

    for input_file in sample_files:
        logging.info(f"--- Trimming: {input_file.name} ---")
        output_filename = f"{input_file.stem}{TRIMMED_SUFFIX}{input_file.suffix}"
        output_path = OUTPUT_DIR / output_filename
        
        try:
            result: SimpleExecutionResult = pipeline.execute_pipeline(
                input_file=input_file, 
                output_file=output_path
            )
            
            final_stage_stats = result.stats.get("Scapy回写器", {})
            total_packets = final_stage_stats.get("total_packets", 0)
            modified_packets = final_stage_stats.get("modified_packets", 0)
            
            result_dict = {
                "input_file": str(input_file),
                "output_file": str(output_path),
                "success": result.success,
                "message": result.error or "Pipeline completed successfully.",
                "total_packets": total_packets,
                "modified_packets": modified_packets,
                "stats": result.stats,
            }
            all_results[input_file.name] = result_dict
            
            if result.success:
                logging.info(f"Successfully trimmed file to {output_path.name}")
            else:
                logging.error(f"Failed to trim {input_file.name}: {result.error}")

        except Exception as e:
            logging.error(f"An unexpected error occurred while processing {input_file.name}: {e}", exc_info=True)
            all_results[input_file.name] = {"success": False, "message": str(e)}
            
    return all_results


def main():
    """Main function to run the batch trimming process."""
    logging.info("Starting batch trimming process using MultiStageExecutor...")

    if not SAMPLES_DIR.is_dir():
        logging.error(f"Samples directory not found: {SAMPLES_DIR}")
        return

    OUTPUT_DIR.mkdir(exist_ok=True)
    (OUTPUT_DIR / "temp").mkdir(exist_ok=True)
    logging.info(f"Output will be saved to: {OUTPUT_DIR}")

    sample_files = sorted(
        list(SAMPLES_DIR.glob("*.pcap")) + list(SAMPLES_DIR.glob("*.pcapng"))
    )

    if not sample_files:
        logging.warning(f"No sample files found in {SAMPLES_DIR}")
        return

    logging.info(f"Found {len(sample_files)} sample files to trim.")
    
    trim_results = run_trimming_process(sample_files)

    logging.info(f"Writing trimming results to {TRIM_RESULTS_FILE}")
    with open(TRIM_RESULTS_FILE, "w") as f:
        json.dump(trim_results, f, indent=2)

    logging.info("Batch trimming process finished.")


if __name__ == "__main__":
    main()
