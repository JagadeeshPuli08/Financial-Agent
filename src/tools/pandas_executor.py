from datetime import date, datetime
import math

import numpy as np
import pandas as pd


_SAFE_BUILTINS = {
    "abs": abs,
    "all": all,
    "any": any,
    "bool": bool,
    "dict": dict,
    "enumerate": enumerate,
    "float": float,
    "int": int,
    "len": len,
    "list": list,
    "max": max,
    "min": min,
    "range": range,
    "round": round,
    "sorted": sorted,
    "str": str,
    "sum": sum,
    "tuple": tuple,
    "zip": zip,
}


def execute_pandas_code(code: str, user_df: pd.DataFrame):
    try:
        local_variables = {
            "user_df": user_df.copy(),
            "pd": pd,
        }

        exec(code, {"__builtins__": _SAFE_BUILTINS.copy()}, local_variables)

        if "result" not in local_variables:
            raise ValueError(
                "Generated code did not produce a result variable."
            )

        result = local_variables["result"]

        return {
            "status": "success",
            "result": normalize_result(result),
            "error": None,
        }
    except Exception as exc:
        return {
            "status": "error",
            "result": None,
            "error": str(exc),
        }


def normalize_result(result):
    if result is None or isinstance(result, str):
        return result

    if isinstance(result, pd.DataFrame):
        return normalize_result(result.to_dict(orient="records"))

    if isinstance(result, pd.Series):
        return normalize_result(result.to_dict())

    if result is pd.NA or result is pd.NaT:
        return None

    if isinstance(result, np.ndarray):
        return normalize_result(result.tolist())

    if isinstance(result, np.generic):
        return normalize_result(result.item())

    if isinstance(result, (pd.Timestamp, pd.Timedelta, datetime, date)):
        return result.isoformat()

    if isinstance(result, bool):
        return result

    if isinstance(result, float):
        return result if math.isfinite(result) else None

    if isinstance(result, int):
        return float(result)

    if isinstance(result, dict):
        normalized = {}
        for key, value in result.items():
            normalized_key = normalize_result(key)
            if normalized_key is not None and not isinstance(
                normalized_key, (str, int, float, bool)
            ):
                normalized_key = str(key)
            normalized[normalized_key] = normalize_result(value)
        return normalized

    if isinstance(result, (list, tuple)):
        return [normalize_result(value) for value in result]

    raise TypeError(
        f"Unsupported result type: {type(result)}"
    )