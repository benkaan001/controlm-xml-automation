import xml.etree.ElementTree as ET
import re
import copy
import sys

# --- Modification Functions ---

def activate_folders(root: ET.Element) -> int:
    """
    Sets FOLDER_ORDER_METHOD to 'SYSTEM' for all FOLDER elements
    that don't already have it set to 'SYSTEM'. Modifies the tree in place.

    Args:
        root: The root ET.Element of the XML tree to modify.

    Returns:
        The number of folders modified, or -1 if an error occurred.
    """
    print("  Ensuring all folders are active (FOLDER_ORDER_METHOD='SYSTEM')...")
    activated_count = 0
    try:
        # Find all FOLDER elements directly under the root
        for folder in root.findall('FOLDER'):
            current_method = folder.get('FOLDER_ORDER_METHOD')
            # Activate if attribute is missing or has a different value
            if current_method != 'SYSTEM':
                folder_name = folder.get('FOLDER_NAME', 'UNKNOWN_FOLDER')
                print(f"    Setting folder to SYSTEM: {folder_name} (was: {current_method})")
                folder.set('FOLDER_ORDER_METHOD', 'SYSTEM')
                activated_count += 1
    except Exception as e:
        # Log unexpected errors during processing
        print(f"  Error during folder activation: {e}", file=sys.stderr)
        return -1

    print(f"  Activation check complete. Folders set to SYSTEM: {activated_count}.")
    return activated_count

# --- Placeholder functions for future steps ---
# These will be implemented incrementally

def apply_environment_promotion(root: ET.Element, target_env: str):
    print(f"  [Placeholder] apply_environment_promotion for {target_env}")
    pass

def standardize_resources(root: ET.Element, target_env: str):
    print(f"  [Placeholder] standardize_resources for {target_env}")
    pass

def standardize_notifications(root: ET.Element, target_env: str):
    print(f"  [Placeholder] standardize_notifications for {target_env}")
    pass

# --- Constants (Placeholders for later implementation) ---
ENV_CONFIG = {
    'dev': {}, 'preprod': {}, 'prod': {}
}
NOTIFICATION_TEMPLATE_PREPROD = ""
NOTIFICATION_TEMPLATE_PROD = ""
