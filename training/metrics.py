"""Evaluation metrics include malformed outputs as failed predictions."""
from src.schemas import Mode


def summarize(rows):
    total = len(rows)
    if not total:
        raise ValueError("评估记录不能为空")
    valid = risk_correct = conversions = conversion_correct = 0
    for row in rows:
        parsed, expected = row["parsed"], row["expected"]
        is_conversion = row["request"]["mode"] == Mode.CONVERT.value
        conversions += int(is_conversion)
        if parsed is not None:
            valid += 1
            risk_correct += int(parsed["risk_level"] == expected["risk_level"])
            if is_conversion:
                conversion_correct += int(parsed["converted_command"] == expected["converted_command"])
    return {
        "total": total,
        "valid_json_count": valid,
        "valid_json_rate": valid / total,
        "risk_correct_count": risk_correct,
        "risk_accuracy": risk_correct / total,
        "conversion_total": conversions,
        "conversion_correct_count": conversion_correct,
        "conversion_exact_match": conversion_correct / conversions if conversions else None,
    }
