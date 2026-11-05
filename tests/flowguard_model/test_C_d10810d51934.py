"""Preserve the repaired model behavior; this makes no native code claim."""
from pathlib import Path
from flowguard.flow.regression import assert_model_regression

def test_C_d10810d51934():
    root = Path(__file__).resolve().parents[2]
    assert_model_regression(root, '.flowguard/flow/native_return_fields.py', {'id': 'C-d10810d51934', 'kind': 'DUPLICATE ROUTE', 'subject': 'finish(value)'})

if __name__ == '__main__':
    test_C_d10810d51934()
