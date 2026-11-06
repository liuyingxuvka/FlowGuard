"""WorldGuard public runtime API, loaded from explicit native owners on demand."""

from importlib import import_module as _import_module

__version__ = "0.10.0"

__all__ = [
    "__version__",
    "GuardContract",
    "GuardRequirementDerivation",
    "GuardResult",
    "GuardStatus",
    "GuardedReport",
    "QualificationContext",
    "QualificationError",
    "MeshReport",
    "ModelMeshContract",
    "run_model_mesh",
    "qualification_context_for_node",
    "run_worldguard",
    "qualify_guard_contract",
    "derive_guard_requirements",
    "derive_required_guards",
]

_EXPORTS = {
    'GuardContract': 'worldguard.contracts',
    'GuardRequirementDerivation': 'worldguard.contracts',
    'derive_guard_requirements': 'worldguard.contracts',
    'derive_required_guards': 'worldguard.contracts',
    'run_worldguard': 'worldguard.kernel',
    'ModelMeshContract': 'worldguard.mesh',
    'MeshReport': 'worldguard.mesh',
    'run_model_mesh': 'worldguard.mesh',
    'qualification_context_for_node': 'worldguard.mesh',
    'QualificationContext': 'worldguard.qualification',
    'QualificationError': 'worldguard.qualification',
    'qualify_guard_contract': 'worldguard.qualification',
    'GuardResult': 'worldguard.reports',
    'GuardedReport': 'worldguard.reports',
    'GuardStatus': 'worldguard.status',
}

_EXPORT_ALIASES = ()


def __getattr__(name: str):
    module_name = _EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    native_name = dict(_EXPORT_ALIASES).get(name, name)
    value = getattr(_import_module(module_name), native_name)
    globals()[name] = value
    return value


def __dir__():
    return sorted(set(globals()) | set(__all__))
