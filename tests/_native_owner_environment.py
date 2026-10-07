"""Real current native-owner identities for isolated subprocess regression fixtures."""
from __future__ import annotations
import os
import sys
from pathlib import Path
from flowguard.model_regressions import (
    ModelRegressionManifest, resolve_entry_input_inventory,
    build_regression_model_instance, input_inventory_fingerprint,
)
from flowguard.native_case_protocol import fingerprint_payload


def native_owner_environment(root: Path, owner_id: str, output_dir: Path) -> dict[str, str]:
    root = root.resolve()
    manifest = ModelRegressionManifest.load(root)
    entry = next(row for row in manifest.entries if row.model_id == owner_id)
    inventory = resolve_entry_input_inventory(root, entry,
        additional_patterns=manifest.owner_patterns_for(owner_id))
    instance = build_regression_model_instance(root, entry, inventory)
    assert entry.purpose_closure is not None
    input_fp = input_inventory_fingerprint(inventory)
    env = dict(os.environ)
    env.pop("GIT_INDEX_FILE", None)
    env.update({
        "FLOWGUARD_PROJECT_ROOT": str(root), "FLOWGUARD_MODEL_ID": owner_id,
        "FLOWGUARD_OUTPUT_DIR": str(output_dir.resolve()),
        "FLOWGUARD_INPUT_FINGERPRINT": input_fp,
        "FLOWGUARD_MODEL_FINGERPRINT": entry.purpose_closure.model_sha256,
        "FLOWGUARD_MODEL_INSTANCE_FINGERPRINT": instance.fingerprint,
        "FLOWGUARD_CODE_FINGERPRINT": fingerprint_payload({"model": entry.purpose_closure.model_sha256, "inputs": input_fp}),
        "FLOWGUARD_TEST_FINGERPRINT": entry.purpose_closure.runner_sha256,
        "FLOWGUARD_TOOLCHAIN_FINGERPRINT": fingerprint_payload({"python": sys.version, "executable": sys.executable}),
        "FLOWGUARD_ENVIRONMENT_FINGERPRINT": fingerprint_payload({"platform": sys.platform, "cwd": str(root)}),
        "FLOWGUARD_SELECTED_OWNER_IDS": "",
        "PYTHONPATH": str(root), "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8",
        "PYTHONDONTWRITEBYTECODE": "1",
    })
    return env
