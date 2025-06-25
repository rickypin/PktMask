#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Debug Script for Offset Mismatch Investigation

This script is designed to investigate the root cause of the payload masking
failure by comparing the packet structures as seen by the key components
of the Enhanced Trimmer.

Diagnosis:
The failure is suspected to be an offset mismatch between the offset
calculated by `EnhancedPySharkAnalyzer` (which works on a TShark-recombined
pcap) and the offset interpretation by `BlindPacketMasker` (which works on
the original pcap).

This script will:
1.  Run the TShark preprocessing to generate the recombined file.
2.  Run the EnhancedPySharkAnalyzer to generate the `MaskingRecipe`.
3.  Isolate a specific problematic packet (e.g., packet #14) from both the
    original and recombined pcaps.
4.  Print a side-by-side comparison of `packet[TCP].payload` from both
    files to expose any discrepancies found by Scapy.
5.  Provide instructions for step-debugging the `BlindPacketMasker` with
    the generated recipe.
"""
import logging
import os
import shutil
import tempfile
from pathlib import Path
from typing import Dict, Optional
from dataclasses import asdict
import json

# --- Path Setup ---
import sys
# Add project root to path to allow absolute imports from src
sys.path.insert(0, str(Path(__file__).resolve().parent))
# --- End Path Setup ---

# Configure logging for visibility
logging.basicConfig(
    level=logging.DEBUG,
    format="[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
)
# Quieten down chatty libraries
logging.getLogger("pyshark").setLevel(logging.WARNING)
logging.getLogger("scapy").setLevel(logging.WARNING)

# PktMask Core Imports
# Ensure the script is run from the project root, or adjust sys.path as needed
from scapy.all import rdpcap
from src.pktmask.core.trim.stages.tshark_preprocessor import TSharkPreprocessor
from src.pktmask.core.trim.stages.enhanced_pyshark_analyzer import EnhancedPySharkAnalyzer
from src.pktmask.core.trim.stages.tcp_payload_masker_adapter import TcpPayloadMaskerAdapter
from src.pktmask.core.trim.multi_stage_executor import StageContext
from src.pktmask.config.settings import AppConfig
from src.pktmask.config.defaults import get_tshark_paths

# --- SCRIPT CONFIGURATION ---
# The problematic PCAP file
INPUT_PCAP_PATH = Path("tests/data/tls/tls_1_2_plainip.pcap")

# The specific packet to analyze (0-indexed)
# Packet #14 in Wireshark is index 13 here.
TARGET_PACKET_INDEX = 13

# Create a temporary directory for outputs
TEMP_DIR = Path(tempfile.mkdtemp(prefix="pktmask_debug_"))


def find_corresponding_packet_index(
    original_pcap: Path, reassembled_pcap: Path, original_index: int
) -> Optional[int]:
    """
    Finds the index of the packet in the reassembled file that corresponds
    to the packet at original_index in the original file, using timestamps.
    NOTE: This is a simplified version of the logic in EnhancedPySharkAnalyzer.
    """
    import pyshark

    try:
        orig_packets = pyshark.FileCapture(str(original_pcap), keep_packets=False)
        target_timestamp = orig_packets[original_index].sniff_timestamp
        orig_packets.close()

        re_packets = pyshark.FileCapture(str(reassembled_pcap), keep_packets=False)
        for i, pkt in enumerate(re_packets):
            if pkt.sniff_timestamp == target_timestamp:
                re_packets.close()
                return i
        re_packets.close()
    except Exception as e:
        logging.error(f"Pyshark based mapping failed: {e}")
    return None


def main():
    """Main execution function"""
    log = logging.getLogger("DEBUG_SCRIPT")
    log.info(f"Temporary output directory: {TEMP_DIR}")

    # --- Setup paths ---
    original_pcap = INPUT_PCAP_PATH
    recombined_pcap = TEMP_DIR / "recombined.pcap"
    masked_pcap = TEMP_DIR / "masked_output.pcap"
    recipe_path = TEMP_DIR / "masking_recipe.json"

    # --- Step 1: TShark Preprocessing ---
    log.info("--- Step 1: Running TShark Preprocessor ---")
    try:
        # Get TShark settings from the default AppConfig and convert to dict
        app_config = AppConfig.default()
        stage_config = asdict(app_config.tools.tshark)

        tshark_stage = TSharkPreprocessor(config=stage_config)
        context = StageContext(
            input_file=original_pcap,
            output_file=recombined_pcap,
            work_dir=TEMP_DIR,
        )
        tshark_stage.initialize()
        result = tshark_stage.execute(context)
        if not result.success:
            log.error("TShark preprocessing failed. Aborting.")
            return

        # FIX: The TShark stage creates its own output file. Get the actual path from the context.
        recombined_pcap = context.tshark_output
        log.info(f"TShark preprocessing successful. Recombined file at: {recombined_pcap}")
    except Exception as e:
        log.error(f"An error occurred during TShark preprocessing: {e}", exc_info=True)
        return

    # --- Step 2: EnhancedPySharkAnalyzer ---
    log.info("--- Step 2: Running EnhancedPySharkAnalyzer ---")
    analyzer_stage = EnhancedPySharkAnalyzer()
    # The context now contains the tshark_output path from the previous step
    context.output_file = masked_pcap # Set a final output for the full chain
    analyzer_stage.initialize()
    result = analyzer_stage.execute(context)
    if not result.success:
        log.error("EnhancedPySharkAnalyzer failed. Aborting.")
        return

    masking_recipe = context.masking_recipe
    log.info("EnhancedPySharkAnalyzer finished.")
    
    # Save the recipe for inspection and for the next stage
    with open(recipe_path, "w") as f:
        f.write(json.dumps(asdict(masking_recipe), indent=2))
    log.info(f"Masking recipe saved to: {recipe_path}")

    packet_instructions = masking_recipe.get_instructions_for_packet(TARGET_PACKET_INDEX)
    log.info(
        f"Instructions for original packet #{TARGET_PACKET_INDEX}: {packet_instructions}"
    )
    if not packet_instructions:
        log.warning("No instructions were generated for the target packet.")

    # --- Step 3: Direct Packet Comparison ---
    log.info("--- Step 3: Direct Comparison of TCP Payloads ---")
    log.info("Comparing packet interpretation by Scapy between original and recombined files.")

    original_packets = rdpcap(str(original_pcap))
    recombined_packets = rdpcap(str(recombined_pcap))

    # Find the corresponding packet in the recombined file
    reassembled_idx = find_corresponding_packet_index(
        original_pcap, recombined_pcap, TARGET_PACKET_INDEX
    )

    if reassembled_idx is None:
        log.error("Could not map target packet to recombined file. Comparison aborted.")
    else:
        log.info(f"Original packet {TARGET_PACKET_INDEX} corresponds to recombined packet {reassembled_idx}")
        
        orig_pkt = original_packets[TARGET_PACKET_INDEX]
        re_pkt = recombined_packets[reassembled_idx]

        from scapy.all import TCP, Raw

        orig_payload = orig_pkt[TCP].payload if orig_pkt.haslayer(TCP) else None
        re_payload = re_pkt[TCP].payload if re_pkt.haslayer(TCP) else None

        orig_payload_bytes = bytes(orig_payload) if orig_payload else b""
        re_payload_bytes = bytes(re_payload) if re_payload else b""

        log.info(f"----- Comparison for Packet #{TARGET_PACKET_INDEX} -----")
        log.info(f"Original Packet Summary:      {orig_pkt.summary()}")
        log.info(f"Recombined Packet Summary:    {re_pkt.summary()}")
        log.info("")
        log.info(f"Original TCP Payload Type:    {type(orig_payload)}")
        log.info(f"Recombined TCP Payload Type:  {type(re_payload)}")
        log.info("")
        log.info(f"Original TCP Payload Length:  {len(orig_payload_bytes)}")
        log.info(f"Recombined TCP Payload Length: {len(re_payload_bytes)}")

        if len(orig_payload_bytes) != len(re_payload_bytes):
            log.warning("!!! PAYLOAD LENGTH MISMATCH DETECTED !!!")
        
        if orig_payload_bytes != re_payload_bytes:
            log.warning("!!! PAYLOAD CONTENT MISMATCH DETECTED !!!")
            # You can print the bytes here for a full diff if needed
            # log.debug(f"Original Bytes:   {orig_payload_bytes.hex()}")
            # log.debug(f"Recombined Bytes: {re_payload_bytes.hex()}")

    # --- Step 4: How to Debug BlindPacketMasker ---
    log.info("--- Step 4: Instructions for Live Debugging ---")
    log.info(
        "To debug the BlindPacketMasker, you can now run the final stage. "
        "The following code snippet shows how to do this."
    )
    log.info(
        "Place a breakpoint inside `src/pktmask/core/tcp_payload_masker/core/blind_masker.py` "
        "in the `_process_packet` method (around line 95)."
    )
    log.info("Then, uncomment and run the code block below.")

    # UNCOMMENT THE BLOCK BELOW TO RUN THE MASKER
    log.info("--- Running TcpPayloadMaskerAdapter (DEBUG) ---")
    try:
        # Ensure you have the context from the analyzer step
        # It already contains the masking_recipe and correct file paths
        masker_stage = TcpPayloadMaskerAdapter()
        masker_stage.initialize()

        # --- SET BREAKPOINT in blind_masker.py BEFORE this line ---
        import pdb; pdb.set_trace()
        # When debugger stops, you can inspect:
        # - packet (the packet being processed)
        # - raw(packet[TCP].payload) (to see its payload)
        # - instructions (the recipe for this packet)

        result = masker_stage.execute(context)
        if result.success:
            log.info(f"Masking stage finished. Output at: {masked_pcap}")
            log.info(f"Stats: {result.data}")
        else:
            log.error(f"Masking stage failed: {result.error}")

    except Exception as e:
        log.error(f"An error occurred during masking stage: {e}", exc_info=True)


if __name__ == "__main__":
    try:
        main()
    finally:
        # Clean up the temporary directory
        # shutil.rmtree(TEMP_DIR)
        # log.info(f"Cleaned up temporary directory: {TEMP_DIR}")
        print(f"Temporary files are in {TEMP_DIR}. Please clean up manually.") 