"""Custom policy loader for user-defined validators."""

from __future__ import annotations

import importlib
from typing import Any

from a2a_spec.exceptions import ConfigError


def load_custom_validator(dotted_path: str) -> Any:
    """Load a custom validator function from a dotted import path.

    Args:
        dotted_path: The dotted path to the function (e.g., 'myapp.validators.check_pii').

    Returns:
        The callable validator function.

    Raises:
        ConfigError: If the module or function cannot be loaded.
    """
    parts = dotted_path.rsplit(".", 1)
    if len(parts) != 2:
        raise ConfigError(
            f"Invalid validator path '{dotted_path}'. Expected format: 'module.path.function_name'"
        )

    module_path, func_name = parts

    try:
        module = importlib.import_module(module_path)
    except ImportError as e:
        raise ConfigError(
            f"Could not import module '{module_path}' for validator '{dotted_path}': {e}"
        ) from e

    func = getattr(module, func_name, None)
    if func is None:
        raise ConfigError(f"Module '{module_path}' has no attribute '{func_name}'")

    if not callable(func):
        raise ConfigError(f"Validator '{dotted_path}' is not callable (got {type(func).__name__})")

    return func


def register_builtin_validators(engine: Any) -> None:
    """Register all built-in policy validators with a PolicyEngine.

    Args:
        engine: A PolicyEngine instance.
    """
    from a2a_spec.policy.builtin import no_pii_in_output, output_not_empty

    engine.register_validator("a2a_spec.policy.builtin.no_pii_in_output", no_pii_in_output)
    engine.register_validator("a2a_spec.policy.builtin.output_not_empty", output_not_empty)
