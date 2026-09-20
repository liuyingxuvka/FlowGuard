"""Package-owned cardinality contract for the current FlowGuard skill."""

# FlowGuard is now one installable public skill. Domain protocols live below
# ``flowguard/references/domains`` and are not discoverable skill members.
FLOWGUARD_EXPECTED_MEMBER_COUNT = 1
FLOWGUARD_EXPECTED_SATELLITE_COUNT = 0


__all__ = [
    "FLOWGUARD_EXPECTED_MEMBER_COUNT",
    "FLOWGUARD_EXPECTED_SATELLITE_COUNT",
]
