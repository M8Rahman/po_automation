"""
read_cw_nos.py
==============
Extractor for CW (Carryover Week) and NOS (Never Out of Stock) ORDER PDFs.

Key differences from Collection PDFs
--------------------------------------
* NO cover/summary page. Every page is a country-group page with its own
  colour/size table.
* ALL pages must be read and their quantities AGGREGATED per colour + size.
* Metadata (Article No., Style No., Price, etc.) is taken from page 1 only.
* PO number format:
    CW files  ->  "317515 CW-17/26"   (week from filename, year from PDF Date)
    NOS files ->  handled in a later step (same script, different PO logic)

Filename conventions expected
-------------------------------
    CW  :  317515_CW-17.pdf
    NOS :  317515_NOS-<ref>.pdf   (future)

Dependencies
-------------
    poppler-utils  (apt install poppler-utils)
    No extra Python packages needed beyond the standard library.
"""

import re
import os
import shutil
import json
import subprocess
from collections import defaultdict

# --- CONFIGURATION ---
SOURCE_DIR  = "uploads"
SUCCESS_DIR = "posted"
ERROR_DIR   = "errors"
LOG_FILE    = "cw_nos_log.json"


# ────────────────────────────────────────────────────────────────────────────
# Text extraction
# ────────────────────────────────────────────────────────────────────────────

def extract_all_pages_layout(file_path):
    """
    Runs `pdftotext -layout` on the entire file and splits by form-feed
    into individual page strings.
    """
    result = subprocess.run(
        ["pdftotext", "-layout", file_path, "-"],
        capture_output=True, text=True, check=True
    )
    # \f is the form-feed page separator pdftotext inserts between pages
    pages = result.stdout.split("\f")
    return [p for p in pages if p.strip()]   # drop trailing empty entry


# ────────────────────────────────────────────────────────────────────────────
# Column-position helpers  (same algorithm as read_collection_final.py)
# ────────────────────────────────────────────────────────────────────────────

def parse_header_centres(header_line):
    """Returns [(label, centre_char_pos), ...] for every token in the line."""
    cols = []
    for m in re.finditer(r"\S+", header_line):
        centre = (m.start() + m.end()) / 2
        cols.append((m.group(), centre))
    return cols


def assign_values_to_columns(data_line, header_cols):
    """
    Maps every number in data_line to the header column whose centre is
    nearest to the number's own centre.  Returns {label: value_str}.
    Only the first value per column label is kept.
    Strips thousand-separator dots/commas (e.g. "3.876" -> "3876").
    """
    mapping = {}
    for m in re.finditer(r"[\d.,]+", data_line):
        val_centre = (m.start() + m.end()) / 2
        best_label, best_dist = None, float("inf")
        for label, col_centre in header_cols:
            dist = abs(val_centre - col_centre)
            if dist < best_dist:
                best_dist  = dist
                best_label = label
        if best_label and best_label not in mapping:
            mapping[best_label] = re.sub(r"[,.]", "", m.group())
    return mapping


# ────────────────────────────────────────────────────────────────────────────
# PO number generation
# ────────────────────────────────────────────────────────────────────────────

def generate_po_cw(filename, date_str):
    """
    '317515_CW-17.pdf'  +  date '21.04.2026'  ->  '317515 CW-17/26'

    date_str format: DD.MM.YYYY  (year is last 4 chars, short year = last 2)
    """
    try:
        base         = os.path.splitext(filename)[0]       # '317515_CW-17'
        article_part, type_week = base.split("_", 1)       # '317515', 'CW-17'
        file_type, week_ref     = type_week.split("-", 1)  # 'CW', '17'
        year_short   = date_str[-2:]                        # '2026' -> '26'
        return f"{article_part} {file_type.upper()}-{week_ref}/{year_short}"
    except Exception:
        return os.path.splitext(filename)[0]


# ────────────────────────────────────────────────────────────────────────────
# Per-page table parser
# ────────────────────────────────────────────────────────────────────────────

def parse_page_table(page_text):
    """
    Given the layout text of one page, finds the 'Summary of Order quantities'
    table and returns:
        header_cols : [(label, centre), ...]  -- ALL column labels detected
        rows        : list of dicts with keys color_id, color_name,
                      total_pcs (str), breakdown ({size: qty_str})

    The 'Total' row is not returned.
    """
    lines = page_text.splitlines()

    # Find the header row (contains 'Col' and 'Pcs')
    header_line = None
    header_idx  = None
    for i, line in enumerate(lines):
        if re.search(r"\bCol\b", line) and re.search(r"\bPcs\b", line, re.IGNORECASE):
            header_line = line
            header_idx  = i
            break

    if header_line is None:
        return [], []

    header_cols = parse_header_centres(header_line)
    skip_labels = {"Col", "Colour", "Pcs"}
    size_labels  = [lbl for lbl, _ in header_cols if lbl not in skip_labels]

    # Pre-compute once: START char position of the 'Pcs' token in the header.
    # Colour names occupy the gap between the colour-id token and this position,
    # so we use the START (not centre) to avoid capturing the Pcs number itself.
    pcs_col_start = next(
        (m.start() for m in re.finditer(r"\S+", header_line) if m.group() == "Pcs"),
        None
    )

    rows = []
    for line in lines[header_idx + 1:]:
        stripped = line.strip()
        if not stripped:
            continue

        first_token = stripped.split()[0]
        if first_token.lower() == "total":
            break   # Total row is always last on each page

        # Data rows: first token is always a 5-digit colour code
        if not re.match(r"^\d{5}$", first_token):
            continue

        col_values = assign_values_to_columns(line, header_cols)

        # Extract colour name: the text between the colour-id end and Pcs column
        col_id_end  = line.index(first_token) + len(first_token)
        name_region = line[col_id_end : pcs_col_start] if pcs_col_start else ""
        colour_name = re.sub(r"\s{2,}", " ", name_region).strip()

        total_pcs = col_values.get("Pcs", "")
        breakdown = {lbl: col_values[lbl] for lbl in size_labels if lbl in col_values}

        rows.append({
            "color_id":   first_token,
            "color_name": colour_name,
            "total_pcs":  total_pcs,
            "breakdown":  breakdown,
        })

    return header_cols, rows


# ────────────────────────────────────────────────────────────────────────────
# Metadata extractor  (page 1 only)
# ────────────────────────────────────────────────────────────────────────────

def extract_metadata(page1_text):
    """
    Pulls all scalar metadata fields from the first page's layout text.
    Returns a dict of raw string values.
    """
    t = page1_text

    date_match       = re.search(r"Date:\s*(\d{2}\.\d{2}\.\d{4})", t)
    company_match    = re.search(r"^(.*?)\s+GmbH\b", t, re.MULTILINE)
    collection_match = re.search(r"Collection:\s*(\S+)", t)
    handover_match   = re.search(r"Handover Date:\s*(\d{2}\.\d{2}\.\d{2})", t)
    # CW/NOS pages use "Article No." (no colon, or with) + 2+ spaces + desc
    article_match    = re.search(r"Article No\.?\s+(\d+)\s{2,}(.+?)\s{2,}", t)
    style_match      = re.search(r"Style No\.:\s*(\d+)", t)
    price_match      = re.search(r"Price:\s*([\d,]+)", t)

    return {
        "date":        date_match.group(1)            if date_match       else "Not Found",
        "company":     company_match.group(1).strip() if company_match    else "Not Found",
        "collection":  collection_match.group(1)      if collection_match else "Not Found",
        "handover":    handover_match.group(1)        if handover_match   else "Not Found",
        "article_no":  article_match.group(1)         if article_match    else "Not Found",
        "description": article_match.group(2).strip() if article_match    else "Not Found",
        "style_no":    style_match.group(1)           if style_match      else "Not Found",
        "price":       price_match.group(1).replace(",", ".") if price_match else "Not Found",
    }


# ────────────────────────────────────────────────────────────────────────────
# Main extraction function
# ────────────────────────────────────────────────────────────────────────────

def extract_cw_nos(file_path):
    """
    Reads ALL pages of a CW/NOS PDF, aggregates quantities across pages,
    and returns a structured result dict.

    Aggregation logic:
        - If colour X appears on page 1 with XL=25 and on page 2 with XL=30,
          the output has XL=55 for colour X.
        - Total Pcs is also summed across pages per colour.
        - Colour name is taken from the first page that mentions the colour.
    """
    filename = os.path.basename(file_path)
    pages    = extract_all_pages_layout(file_path)

    if not pages:
        raise ValueError(f"No pages found in {filename}")

    # ── Metadata from page 1 ────────────────────────────────────────────── #
    meta  = extract_metadata(pages[0])
    po_no = generate_po_cw(filename, meta["date"])

    # ── Aggregate tables from ALL pages ─────────────────────────────────── #
    agg_pcs    = defaultdict(int)              # color_id -> total pcs (summed)
    agg_sizes  = defaultdict(lambda: defaultdict(int))  # color_id -> {size -> qty}
    color_names = {}                           # color_id -> colour name (first seen)
    color_order = []                           # insertion-ordered list of colour ids
    size_order  = []                           # insertion-ordered list of size labels

    for page_text in pages:
        header_cols, rows = parse_page_table(page_text)

        # Track size column ordering from this page's header
        skip_labels = {"Col", "Colour", "Pcs"}
        for lbl, _ in header_cols:
            if lbl not in skip_labels and lbl not in size_order:
                size_order.append(lbl)

        for row in rows:
            cid = row["color_id"]

            # Register colour for ordering and name
            if cid not in color_names:
                color_names[cid] = row["color_name"]
                color_order.append(cid)

            # Sum Pcs
            pcs_str = row["total_pcs"]
            agg_pcs[cid] += int(pcs_str) if pcs_str.isdigit() else 0

            # Sum each size
            for size, qty_str in row["breakdown"].items():
                agg_sizes[cid][size] += int(qty_str) if qty_str.isdigit() else 0

    # ── Build output table ───────────────────────────────────────────────── #
    table = []
    for cid in color_order:
        # Breakdown in canonical size order; only include sizes with qty > 0
        breakdown = {
            sz: str(agg_sizes[cid][sz])
            for sz in size_order
            # if agg_sizes[cid].get(sz, 0) > 0  #This line skips the zeroes intentionally
        }
        table.append({
            "Color":      cid,
            "Color Name": color_names.get(cid, ""),
            "Total Pcs":  str(agg_pcs[cid]),
            "Breakdown":  breakdown,
        })

    return {
        "PO No.":        po_no,
        "Date":          meta["date"],
        "Company":       meta["company"],
        "Collection":    meta["collection"],
        "Handover Date": meta["handover"],
        "Article No":    meta["article_no"],
        "Description":   meta["description"],
        "Style No":      meta["style_no"],
        "Price":         meta["price"],
        "Table":         table,
    }


# ────────────────────────────────────────────────────────────────────────────
# Folder processor  (with duplicate prevention)
# ────────────────────────────────────────────────────────────────────────────

def process_folder():
    """
    Scans SOURCE_DIR for CW/NOS PDFs (filename pattern: <article>_CW-<n>.pdf
    or <article>_NOS-<n>.pdf), processes each, prevents duplicates via PO No.,
    moves files to SUCCESS_DIR or ERROR_DIR, and appends to LOG_FILE.
    """
    for d in [SOURCE_DIR, SUCCESS_DIR, ERROR_DIR]:
        os.makedirs(d, exist_ok=True)

    all_data = []
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            try:
                all_data = json.load(f)
            except json.JSONDecodeError:
                pass

    processed_po_set = {item["PO No."] for item in all_data}

    # Match CW or NOS filenames: <digits>_CW-<anything>.pdf
    cw_nos_pattern = re.compile(r"^\d+\s+(CW|NOS|QR)-.+\.pdf$", re.IGNORECASE)
    pdf_files = sorted(
        f for f in os.listdir(SOURCE_DIR)
        if f.lower().endswith(".pdf") and cw_nos_pattern.match(f)
    )

    if not pdf_files:
        print("No CW/NOS PDF files found in uploads/")
        return

    for filename in pdf_files:
        file_path = os.path.join(SOURCE_DIR, filename)

        # Peek at metadata to determine PO number before full processing
        try:
            pages = extract_all_pages_layout(file_path)
            meta  = extract_metadata(pages[0])
            po_no = generate_po_cw(filename, meta["date"])
        except Exception as e:
            print(f"  [ERR]  {filename} -- could not determine PO: {e}")
            shutil.move(file_path, os.path.join(ERROR_DIR, filename))
            continue

        if po_no in processed_po_set:
            print(f"  [SKIP] {filename} -- PO {po_no} already logged.")
            shutil.move(file_path, os.path.join(SUCCESS_DIR, filename))
            continue

        print(f"  [PROC] {filename}  ->  PO: {po_no}")
        try:
            data          = extract_cw_nos(file_path)
            all_data.append(data)
            processed_po_set.add(po_no)
            shutil.move(file_path, os.path.join(SUCCESS_DIR, filename))
            total_colours = len(data["Table"])
            total_pcs     = sum(int(r["Total Pcs"]) for r in data["Table"])
            print(f"         OK  {total_colours} colour(s), "
                  f"{total_pcs} total pcs across {len(pages)} page(s).")
        except Exception as e:
            print(f"         ERR {e}")
            shutil.move(file_path, os.path.join(ERROR_DIR, filename))

    with open(LOG_FILE, "w", encoding="utf-8") as f:
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
            print("=" * 60)
            result = extract_cw_nos(path)
            print(json.dumps(result, indent=4, ensure_ascii=False))
    else:
        process_folder()