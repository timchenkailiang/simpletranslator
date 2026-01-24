from typing import Any, Dict, List, Set
import re
import pandas as pd
import logging

logger = logging.getLogger(__name__)

def detect_column_rules(job: Dict[str, Any], post_processing: Dict[str, List[str]]) -> Set[str]:
    """
    Analyzes the example row to automatically detect validation rules and cleaning steps.
    """
    columns = job['columns']
    example_row = job['example_row']
    numeric_validation_cols = set()

    for col in columns:
        val = str(example_row.get(col, "")).strip()
        if not val:
            continue

        if not re.search(r'[\s\u00A0]', val):
            if col not in post_processing:
                post_processing[col] = []
            if "remove_whitespace" not in post_processing[col]:
                post_processing[col].append("remove_whitespace")
                logger.info(f"Auto-detected pattern: enforcing no whitespace for column '{col}'")
        
        if re.match(r'^[\d.,\-]+$', val) and any(c.isdigit() for c in val):
            numeric_validation_cols.add(col)
            
            if re.match(r'^\d+(\.\d+)?$', val):
                if col not in post_processing:
                    post_processing[col] = []
                if "keep_numeric_only" not in post_processing[col]:
                    post_processing[col].append("keep_numeric_only")
                    logger.info(f"Auto-detected pattern: enforcing numeric only for column '{col}'")
    
    for col, rules in post_processing.items():
        if "keep_numeric_only" in rules:
            numeric_validation_cols.add(col)
            
    return numeric_validation_cols

def clean_dataframe(df: pd.DataFrame, post_processing: Dict[str, List[str]]) -> pd.DataFrame:
    """
    Applies global cleaning (like soft hyphen removal) and configured post-processing rules.
    """
    for col in df.columns:
        df[col] = df[col].astype(str).str.replace('\xad', '-', regex=False)

    for col, rules in post_processing.items():
        if col in df.columns:
            for rule in rules:
                if rule == "remove_whitespace":
                    df[col] = df[col].astype(str).str.replace(r'[\s\u00A0\u200b\u202f]+', '', regex=True)
                elif rule == "keep_numeric_only":
                    df[col] = df[col].astype(str).str.replace(r'[^\d.]', '', regex=True)
    return df
