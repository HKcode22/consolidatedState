from __future__ import annotations

import importlib


def test_runtime_modules_import_cleanly():
    modules = [
        "consolidated_state.report_data",
        "consolidated_state.export_excel",
        "consolidated_state.export_pdf",
        "consolidated_state.pipeline",
    ]

    for name in modules:
        module = importlib.import_module(name)
        assert module is not None
