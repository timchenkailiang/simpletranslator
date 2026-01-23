import json
import pdfplumber
import pandas as pd
import re
from operator import itemgetter

class SmartExtractor:
    def __init__(self, config_path=None, config_data=None):
        if config_data:
            self.config = config_data
        elif config_path:
            with open(config_path, 'r', encoding='utf-8') as f:
                self.config = json.load(f)
        else:
            self.config = []

    def extract_all(self):
        for job in self.config:
            print(f"Processing {job['pdf_path']}...")
            try:
                self.process_job(job)
                print(f"Successfully created {job['output_csv_path']}")
            except Exception as e:
                print(f"Error processing {job['pdf_path']}: {e}")

    def process_job(self, job):
        pdf_path = job['pdf_path']
        output_csv = job['output_csv_path']
        start_anchor = job['start_anchor']
        end_anchor = job.get('end_anchor')
        columns = job['columns']
        example_row = job['example_row']
        # Create a copy of post_processing to avoid modifying the original config
        post_processing = job.get('post_processing', {}).copy()

        # Learn pattern from example_row: 
        # If an example value has no whitespace, assume we should strip whitespace from extracted data for that column.
        for col in columns:
            val = str(example_row.get(col, "")).strip()
            if val:
                # If there is a value and it contains NO whitespace...
                if not re.search(r'\s', val):
                    # ...add automatic whitespace removal rule
                    if col not in post_processing:
                        post_processing[col] = []
                    if "remove_whitespace" not in post_processing[col]:
                        post_processing[col].append("remove_whitespace")
                        print(f"Auto-detected pattern: enforcing no whitespace for column '{col}'")
                
                # Check if value is numeric (allowing for common numeric chars like .-), but extracted data might contain text like 'STK'
                # If example is "3600" (numeric), we should probably strip non-numeric characters from the result if it contains letters like 'STK'
                if re.match(r'^[\d.,]+$', val):
                     if col not in post_processing:
                        post_processing[col] = []
                     if "keep_numeric_only" not in post_processing[col]:
                        post_processing[col].append("keep_numeric_only")
                        print(f"Auto-detected pattern: enforcing numeric only for column '{col}'")

        # We will learn the x-boundaries (cuts) from the example row
        column_cuts = None
        extracted_rows = []

        with pdfplumber.open(pdf_path) as pdf:
            # First pass: try to find the example row to learn layout
            if column_cuts is None:
                column_cuts = self.learn_layout(pdf, start_anchor, end_anchor, columns, example_row)
                if not column_cuts:
                    raise ValueError(f"Could not learn layout for {pdf_path}. The 'example_row' provided in config does not match any row in the PDF. Please verify your config values match the PDF exactly.")

            # Second pass (or continuation): extract data using learned cuts
            for page in pdf.pages:
                page_rows = self.extract_page_data(page, start_anchor, end_anchor, column_cuts, columns)
                extracted_rows.extend(page_rows)

        # Create DataFrame
        df = pd.DataFrame(extracted_rows, columns=columns)

        # Apply post-processing
        for col, rules in post_processing.items():
            if col in df.columns:
                for rule in rules:
                    if rule == "remove_whitespace":
                        df[col] = df[col].astype(str).str.replace(r'\s+', '', regex=True)
                    elif rule == "keep_numeric_only":
                         # Remove anything that is not a digit, comma, or period
                         df[col] = df[col].astype(str).str.replace(r'[^\d.,]', '', regex=True)
                         # Explicitly handle .0 float string conversion artifact
                         # This happens if pandas inferred it as float before conversion to string
                         df[col] = df[col].apply(lambda x: x[:-2] if str(x).endswith('.0') else x)

        # Save to CSV
        df.to_csv(output_csv, index=False)

    def get_lines_on_page(self, page, tolerance=3):
        """
        Groups words into lines based on vertical position.
        """
        words = page.extract_words()
        if not words:
            return []
        
        # Sort by top position
        words.sort(key=itemgetter('top'))
        
        lines = []
        current_line = []
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
        
        # Sort words in each line by x0
        for line in lines:
            line.sort(key=itemgetter('x0'))
            
        return lines

    def line_to_text(self, line):
        return " ".join([w['text'] for w in line])

    def learn_layout(self, pdf, start_anchor, end_anchor, columns, example_row):
        """
        Scans the PDF to find the row matching example_row and determines column x-boundaries.
        """
        print("Learning layout from example row...")
        
        # Phase 1: Try to learn column centroids from the Header Line (start_anchor)
        # This helps resolve ambiguities when the same value appears in multiple columns.
        header_centroids = {}
        for page in pdf.pages:
            lines = self.get_lines_on_page(page)
            normalized_start = re.sub(r'\s+', '', start_anchor)
            
            for line in lines:
                line_text = self.line_to_text(line)
                normalized_line = re.sub(r'\s+', '', line_text)
                
                if normalized_start in normalized_line:
                    # Found header line. Try to map columns to words.
                    # This is a bit heuristics-heavy.
                    # We look for the column name in the header line words.
                    
                    # Create a rough map of text to x-range in this line
                    # We'll merge words back into a string but keep their x-coords mapping
                    # Actually, easier: search for the column name specific tokens.
                    
                    full_line_text = "".join([w['text'] for w in line])
                    
                    for col in columns:
                        # Simple search for the column name in the header words
                        # Remove spaces from col name for search
                        col_clean = re.sub(r'\s+', '', col)
                        
                        # Find which words contribute to this column header
                        # This is naive but might work for "Vort part Nr."
                        
                        current_search = ""
                        start_idx = -1
                        
                        for i, w in enumerate(line):
                            # Check if adding this word helps match match the col name
                            # This is tricky because "Vort part Nr." spans multiple words.
                            
                            # Try matching sequence of words
                            match_found = False
                            for k in range(i, len(line)):
                                sub_text = "".join([wx['text'] for wx in line[i:k+1]])
                                sub_clean = re.sub(r'[^a-zA-Z0-9]', '', sub_text)
                                target_clean = re.sub(r'[^a-zA-Z0-9]', '', col)
                                
                                if target_clean == sub_clean:
                                    # Found the header for this column
                                    xs = [wx['x0'] for wx in line[i:k+1]] + [wx['x1'] for wx in line[i:k+1]]
                                    center = sum(xs) / len(xs)
                                    header_centroids[col] = center
                                    match_found = True
                                    break
                            if match_found:
                                break
                    break
            if header_centroids:
                break

        best_matches = {}
        best_match_count = 0
        
        # columns to check - only those with values in example_row
        target_cols = [c for c in columns if str(example_row.get(c, "")).strip()]

        for page in pdf.pages:
            lines = self.get_lines_on_page(page)
            
            for line in lines:
                # Find all potential matches for each column first
                # candidates[col] = [ {'x0':..., 'x1':..., 'word_idx_start':..., 'word_idx_end':...} ]
                
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
                            
                            if val_clean == joined_clean or val_clean in joined_clean:
                                # Found a match candidate
                                # Do shrinkage (same as before)
                                match_i = i
                                match_j = j
                                
                                # ... Shrinkage logic ...
                                while match_i < match_j:
                                    sub_text = "".join([w['text'] for w in line[match_i+1 : match_j+1]])
                                    sub_clean = re.sub(r'[^a-zA-Z0-9]', '', sub_text)
                                    if val_clean in sub_clean:
                                        match_i += 1
                                    else:
                                        break
                                while match_j > match_i:
                                    sub_text = "".join([w['text'] for w in line[match_i : match_j]])
                                    sub_clean = re.sub(r'[^a-zA-Z0-9]', '', sub_text)
                                    if val_clean in sub_clean:
                                        match_j -= 1
                                    else:
                                        break
                                
                                match_words = line[match_i : match_j+1]
                                min_x0 = min(w['x0'] for w in match_words)
                                max_x1 = max(w['x1'] for w in match_words)
                                center_x = (min_x0 + max_x1) / 2
                                
                                candidates[col].append({
                                    'x0': min_x0, 
                                    'x1': max_x1,
                                    'center_x': center_x,
                                    'start_idx': match_i,
                                    'end_idx': match_j
                                })
                                break # Move to next start word 'i'
                            
                            if len(joined_clean) > len(val_clean) + 20: 
                                break

                # Now try to form a valid chain from candidates
                # Valid chain: matches must be in column order, and non-overlapping
                # We want to maximize the number of columns matched.
                
                # We can use a simple recursive solver
                # chain = [ (col, match), ... ]
                
                valid_chain = self.solve_best_chain(target_cols, candidates, header_centroids)
                
                if valid_chain:
                    match_count = len(valid_chain)
                    match_set = {col: match for col, match in valid_chain.items()}
                    
                    if match_count > best_match_count:
                        best_match_count = match_count
                        best_matches = match_set
                        
                        if match_count == len(target_cols):
                            # Pass the current line as a guide for detecting obstacles
                            return self.calculate_cuts(best_matches, columns, page.width, guide_line=line)
 
        # DISABLED: Partial matching logic to enforce strict configuration correctness.
        # if best_match_count >= max(2, len(target_cols) / 2): 
        #     return self.calculate_cuts(best_matches, columns, pdf.pages[0].width)
            
        return None

    def solve_best_chain(self, target_cols, candidates, header_centroids):
        """
        Finds the combination of candidates that:
        1. Includes the most columns
        2. Respects left-to-right order
        3. Minimizes deviation from header centroids (if available)
        """
        # Sort cols by index to ensure order
        # Actually target_cols is already ordered from config? Yes.
        
        best_chain = {}
        best_score = -1
        
        # We can implement a recursive search
        # state: (col_idx, last_match_end_idx, current_chain)
        
        stack = [(0, -1, {})] # col_idx, last_end_index, chain_dict
        
        while stack:
            c_idx, last_end, chain = stack.pop()
            
            # Base case: checked all cols
            if c_idx >= len(target_cols):
                # Calculate score
                # Score = num_matched * 1000 - distance_penalty
                score = len(chain) * 10000
                
                dist_penalty = 0
                for col, match in chain.items():
                    if col in header_centroids:
                        dist_penalty += abs(match['center_x'] - header_centroids[col])
                
                score -= dist_penalty
                
                if score > best_score:
                    best_score = score
                    best_chain = chain
                continue

            col_name = target_cols[c_idx]
            
            # Option 1: Skip this column
            stack.append((c_idx + 1, last_end, chain.copy()))
            
            # Option 2: Try to match this column
            if col_name in candidates:
                for match in candidates[col_name]:
                    # Check for overlap: match must start after last_end
                    # Using word indices is safer than x coordinates for ensuring "same line distinct words"
                    if match['start_idx'] > last_end:
                         new_chain = chain.copy()
                         new_chain[col_name] = match
                         stack.append((c_idx + 1, match['end_idx'], new_chain))
        
        return best_chain

    def calculate_cuts(self, column_matches, columns, page_width, guide_line=None):
        """
        Calculates vertical cuts (x-coordinates) separating columns.
        Uses a dynamic expansion strategy based on the available gap between columns.
        """
        EXPANSION_RATIO = 0.35  # Consume 35% of the gap on each side, leaving 30% buffer in middle.
        MAX_EXPANSION = 50      # Don't expand more than 50 points regardless of gap size.
        MIN_EXPANSION = 5       # Always allow at least small wiggle room.
        
        final_zones = []
        
        # Ensure we have matches for all columns
        for col in columns:
            if col not in column_matches:
                 column_matches[col] = {'x0': 0, 'x1': 0}

        for i, col in enumerate(columns):
            curr_match = column_matches[col]
            is_present = (curr_match['x0'] != 0 or curr_match['x1'] != 0)
            
            # --- START POSITION ---
            if i == 0:
                if is_present:
                     x_start = max(0, curr_match['x0'] - MAX_EXPANSION)
                else:
                     x_start = 0
            else:
                prev_zone = final_zones[-1]
                prev_col = columns[i-1]
                prev_match = column_matches[prev_col]
                prev_present = (prev_match['x0'] != 0 or prev_match['x1'] != 0)
                
                if is_present:
                    if prev_present:
                         # Both present: standard gap logic
                         gap = curr_match['x0'] - prev_match['x1']
                         expansion = max(MIN_EXPANSION, min(MAX_EXPANSION, gap * EXPANSION_RATIO))
                         x_start = curr_match['x0'] - expansion
                    else:
                         # Previous missing (but has a zone). 
                         # Current expands left into the void? 
                         # Just use standard MAX expansion left to be safe
                         x_start = curr_match['x0'] - MAX_EXPANSION
                else:
                    # Current missing. Start where previous zone ended.
                    x_start = prev_zone['x1']
            
            # --- END POSITION ---
            # Determine Right Expansion
            if i == len(columns) - 1:
                # Last column: expand right
                right_padding = MAX_EXPANSION
                x_end = curr_match['x1'] + right_padding
                # Or just expand to page width? usually safer to go to edge for last col
                x_end = page_width 
            else:
                next_col = columns[i+1]
                next_match = column_matches[next_col]
                
                # Check if next match is effectively missing
                next_is_missing = (next_match['x0'] == 0 and next_match['x1'] == 0)
                
                if next_is_missing:
                     # Look ahead for a valid anchor
                     valid_anchor_x0 = None
                     for k in range(i+2, len(columns)):
                         m = column_matches[columns[k]]
                         if m['x0'] != 0 or m['x1'] != 0:
                             valid_anchor_x0 = m['x0']
                             break
                     
                     if valid_anchor_x0:
                         # We have a gap to a future anchor.
                         # The gap starts at curr_match['x1'] and ends at valid_anchor_x0.
                         # We need to fit (1 + num_missing_cols) columns in this gap.
                         
                         # check for "obstacle words" in the gap if we have the guide line
                         obstacle_found = False
                         obstacle_x0 = valid_anchor_x0
                         
                         if guide_line:
                            gap_start = curr_match['x1'] if is_present else x_start
                            gap_end = valid_anchor_x0
                            for w in guide_line:
                                w_center = (w['x0'] + w['x1']) / 2
                                if gap_start < w_center < gap_end:
                                    # Found a word in the gap not belonging to current or next anchor
                                    # Since next_match is missing, this word likely belongs to it (or others in between)
                                    # Treat the first such word as the hard stop for the current column
                                    if w['x0'] < obstacle_x0:
                                        obstacle_x0 = w['x0']
                                        obstacle_found = True

                         if obstacle_found:
                             # If we found an unclaimed word (obstacle) immediately following,
                             # we should NOT expand aggressively.
                             # If current is present, stop before obstacle.
                             if is_present:
                                 # Distinguish between suffix (unit) and separate column
                                 dist_to_obstacle = obstacle_x0 - curr_match['x1']
                                 
                                 if dist_to_obstacle < 15: # Liberal threshold for "belonging to same column"
                                     # It is likely a suffix like "STK"
                                     
                                     # HEURISTIC: Check text patterns to decide on merge.
                                     # If [Digit] -> [Letter], likely Unit/Suffix (Merge).
                                     # If [Letter] -> [Digit], likely End of Unit -> Start of ID (Split).
                                     # If [Digit] -> [Digit], likely distinct columns (Split).
                                     
                                     should_merge = False
                                     
                                     # Find the text ending at curr_match['x1'] and starting at obstacle_x0
                                     last_word_text = ""
                                     obstacle_text = ""
                                     
                                     if guide_line:
                                         # Find word ending near curr_match['x1']
                                         for w in guide_line:
                                             if abs(w['x1'] - curr_match['x1']) < 2:
                                                 last_word_text = w['text']
                                             if abs(w['x0'] - obstacle_x0) < 2:
                                                 obstacle_text = w['text']
                                                 
                                     if last_word_text and obstacle_text:
                                         last_char = last_word_text[-1]
                                         first_char = obstacle_text[0]
                                         
                                         is_last_digit = last_char.isdigit()
                                         is_first_digit = first_char.isdigit()
                                         is_last_alpha = last_char.isalpha()
                                         is_first_alpha = first_char.isalpha()
                                         
                                         if is_last_digit and is_first_alpha:
                                             should_merge = True # "3600" "STK"
                                         elif is_last_alpha and is_first_alpha:
                                             should_merge = True # "Description" "Text"
                                         # Default to False for Digit->Digit or Alpha->Digit
                                     else:
                                         # Fallback if we can't identify words (shouldn't happen with guide_line)
                                         should_merge = False

                                     if should_merge:
                                         # Include it!
                                     
                                         # Find cluster end
                                         cluster_end = obstacle_x0
                                         if guide_line:
                                             for w in guide_line:
                                                 if w['x0'] >= obstacle_x0:
                                                    if w['x0'] - cluster_end < 15:
                                                        cluster_end = w['x1']
                                                        # Also update last_word_text for chain checking?
                                                        # Simplification: just take the cluster.
                                                    else:
                                                        break
                                         
                                         # Recalculate end
                                         # But wait, what if we merged "STK", and NOW we are facing "661001"?
                                         # We really should loop this check.
                                         # But for now, let's just extend to cluster_end and assume the NEXT split handles the break.
                                         # The logic below (clamp to next obstacle) handles the subsequent break.
                                         
                                         # Check distance to NEXT obstacle after the merged cluster
                                         # ... (reuse existing logic for next obstacle clamping) ...
                                         
                                         next_obstacle_x0 = valid_anchor_x0
                                         next_obstacle_found = False
                                         
                                         if guide_line:
                                             for w in guide_line:
                                                 w_center = (w['x0'] + w['x1']) / 2
                                                 if cluster_end < w_center < valid_anchor_x0:
                                                     if w['x0'] < next_obstacle_x0:
                                                         next_obstacle_x0 = w['x0']
                                                         next_obstacle_found = True
                                         
                                         if next_obstacle_found:
                                             x_end = next_obstacle_x0 - MIN_EXPANSION
                                         else:
                                             # Same gap logic as before
                                             num_missing = 0
                                             for k in range(i+1, len(columns)):
                                                 if column_matches[columns[k]]['x0'] == 0:
                                                     num_missing += 1
                                                 else:
                                                     break
                                             
                                             remaining_gap = valid_anchor_x0 - cluster_end
                                             if remaining_gap > 0:
                                                x_end = cluster_end + MIN_EXPANSION
                                                fair_share_start = cluster_end + (remaining_gap / (num_missing + 1))
                                                x_end = min(x_end, fair_share_start)
                                             else:
                                                 x_end = cluster_end  
                                     else:
                                         # heuristic says DO NOT MERGE
                                         x_end = max(curr_match['x1'], obstacle_x0 - MIN_EXPANSION)
                                 else:
                                     # Obstacle is clearly separate. Stop before it.
                                     x_end = max(curr_match['x1'], obstacle_x0 - MIN_EXPANSION)
                             else:
                                 # Current missing. Bound to obstacle.
                                 x_end = max(x_start, obstacle_x0 - MIN_EXPANSION)
                         else:
                             # Count missing cols immediately following
                             num_missing = 0
                             for k in range(i+1, len(columns)):
                                 if column_matches[columns[k]]['x0'] == 0:
                                     num_missing += 1
                                 else:
                                     break
                            
                             total_gap = valid_anchor_x0 - curr_match['x1']
                             if total_gap > 0:
                                 # STRATEGY CHANGE: Valid columns should be conservative when followed by missing columns.
                                 # If we split equally, we might grab data belonging to the missing column if it's left-aligned.
                                 # Give the valid column a smaller "safe" buffer, and give the rest to the missing ones.
                                 
                                 # Calculate equal share first
                                 equal_share = total_gap / (num_missing + 1)
                                 
                                 # But clamp the valid column's expansion significantly
                                 # Use 30% of the equal share, or a fixed max of 30pts (approx 10mm)
                                 conservative_expansion = min(equal_share * 0.4, 30)
                                 
                                 x_end = curr_match['x1'] + conservative_expansion
                             else:
                                 x_end = curr_match['x1'] + MIN_EXPANSION
                     else:
                         # Found no future anchors (end of table?) but we have a missing next col
                         if curr_match['x0'] == 0:
                             # Current is missing too.
                             x_end = x_start + MAX_EXPANSION
                         else:
                             x_end = curr_match['x1'] + MIN_EXPANSION
                         
                elif curr_match['x0'] == 0 and curr_match['x1'] == 0:
                    # Current is missing, Next is present.
                    # We are filling the gap bridging to the next column.
                    # Since we are "missing", we should just take up the space up to the next column.
                    # The previous column already took its "share" (calculated in previous iteration).
                    # So we just go up to the next match.
                    x_end = next_match['x0'] - MIN_EXPANSION
                    
                else:
                    # Current Present, Next Present
                    gap = next_match['x0'] - curr_match['x1']
                    if gap > 0:
                        x_end = curr_match['x1'] + (gap / 2)
                    else:
                        x_end = (curr_match['x1'] + next_match['x0']) / 2

            # Safety clip
            x_start = max(0, x_start)
            if x_start > x_end:
                 x_end = x_start
            
            final_zones.append({'col': col, 'x0': x_start, 'x1': x_end})
            
        return final_zones

    def extract_page_data(self, page, start_anchor, end_anchor, column_cuts, columns):
        """
        Extracts data from a single page using the learned column cuts.
        Only processes text between start_anchor and end_anchor.
        """
        data = []
        
        # Find start y (bottom of start_anchor line)
        words = page.extract_words()
        full_text = page.extract_text() or ""
        
        start_y = 0
        end_y = page.height

        # Find exact Y position of start anchor
        lines = self.get_lines_on_page(page)
        normalized_start = re.sub(r'\s+', '', start_anchor)
        
        found_start = False
        
        for line in lines:
            line_text = self.line_to_text(line)
            normalized_line = re.sub(r'\s+', '', line_text)
            
            if normalized_start in normalized_line:
                start_y = max(w['bottom'] for w in line)
                found_start = True
                break
        
        if not found_start:
            return []

        # Find end Y
        if end_anchor:
             normalized_end = re.sub(r'\s+', '', end_anchor)
             for line in lines:
                line_text = self.line_to_text(line)
                if end_anchor in line_text:
                    end_y = min(w['top'] for w in line)
                    break
                # Fallback to normalized check
                if normalized_end in re.sub(r'\s+', '', line_text):
                    end_y = min(w['top'] for w in line)
                    break
        
        # Now extract rows between start_y and end_y
        for line in lines:
            # Check vertical position
            line_top = min(w['top'] for w in line)
            line_bottom = max(w['bottom'] for w in line)
            
            if line_top > start_y and line_bottom < end_y:
                row_data = self.process_line_to_row(line, column_cuts, columns)
                
                # Filter invalid rows
                if row_data[0] == columns[0]:
                    continue

                non_empty = [c for c in row_data if c.strip()]
                if not non_empty:
                    continue
                    
                if not row_data[0].strip():
                     continue
                     
                data.append(row_data)
                    
        return data

    def process_line_to_row(self, line, column_cuts, columns):
        """
        Distributes words in a line into columns based on x-ranges.
        Words falling into 'dead zones' are discarded.
        """
        row = [""] * len(columns)
        
        for word in line:
            # Find which column this word belongs to based on its center point
            center_x = (word['x0'] + word['x1']) / 2
            
            for i, cut in enumerate(column_cuts):
                if cut['x0'] <= center_x < cut['x1']:
                    if row[i]:
                        row[i] += " " + word['text']
                    else:
                        row[i] = word['text']
                    break
        return row

if __name__ == "__main__":
    extractor = SmartExtractor('config.json')
    extractor.extract_all()