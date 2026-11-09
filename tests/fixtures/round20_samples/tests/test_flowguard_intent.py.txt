"""Fail when declared FlowGuard intent was not collected."""
def test_flowguard_intent(request):
    from flowguard.intent.plugin import sentinel
    sentinel(request.config)
