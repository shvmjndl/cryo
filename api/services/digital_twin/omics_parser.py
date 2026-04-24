from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd


def load_omics_payload(patient_omics_profile_path: str | None) -> dict[str, Any]:
    """Load optional omics input from JSON or tabular text files."""
    if not patient_omics_profile_path:
        return {}

    path = Path(patient_omics_profile_path)
    if not path.exists():
        return {
            "path": patient_omics_profile_path,
            "error": "Omics file not found",
        }

    suffix = path.suffix.lower()
    if suffix == ".json":
        data = json.loads(path.read_text())
        return {
            "path": str(path),
            "format": "json",
            "data": data,
        }

    if suffix in {".csv", ".tsv", ".txt"}:
        sep = "\t" if suffix in {".tsv", ".txt"} else ","
        frame = pd.read_csv(path, sep=sep)
        return {
            "path": str(path),
            "format": "table",
            "columns": list(frame.columns),
            "rows": frame.head(25).to_dict(orient="records"),
            "row_count": int(frame.shape[0]),
        }

    return {
        "path": str(path),
        "error": f"Unsupported omics file type: {suffix}",
    }
