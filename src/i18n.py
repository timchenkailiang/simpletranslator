"""Lightweight internationalisation (i18n) support.

Usage::

    from i18n import t, set_language, get_language, LANGUAGES

    set_language("zh")
    print(t("app.title"))        # → "PDF 转 Excel 合并工具"
    print(t("btn.browse"))       # → "浏览..."

Add new languages by creating a new dict in ``_TRANSLATIONS`` and
registering it in ``LANGUAGES``.
"""

import json
import logging
import os

_current_language = "en"
_logger = logging.getLogger(__name__)

LANGUAGES = {
    "en": "English",
    "zh": "中文",
}

# ── Translation tables ────────────────────────────────────────────────

_EN = {
    # Window / app
    "app.title": "PDF to Excel Merger Application",
    "app.heading": "PDF to Excel Data Merger",
    "app.ready": "Ready",

    # Menu
    "menu.file": "File",
    "menu.exit": "Exit",
    "menu.language": "Language",

    # Section 1 — Profile
    "section.profile": "1. Load Saved Configuration",
    "btn.delete_profile": "Delete Profile",

    # Section 2 — PDF Input
    "section.pdf_input": "2. Input PDF File",
    "btn.browse_dots": "Browse...",

    # Section 3 — Configuration
    "section.config": "3. Configuration Settings",
    "label.converter": "Converter Model:",
    "btn.edit": "Edit",
    "label.excel_template": "Excel Template:",
    "btn.browse": "Browse",
    "label.pdf_columns": "PDF Columns:",
    "label.excel_columns": "Excel Columns:",
    "hint.comma_separated": "(comma separated)",
    "label.qty_tolerance": "Qty Tolerance:",
    "hint.tolerance_format": "(5%, 0.05, or 100)",
    "btn.save_profile": "\U0001f4be Save Current Settings as Profile",

    # Section 4 — Action
    "btn.run_merge": "RUN MERGE PROCESS",
    "btn.convert_only": "Tools: Convert PDF to CSV Only (No Merge)",

    # File dialogs
    "dialog.open_pdf": "Open PDF File",
    "dialog.open_excel": "Open Excel Template",
    "dialog.save_merged": "Save Merged Excel As",
    "dialog.save_csv": "Save CSV As",

    # Tool dialog
    "dialog.add_converter": "Add New Converter",
    "dialog.edit_converter": "Edit {name}",
    "label.converter_name": "Converter Name:",
    "label.category": "Category (optional):",
    "label.description": "Description:",
    "label.script_file": "Python Script (.py):",
    "btn.add_converter": "Add Converter",
    "btn.save_changes": "Save Changes",
    "btn.delete_tool": "Delete Tool",

    # Profile save dialog
    "dialog.save_profile": "Save Profile",
    "label.profile_name": "Profile Name:",
    "btn.save": "Save",

    # Messages — errors
    "error": "Error",
    "error.tools_json_array": "tools.json must be a JSON array",
    "error.profiles_json_array": "merge_profiles.json must be a JSON array",
    "error.save_profiles": "Could not save profiles: {e}",
    "error.save_tools": "Could not save tools: {e}",
    "error.tool_not_found": "Tool configuration not found.",
    "error.name_required": "Name required",
    "error.name_script_required": "Name and Script File are required.",
    "error.script_not_found": "Script file not found: {path}",
    "error.save_tool_failed": "Failed to save tool: {e}",
    "error.column_mismatch": "Column count mismatch!\nPDF: {pdf}, Excel: {excel}",
    "error.file_not_found": "File not found.",
    "error.merge_error": "An error occurred:\n{e}",

    # Messages — warnings
    "warning": "Warning",
    "warning.missing_files": "Missing Files",
    "warning.select_both": "Select both a PDF input and an Excel template.",
    "warning.missing_columns": "Missing Columns",
    "warning.specify_columns": "Specify columns for both PDF and Excel.",
    "warning.select_file_first": "Please select a file first.",
    "warning.incomplete": "Incomplete",
    "warning.fill_fields": "Please fill in Converter, Excel Template, and Columns before saving.",
    "warning.file_not_found_title": "File Not Found",
    "warning.template_not_found": "Template not found:\n{path}\n\nPlease select a new file.",

    # Messages — info / success
    "success": "Success",
    "info.tool_saved": "Tool '{name}' saved!",
    "info.profile_saved": "Profile '{name}' saved.",
    "info.saved": "Saved",
    "info.deleted": "Deleted",
    "info.profile_deleted": "Profile deleted.",
    "info.loaded_profile": "Loaded profile: {name}",

    # Confirmations
    "confirm": "Confirm",
    "confirm.delete_tool": "Delete '{name}'?",
    "confirm.overwrite": "Overwrite",
    "confirm.overwrite_profile": "Profile '{name}' exists. Overwrite?",
    "confirm.delete": "Delete",
    "confirm.delete_profile": "Delete profile '{name}'?",

    # Merge report
    "report.merge_complete": "Merge Complete",
    "report.rows_extracted": "Rows extracted from PDF:    {n}",
    "report.rows_removed": "Rows removed (invalid):     {n}",
    "report.validation_flags": "Validation flags:           {n} cell(s)",
    "report.rows_matched": "Rows matched in Excel:      {matched}/{total}",
    "report.rows_not_found": "Rows not found:             {n}",
    "report.missing_columns": "\n\u26a0 Column(s) not found in Excel: {cols}",
    "report.qty_disabled": "\n\u26a0 Quantity recalculation disabled: 'Pcs/Ctn' or 'Pcs/Plt' columns not found in Excel.",
    "report.output": "Output: {path}",
    "report.success_saved": "Success! Saved to {path}",
    "report.no_matches_title": "No Matches",
    "report.no_matches_body": "No matches found between CSV keys and Excel template.\nFile was not generated.",
    "report.no_matches_status": "No matches. File not generated.",
    "report.error_during_merge": "Error during merge.",
    "report.error_occurred": "Error Occurred",

    # Convert-only report
    "convert.running": "Running {name}...",
    "convert.done": "Done! Saved to {name}",
    "convert.flagged": "{n} cell(s) flagged (will be marked red during merge).",
    "convert.success_msg": "Converted & validated!\n\nSaved to: {path}{flag_msg}",

    # Pipeline progress
    "pipeline.preparing": "Preparing merge...",
    "pipeline.loading_converter": "Loading converter...",
    "pipeline.validating_inputs": "Validating inputs...",
    "pipeline.converting_pdf_csv": "Converting PDF to intermediate CSV...",
    "pipeline.validating_csv": "Validating intermediate CSV...",
    "pipeline.inserting_csv_excel": "Inserting CSV into Excel template...",
    "pipeline.success": "Success! Saved to {path}",
    "pipeline.converting_pdf": "Converting PDF to CSV...",
    "pipeline.validating": "Validating CSV...",
    "pipeline.done": "Done!",
}

_ZH = {
    # Window / app
    "app.title": "PDF 转 Excel 合并工具",
    "app.heading": "PDF 转 Excel 数据合并",
    "app.ready": "就绪",

    # Menu
    "menu.file": "文件",
    "menu.exit": "退出",
    "menu.language": "语言",

    # Section 1 — Profile
    "section.profile": "1. 加载已保存的配置",
    "btn.delete_profile": "删除配置",

    # Section 2 — PDF Input
    "section.pdf_input": "2. 输入 PDF 文件",
    "btn.browse_dots": "浏览...",

    # Section 3 — Configuration
    "section.config": "3. 配置设置",
    "label.converter": "转换器模型：",
    "btn.edit": "编辑",
    "label.excel_template": "Excel 模板：",
    "btn.browse": "浏览",
    "label.pdf_columns": "PDF 列：",
    "label.excel_columns": "Excel 列：",
    "hint.comma_separated": "（逗号分隔）",
    "label.qty_tolerance": "数量容差：",
    "hint.tolerance_format": "（5%、0.05 或 100）",
    "btn.save_profile": "\U0001f4be 将当前设置保存为配置",

    # Section 4 — Action
    "btn.run_merge": "运行合并流程",
    "btn.convert_only": "工具：仅将 PDF 转换为 CSV（不合并）",

    # File dialogs
    "dialog.open_pdf": "打开 PDF 文件",
    "dialog.open_excel": "打开 Excel 模板",
    "dialog.save_merged": "保存合并后的 Excel",
    "dialog.save_csv": "保存 CSV 文件",

    # Tool dialog
    "dialog.add_converter": "添加新转换器",
    "dialog.edit_converter": "编辑 {name}",
    "label.converter_name": "转换器名称：",
    "label.category": "分类（可选）：",
    "label.description": "描述：",
    "label.script_file": "Python 脚本（.py）：",
    "btn.add_converter": "添加转换器",
    "btn.save_changes": "保存更改",
    "btn.delete_tool": "删除工具",

    # Profile save dialog
    "dialog.save_profile": "保存配置",
    "label.profile_name": "配置名称：",
    "btn.save": "保存",

    # Messages — errors
    "error": "错误",
    "error.tools_json_array": "tools.json 必须是 JSON 数组",
    "error.profiles_json_array": "merge_profiles.json 必须是 JSON 数组",
    "error.save_profiles": "无法保存配置：{e}",
    "error.save_tools": "无法保存工具：{e}",
    "error.tool_not_found": "未找到工具配置。",
    "error.name_required": "名称为必填项",
    "error.name_script_required": "名称和脚本文件为必填项。",
    "error.script_not_found": "未找到脚本文件：{path}",
    "error.save_tool_failed": "保存工具失败：{e}",
    "error.column_mismatch": "列数不匹配！\nPDF：{pdf}，Excel：{excel}",
    "error.file_not_found": "文件未找到。",
    "error.merge_error": "发生错误：\n{e}",

    # Messages — warnings
    "warning": "警告",
    "warning.missing_files": "缺少文件",
    "warning.select_both": "请同时选择 PDF 输入文件和 Excel 模板。",
    "warning.missing_columns": "缺少列",
    "warning.specify_columns": "请为 PDF 和 Excel 指定列。",
    "warning.select_file_first": "请先选择一个文件。",
    "warning.incomplete": "不完整",
    "warning.fill_fields": "请填写转换器、Excel 模板和列信息后再保存。",
    "warning.file_not_found_title": "文件未找到",
    "warning.template_not_found": "模板未找到：\n{path}\n\n请选择一个新文件。",

    # Messages — info / success
    "success": "成功",
    "info.tool_saved": "工具 '{name}' 已保存！",
    "info.profile_saved": "配置 '{name}' 已保存。",
    "info.saved": "已保存",
    "info.deleted": "已删除",
    "info.profile_deleted": "配置已删除。",
    "info.loaded_profile": "已加载配置：{name}",

    # Confirmations
    "confirm": "确认",
    "confirm.delete_tool": "删除 '{name}'？",
    "confirm.overwrite": "覆盖",
    "confirm.overwrite_profile": "配置 '{name}' 已存在。是否覆盖？",
    "confirm.delete": "删除",
    "confirm.delete_profile": "删除配置 '{name}'？",

    # Merge report
    "report.merge_complete": "合并完成",
    "report.rows_extracted": "从 PDF 提取的行数：    {n}",
    "report.rows_removed": "删除的行数（无效）：    {n}",
    "report.validation_flags": "验证标记：              {n} 个单元格",
    "report.rows_matched": "Excel 中匹配的行数：    {matched}/{total}",
    "report.rows_not_found": "未找到的行数：          {n}",
    "report.missing_columns": "\n\u26a0 Excel 中未找到的列：{cols}",
    "report.qty_disabled": "\n\u26a0 数量重新计算已禁用：Excel 中未找到 'Pcs/Ctn' 或 'Pcs/Plt' 列。",
    "report.output": "输出：{path}",
    "report.success_saved": "成功！已保存至 {path}",
    "report.no_matches_title": "无匹配",
    "report.no_matches_body": "CSV 键与 Excel 模板之间未找到匹配项。\n文件未生成。",
    "report.no_matches_status": "无匹配。文件未生成。",
    "report.error_during_merge": "合并过程中出错。",
    "report.error_occurred": "发生错误",

    # Convert-only report
    "convert.running": "正在运行 {name}...",
    "convert.done": "完成！已保存至 {name}",
    "convert.flagged": "{n} 个单元格被标记（合并时将标记为红色）。",
    "convert.success_msg": "转换并验证完成！\n\n已保存至：{path}{flag_msg}",

    # Pipeline progress
    "pipeline.preparing": "正在准备合并...",
    "pipeline.loading_converter": "正在加载转换器...",
    "pipeline.validating_inputs": "正在验证输入...",
    "pipeline.converting_pdf_csv": "正在将 PDF 转换为中间 CSV...",
    "pipeline.validating_csv": "正在验证中间 CSV...",
    "pipeline.inserting_csv_excel": "正在将 CSV 插入 Excel 模板...",
    "pipeline.success": "成功！已保存至 {path}",
    "pipeline.converting_pdf": "正在将 PDF 转换为 CSV...",
    "pipeline.validating": "正在验证 CSV...",
    "pipeline.done": "完成！",
}

_TRANSLATIONS = {
    "en": _EN,
    "zh": _ZH,
}


# ── Public API ────────────────────────────────────────────────────────

def set_language(lang_code: str):
    """Set the active language.  *lang_code* must be a key in ``LANGUAGES``."""
    global _current_language
    if lang_code not in _TRANSLATIONS:
        raise ValueError(f"Unknown language: {lang_code}")
    _current_language = lang_code


def get_language() -> str:
    """Return the current language code."""
    return _current_language


def t(key: str, **kwargs) -> str:
    """Look up a translated string by *key*, with optional ``str.format`` kwargs.

    Falls back to the English text, then to the raw key itself.
    """
    table = _TRANSLATIONS.get(_current_language, _EN)
    text = table.get(key) or _EN.get(key) or key
    if kwargs:
        text = text.format(**kwargs)
    return text


# ── Language persistence ──────────────────────────────────────────────

_LANG_FILENAME = os.path.join("config", "language.json")


def _language_json_path():
    """Return the path to language.json (in the user data dir)."""
    from utils import get_user_data_dir
    return os.path.join(get_user_data_dir(), _LANG_FILENAME)


def load_saved_language():
    """Load the language preference from language.json and activate it.

    Checked locations (first match wins):
      1. User data dir  (``config/language.json``)
      2. Install dir    (written by the Inno Setup installer)

    Falls back to English silently if the file is absent or malformed.
    """
    from utils import get_user_data_dir, get_install_dir

    candidates = [
        os.path.join(get_user_data_dir(), _LANG_FILENAME),
        os.path.join(get_install_dir(), _LANG_FILENAME),
    ]
    for path in candidates:
        if os.path.isfile(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                code = data.get("language", "en")
                if code in _TRANSLATIONS:
                    set_language(code)
                    _logger.info("Language loaded: %s (from %s)", code, path)
                    return
            except Exception as exc:
                _logger.debug("Could not read %s: %s", path, exc)
    _logger.info("No language preference found — defaulting to English.")


def save_language(lang_code: str):
    """Persist the language choice to language.json in the user data dir."""
    set_language(lang_code)
    path = _language_json_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"language": lang_code}, f)
        _logger.info("Language saved: %s → %s", lang_code, path)
    except Exception as exc:
        _logger.warning("Could not save language preference: %s", exc)
