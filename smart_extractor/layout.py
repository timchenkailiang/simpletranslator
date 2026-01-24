from typing import Any, Dict, List, Optional, Union, Tuple
import re
import math
from operator import itemgetter
from pdfplumber.page import Page
from pdfplumber.pdf import PDF
import logging

logger = logging.getLogger(__name__)

# Constants moved from class attributes
EXPANSION_RATIO = 0.35
MAX_EXPANSION = 50.0
MIN_EXPANSION = 5.0
OBSTACLE_MERGE_THRESHOLD = 15.0
SEARCH_WINDOW_BUFFER = 20

def get_lines_on_page(page: Page, tolerance: int = 3) -> List[List[Dict[str, Any]]]:
    """
    Groups words into lines based on vertical position.
    """
    words = page.extract_words()
    if not words:
        return []
    
    words.sort(key=itemgetter('top'))
    
    lines = []
    current_line = []
    if not words:
        return []
        
    current_top = words[0]['top']

    for word in words:
        if abs(word['top'] - current_top) <= tolerance:
            current_line.append(word)
        else:
            lines.append(current_line)
            current_line = [word]
            current_top = word['top']
    if current_line:
        lines.append(current_line)
    
    for line in lines:
        line.sort(key=itemgetter('x0'))
        
    return lines

def line_to_text(line: List[Dict[str, Any]]) -> str:
    return " ".join([w['text'] for w in line])

def learn_layout(pdf: PDF, start_anchor: str, end_anchor: Optional[str], columns: List[str], example_row: Dict[str, Any]) -> Optional[List[Dict[str, Union[str, float]]]]:
    """
    Scans the PDF to find the row matching example_row and determines column x-boundaries.
    """
    logger.info("Learning layout from example row...")
    
    header_centroids = _find_header_centroids(pdf, start_anchor, columns)
    target_cols = [c for c in columns if str(example_row.get(c, "")).strip()]

    for page in pdf.pages:
        lines = get_lines_on_page(page)
        
        for line in lines:
            candidates = _find_column_candidates_in_line(line, target_cols, example_row)
            valid_chain = solve_best_chain(target_cols, candidates, header_centroids)
            
            if valid_chain:
                if len(valid_chain) == len(target_cols):
                     return calculate_cuts(valid_chain, columns, page.width, guide_line=line, example_row=example_row)
    
    return None

def _find_header_centroids(pdf: PDF, start_anchor: str, columns: List[str]) -> Dict[str, float]:
    header_centroids = {}
    normalized_start = re.sub(r'\s+', '', start_anchor)
    
    for page in pdf.pages:
        lines = get_lines_on_page(page)
        for line in lines:
            line_text = line_to_text(line)
            if normalized_start in re.sub(r'\s+', '', line_text):
                for col in columns:
                    target_clean = re.sub(r'[^a-zA-Z0-9]', '', col)
                    
                    for i in range(len(line)):
                        for k in range(i, len(line)):
                            sub_text = "".join([wx['text'] for wx in line[i:k+1]])
                            sub_clean = re.sub(r'[^a-zA-Z0-9]', '', sub_text)
                            
                            if target_clean == sub_clean:
                                xs = [wx['x0'] for wx in line[i:k+1]] + [wx['x1'] for wx in line[i:k+1]]
                                center = sum(xs) / len(xs)
                                header_centroids[col] = center
                                break
        if header_centroids:
            break
    return header_centroids

def _find_column_candidates_in_line(line: List[Dict[str, Any]], target_cols: List[str], example_row: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
    candidates = {}
    
    for col in target_cols:
        val = str(example_row.get(col, "")).strip()
        if not val: continue
        
        val_clean = re.sub(r'[^a-zA-Z0-9]', '', val)
        if not val_clean: continue
        
        candidates[col] = []
        
        for i in range(len(line)):
            joined_text = ""
            for j in range(i, len(line)):
                joined_text += line[j]['text']
                joined_clean = re.sub(r'[^a-zA-Z0-9]', '', joined_text)
                
                if val_clean in joined_clean:
                        match = _refine_match(line, i, j, val_clean)
                        candidates[col].append(match)
                        break
                    
                if len(joined_clean) > len(val_clean) + SEARCH_WINDOW_BUFFER: 
                        break
    return candidates

def _refine_match(line: List[Dict[str, Any]], start_idx: int, end_idx: int, val_clean: str) -> Dict[str, Any]:
    match_i = start_idx
    match_j = end_idx
    
    while match_i < match_j:
        sub_text = "".join([w['text'] for w in line[match_i+1 : match_j+1]])
        if val_clean in re.sub(r'[^a-zA-Z0-9]', '', sub_text):
            match_i += 1
        else:
            break
    while match_j > match_i:
        sub_text = "".join([w['text'] for w in line[match_i : match_j]])
        if val_clean in re.sub(r'[^a-zA-Z0-9]', '', sub_text):
            match_j -= 1
        else:
            break
    
    match_words = line[match_i : match_j+1]
    min_x0 = min(w['x0'] for w in match_words)
    max_x1 = max(w['x1'] for w in match_words)
    center_x = (min_x0 + max_x1) / 2
    
    return {
        'x0': min_x0, 
        'x1': max_x1,
        'center_x': center_x,
        'start_idx': match_i,
        'end_idx': match_j
    }

def solve_best_chain(target_cols: List[str], candidates: Dict[str, List[Dict[str, Any]]], header_centroids: Dict[str, float]) -> Dict[str, Any]:
    best_chain = {}
    best_score = -1
    stack = [(0, -1, {})]
    
    while stack:
        c_idx, last_end, chain = stack.pop()
        
        if c_idx >= len(target_cols):
            score = _calculate_chain_score(chain, header_centroids)
            if score > best_score:
                best_score = score
                best_chain = chain
            continue

        col_name = target_cols[c_idx]
        stack.append((c_idx + 1, last_end, chain.copy()))
        
        if col_name in candidates:
            for match in candidates[col_name]:
                if match['start_idx'] > last_end:
                        new_chain = chain.copy()
                        new_chain[col_name] = match
                        stack.append((c_idx + 1, match['end_idx'], new_chain))
    
    return best_chain

def _calculate_chain_score(chain: Dict[str, Any], header_centroids: Dict[str, float]) -> float:
    score = len(chain) * 10000
    dist_penalty = 0
    for col, match in chain.items():
        if col in header_centroids:
            dist_penalty += abs(match['center_x'] - header_centroids[col])
    score -= dist_penalty
    return score

def calculate_cuts(column_matches: Dict[str, Any], columns: List[str], page_width: float, guide_line: Optional[List[Dict[str, Any]]] = None, example_row: Optional[Dict[str, Any]] = None) -> List[Dict[str, Union[str, float]]]:
    final_zones = []
    
    for col in columns:
        if col not in column_matches:
                column_matches[col] = {'x0': 0, 'x1': 0}

    for i, col in enumerate(columns):
        x_start = _calculate_x_start(i, col, columns, column_matches, final_zones)
        
        if i == len(columns) - 1:
            x_end = page_width
        else:
            x_end = _calculate_x_end_intermediate(i, col, columns, column_matches, guide_line, example_row, x_start, page_width)

        x_start = max(0, x_start)
        if x_start > x_end:
                x_end = x_start
        
        final_zones.append({'col': col, 'x0': x_start, 'x1': x_end})
        
    return final_zones

def _calculate_x_start(i: int, col: str, columns: List[str], column_matches: Dict[str, Any], final_zones: List[Dict]) -> float:
    curr_match = column_matches[col]
    is_present = (curr_match['x0'] != 0 or curr_match['x1'] != 0)

    if i == 0:
        return max(0, curr_match['x0'] - MAX_EXPANSION) if is_present else 0
    
    prev_zone = final_zones[-1]
    prev_col = columns[i-1]
    prev_match = column_matches[prev_col]
    prev_present = (prev_match['x0'] != 0 or prev_match['x1'] != 0)
    
    if is_present:
        if prev_present:
            gap = curr_match['x0'] - prev_match['x1']
            expansion = max(MIN_EXPANSION, min(MAX_EXPANSION, gap * EXPANSION_RATIO))
            return curr_match['x0'] - expansion
        else:
            return curr_match['x0'] - MAX_EXPANSION
    else:
        return prev_zone['x1']

def _calculate_x_end_intermediate(i: int, col: str, columns: List[str], column_matches: Dict[str, Any], guide_line: List[Dict], example_row: Dict, x_start: float, page_width: float) -> float:
    curr_match = column_matches[col]
    is_present = (curr_match['x0'] != 0 or curr_match['x1'] != 0)
    
    next_col = columns[i+1]
    next_match = column_matches[next_col]
    next_is_missing = (next_match['x0'] == 0 and next_match['x1'] == 0)
    
    if not next_is_missing:
        if is_present:
            gap = next_match['x0'] - curr_match['x1']
            return curr_match['x1'] + (gap / 2) if gap > 0 else (curr_match['x1'] + next_match['x0']) / 2
        else:
                return next_match['x0'] - MIN_EXPANSION

    valid_anchor_x0 = None
    for k in range(i+2, len(columns)):
        m = column_matches[columns[k]]
        if m['x0'] != 0 or m['x1'] != 0:
            valid_anchor_x0 = m['x0']
            break
    
    obstacle_x0 = valid_anchor_x0
    obstacle_found = False
    
    if guide_line:
        gap_start = curr_match['x1'] if is_present else x_start
        gap_end = valid_anchor_x0 if valid_anchor_x0 else page_width
        
        for w in guide_line:
            w_center = (w['x0'] + w['x1']) / 2
            if gap_start < w_center < gap_end:
                if obstacle_x0 is None or w['x0'] < obstacle_x0:
                        obstacle_x0 = w['x0']
                        obstacle_found = True

    if obstacle_found:
            return _handle_obstacle_collision(curr_match, obstacle_x0, guide_line, example_row, col, valid_anchor_x0, columns, i, is_present, x_start)
    
    if valid_anchor_x0:
            num_missing = 0
            for k in range(i+1, len(columns)):
                if column_matches[columns[k]]['x0'] == 0:
                    num_missing += 1
                else:
                    break
            
            total_gap = valid_anchor_x0 - curr_match['x1']
            if total_gap > 0:
                equal_share = total_gap / (num_missing + 1)
                conservative_expansion = min(equal_share * 0.4, 30)
                return curr_match['x1'] + conservative_expansion
            else:
                return curr_match['x1'] + MIN_EXPANSION
    else:
            return (x_start + MAX_EXPANSION) if not is_present else (curr_match['x1'] + MIN_EXPANSION)

def _handle_obstacle_collision(curr_match, obstacle_x0, guide_line, example_row, col, valid_anchor_x0, columns, i, is_present, x_start):
    if not is_present:
        return max(x_start + MIN_EXPANSION, obstacle_x0 - MIN_EXPANSION)
        
    dist_to_obstacle = obstacle_x0 - curr_match['x1']
    
    if dist_to_obstacle >= OBSTACLE_MERGE_THRESHOLD:
            return max(curr_match['x1'], obstacle_x0 - MIN_EXPANSION)

    should_merge = _check_should_merge(guide_line, curr_match['x1'], obstacle_x0)
    
    if should_merge:
            cluster_end = _extend_cluster(guide_line, obstacle_x0, valid_anchor_x0)
            return cluster_end + MIN_EXPANSION
    else:
            return max(curr_match['x1'], obstacle_x0 - MIN_EXPANSION)

def _check_should_merge(guide_line: List[Dict], x1_current: float, x0_obstacle: float) -> bool:
    last_word_text = ""
    obstacle_text = ""
    
    for w in guide_line:
        if abs(w['x1'] - x1_current) < 2:
            last_word_text = w['text']
        if abs(w['x0'] - x0_obstacle) < 2:
            obstacle_text = w['text']
    
    if last_word_text and obstacle_text:
        last_char = last_word_text[-1]
        first_char = obstacle_text[0]
        
        if last_char.isdigit() and first_char.isalpha():
            return True
        if last_char.isalpha() and first_char.isalpha():
            return True
            
    return False

def _extend_cluster(guide_line: List[Dict], start_x: float, limit_x: Optional[float]) -> float:
    cluster_end = start_x
    last_word = None
    for w in guide_line:
        if abs(w['x0'] - start_x) < 2:
            last_word = w
            cluster_end = w['x1']
            break
    
    if not last_word: 
        return start_x 

    limit = limit_x if limit_x else 10000
    start_idx = -1
    for idx, w in enumerate(guide_line):
        if w is last_word:
            start_idx = idx
            break
    
    if start_idx == -1: return cluster_end
    
    for k in range(start_idx + 1, len(guide_line)):
        w = guide_line[k]
        if w['x0'] >= limit: break
        
        dist = w['x0'] - cluster_end
        if dist > OBSTACLE_MERGE_THRESHOLD:
            break
            
        prev_text = last_word['text']
        curr_text = w['text']
        
        is_prev_alpha = prev_text[-1].isalpha()
        is_curr_digit = curr_text[0].isdigit()
        is_prev_digit = prev_text[-1].isdigit()
        
        if is_prev_alpha and is_curr_digit: break
        if is_prev_digit and is_curr_digit: break
        
        cluster_end = w['x1']
        last_word = w
        
    return cluster_end
