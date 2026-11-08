"""Use the existing source fixture collector; never make a runner or fake item."""
from types import SimpleNamespace

from flowguard.intent import anchors
from flowguard.intent.config import load_config
from flowguard.intent.loader import Model
from tests.intent_engine._source_fixture import source_engine


def bind_anchor(root, anchor):
    model = Model(load_config(root))
    model.anchor_index = anchors.Index((anchor,))
    # This shape only supplies the source fixture collector with a real testnode.
    # No predicate is run or accepted as an observed production outcome.
    model.rules['NATIVE_CONTEXT'] = SimpleNamespace(homes=[SimpleNamespace(anchor=anchor)])
    source_engine(model)
    from flowguard.intent import calibration
    scope, item = calibration._context(root, anchor.calibrated_by)
    return scope, item


def bind_scenario(root, binding):
    model = Model(load_config(root))
    model.anchor_index = binding.anchor_index
    model.rules['NATIVE_CONTEXT'] = SimpleNamespace(homes=[binding])
    source_engine(model)
    from flowguard.intent import calibration
    scope, item = calibration._context(root, binding.testnode)
    return scope, item
