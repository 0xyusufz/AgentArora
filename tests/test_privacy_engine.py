import json
import sys
from pathlib import Path

# Add project root path to sys.path to resolve imports cleanly
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT_DIR))

from src.detector import evaluate_item

# Path to the JSON benchmark file
JSON_BENCHMARK_PATH = Path(__file__).resolve().parent / "benchmark_data.json"
with open(JSON_BENCHMARK_PATH, "r", encoding="utf-8") as _benchmark_file:
    BENCHMARK_DATASET = json.load(_benchmark_file)


def load_benchmark_dataset():
    """Loads the benchmark dataset from benchmark_data.json."""
    if JSON_BENCHMARK_PATH.exists():
        with open(JSON_BENCHMARK_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    else:
        raise FileNotFoundError(
            f"Could not find benchmark file at: {JSON_BENCHMARK_PATH}"
        )


def run_benchmark_audit():
    """
    Executes precision and recall checks across all 8 taxonomy categories
    and prints a formatted summary audit report.
    """
    benchmark_dataset = load_benchmark_dataset()

    print("=" * 75)
    print(" AGENTARORA PRIVACY ENGINE - BENCHMARK EXECUTION REPORT ")
    print("=" * 75)

    total_tp, total_fp, total_tn, total_fn = 0, 0, 0, 0

    for category, cases in benchmark_dataset.items():
        positives = cases.get("positive", [])
        negatives = cases.get("negative", [])

        # Evaluate Positive Cases (True Positives vs False Negatives)
        tp = sum(1 for item in positives if evaluate_item(category, item))
        fn = len(positives) - tp

        # Evaluate Negative Cases (True Negatives vs False Positives)
        fp = sum(1 for item in negatives if evaluate_item(category, item))
        tn = len(negatives) - fp

        total_tp += tp
        total_fn += fn
        total_fp += fp
        total_tn += tn

        recall = (tp / len(positives)) * 100 if positives else 0.0
        precision = (tp / (tp + fp)) * 100 if (tp + fp) > 0 else 100.0

        status = "PASSED" if (fn == 0 and fp == 0) else "FAILED"
        print(
            f"[{status}] Category: {category.upper():<10} | "
            f"Recall: {recall:6.1f}% | Precision: {precision:6.1f}% | "
            f"(FN: {fn}, FP: {fp})"
        )

    print("-" * 75)
    overall_recall = (
        (total_tp / (total_tp + total_fn)) * 100
        if (total_tp + total_fn) > 0
        else 0.0
    )
    overall_precision = (
        (total_tp / (total_tp + total_fp)) * 100
        if (total_tp + total_fp) > 0
        else 0.0
    )

    print("OVERALL SUMMARY METRICS:")
    print(
        f" Total Positive Tests (Recall Check)   : {total_tp}/{total_tp + total_fn} Passed ({overall_recall:.1f}%)"
    )
    print(
        f" Total Negative Tests (Precision Check): {total_tn}/{total_tn + total_fp} Passed"
    )
    print(
        f" Overall Engine Precision Metric       : {overall_precision:.1f}%"
    )
    print("=" * 75)

    if total_fn == 0 and total_fp == 0:
        print("AUDIT VERDICT: ALL BENCHMARK TEST CASES PASSED (100% SUCCESS).")
    else:
        print("AUDIT VERDICT: DETECTION RULES REQUIRED CALIBRATION.")


if __name__ == "__main__":
    run_benchmark_audit()