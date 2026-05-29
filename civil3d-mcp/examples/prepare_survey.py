"""
Standalone pre-processing script.

Usage:
    python prepare_survey.py input.csv output_ascii.csv

Can be called from the MCP tool run_python_script, or run independently
before launching Civil 3D.  Adds .B/.E figure codes to consecutive runs
of points sharing the same description, then writes ASCII PNEZD CSV.
"""

import sys
from pathlib import Path

# Allow running without installing the package
sys.path.insert(0, str(Path(__file__).parent.parent / "python-server" / "src"))

from civil3d_mcp.csv_utils import process_pipeline  # noqa: E402

if len(sys.argv) < 3:
    print("Usage: python prepare_survey.py <input_csv> <output_csv>")
    sys.exit(1)

inp = sys.argv[1]
out = sys.argv[2]
result = process_pipeline(inp, out, inject_codes=True)

print(f"Encoding detected : {result['input_encoding']}")
print(f"Columns           : {', '.join(result['columns_detected'])}")
print(f"Rows processed    : {result['rows_processed']}")
print(f"Output written    : {result['output_path']}")
