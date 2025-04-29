import xml.etree.ElementTree as ET
import re
import copy
import sys

# --- Constants ---

# Environment specific values & patterns for promotion
ENV_CONFIG = {
    'dev': {
        'notification_dest': 'dev-alerts@example.com', 'remedy_urgency': 'L',
        'adf_resource': 'ADFDEV', 'dw_resource': 'DWDEV', 'adb_resource': 'ADBDEV',
        'env_tag_pattern': re.compile(r'-DEV-', re.IGNORECASE),
        'user_suffix': '_dev',
        'node_env_id': 'dev',
        'datacenter_pattern': re.compile(r'dev_dc_\d+', re.IGNORECASE),
        'job_suffix_to_add': '',
        'job_suffix_to_remove': '-preprod'
    },
    'preprod': {
        'notification_dest': 'preprod-alerts@example.com', 'remedy_urgency': 'M',
        'adf_resource': 'APP-AZ-ADF-PP', 'dw_resource': 'DWPREPROD', 'adb_resource': 'APP-AZ-ADB-PP',
        'env_tag_pattern': re.compile(r'-PREPROD-', re.IGNORECASE),
        'env_tag_replacement': '-PREPROD-',
        'user_suffix': '_pp',
        'node_env_id': 'pp',
        'datacenter_pattern': re.compile(r'preprod_dc_\d+', re.IGNORECASE),
        'datacenter_replacement': 'preprod_dc_1',
        'job_suffix_to_add': '-preprod',
        'job_suffix_to_remove': ''
    },
    'prod': {
        'notification_dest': 'prod-support@example.com', 'remedy_urgency': 'H',
        'adf_resource': 'APP-AZ-ADF', 'dw_resource': 'DWPROD', 'adb_resource': 'APP-AZ-ADB',
        'env_tag_replacement': '-PROD-',
        'user_suffix': '',
        'node_env_id': 'prod',
        'datacenter_replacement': 'prod_dc_1',
        'job_suffix_to_add': '',
        'job_suffix_to_remove': '-preprod'
    }
}

# Notification templates
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
    """
    Sets FOLDER_ORDER_METHOD to 'SYSTEM' for all FOLDER elements
    that don't already have it set to 'SYSTEM'. Modifies the tree in place.
    """
    print("  Ensuring all folders are active (FOLDER_ORDER_METHOD='SYSTEM')...")
    activated_count = 0
    try:
        for folder in root.findall('FOLDER'): # Iterate through direct children only
            current_method = folder.get('FOLDER_ORDER_METHOD')
            if current_method != 'SYSTEM':
                folder_name = folder.get('FOLDER_NAME', 'UNKNOWN_FOLDER')
                # print(f"    Setting folder to SYSTEM: {folder_name} (was: {current_method})")
                folder.set('FOLDER_ORDER_METHOD', 'SYSTEM')
                activated_count += 1
    except Exception as e:
        print(f"  Error during folder activation: {e}", file=sys.stderr)
        return -1 
    # print(f"  Activation check complete. Folders set to SYSTEM: {activated_count}.")
    return activated_count

def standardize_notifications(root: ET.Element, target_env: str):
    """
    Replaces existing ON blocks within each JOB with standardized templates
    for the target environment ('preprod' or 'prod'). Skips if target_env is 'dev'.
    Modifies the tree in place.
    """
    print(f"  Standardizing notifications for target: {target_env}")
    if target_env == 'dev':
        print(f"  Skipping notification standardization for 'dev' environment.")
        return
    if target_env not in PARSED_NOTIFICATIONS:
        print(f"  Error: Notification templates not available or invalid for target env '{target_env}'. Skipping step.", file=sys.stderr)
        return # Skip if templates failed to parse

    notification_elements_template = PARSED_NOTIFICATIONS[target_env]
    jobs_processed = 0
    try:
        for job in root.findall('.//JOB'):
            # Remove existing ON elements first
            existing_on_elements = job.findall('ON')
            for on_elem in existing_on_elements:
                job.remove(on_elem)

            # Append deep copies of the standard ON elements
            for on_template in notification_elements_template:
                job.append(copy.deepcopy(on_template))
            jobs_processed += 1
    except Exception as e:
        print(f"  Error during notification standardization: {e}", file=sys.stderr)
        raise # Re-raise error to stop processing
    # print(f"  Notification standardization complete. Processed {jobs_processed} jobs for {target_env}.")


def standardize_resources(root: ET.Element, target_env: str):
    """
    Adds/Modifies QUANTITATIVE resources based on job name patterns
    (-ADB-, -ADF-, -DW-) and target environment. Modifies tree in place.
    Also updates any existing ADF/DW/ADB resource names to match the target environment.
    """
    print(f"  Standardizing QUANTITATIVE resources for target: {target_env}")
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
            job_name_str = str(job.get('JOBNAME', ''))
            jobs_processed += 1

            # --- Determine insertion index ---
            insert_index = len(job)
            for i, child in enumerate(job):
                if child.tag in ['OUTCOND', 'ON', 'SHOUT', 'VARIABLE']:
                    insert_index = i
                    break

            # --- Get current resources ---
            current_quants = job.findall('QUANTITATIVE')
            current_resources = {q.get('NAME') for q in current_quants}

            # --- Update any existing ADF/DW/ADB resource names to match the target environment ---
            for quant in current_quants:
                name = quant.get('NAME', '')
                if 'ADF' in name and name != res_adf:
                    quant.set('NAME', res_adf)
                    resources_updated += 1
                elif 'DW' in name and name != res_dw:
                    quant.set('NAME', res_dw)
                    resources_updated += 1
                elif 'ADB' in name and name != res_adb:
                    quant.set('NAME', res_adb)
                    resources_updated += 1

            # --- Ensure CONTROLM-RESOURCE exists ---
            if res_controlm not in current_resources:
                attribs = {'NAME': res_controlm, 'QUANT': '1', 'ONFAIL': 'R', 'ONOK': 'R'}
                job.insert(insert_index, ET.Element('QUANTITATIVE', attribs))
                insert_index += 1
                resources_added += 1
                current_resources.add(res_controlm)

            # --- Handle ADB jobs ---
            if '-ADB-' in job_name_str:
                for res_name in adb_resources_expected:
                    if res_name not in current_resources:
                        attribs = {'NAME': res_name, 'QUANT': '1', 'ONFAIL': 'R', 'ONOK': 'R'}
                        job.insert(insert_index, ET.Element('QUANTITATIVE', attribs))
                        insert_index += 1
                        resources_added += 1

            # --- Handle ADF/DW jobs ---
            elif '-ADF-' in job_name_str or '-DW-' in job_name_str:
                target_res = res_adf if '-ADF-' in job_name_str else res_dw
                resource_to_update = None
                found_target_res = False
                for quant in job.findall('QUANTITATIVE'):
                    q_name = quant.get('NAME')
                    if q_name == target_res:
                        found_target_res = True
                        break
                    elif q_name != res_controlm:
                        resource_to_update = quant

                if not found_target_res:
                    if resource_to_update is not None:
                        current_q_name = resource_to_update.get('NAME')
                        if current_q_name != target_res:
                            resource_to_update.set('NAME', target_res)
                            resources_updated += 1
                    else:
                        attribs = {'NAME': target_res, 'QUANT': '1', 'ONFAIL': 'R', 'ONOK': 'R'}
                        job.insert(insert_index, ET.Element('QUANTITATIVE', attribs))
                        resources_added += 1


    except Exception as e:
        print(f"  Error during resource standardization: {e}", file=sys.stderr)
        raise

    # print(f"  Resource standardization complete. Processed {jobs_processed} jobs for {target_env}.")
    # print(f"    Resources Added: {resources_added}, Resources Updated: {resources_updated}")

# --- Environment Promotion Function ---
def apply_environment_promotion(root: ET.Element, target_env: str):
    """
    Modifies XML attributes, names, and variables for environment promotion.
    Assumes promotion path is dev -> preprod -> prod. Modifies the tree in place.
    Also updates OUTCOND and INCOND NAME attributes to match promoted environment.
    """
    print(f"  Applying environment promotion modifications for target: {target_env}")
    if target_env not in ['preprod', 'prod']:
        print(f"  Error: Invalid target env '{target_env}' for promotion.", file=sys.stderr)
        return

    source_env_type = 'dev' if target_env == 'preprod' else 'preprod'
    source_cfg = ENV_CONFIG.get(source_env_type, {})
    target_cfg = ENV_CONFIG.get(target_env, {})
    if not source_cfg or not target_cfg:
        print(f"  Error: Missing config for '{source_env_type}' or '{target_env}'.", file=sys.stderr)
        return

    # --- Source Patterns ---
    source_tag_pattern = source_cfg.get('env_tag_pattern')
    source_user_suffix = source_cfg.get('user_suffix')
    source_user_pattern = re.compile(re.escape(source_user_suffix) + r'$', re.IGNORECASE) if source_user_suffix is not None else None
    source_node_env_id = source_cfg.get('node_env_id')
    source_node_pattern = re.compile(rf"(.*?)({re.escape(source_node_env_id)})(.*)", re.IGNORECASE) if source_node_env_id else None
    source_dc_pattern = source_cfg.get('datacenter_pattern')

    # --- Target Replacements ---
    target_tag_replace = target_cfg.get('env_tag_replacement', '')
    target_user_suffix = target_cfg.get('user_suffix', '')
    target_node_env_id = target_cfg.get('node_env_id', '')
    target_dc_replace = target_cfg.get('datacenter_replacement', '')
    job_suffix_remove = target_cfg.get('job_suffix_to_remove', '')
    job_suffix_add = target_cfg.get('job_suffix_to_add', '')

    print(f"  Promoting FROM '{source_env_type}' TO '{target_env}' configuration.")
    modified_count = 0
    name_attributes = ['FOLDER_NAME', 'APPLICATION', 'SUB_APPLICATION', 'PARENT_FOLDER', 'JOBNAME']

    for element in root.findall('.//*'):
        # 1. Update Name Attributes
        for attr_name in name_attributes:
            current_val = element.get(attr_name)
            if current_val is None: continue
            new_val = current_val
            if source_tag_pattern: new_val = source_tag_pattern.sub(target_tag_replace, new_val)
            if element.tag == 'JOB' and attr_name == 'JOBNAME':
                if job_suffix_remove and new_val.endswith(job_suffix_remove): new_val = new_val[:-len(job_suffix_remove)]
                if job_suffix_add and not new_val.endswith(job_suffix_add): new_val += job_suffix_add
            if new_val != current_val:
                element.set(attr_name, new_val); modified_count += 1

        # 2. Update DATACENTER
        current_dc = element.get('DATACENTER')
        if current_dc is not None and source_dc_pattern:
            new_dc = source_dc_pattern.sub(target_dc_replace, current_dc)
            if new_dc != current_dc: element.set('DATACENTER', new_dc); modified_count +=1

        # 3. Update RUN_AS
        current_run_as = element.get('RUN_AS')
        if current_run_as is not None and source_user_pattern:
            new_run_as = source_user_pattern.sub(target_user_suffix, current_run_as)
            if new_run_as != current_run_as: element.set('RUN_AS', new_run_as); modified_count +=1

        # 4. Update NODEID
        current_node = element.get('NODEID')
        if current_node is not None and source_node_pattern:
             new_node = source_node_pattern.sub(lambda m: f"{m.group(1)}{target_node_env_id}{m.group(3)}", current_node)
             if new_node != current_node:
                 element.set('NODEID', new_node)
                 modified_count +=1

        # 5. Update %%user VARIABLE
        if element.tag == 'VARIABLE' and element.get('NAME') == '%%user':
            current_user_val = element.get('VALUE')
            if current_user_val is not None and source_user_pattern:
                new_user_val = source_user_pattern.sub(target_user_suffix, current_user_val)
                if new_user_val != current_user_val:
                    element.set('VALUE', new_user_val); modified_count +=1

        # 6. Update OUTCOND and INCOND NAME attributes
        if element.tag in ('OUTCOND', 'INCOND'):
            cond_name = element.get('NAME')
            if cond_name and source_tag_pattern:
                new_cond_name = source_tag_pattern.sub(target_tag_replace, cond_name)
                if new_cond_name != cond_name:
                    element.set('NAME', new_cond_name)
                    modified_count += 1

    # print(f"  Environment promotion logic applied. Checked/modified approx {modified_count} instances.")

