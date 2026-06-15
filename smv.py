# import pyautogui
# import time
# import pandas as pd
# import pygetwindow as gw
# import os
# from tkinter import *
# from tkinter import filedialog, messagebox

# # --- CONFIGURATION ---
# CONFIDENCE_LEVEL = 0.8
# FIELD_X_OFFSET = 150 
# ASSET_PATH = "assets/smv/"
# ERP_TITLE = 'CLICK ERP - FAST. ACCURATE. INFORMATION'
# FIXED_VAL = "3"

# def bring_erp_to_front():
#     try:
#         erp_window = gw.getWindowsWithTitle(ERP_TITLE)[0]
#         if erp_window.isMinimized:
#             erp_window.restore()
#         erp_window.activate()
#         time.sleep(1)
#         return True
#     except IndexError:
#         print("DEBUG: Could not find the ERP window.")
#         return False

# def find_and_click(img, desc, click_type='single', wait=0.5, offset_x=0, retries=3):
#     """Enhanced click function with internal retries for menu stability."""
#     path = os.path.join(ASSET_PATH, img)
#     if not os.path.exists(path):
#         print(f"DEBUG: Asset missing -> {path}")
#         return None
        
#     for attempt in range(retries):
#         try:
#             location = pyautogui.locateOnScreen(path, confidence=CONFIDENCE_LEVEL, grayscale=True)
#             if location:
#                 center = pyautogui.center(location)
#                 target_x = center.x + offset_x
#                 target_y = center.y
                
#                 if click_type == 'double':
#                     pyautogui.doubleClick(target_x, target_y)
#                 else:
#                     pyautogui.click(target_x, target_y)
#                 print(f"Success: {desc}")
#                 time.sleep(wait)
#                 return center 
#         except Exception as e:
#             print(f"DEBUG: Attempt {attempt+1} failed for {desc}: {e}")
        
#         time.sleep(0.5) # Short wait before retry
    
#     print(f"DEBUG: Error searching for {desc} after {retries} attempts.")
#     return None

# def force_clear_and_type(value, press_backspace_count=7):
#     for _ in range(press_backspace_count):
#         pyautogui.press('backspace')
#     time.sleep(0.1)
#     pyautogui.write(str(value))

# def process_smv_entry(buyer_name, display_style, smv_val):
#     """Refreshes the page and types the 'display_style' into the ERP field."""
#     print(f"\n>>> PROCESSING: {display_style} | BUYER: {buyer_name.upper()} | SMV: {smv_val}")
    
#     # 1. Navigation Refresh
#     # Clicking IE Tools then Set Style SMV clears the previous entry.
#     if not find_and_click('ie_tools_menu.png', 'IE Tools Menu'): return False
#     if not find_and_click('set_style_smv_btn.png', 'Set Style SMV'): return False

#     # 2. Search Style (For Tom Tailor, display_style is the ORDER value)
#     if not find_and_click('style_no_field.png', 'Style No Field'): return False
#     pyautogui.write(str(display_style))
#     time.sleep(1.5)

#     # 3. Buyer Selection
#     buyer_img = f"{str(buyer_name).lower().replace(' ', '_')}.png"
#     if not find_and_click(buyer_img, f"Buyer: {buyer_name}", click_type='double'):
#         return False

#     pyautogui.press('down')
#     pyautogui.press('enter')
#     time.sleep(2.5) 

#     # 4. Data Entry Logic[cite: 3]
#     if find_and_click('sewing_smv_field.png', 'Sewing SMV Field', offset_x=FIELD_X_OFFSET):
#         force_clear_and_type(smv_val, 10) # Increased backspace for safety
#         pyautogui.press('tab')
#         force_clear_and_type(FIXED_VAL, 1) 
#         pyautogui.press('tab')
#         force_clear_and_type(FIXED_VAL, 1)
        
#         for _ in range(6): # Operator Sewing Tabs
#             pyautogui.press('tab')
#         force_clear_and_type(FIXED_VAL, 1)
#         pyautogui.press('tab')
#         force_clear_and_type(FIXED_VAL, 1)

#     # 5. Finalize
#     time.sleep(0.5)
#     btn_found = find_and_click('save_btn.png', 'Save Button')
#     if not btn_found:
#         btn_found = find_and_click('update_btn.png', 'Update Button')
    
#     if btn_found:
#         time.sleep(1.5)
#         if find_and_click('ok_btn.png', 'Success OK'):
#             print(f"DONE: {display_style} finalized.")
#             time.sleep(1.0) 
#             return True
    
#     return False

# def start_automation(file_path, order_filter, manual_input, selected_buyer):
#     if not bring_erp_to_front(): return

#     try:
#         df = pd.read_excel(file_path, header=1)
#         df.columns = df.columns.str.strip()

#         filtered_df = pd.DataFrame()

#         # Filtering Logic[cite: 3]
#         if manual_input:
#             input_list = [s.strip() for s in manual_input.split(',')]
#             # Tom Tailor searches ORDER column, others search Style column[cite: 3]
#             search_col = 'ORDER' if selected_buyer == "Tom Tailor" else 'Style/Article Name'
#             filtered_df = df[df[search_col].astype(str).isin(input_list)]
#         elif order_filter:
#             filtered_df = df[df['ORDER'].astype(str).str.contains(order_filter, case=False, na=False)]
#             print(f"DEBUG: Order Filter '{order_filter}' found {len(filtered_df)} matching rows.")

#         if filtered_df.empty:
#             messagebox.showwarning("No Data", "No matching records found.")
#             return

#         # Main Module Navigation (Once)[cite: 3]
#         if not find_and_click('industrial_engineering_btn.png', 'IE Module'): return

#         for _, row in filtered_df.iterrows():
#             # For Tom Tailor, the 'ORDER' is used as the Style Number in ERP[cite: 3]
#             if selected_buyer == "Tom Tailor":
#                 style_to_type = str(row['ORDER']).strip()
#             else:
#                 style_to_type = str(row['Style/Article Name']).strip()
                
#             buyer_for_erp = str(row['Buyer']).strip() if 'Buyer' in row else selected_buyer
#             raw_smv = row['SMV']
            
#             try:
#                 smv_val = "{:.2f}".format(float(raw_smv)) if not pd.isna(raw_smv) else None
#             except ValueError: continue

#             if smv_val and style_to_type != "nan":
#                 # If entry fails, we log it and continue to the next one
#                 success = process_smv_entry(buyer_for_erp, style_to_type, smv_val)
#                 if not success:
#                     print(f"CRITICAL: Failed to process {style_to_type}. Moving to next.")

#         messagebox.showinfo("Finished", "Batch process completed.")

#     except Exception as e:
#         print(f"DEBUG: Excel Error: {e}")
#         messagebox.showerror("Error", f"An error occurred: {e}")

# def select_and_run():
#     order_val = order_entry.get().strip()
#     styles_val = style_entry.get().strip()
#     buyer_val = buyer_var.get()
    
#     if not order_val and not styles_val:
#         messagebox.showwarning("Input Required", "Provide an Order filter or Specific inputs.")
#         return

#     file_path = filedialog.askopenfilename(title="Select Excel", filetypes=[("Excel", "*.xlsx *.xls")])
#     if file_path:
#         status_label.config(text="Processing...")
#         root.update()
#         start_automation(file_path, order_val, styles_val, buyer_val)
#         status_label.config(text="Ready")

# # --- GUI ---
# root = Tk()
# root.title("ERP SMV Automator v4")
# root.geometry("450x450")
# root.config(padx=20, pady=20)

# Label(root, text="Select Buyer", font=("Arial", 10, "bold")).pack(anchor=W)
# buyer_options = ["Cecil", "Tom Tailor"]
# buyer_var = StringVar(root)
# buyer_var.set(buyer_options[0])
# OptionMenu(root, buyer_var, *buyer_options).pack(fill=X, pady=(0, 15))

# Label(root, text="1. Specific Style/Order(s)", font=("Arial", 10, "bold")).pack(anchor=W)
# style_entry = Entry(root)
# style_entry.pack(fill=X, pady=(0, 15))

# Label(root, text="2. OR Order Filter (Case-Insensitive)", font=("Arial", 10, "bold")).pack(anchor=W)
# order_entry = Entry(root)
# order_entry.pack(fill=X, pady=(0, 15))

# Button(root, text="Select Excel & Start", command=select_and_run, bg="#cfe2f3", font=("Arial", 10, "bold")).pack(fill=X, pady=10)
# status_label = Label(root, text="Ready", fg="blue")
# status_label.pack()

# root.mainloop()



import pyautogui
import time
import pandas as pd
import pygetwindow as gw
import os
from datetime import datetime
from tkinter import *
from tkinter import filedialog, messagebox

# --- CONFIGURATION ---
CONFIDENCE_LEVEL = 0.8
FIELD_X_OFFSET = 150 
ASSET_PATH = "assets/smv/"
ERP_TITLE = 'CLICK ERP - FAST. ACCURATE. INFORMATION'
FIXED_VAL = "3"

def log_error(style, error_msg):
    """Creates/Appends to an error log text file."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open("smv_error_log.txt", "a") as f:
        f.write(f"[{timestamp}] STYLE: {style} | ERROR: {error_msg}\n")

def bring_erp_to_front():
    try:
        erp_window = gw.getWindowsWithTitle(ERP_TITLE)[0]
        if erp_window.isMinimized:
            erp_window.restore()
        erp_window.activate()
        time.sleep(1)
        return True
    except IndexError:
        print("DEBUG: Could not find the ERP window.")
        return False

def find_and_click(img, desc, click_type='single', wait=0.5, offset_x=0, retries=3):
    path = os.path.join(ASSET_PATH, img)
    if not os.path.exists(path):
        print(f"DEBUG: Asset missing -> {path}")
        return None
        
    for attempt in range(retries):
        try:
            location = pyautogui.locateOnScreen(path, confidence=CONFIDENCE_LEVEL, grayscale=True)
            if location:
                center = pyautogui.center(location)
                target_x = center.x + offset_x
                target_y = center.y
                
                if click_type == 'double':
                    pyautogui.doubleClick(target_x, target_y)
                else:
                    pyautogui.click(target_x, target_y)
                print(f"Success: {desc}")
                time.sleep(wait)
                return center 
        except Exception:
            pass
        time.sleep(0.5)
    
    return None

def force_clear_and_type(value, press_backspace_count=10):
    for _ in range(press_backspace_count):
        pyautogui.press('backspace')
    time.sleep(0.1)
    pyautogui.write(str(value))

def process_smv_entry(buyer_name, display_style, smv_val):
    """Refreshes the page and types the 'display_style' into the ERP field."""
    # 1. Navigation Refresh
    if not find_and_click('ie_tools_menu.png', 'IE Tools Menu'): return "Menu missing"
    if not find_and_click('set_style_smv_btn.png', 'Set Style SMV'): return "Button missing"

    # 2. Search Style
    if not find_and_click('style_no_field.png', 'Style No Field'): return "Search field missing"
    pyautogui.write(str(display_style))
    time.sleep(1.5)

    # 3. Buyer Selection
    buyer_img = f"{str(buyer_name).lower().replace(' ', '_')}.png"
    if not find_and_click(buyer_img, f"Buyer: {buyer_name}", click_type='double'):
        return f"Buyer image {buyer_img} not found"

    pyautogui.press('down')
    pyautogui.press('enter')
    time.sleep(2.5) 

    # 4. Data Entry
    if find_and_click('sewing_smv_field.png', 'Sewing SMV Field', offset_x=FIELD_X_OFFSET):
        force_clear_and_type(smv_val)
        pyautogui.press('tab')
        force_clear_and_type(FIXED_VAL, 1) 
        pyautogui.press('tab')
        force_clear_and_type(FIXED_VAL, 1)
        for _ in range(6): 
            pyautogui.press('tab')
        force_clear_and_type(FIXED_VAL, 1)
        pyautogui.press('tab')
        force_clear_and_type(FIXED_VAL, 1)
    else:
        return "SMV Field not found"

    # 5. Finalize
    time.sleep(0.5)
    btn_found = find_and_click('save_btn.png', 'Save Button') or find_and_click('update_btn.png', 'Update Button')
    
    if btn_found:
        time.sleep(1.5)
        if find_and_click('ok_btn.png', 'Success OK'):
            return "SUCCESS"
    
    return "Failed to save/update"

def start_automation(file_path, order_filter, manual_input, selected_buyer, process_all):
    if not bring_erp_to_front(): return

    try:
        df = pd.read_excel(file_path, header=1)
        df.columns = df.columns.str.strip()
        filtered_df = pd.DataFrame()

        # Selection Logic
        if process_all:
            # Drop duplicates to process each style only once
            style_col = 'ORDER' if selected_buyer == "Tom Tailor" else 'Style/Article Name'
            filtered_df = df.drop_duplicates(subset=[style_col])
            print(f"DEBUG: Processing ALL unique styles. Found {len(filtered_df)} total.")
        elif manual_input:
            input_list = [s.strip() for s in manual_input.split(',')]
            search_col = 'ORDER' if selected_buyer == "Tom Tailor" else 'Style/Article Name'
            filtered_df = df[df[search_col].astype(str).isin(input_list)]
        elif order_filter:
            filtered_df = df[df['ORDER'].astype(str).str.contains(order_filter, case=False, na=False)]

        if filtered_df.empty:
            messagebox.showwarning("No Data", "No matching records found.")
            return

        if not find_and_click('industrial_engineering_btn.png', 'IE Module'): return

        for _, row in filtered_df.iterrows():
            style_to_type = str(row['ORDER']).strip() if selected_buyer == "Tom Tailor" else str(row['Style/Article Name']).strip()
            buyer_for_erp = str(row['Buyer']).strip() if 'Buyer' in row else selected_buyer
            raw_smv = row['SMV']
            
            # Validation before ERP attempt
            if pd.isna(raw_smv) or style_to_type == "nan":
                log_error(style_to_type, "Missing SMV or Style name in Excel")
                continue

            try:
                smv_val = "{:.2f}".format(float(raw_smv))
            except ValueError:
                log_error(style_to_type, f"Invalid SMV value: {raw_smv}")
                continue

            # ERP Processing
            result = process_smv_entry(buyer_for_erp, style_to_type, smv_val)
            if result != "SUCCESS":
                log_error(style_to_type, result)
                print(f"FAILED: {style_to_type} - {result}")
            else:
                print(f"DONE: {style_to_type}")

        messagebox.showinfo("Finished", "Batch process completed. Check smv_error_log.txt for failures.")

    except Exception as e:
        messagebox.showerror("Error", f"An error occurred: {e}")

def select_and_run():
    order_val = order_entry.get().strip()
    styles_val = style_entry.get().strip()
    buyer_val = buyer_var.get()
    all_val = process_all_var.get()
    
    if not order_val and not styles_val and not all_val:
        messagebox.showwarning("Input Required", "Select 'Add All', provide an Order filter, or Specific inputs.")
        return

    file_path = filedialog.askopenfilename(title="Select Excel", filetypes=[("Excel", "*.xlsx *.xls")])
    if file_path:
        status_label.config(text="Processing...")
        root.update()
        start_automation(file_path, order_val, styles_val, buyer_val, all_val)
        status_label.config(text="Ready")

# --- GUI ---
root = Tk()
root.title("ERP SMV Automator v5")
root.geometry("450x500")
root.config(padx=20, pady=20)

# Buyer Dropdown
Label(root, text="Select Buyer", font=("Arial", 10, "bold")).pack(anchor=W)
buyer_options = ["Cecil", "Tom Tailor"]
buyer_var = StringVar(root)
buyer_var.set(buyer_options[0])
OptionMenu(root, buyer_var, *buyer_options).pack(fill=X, pady=(0, 15))

# Process All Checkbox
process_all_var = BooleanVar()
Checkbutton(root, text="Add All Unique Styles (Ignore Filters)", variable=process_all_var, font=("Arial", 10, "bold")).pack(anchor=W, pady=(0, 15))

Label(root, text="1. Specific Style/Order(s)", font=("Arial", 10, "bold")).pack(anchor=W)
style_entry = Entry(root)
style_entry.pack(fill=X, pady=(0, 15))

Label(root, text="2. OR Order Filter (Case-Insensitive)", font=("Arial", 10, "bold")).pack(anchor=W)
order_entry = Entry(root)
order_entry.pack(fill=X, pady=(0, 15))

Button(root, text="Select Excel & Start", command=select_and_run, bg="#cfe2f3", font=("Arial", 10, "bold")).pack(fill=X, pady=10)
status_label = Label(root, text="Ready", fg="blue")
status_label.pack()

root.mainloop()