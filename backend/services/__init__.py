"""Cognimend services package."""

from importlib import import_module


def __getattr__(name: str):
	if name == "evaluation":
		module = import_module(".evaluation", __name__)
		globals()[name] = module
		return module
	raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
