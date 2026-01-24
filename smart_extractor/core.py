import json
import re
import logging
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import pdfplumber
from pdfplumber.page import Page
import warnings

# Import from local modules
from .layout import learn_layout, get_lines_on_page, line_to_text
from .cleaning import detect_column_rules, clean_dataframe

logger = logging.getLogger(__name__)

# Suppress pandas FutureWarnings
warnings.simplefilter(action='ignore', category=FutureWarning)

class SmartExtractor:
    """
    A smart extraction tool for PDF documents based on configuration and layout learning.
    """
    
    def __init__(self, config_path: Optional[str] = None, config_data: Optional[List[Dict[str, Any]]] = None):
        if config_data:
            self.config = config_data
        elif config_path:
            with open(config_path, 'r', encoding='utf-8') as f:
                self.config = json.load(f)
        else:
            self.config = []

    def extract_all(self) -> None:
        """
        Process all jobs defined in the configuration.
        """
        for job in self.config:
            job_name = job.get('pdf_path', 'unknown job')
            logger.info(f"Processing {job_name}...")
            try:
                self.process_job(job)
                logger.info(f"Successfully created {job['output_csv_path']}")
            except Exception as e:
                logger.error(f"Error processing {job['pdf_path']}: {e}", exc_info=True)

    def process_job(self, job: Dict[str, Any]) -> None:
        """
        Orchestrates the extraction for a single job.
        """
        pdf_path = job['pdf_path']
        output_csv = job['output_csv_path']
        columns = job['columns']
        
        post_processing = job.get('post_processing', {}).copy()

        # Update post_processing with auto-detected rules (Delegated to cleaning module)
        numeric_validation_cols = detect_column_rules(job, post_processing)
        
        numeric_columns_indices = [i for i, col in enumerate(columns) if col in numeric_validation_cols]
        
        extracted_rows = self._extract_rows_from_pdf(job, numeric_columns_indices)

        df = pd.DataFrame(extracted_rows, columns=columns)

        # Apply cleanup (Delegated to cleaning module)
        df = clean_dataframe(df, post_processing)

        df.to_csv(output_csv, index=False)

    def _extract_rows_from_pdf(self, job: Dict[str, Any], numeric_columns_indices: List[int]) -> List[List[str]]:
        pdf_path = job['pdf_path']
        start_anchor = job['start_anchor']
        end_anchor = job.get('end_anchor')
        columns = job['columns']
        example_row = job['example_row']

        extracted_rows = []

        with pdfplumber.open(pdf_path) as pdf:
            # Layout Learning (Delegated to layout module)
            column_cuts = learn_layout(pdf, start_anchor, end_anchor, columns, example_row)
            if not column_cuts:
                raise ValueError(f"Could not learn layout for {pdf_path}. The 'example_row' provided in config does not match any row in the PDF.")

            for page in pdf.pages:
                page_rows = self.extract_page_data(page, start_anchor, end_anchor, column_cuts, columns, numeric_columns_indices)
                extracted_rows.extend(page_rows)
        
        return extracted_rows

    def extract_page_data(self, page: Page, start_anchor: str, end_anchor: Optional[str], column_cuts: List[Dict[str, Any]], columns: List[str], numeric_columns_indices: Optional[List[int]] = None) -> List[List[str]]:
        """
        Extracts data from a single page using the learned column cuts.
        """
        data = []
        
        start_y, end_y = self._get_page_boundaries(page, start_anchor, end_anchor)
        
        lines = get_lines_on_page(page)
        
        for line in lines:
            line_top = min(w['top'] for w in line)
            line_bottom = max(w['bottom'] for w in line)
            
            if line_top > start_y and line_bottom < end_y:
                row_data = self.process_line_to_row(line, column_cuts, columns)
                
                if self._is_valid_row(row_data, columns, numeric_columns_indices):
                    data.append(row_data)
                    
        return data

    def _get_page_boundaries(self, page: Page, start_anchor: str, end_anchor: Optional[str]) -> Tuple[float, float]:
        start_y = 0.0
        end_y = float(page.height)
        
        lines = get_lines_on_page(page)
        normalized_start = re.sub(r'\s+', '', start_anchor)
        
        for line in lines:
            line_txt = line_to_text(line) # Helper usage
            if normalized_start in re.sub(r'\s+', '', line_txt):
                start_y = max(w['bottom'] for w in line)
                break
        
        if end_anchor:
             normalized_end = re.sub(r'\s+', '', end_anchor)
             for line in lines:
                line_txt = line_to_text(line)
                if end_anchor in line_txt or normalized_end in re.sub(r'\s+', '', line_txt):
                    end_y = min(w['top'] for w in line)
                    break
                    
        return start_y, end_y

    def _is_valid_row(self, row_data: List[str], columns: List[str], numeric_columns_indices: Optional[List[int]]) -> bool:
        if row_data[0] == columns[0]:
            return False

        non_empty = [c for c in row_data if c.strip()]
        if not non_empty:
            return False
            
        if not row_data[0].strip():
             return False

        if numeric_columns_indices:
            has_numeric = False
            for ni in numeric_columns_indices:
                val = row_data[ni].strip()
                if val and (val[0].isdigit() or (len(val) > 1 and val[0] == '-' and val[1].isdigit())):
                     has_numeric = True
                     break
            if not has_numeric:
                return False
                
        return True

    def process_line_to_row(self, line: List[Dict[str, Any]], column_cuts: List[Dict[str, Any]], columns: List[str]) -> List[str]:
        row = [""] * len(columns)
        
        for word in line:
            center_x = (word['x0'] + word['x1']) / 2
            
            for i, cut in enumerate(column_cuts):
                if cut['x0'] <= center_x < cut['x1']:
                    if row[i]:
                        row[i] += " " + word['text']
                    else:
                        row[i] = word['text']
                    break
        return row
