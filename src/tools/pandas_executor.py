import pandas as pd
def execute_pandas_code(code: str, user_df: pd.DataFrame):

    try:
        local_variables = {
            "user_df": user_df.copy(),
            "pd": pd
        }

        exec(code, {"__builtins__": {}}, local_variables)

        if "result" not in local_variables:
            raise ValueError(
                "Generated code did not produce a result variable."
            )

        result = local_variables["result"]

        return {
            "status": "success",
            "result": normalize_result(result),
            "error": None
        }

    except Exception as exc:

        return {
            "status": "error",
            "result": None,
            "error": str(exc)
        }


def normalize_result(result):

    if isinstance(result, pd.DataFrame):
        return result.to_dict(orient="records")

    if isinstance(result, pd.Series):
        return result.to_dict()

    if isinstance(result, (int, float)):
        return float(result)

    if isinstance(result, dict):
        return result

    raise TypeError(
        f"Unsupported result type: {type(result)}"
    )