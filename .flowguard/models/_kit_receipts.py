"""Expose clean kit evaluations as receipts without changing features or verdicts."""
from dataclasses import replace
from functools import wraps

def clean_receipts(builder):
    """Keep the kit state/workflow; also evaluate clean after a rejected case.

    feature_conformance already exercises the empty feature set. A producer
    whose public verdict includes accepted must write it in a real transition,
    so its explorer includes the same clean input and two independent requests.
    """
    @wraps(builder)
    def configured():
        design=builder()
        return replace(design,external_inputs=((),*design.external_inputs),max_sequence_length=2)
    return configured
