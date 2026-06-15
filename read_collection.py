"""
read_collection_final.py
========================
Reliable cover-page extractor for Cecil / Street One ORDER PDFs.

Strategy
--------
* Uses `pdftotext -layout` (poppler-utils) to get spatially aligned text.
  This preserves column positions exactly as they appear on-screen, which
  is the only reliable way to handle borderless tables whose columns sit
  very close together (XS / S / M / L / XL / XXL etc.).
* Column matching: each number in a data row is assigned to the header
  column whose *centre* position is closest to the number's own centre.
  This avoids the tolerance-guessing problems of right-edge matching.
"""

import re
import os
import shutil
import json
import subprocess

# --- CONFIGURATION ---
SOURCE_DIR = "uploads"
SUCCESS_DIR = "posted"
ERROR_DIR   = "errors"
LOG_FILE    = "collection.json"


# ────────────────────────────────────────────────────────────────────────────
# PO number helper
# ────────────────────────────────────────────────────────────────────────────

def generate_po_logic(filename):
    """
    '2026066-325422.pdf'  ->  '325422 C-6.6/26'
    '2026070-317515.pdf'  ->  '317515 C-7/26'
    '2026072-325647.pdf'  ->  '325647 C-7.2/26'
    """
    try:
        base_name          = os.path.splitext(filename)[0]
        name_part, article = base_name.split('-')
        year_short         = name_part[:4][-2:]          # '2026' -> '26'
        coll_val           = float(name_part[-3:]) / 10  # '066' -> 6.6
        coll_str           = f"{coll_val:g}"             # remove trailing .0
        return f"{article} C-{coll_str}/{year_short}"
    except Exception:
        return os.path.splitext(filename)[0]


# ────────────────────────────────────────────────────────────────────────────
# Text extraction
# ────────────────────────────────────────────────────────────────────────────

def extract_layout_text(file_path):
    """
    Calls `pdftotext -layout` on page 1 and returns the raw string.
    Requires poppler-utils  (apt install poppler-utils).
    """
    result = subprocess.run(
        ["pdftotext", "-layout", "-f", "1", "-l", "1", file_path, "-"],
        capture_output=True, text=True, check=True
    )
    return result.stdout


# ────────────────────────────────────────────────────────────────────────────
# Column-position helpers
# ────────────────────────────────────────────────────────────────────────────

def parse_header_centres(header_line):
    """
    Returns an ordered list of (label, centre_pos) tuples, where centre_pos
    is the mid-point character position of the token in the header line.
    """
    cols = []
    for m in re.finditer(r'\S+', header_line):
        centre = (m.start() + m.end()) / 2
        cols.append((m.group(), centre))
    return cols


def assign_values_to_columns(data_line, header_cols):
    """
    For every number in data_line, find the header column whose centre is
    closest to the number's own centre.  Returns a dict {label: value_str}.
    Only the first value assigned to each column label is kept.
    """
    mapping = {}
    for m in re.finditer(r'[\d.,]+', data_line):
        val_centre = (m.start() + m.end()) / 2
        best_label, best_dist = None, float('inf')
        for label, col_centre in header_cols:
            dist = abs(val_centre - col_centre)
            if dist < best_dist:
                best_dist  = dist
                best_label = label
        if best_label and best_label not in mapping:
            # Strip thousands separators (comma or period used as thousand sep)
            raw = m.group()
            # Normalise: remove dots/commas used as thousand separators
            # Heuristic: if the number has a separator that's not at the
            # decimal position, strip it. We treat all , and . as thousands
            # separators here since prices are handled separately via regex.
            normalised = re.sub(r'[,.]', '', raw)
            mapping[best_label] = normalised
    return mapping


# ────────────────────────────────────────────────────────────────────────────
# Main extractor
# ────────────────────────────────────────────────────────────────────────────

def extract_cover_page(file_path):
    """
    Extracts metadata + summary table from the ORDER cover page (page 1).
    Returns a structured dict ready for JSON serialisation.
    """
    layout_text = extract_layout_text(file_path)
    lines       = layout_text.splitlines()

    # ── 1. Metadata (regex on the full page text) ───────────────────────── #
    date_match       = re.search(r'Date:\s*(\d{2}\.\d{2}\.\d{4})', layout_text)
    company_match    = re.search(r'^(.*?)\s+GmbH\b', layout_text, re.MULTILINE)
    collection_match = re.search(r'Collection:\s*(\d+)', layout_text)
    handover_match   = re.search(r'Handover Date:\s*(\d{2}\.\d{2}\.\d{2})', layout_text)
    # Description sits between Article No. number and two+ spaces / Incoterm
    article_match    = re.search(r'Article No\.:\s*(\d+)\s{2,}(.+?)\s{2,}', layout_text)
    style_match      = re.search(r'Style No\.:\s*(\d+)', layout_text)
    price_match      = re.search(r'Price:\s*([\d,]+)', layout_text)

    # ── 2. Locate the summary-table header row ───────────────────────────── #
    header_line = None
    header_idx  = None

    for i, line in enumerate(lines):
        if re.search(r'\bCol\b', line) and re.search(r'\bpcs\b', line):
            header_line = line
            header_idx  = i
            break

    color_data = []

    if header_line is not None:
        header_cols = parse_header_centres(header_line)

        # Labels we DON'T want in the size breakdown
        skip_labels = {'Col', 'Length', 'pcs'}
        size_labels  = [label for label, _ in header_cols if label not in skip_labels]

        for line in lines[header_idx + 1:]:
            stripped = line.strip()
            if not stripped:
                continue
            if re.match(r'^Total\b', stripped, re.IGNORECASE):
                break   # reached the summary total row — done

            # Data rows always start with a colour code: optional Y + 5 digits
            first_token = stripped.split()[0]
            if not re.match(r'^Y?\d{5}', first_token):
                continue

            raw_color   = first_token
            clean_color = raw_color[1:] if raw_color.upper().startswith('Y') else raw_color

            col_values = assign_values_to_columns(line, header_cols)

            total_pcs = col_values.get('pcs', '')
            breakdown = {lbl: col_values[lbl] for lbl in size_labels if lbl in col_values}  #This line records if there is a zero but not empty sizes
            # breakdown = {lbl: col_values.get(lbl, "0") for lbl in size_labels}  # This line records empty + 0

            color_data.append({
                "Color":     clean_color,
                "Total Pcs": total_pcs,
                "Breakdown": breakdown,
            })

    # ── 3. Assemble and return ───────────────────────────────────────────── #
    return {
        "PO No.":        generate_po_logic(os.path.basename(file_path)),
        "Date":          date_match.group(1)             if date_match       else "Not Found",
        "Company":       company_match.group(1).strip()  if company_match    else "Not Found",
        "Collection":    collection_match.group(1)       if collection_match else "Not Found",
        "Handover Date": handover_match.group(1)         if handover_match   else "Not Found",
        "Article No":    article_match.group(1)          if article_match    else "Not Found",
        "Description":   article_match.group(2).strip()  if article_match    else "Not Found",
        "Style No":      style_match.group(1)            if style_match      else "Not Found",
        "Price":         price_match.group(1).replace(',', '.') if price_match else "Not Found",
        "Table":         color_data,
    }


# ────────────────────────────────────────────────────────────────────────────
# Folder processor  (with duplicate prevention)
# ────────────────────────────────────────────────────────────────────────────

def process_folder():
    """
    Scans SOURCE_DIR for PDFs, extracts cover-page data, prevents duplicates,
    moves processed files to SUCCESS_DIR or ERROR_DIR, and appends to LOG_FILE.
    """
    for d in [SOURCE_DIR, SUCCESS_DIR, ERROR_DIR]:
        os.makedirs(d, exist_ok=True)

    all_data = []
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, 'r', encoding='utf-8') as f:
            try:
                all_data = json.load(f)
            except json.JSONDecodeError:
                pass

    processed_po_set = {item["PO No."] for item in all_data}
    # pdf_files = sorted(f for f in os.listdir(SOURCE_DIR) if f.lower().endswith('.pdf'))   # Reads all PDFs in the upload folder
    # Filter out files containing 'cw', 'nos', or 'qr' (case insensitive)
    pdf_files = sorted(
        f for f in os.listdir(SOURCE_DIR) 
        if f.lower().endswith('.pdf') 
        and not any(exclude in f.lower() for exclude in ['cw', 'nos', 'qr'])
    )

    for filename in pdf_files:
        file_path = os.path.join(SOURCE_DIR, filename)
        new_po    = generate_po_logic(filename)

        if new_po in processed_po_set:
            print(f"  [SKIP] {filename} -- PO {new_po} already logged.")
            shutil.move(file_path, os.path.join(SUCCESS_DIR, filename))
            continue

        print(f"  [PROC] {filename}  ->  PO: {new_po}")
        try:
            data = extract_cover_page(file_path)
            all_data.append(data)
            processed_po_set.add(new_po)
            shutil.move(file_path, os.path.join(SUCCESS_DIR, filename))
            print(f"         OK  {len(data['Table'])} colour row(s) extracted.")
        except Exception as e:
            print(f"         ERR {e}")
            shutil.move(file_path, os.path.join(ERROR_DIR, filename))

    with open(LOG_FILE, 'w', encoding='utf-8') as f:
        json.dump(all_data, f, indent=4, ensure_ascii=False)

    print(f"\nDone -- results written to '{LOG_FILE}'.")


# ────────────────────────────────────────────────────────────────────────────
# Entry point
# ────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        # Test mode: pass PDF file paths as arguments
        for path in sys.argv[1:]:
            print(f"\n{'='*60}")
            print(f"File: {os.path.basename(path)}")
            print('='*60)
            result = extract_cover_page(path)
            print(json.dumps(result, indent=4, ensure_ascii=False))
    else:
        process_folder()