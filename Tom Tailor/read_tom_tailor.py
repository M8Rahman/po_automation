import os
import re
import json
import shutil

# --- CONFIGURATION ---
SOURCE_DIR  = "uploads"
SUCCESS_DIR = "posted"
ERROR_DIR   = "errors"
LOG_FILE    = "tom_tailor_log.json"

# ────────────────────────────────────────────────────────────────────────────
# Core Extractor Logic
# ────────────────────────────────────────────────────────────────────────────

def extract_tom_tailor_pdf(file_path):
    """
    Extracts metadata + summary Total Production-Breakdown table from 
    Tom Tailor SAP Order PDFs using pages 1 and 2.
    """
    import pdfplumber
    filename = os.path.basename(file_path)
    
    # 1. Parse PO and Style Number from Filename (Bulletproof Key Extraction)
    base_name = os.path.splitext(filename)[0]
    file_match = re.search(r'^(\d+)-(\d+)$', base_name)
    fn_style_no = file_match.group(1) if file_match else "Unknown"
    fn_po_no = file_match.group(2) if file_match else "Unknown"

    # 2. Extract Text safely from Pages 1 and 2
    full_text = ""
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages[:2]:
            text_content = page.extract_text(layout=False)
            if text_content:
                full_text += text_content + "\n"

    lines = full_text.splitlines()

    # 3. Extract Metadata via Context-Aware Regex
    date_match = re.search(r'Date:\s*(\d{2}\.\d{2}\.\d{4})', full_text)
    ex_date_match = re.search(r'Ex-Country Date:\s*(\d{2}\.\d{2}\.\d{4})', full_text)
    desc_match = re.search(r'Article-Description.*?\n"?(.*?)"?\n', full_text, re.IGNORECASE)

    order_date = date_match.group(1) if date_match else "Not Found"
    ex_date = ex_date_match.group(1) if ex_date_match else "Not Found"
    description = desc_match.group(1).strip() if desc_match else "Not Found"

    # 4. Parse Total Production-Breakdown Table Rows
    size_headers = []
    header_idx = None
    table_data = []

    # Locate the definitive grid header line
    for i, line in enumerate(lines):
        if "Colours" in line and "Total" in line:
            tokens = [t.strip('" ,[]') for t in re.split(r'\s+', line)]
            size_headers = [t for t in tokens if t and t.lower() not in ['colours', 'total']]
            header_idx = i
            break

    if header_idx is not None:
        for line in lines[header_idx + 1:]:
            stripped = line.strip()
            if not stripped:
                continue
            
            # Cease scanning when hit summary bounds or subsequent channel matrices
            if stripped.lower().startswith("total") or "packing-breakdown" in stripped.lower():
                break

            tokens = stripped.split()
            # Every true color row starts with a strict 5-digit string pattern
            if not tokens or not re.match(r'^\d{5}$', tokens[0]):
                continue

            color_code = tokens[0]

            # Grab all numbers present in the string
            all_numbers = [t for t in tokens if t.replace(',', '').replace('.', '').isdigit()]
            
            # Slice away the color code from numbers array to keep purely quantities
            qty_tokens = all_numbers[1:]
            
            # Assign final index to Total Pcs, remaining tokens map to size list
            total_pcs = qty_tokens[-1] if qty_tokens else "0"
            size_qtys = qty_tokens[:-1] if qty_tokens else []

            # Clean and isolate the Color Name literal string text
            # Step A: Slice away the leading color code
            color_name_raw = stripped[len(color_code):].strip()
            # Step B: Safe regex substitution to strip off the trailing sequence of quantities
            color_name = re.sub(r'\s*[\d\s.,]+$', '', color_name_raw).strip()
            # Step C: Strip accidental outer quotes if formatted by SAP as a text cell literal
            color_name = color_name.strip('"\'')

            # Dynamic structural mapping of size keys to respective quantities
            breakdown = {}
            for idx, size_lbl in enumerate(size_headers):
                if idx < len(size_qtys):
                    breakdown[size_lbl] = size_qtys[idx]
                else:
                    breakdown[size_lbl] = "0"

            table_data.append({
                "Color": color_code,
                "Color Name": color_name,
                "Total Pcs": total_pcs,
                "Breakdown": breakdown
            })

    return {
        "PO No.": fn_po_no,
        "Date": order_date,
        "Company": "TOM TAILOR",
        "Article No": fn_style_no,
        "Description": description,
        "Handover Date": ex_date,
        "Table": table_data
    }

# ────────────────────────────────────────────────────────────────────────────
# Folder Workflow Automation Manager
# ────────────────────────────────────────────────────────────────────────────

def process_folder():
    """
    Scans SOURCE_DIR for Tom Tailor PDFs, extracts structural datasets,
    enforces duplicate validation, logs transaction states, and routes documents.
    """
    for folder in [SOURCE_DIR, SUCCESS_DIR, ERROR_DIR]:
        os.makedirs(folder, exist_ok=True)

    all_data = []
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, 'r', encoding='utf-8') as f:
            try:
                all_data = json.load(f)
            except json.JSONDecodeError:
                pass

    # Create reference index of historically committed purchase orders
    processed_po_set = {item["PO No."] for item in all_data if "PO No." in item}
    
    # Scan target directory for valid PDFs
    pdf_files = sorted(f for f in os.listdir(SOURCE_DIR) if f.lower().endswith('.pdf'))

    if not pdf_files:
        print(f"No PDF files discovered inside target '{SOURCE_DIR}/' folder.")
        return

    for filename in pdf_files:
        file_path = os.path.join(SOURCE_DIR, filename)
        
        # Pre-calculate PO via parsing layer to enforce unique check early
        base_name = os.path.splitext(filename)[0]
        file_match = re.search(r'^(\d+)-(\d+)$', base_name)
        extracted_po = file_match.group(2) if file_match else base_name

        if extracted_po in processed_po_set:
            print(f"  [SKIP] {filename} -- PO {extracted_po} historically committed.")
            shutil.move(file_path, os.path.join(SUCCESS_DIR, filename))
            continue

        print(f"  [PROC] {filename} -> Target PO ID: {extracted_po}")
        try:
            data = extract_tom_tailor_pdf(file_path)
            all_data.append(data)
            processed_po_set.add(extracted_po)
            shutil.move(file_path, os.path.join(SUCCESS_DIR, filename))
            print(f"         SUCCESS: Captured {len(data['Table'])} structural row units.")
        except Exception as err:
            print(f"         FAILURE: Operational extraction fault -> {err}")
            shutil.move(file_path, os.path.join(ERROR_DIR, filename))

    # Safely commit records to persistent log tracking file
    with open(LOG_FILE, 'w', encoding='utf-8') as f:
        json.dump(all_data, f, indent=4, ensure_ascii=False)

    print(f"\nProcessing lifecycle completed. State records persistent in '{LOG_FILE}'.")

# ────────────────────────────────────────────────────────────────────────────
# Execution Routing
# ────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    # If arguments are passed, trigger immediate single file test mode
    if len(sys.argv) > 1:
        for path in sys.argv[1:]:
            if os.path.exists(path):
                print(f"\n============================================================")
                print(f"Single Target CLI Execution Mode: {os.path.basename(path)}")
                print(f"============================================================")
                print(json.dumps(extract_tom_tailor_pdf(path), indent=4, ensure_ascii=False))
    else:
        # Standard loop processing execution flow
        # For a quick Colab folder simulation execution context:
        print("Initializing directory workflow processing loops...")
        process_folder()