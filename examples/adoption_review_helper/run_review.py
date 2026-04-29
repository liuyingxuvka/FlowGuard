"""Run the adoption-review helper classification model."""

from __future__ import annotations

from pathlib import Path
import importlib.util
import sys


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from flowguard.review import review_scenarios


def _load_model():
    model_path = Path(__file__).with_name("model.py")
    spec = importlib.util.spec_from_file_location("adoption_review_helper_model", model_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load model from {model_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def main() -> int:
    model = _load_model()
    report = review_scenarios(model.scenarios())
    print("=== flowguard adoption review helper model ===")
    print(report.format_text(max_counterexamples=2))
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
