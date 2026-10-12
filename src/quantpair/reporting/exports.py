"""CSV/JSON exports and the experiment log (reports/experiments.jsonl)."""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import platform
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import quantpair

REPORTS_DIR = Path(__file__).resolve().parents[3] / "reports"
EXPERIMENT_LOG = REPORTS_DIR / "experiments.jsonl"


def to_jsonable(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {str(k): to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [to_jsonable(v) for v in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating, float)):
        return None if not math.isfinite(float(obj)) else float(obj)
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    if isinstance(obj, (pd.Timestamp, dt.date, dt.datetime)):
        return str(obj)[:10] if not pd.isna(obj) else None
    if obj is pd.NaT:
        return None
    return obj


def csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=not isinstance(df.index, pd.RangeIndex)).encode()


def json_bytes(obj: Any) -> bytes:
    return json.dumps(to_jsonable(obj), indent=2).encode()


def environment_info() -> dict:
    import scipy
    import statsmodels
    return {"quantpair": quantpair.__version__, "python": platform.python_version(),
            "pandas": pd.__version__, "numpy": np.__version__, "scipy": scipy.__version__,
            "statsmodels": statsmodels.__version__}


def make_experiment(config: dict, data_info: dict, results: dict) -> dict:
    cfg_hash = hashlib.sha1(json.dumps(to_jsonable(config), sort_keys=True).encode()).hexdigest()[:8]
    ts = dt.datetime.now().isoformat(timespec="seconds")
    return {"id": f"{ts[:10]}-{cfg_hash}-{ts[11:].replace(':', '')}", "timestamp": ts,
            "config": config, "data": data_info, "results": results, "environment": environment_info()}


def save_experiment(record: dict, path: Path = EXPERIMENT_LOG) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(to_jsonable(record)) + "\n")


def load_experiments(path: Path = EXPERIMENT_LOG) -> list[dict]:
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out
