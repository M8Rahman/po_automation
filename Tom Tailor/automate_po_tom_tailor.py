import pyautogui
import time
import json
import pygetwindow as gw
import os
import pyperclip

# --- CONFIGURATION ---
CONFIDENCE_LEVEL = 0.8
ASSET_PATH = "assets/po/"
DATA_FILE = "tom_tailor_log.json"  # Points to your new Tom Tailor dataset

def bring_erp_to_front():
    """Finds the ERP window by title and brings it to focus."""
    try:
        erp_window = gw.getWindowsWithTitle('CLICK ERP - FAST. ACCURATE. INFORMATION')[0]
        if erp_window.isMinimized:
            erp_window.restore()
        erp_window.activate()
        print("ERP Window activated.")
        time.sleep(1)
        return True
    except IndexError:
        print("Error: Could not find the ERP window.")
        return False

# --- HELPER FUNCTIONS ---

def find_and_click(img, desc, click_type='single', wait=1):
    """Locates an image on screen and interacts with it using pacing cushions."""
    path = os.path.join(ASSET_PATH, img)
    try:
        location = pyautogui.locateOnScreen(path, confidence=CONFIDENCE_LEVEL)
        if location:
            center = pyautogui.center(location)
            if click_type == 'double':
                pyautogui.doubleClick(center)
            else:
                pyautogui.click(center)
            print(f"Success: {desc}")
            time.sleep(wait)
            return center 
        print(f"Failed: Could not find {desc}")
        return None
    except Exception as e:
        print(f"Error finding {desc}: {e}")
        return None

def handle_keyboard_date(img_path, date_str):
    """Enters dates by clicking the field and using arrow keys to move segments."""
    parts = date_str.replace('.', ' ').replace('/', ' ').split()
    day, month, year = parts[0], parts[1], parts[2]
    
    path = os.path.join(ASSET_PATH, img_path)
    try:
        location = pyautogui.locateOnScreen(path, confidence=CONFIDENCE_LEVEL)
        if location:
            left, top, width, height = location
            pyautogui.click(left + (width * 0.1), top + (height / 2))
            time.sleep(0.3)
            pyautogui.write(day)
            pyautogui.press('right')
            pyautogui.write(month)
            pyautogui.press('right')
            pyautogui.write(year)
            print(f"Success: Date {date_str} entered.")
            return True
        return False
    except Exception as e:
        print(f"Error in date entry: {e}")
        return False

def select_color_by_cycling(target_code, is_first_color=True, max_attempts=300):
    """
    Uses Size field as a mechanical anchor to return to Color field, 
    cycling downward until the target color digit string matches.
    """
    print(f"Targeting Color Code: {target_code}")
    
    if is_first_color:
        if not find_and_click('color_field_box.png', 'Color Field Focus'): return False
    else:
        if not find_and_click('size_field_box.png', 'Size Field Anchor'): return False
        time.sleep(0.3)
        pyautogui.hotkey('shift', 'tab')
        time.sleep(0.2)
        pyautogui.press('backspace')
        time.sleep(0.2)

    pyautogui.press('home')
    time.sleep(0.3)

    for i in range(max_attempts):
        pyautogui.hotkey('ctrl', 'a')
        pyautogui.hotkey('ctrl', 'c')
        time.sleep(0.1)
        current_text = pyperclip.paste().strip()

        if str(target_code) in current_text:
            print(f"Match: {current_text}")
            pyautogui.press('enter')
            time.sleep(0.5)
            return True
        
        pyautogui.press('down')
    return False

def enter_grid_quantities(item_data, is_first_color=True):
    """Dynamically enters quantities into the matrix column based on JSON keys."""
    if is_first_color:
        print("Navigating to grid for the first time...")
        pyautogui.press('tab', presses=17, interval=0.1)
    else:
        print("Returning to grid position...")
        pyautogui.press('tab', presses=14, interval=0.1)
        pyautogui.press('down')
        time.sleep(0.2)

    breakdown = item_data['Breakdown']
    size_order = list(breakdown.keys()) 

    print(f"Processing sizes dynamically: {size_order}")

    for i, size in enumerate(size_order):
        qty = breakdown.get(size, "0")
        pyautogui.write(str(qty))
        
        # Move down to the next size grid row until the end of this color's set
        if i < len(size_order) - 1:
            pyautogui.press('down')
            time.sleep(0.1)

    print(f"Finished grid block for color {item_data['Color']}.")

# --- MAIN WORKFLOW ---

def run_navigation():
    """Initializes and navigates with robust delays between window transitions."""
    print("\n--- Phase 1: Navigation ---")
    if not find_and_click('merchandising_btn.png', 'Merchandising Module', wait=0.5): return False
    time.sleep(0.2)
    if not find_and_click('merchandising_menu.png', 'Merchandising Menu', wait=0.5): return False
    time.sleep(0.2)
    if not find_and_click('buyer_po.png', 'Buyer Purchase Order', wait=0.5): return False 
    time.sleep(0.2)
    if not find_and_click('po_entry.png', 'Purchase Order Entry', wait=0.5): return False
    time.sleep(0.2)
    return True

def process_po_data(po_data):
    """Executes the exact structural input matrix field entry for a single PO dataset."""
    print(f"\n--- Phase 2: Processing PO {po_data['PO No.']} ---")

    # Start by opening a clean form context
    time.sleep(0.2)
    if not find_and_click('create_new_po.png', 'Create New PO', wait=0.5): return

    # 1. Buyer Mapping
    time.sleep(0.2)
    if not find_and_click('buyer_dropdown.png', 'Buyer Dropdown', wait=0.5): return
    buyer_img = f"buyer_{po_data['Company'].lower().replace(' ', '_')}.png"
    time.sleep(0.2)
    if not find_and_click(buyer_img, f"Buyer {po_data['Company']}"): return

    # 2. Agent Field Bypass
    path = os.path.join(ASSET_PATH, 'buying_agent_dropdown.png')
    loc = pyautogui.locateOnScreen(path, confidence=CONFIDENCE_LEVEL)
    if loc:
        pyautogui.click(loc.left + (loc.width * 0.95), loc.top + (loc.height / 2))
        time.sleep(1)
        find_and_click('na_option.png', 'NA Option')

    # 3. PO Number Entry
    po_loc = find_and_click('po_field.png', 'PO Field')
    if po_loc: 
        pyautogui.write(po_data['PO No.'], interval=0.05)

    # 4. Season Bypass
    if find_and_click('season_field.png', 'Season Field', click_type='double'):
        find_and_click('na_season.png', 'NA Season')

    # 5. Order Creation Date
    handle_keyboard_date('date_field_box.png', po_data['Date'])

    # 6. Article Number Field Entry (Fixed KeyError bug context)
    style_center = find_and_click('style_field.png', 'Style Field', click_type='double', wait=0.5)
    if style_center:
        pyautogui.write(po_data['Article No'], interval=0.1)
        time.sleep(2)
        pyautogui.click(style_center.x, style_center.y + 40)

    # 7. Dynamic Color Table & Size Processing Loop
    for index, item in enumerate(po_data['Table']):
        is_first = (index == 0)
        if not select_color_by_cycling(item['Color'], is_first_color=is_first):
            continue

        # Generous 2-second buffer for the ERP to map out internal inventory subgrids
        time.sleep(2)

        if is_first:
            # Correctly inputs the renamed 'Handover Date' attribute
            handle_keyboard_date('etd_field_box.png', po_data['Handover Date'])
            
        if not find_and_click('add_all_size_btn.png', 'Add All Size'): 
            continue
        time.sleep(2)
        
        enter_grid_quantities(item, is_first_color=is_first)

    # Commit data entry modifications and Save sequence
    pyautogui.press('enter')
    time.sleep(1)
    
    if find_and_click('save_btn.png', 'Save Button'):
        time.sleep(2) 
        find_and_click('ok_btn.png', 'Success OK Button')
        time.sleep(1)
        
        # Return cleanly to base list index state
        find_and_click('back_to_list_btn.png', 'Back to List Button')
        time.sleep(1)

    print(f"--- PO {po_data['PO No.']} Processing Lifecycle Finished ---")

def main():
    # Emergency cursor corner safeguard protocol activated
    pyautogui.FAILSAFE = True
    
    if not bring_erp_to_front(): return
    if not run_navigation(): return

    try:
        if not os.path.exists(DATA_FILE):
            print(f"Error: Target extraction data source '{DATA_FILE}' was not located.")
            return

        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            all_pos = json.load(f)
        
        print(f"Discovered {len(all_pos)} Purchase Orders scheduled for automated entry processing.")
        for po in all_pos:
            process_po_data(po)
            
    except Exception as e:
        print(f"Critical execution error encountered: {e}")

if __name__ == "__main__":
    main()