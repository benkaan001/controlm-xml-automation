import xml.etree.ElementTree as ET
import re
import copy
import sys

# --- Constants ---
ENV_CONFIG = {
    'dev': {
        'notification_dest': 'dev-alerts@example.com', 'remedy_urgency': 'L',
        'adf_resource': 'ADFDEV', 'dw_resource': 'DWDEV', 'adb_resource': 'ADBDEV',
    },
    'preprod': {
        'notification_dest': 'preprod-alerts@example.com', 'remedy_urgency': 'M',
        'adf_resource': 'APP-AZ-ADF-PP', 'dw_resource': 'DWPREPROD', 'adb_resource': 'APP-AZ-ADB-PP',
    },
    'prod': {
        'notification_dest': 'prod-support@example.com', 'remedy_urgency': 'H',
        'adf_resource': 'APP-AZ-ADF', 'dw_resource': 'DWPROD', 'adb_resource': 'APP-AZ-ADB',
    }
}
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
    for env, template in [('preprod', NOTIFICATION_TEMPLATE_PREPROD), ('prod', NOTIFICATION_TEMPLATE_PROD)]:
        if env not in ENV_CONFIG: continue
        cfg = ENV_CONFIG[env]
        formatted_template = template.format(
            dest=cfg.get('notification_dest', 'default_dest@example.com'),
            urgency=cfg.get('remedy_urgency', 'M')
        )
        root_wrapper = ET.fromstring(f"<root>{formatted_template.strip()}</root>")
        PARSED_NOTIFICATIONS[env] = list(root_wrapper)
except Exception as e:
    print(f"FATAL ERROR during template parsing: {e}", file=sys.stderr)
    PARSED_NOTIFICATIONS = {}


# --- Modification Functions ---

def activate_folders(root: ET.Element) -> int:
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
    print(f"  Standardizing notifications for target: {target_env}")
    if target_env == 'dev':
        print(f"  Skipping notification standardization for 'dev' environment.")
        return
    if target_env not in PARSED_NOTIFICATIONS:
        print(f"  Error: Notification templates not available or invalid for target env '{target_env}'. Skipping step.", file=sys.stderr)
        return

    notification_elements_template = PARSED_NOTIFICATIONS[target_env]
    jobs_processed = 0
    try:
        for job in root.findall('.//JOB'):
            job_name = job.get('JOBNAME', 'UNKNOWN_JOB')
            existing_on_elements = job.findall('ON')
            if existing_on_elements:
                for on_elem in existing_on_elements:
                    job.remove(on_elem)
            for on_template in notification_elements_template:
                new_on_element = copy.deepcopy(on_template)
                job.append(new_on_element)
            jobs_processed += 1
    except Exception as e:
        print(f"  Error during notification standardization: {e}", file=sys.stderr)
        raise
    print(f"  Notification standardization complete. Processed {jobs_processed} jobs for {target_env}.")


def standardize_resources(root: ET.Element, target_env: str):
    """
    Adds/Modifies QUANTITATIVE resources based on job name patterns
    (-ADB-, -ADF-, -DW-) and target environment. Modifies tree in place.
    """
    # print(f"  DEBUG: Entering standardize_resources for target: {target_env}")
    if target_env == 'dev':
         print(f"  Skipping resource standardization for 'dev' environment.")
         return
    if target_env not in ENV_CONFIG:
        print(f"  Error: Environment config not found for '{target_env}'. Skipping step.", file=sys.stderr)
        return

    target_cfg = ENV_CONFIG[target_env]
    res_controlm = "CONTROLM-RESOURCE"

    res_adf = target_cfg.get('adf_resource')
    res_dw = target_cfg.get('dw_resource')
    res_adb = target_cfg.get('adb_resource')

    if not all([res_adf, res_dw, res_adb]):
         print(f"  Error: Missing target resource names in config for '{target_env}'. Skipping step.", file=sys.stderr)
         return

    adb_resources_expected = {res_controlm, res_dw, res_adb}

    jobs_processed = 0
    resources_added = 0
    resources_updated = 0

    try:
        for job in root.findall('.//JOB'):
            # *** Explicitly get job name as string ***
            job_name_str = str(job.get('JOBNAME', ''))
            jobs_processed += 1
            # print(f"\n    DEBUG: Processing Job: {job_name_str}")

            insert_index = len(job)
            for i, child in enumerate(job):
                if child.tag in ['OUTCOND', 'ON', 'SHOUT']:
                    insert_index = i
                    break
            # print(f"    DEBUG: Determined insertion index: {insert_index}")

            current_resources = {q.get('NAME') for q in job.findall('QUANTITATIVE')}
            # print(f"    DEBUG: Current resources: {current_resources}")

            # --- Ensure CONTROLM-RESOURCE exists ---
            if res_controlm not in current_resources:
                 # print(f"    DEBUG: Adding missing '{res_controlm}'")
                 attribs = {'NAME': res_controlm, 'QUANT': '1', 'ONFAIL': 'R', 'ONOK': 'R'}
                 new_quant = ET.Element('QUANTITATIVE', attribs)
                 job.insert(insert_index, new_quant)
                 insert_index += 1
                 resources_added += 1
                 current_resources.add(res_controlm)

            # --- Handle ADB jobs ---
            if '-ADB-' in job_name_str:
                # print(f"    DEBUG: Is ADB job.")
                for res_name in adb_resources_expected:
                    if res_name not in current_resources:
                         # print(f"    DEBUG: *** About to ADD ADB resource '{res_name}' ***")
                         attribs = {'NAME': res_name, 'QUANT': '1', 'ONFAIL': 'R', 'ONOK': 'R'}
                         new_quant = ET.Element('QUANTITATIVE', attribs)
                         job.insert(insert_index, new_quant)
                         insert_index += 1
                         resources_added += 1

            # --- Handle ADF/DW jobs ---
            # *** Check the explicit string ***
            elif '-ADF-' in job_name_str or '-DW-' in job_name_str:
                is_adf = '-ADF-' in job_name_str
                # print(f"    DEBUG: Is {'ADF' if is_adf else 'DW'} job.")
                target_res = res_adf if is_adf else res_dw
                resource_to_update = None
                found_target_res = False

                for quant in job.findall('QUANTITATIVE'):
                    q_name = quant.get('NAME')
                    if q_name == target_res:
                        found_target_res = True
                        # print(f"    DEBUG: Found target resource '{target_res}' already exists.")
                        break
                    elif q_name != res_controlm:
                        resource_to_update = quant

                if found_target_res:
                    pass
                elif resource_to_update is not None:
                    current_q_name = resource_to_update.get('NAME')
                    if current_q_name != target_res:
                        # print(f"    DEBUG: *** About to UPDATE resource '{current_q_name}' to '{target_res}' ***")
                        resource_to_update.set('NAME', target_res)
                        resources_updated += 1
                elif not found_target_res:
                    # print(f"    DEBUG: *** About to ADD resource '{target_res}' ***")
                    attribs = {'NAME': target_res, 'QUANT': '1', 'ONFAIL': 'R', 'ONOK': 'R'}
                    new_quant = ET.Element('QUANTITATIVE', attribs)
                    job.insert(insert_index, new_quant)
                    resources_added += 1

            else:
                 # print(f"    DEBUG: Job type not ADB/ADF/DW. Skipping resource logic.")
                 pass

    except Exception as e:
        print(f"  Error during resource standardization: {e}", file=sys.stderr)
        raise

    print(f"\n  Resource standardization complete. Processed {jobs_processed} jobs for {target_env}.")
    print(f"    Resources Added: {resources_added}, Resources Updated: {resources_updated}")


# --- Placeholder function for promotion ---
def apply_environment_promotion(root: ET.Element, target_env: str):
    print(f"  [Placeholder] apply_environment_promotion for {target_env}")
    pass
