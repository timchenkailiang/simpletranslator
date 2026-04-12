# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] - 2026-04-12

### Added

- **Internationalization (i18n)**: New `i18n.py` module with English and Chinese (中文) translations covering 90+ UI strings
- **Runtime language switching**: Language menu in the menu bar lets users switch between English and Chinese on the fly
- **Pipeline orchestration**: New `engine/pipeline.py` module — single entry point for the extract → validate → insert workflow
- **CSV→Excel insertion engine**: New `engine/insert.py` with key-based row matching, quantity recalculation, and cell highlighting
- **Utility functions**: `smart_number_convert()` and `parse_localized_number()` for EU/US number format handling
- **Inno Setup Chinese support**: Installer now offers Chinese Simplified language option
- **Test infrastructure**: `tests/conftest.py` for automatic `src/` path setup in pytest

### Changed

- **Project structure**: Source code reorganized into `src/` directory (`converters/`, `engine/`, `ui/`, `utils.py`, `i18n.py`)
- **Test fixtures**: `resource/` → `tests/fixtures/pdfs/`; `tests/expected_outputs/` → `tests/fixtures/expected_outputs/`
- **Build files**: `SimpleTranslator.spec` and `iss1.iss` moved to `packaging/`
- **UI rewrite**: All hardcoded English strings in `app.py` replaced with `t()` translation calls
- **Converter improvements**: Updated `globe.py`, `jeffco.py`, and `millarco.py` with better extraction logic
- **Converter loader**: Enhanced `converters/__init__.py` with improved dynamic module loading
- **Validation engine**: Refined validation rules and suspicious-character checks in `validate.py`
- **SearchableDropdown**: Simplified `widgets.py` implementation
- **Dependencies**: Updated `requirements.txt`; version bumped to 1.1.0

### Removed

- **`engine/merge.py`**: Replaced by `engine/pipeline.py` + `engine/insert.py` for clearer separation of concerns
