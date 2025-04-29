import xml.etree.ElementTree as ET
import re
import copy
import sys

# --- Constants ---

# Environment specific values (Keep placeholders or refine as needed)
ENV_CONFIG = {
    'dev': {
        'notification_dest': 'dev-alerts@example.com',
        'remedy_urgency': 'L',
    },
    'preprod': {
        'notification_dest': 'preprod-alerts@example.com',
        'remedy_urgency': 'M',
    },
    'prod': {
        'notification_dest': 'prod-support@example.com',
        'remedy_urgency': 'H',

    }
}

# Notification templates (Anonymized XML snippets)
NOTIFICATION_TEMPLATE_PREPROD = """
<ON STMT="*" CODE="NOTOK">
    <DOACTION ACTION="NOTOK" />
    <DOMAIL URGENCY="R" DEST="{dest}" SUBJECT="PREPROD FAILED Job: %%JOBNAME" MESSAGE="Job %%JOBNAME failed on %%NODEID. Check logs." ATTACH_SYSOUT="Y"/>
    <DOSHOUT URGENCY="R" MESSAGE="PREPROD Job %%JOBNAME Failed" DEST="PreprodSupportTeam"/>
</ON>
<ON STMT="*" CODE="ENDEDOK">
    <DOMAIL URGENCY="S" DEST="{dest}" SUBJECT="PREPROD OK Job: %%JOBNAME" MESSAGE="Job %%JOBNAME OK." ATTACH_SYSOUT="N"/>
</ON>
"""

NOTIFICATION_TEMPLATE_PROD = """
<ON STMT="*" CODE="NOTOK">
    <DOACTION ACTION="NOTOK" />
    <DOREMEDY URGENCY="{urgency}" DESCRIPTION="PROD FAILURE: Control-M job %%JOBNAME run %%RUNCOUNT failed on node %%NODEID RC=%%COMPSTAT App=%%APPLIC Group=%%APPLGROUP" SUMMARY="PROD FAILURE: %%JOBNAME on %%NODEID RC=%%COMPSTAT"/>
    <DOMAIL URGENCY="C" DEST="{dest}" SUBJECT="CRITICAL PROD FAILED Job: %%JOBNAME" MESSAGE="PROD Job %%JOBNAME failed on %%NODEID. Remedy Ticket Created. Check logs." ATTACH_SYSOUT="Y"/>
    <DOSHOUT URGENCY="C" MESSAGE="CRITICAL PROD Job %%JOBNAME Failed - PagerDuty" DEST="ProdOnCallPager"/>
</ON>
"""

# --- Pre-parsed Notification Templates ---
PARSED_NOTIFICATIONS = {}
try:
    # Only parse templates for environments where standardization applies
    for env, template in [('preprod', NOTIFICATION_TEMPLATE_PREPROD), ('prod', NOTIFICATION_TEMPLATE_PROD)]:
        # Check if config exists before formatting
        if env not in ENV_CONFIG:
             print(f"WARNING: Missing ENV_CONFIG entry for '{env}', cannot parse notification template.", file=sys.stderr)
             continue
        cfg = ENV_CONFIG[env]
        formatted_template = template.format(
            dest=cfg.get('notification_dest', 'default_dest@example.com'), # Use .get for safety
            urgency=cfg.get('remedy_urgency', 'M')
        )
        root_wrapper = ET.fromstring(f"<root>{formatted_template}</root>")
        PARSED_NOTIFICATIONS[env] = list(root_wrapper)
except ET.ParseError as e:
    print(f"FATAL ERROR: Could not parse notification template XML. Details: {e}", file=sys.stderr)
    PARSED_NOTIFICATIONS = {}
except KeyError as e:
     print(f"FATAL ERROR: Missing key {e} in ENV_CONFIG for notification templates.", file=sys.stderr)
     PARSED_NOTIFICATIONS = {}


# --- Modification Functions ---

def activate_folders(root: ET.Element) -> int:
    """
    Sets FOLDER_ORDER_METHOD to 'SYSTEM' for all FOLDER elements
    that don't already have it set to 'SYSTEM'. Modifies the tree in place.
    """
    print("  Ensuring all folders are active (FOLDER_ORDER_METHOD='SYSTEM')...")
    activated_count = 0
    try:
        for folder in root.findall('FOLDER'):
            current_method = folder.get('FOLDER_ORDER_METHOD')
            if current_method != 'SYSTEM':
                folder_name = folder.get('FOLDER_NAME', 'UNKNOWN_FOLDER')
                print(f"    Setting folder to SYSTEM: {folder_name} (was: {current_method})")
                folder.set('FOLDER_ORDER_METHOD', 'SYSTEM')
                activated_count += 1
    except Exception as e:
        print(f"  Error during folder activation: {e}", file=sys.stderr)
        return -1

    print(f"  Activation check complete. Folders set to SYSTEM: {activated_count}.")
    return activated_count

def standardize_notifications(root: ET.Element, target_env: str):
    """
    Replaces existing ON blocks within each JOB with standardized templates
    for the target environment ('preprod' or 'prod'). Skips if target_env is 'dev'.
    Modifies the tree in place.
    """
    print(f"  Standardizing notifications for target: {target_env}")

    # Explicitly skip if target is 'dev' since the notification is updated only for preprod and prod promotions
    if target_env == 'dev':
        print(f"  Skipping notification standardization for 'dev' environment.")
        return

    # Check if templates are available for the target env (preprod/prod)
    if target_env not in PARSED_NOTIFICATIONS:
        print(f"  Error: Notification templates not available or invalid for target env '{target_env}'. Skipping step.", file=sys.stderr)
        return

    notification_elements_template = PARSED_NOTIFICATIONS[target_env]
    jobs_processed = 0

    try:
        for job in root.findall('.//JOB'):
            job_name = job.get('JOBNAME', 'UNKNOWN_JOB')

            # Find and remove existing ON elements
            existing_on_elements = job.findall('ON')
            if existing_on_elements:
                for on_elem in existing_on_elements:
                    job.remove(on_elem)

            # Append deep copies of the standard ON elements
            for on_template in notification_elements_template:
                new_on_element = copy.deepcopy(on_template)
                job.append(new_on_element)
            jobs_processed += 1

    except Exception as e:
        print(f"  Error during notification standardization: {e}", file=sys.stderr)
        raise # Re-raise to signal failure in the main script

    print(f"  Notification standardization complete. Processed {jobs_processed} jobs for {target_env}.")


# ---future steps ---
def apply_environment_promotion(root: ET.Element, target_env: str):
    print(f"  [Placeholder] apply_environment_promotion for {target_env}")
    pass

def standardize_resources(root: ET.Element, target_env: str):
    print(f"  [Placeholder] standardize_resources for {target_env}")
    pass
