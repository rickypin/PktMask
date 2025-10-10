# Shared PyInstaller configuration fragments for PktMask
# Keep this file minimal to avoid duplication across spec files.

# Data files bundled into the application
common_datas = [
    ("config/templates/log_template.html", "resources"),
    ("config/templates/summary.md", "resources"),
    ("config/templates/config_template.yaml", "resources"),
    ("config/templates/tls_flow_analysis_template.html", "resources"),
]

# Hidden imports commonly required across platforms
common_hiddenimports = [
    # Keep hidden imports minimal and high-level; rely on pyinstaller-hooks-contrib
    "markdown",
    "pydantic",
    "pydantic_core",
    "yaml",
    "typing_extensions",
    "annotated_types",
    "scapy",
]
