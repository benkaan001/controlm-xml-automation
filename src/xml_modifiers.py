import xml.etree.ElementTree as ET
import re
import copy
import sys
import logging
from src.errors import ControlMXmlError

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

def _update_folder_order_method(folder: ET.Element) -> bool:
    """Set FOLDER_ORDER_METHOD to 'SYSTEM' if not already set."""
    current_method = folder.get('FOLDER_ORDER_METHOD')
    if current_method != 'SYSTEM':
        folder.set('FOLDER_ORDER_METHOD', 'SYSTEM')
        return True
    return False

def activate_folders(root: ET.Element) -> int:
    """
    Sets FOLDER_ORDER_METHOD to 'SYSTEM' for all FOLDER elements
    that don't already have it set to 'SYSTEM'. Modifies the tree in place.
    """
    logging.info("Ensuring all folders are active (FOLDER_ORDER_METHOD='SYSTEM')...")
    activated_count = 0
    try:
        for folder in root.findall('FOLDER'):
            if _update_folder_order_method(folder):
                activated_count += 1
    except Exception as e:
        logging.error(f"Error during folder activation: {e}")
        return -1
    return activated_count

def _remove_existing_on_blocks(job: ET.Element):
    """Remove all ON blocks from a JOB element."""
    for on_elem in job.findall('ON'):
        job.remove(on_elem)

def _add_notification_blocks(job: ET.Element, notification_elements_template):
    """Add notification ON blocks to a JOB element."""
    for on_template in notification_elements_template:
        job.append(copy.deepcopy(on_template))

def standardize_notifications(root: ET.Element, target_env: str) -> None:
    """
    Replaces existing ON blocks within each JOB with standardized templates
    for the target environment ('preprod' or 'prod'). Skips if target_env is 'dev'.
    Modifies the tree in place.
    """
    logging.info(f"Standardizing notifications for target: {target_env}")
    if target_env == 'dev':
        logging.info("Skipping notification standardization for 'dev' environment.")
        return
    if target_env not in PARSED_NOTIFICATIONS:
        logging.error(f"Notification templates not available or invalid for target env '{target_env}'. Skipping step.")
        return

    notification_elements_template = PARSED_NOTIFICATIONS[target_env]
    jobs_processed = 0
    try:
        for job in root.findall('.//JOB'):
            _remove_existing_on_blocks(job)
            _add_notification_blocks(job, notification_elements_template)
            jobs_processed += 1
    except Exception as e:
        logging.error(f"Error during notification standardization: {e}")
        raise

def _get_insert_index_for_resources(job: ET.Element) -> int:
    """Determine the index to insert new QUANTITATIVE elements."""
    for i, child in enumerate(job):
        if child.tag in ['OUTCOND', 'ON', 'SHOUT', 'VARIABLE']:
            return i
    return len(job)

def _get_current_quant_resources(job: ET.Element):
    """Return set of current QUANTITATIVE resource names and the elements."""
    quants = job.findall('QUANTITATIVE')
    return {q.get('NAME') for q in quants}, quants

def _update_resource_names(quants, res_adf, res_dw, res_adb):
    """Update resource names in QUANTITATIVE elements to match target env."""
    resources_updated = 0
    for quant in quants:
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
    return resources_updated

def _ensure_quant_resource(job, res_name, insert_index):
    """Ensure a QUANTITATIVE resource exists, insert if missing."""
    attribs = {'NAME': res_name, 'QUANT': '1', 'ONFAIL': 'R', 'ONOK': 'R'}
    job.insert(insert_index, ET.Element('QUANTITATIVE', attribs))

def standardize_resources(root: ET.Element, target_env: str) -> None:
    """
    Adds/Modifies QUANTITATIVE resources based on job name patterns
    (-ADB-, -ADF-, -DW-) and target environment. Modifies tree in place.
    Also updates any existing ADF/DW/ADB resource names to match the target environment.
    """
    logging.info(f"Standardizing QUANTITATIVE resources for target: {target_env}")
    if target_env == 'dev':
        logging.info("Skipping resource standardization for 'dev' environment.")
        return
    if target_env not in ENV_CONFIG:
        logging.error(f"Environment config not found for '{target_env}'. Skipping step.")
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

    try:
        for job in root.findall('.//JOB'):
            job_name_str = str(job.get('JOBNAME', ''))
            insert_index = _get_insert_index_for_resources(job)
            current_resources, current_quants = _get_current_quant_resources(job)
            resources_updated = _update_resource_names(current_quants, res_adf, res_dw, res_adb)

            # Ensure CONTROLM-RESOURCE exists
            if res_controlm not in current_resources:
                _ensure_quant_resource(job, res_controlm, insert_index)
                insert_index += 1
                current_resources.add(res_controlm)

            # Handle ADB jobs
            if '-ADB-' in job_name_str:
                for res_name in adb_resources_expected:
                    if res_name not in current_resources:
                        _ensure_quant_resource(job, res_name, insert_index)
                        insert_index += 1

            # Handle ADF/DW jobs
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
                    else:
                        _ensure_quant_resource(job, target_res, insert_index)
    except Exception as e:
        logging.error(f"Error during resource standardization: {e}")
        raise

def _get_env_promotion_patterns(source_cfg, target_cfg):
    """Extract and compile patterns and replacements for environment promotion."""
    source_tag_pattern = source_cfg.get('env_tag_pattern')
    source_user_suffix = source_cfg.get('user_suffix')
    source_user_pattern = re.compile(re.escape(source_user_suffix) + r'$', re.IGNORECASE) if source_user_suffix is not None else None
    source_node_env_id = source_cfg.get('node_env_id')
    source_node_pattern = re.compile(rf"(.*?)({re.escape(source_node_env_id)})(.*)", re.IGNORECASE) if source_node_env_id else None
    source_dc_pattern = source_cfg.get('datacenter_pattern')

    target_tag_replace = target_cfg.get('env_tag_replacement', '')
    target_user_suffix = target_cfg.get('user_suffix', '')
    target_node_env_id = target_cfg.get('node_env_id', '')
    target_dc_replace = target_cfg.get('datacenter_replacement', '')
    job_suffix_remove = target_cfg.get('job_suffix_to_remove', '')
    job_suffix_add = target_cfg.get('job_suffix_to_add', '')

    return {
        'source_tag_pattern': source_tag_pattern,
        'source_user_pattern': source_user_pattern,
        'source_node_pattern': source_node_pattern,
        'source_dc_pattern': source_dc_pattern,
        'target_tag_replace': target_tag_replace,
        'target_user_suffix': target_user_suffix,
        'target_node_env_id': target_node_env_id,
        'target_dc_replace': target_dc_replace,
        'job_suffix_remove': job_suffix_remove,
        'job_suffix_add': job_suffix_add
    }

def _promote_element_attributes(element, patterns, name_attributes):
    """Promote environment-specific attributes for a single element."""
    modified_count = 0
    for attr_name in name_attributes:
        current_val = element.get(attr_name)
        if current_val is None: continue
        new_val = current_val
        if patterns['source_tag_pattern']:
            new_val = patterns['source_tag_pattern'].sub(patterns['target_tag_replace'], new_val)
        if element.tag == 'JOB' and attr_name == 'JOBNAME':
            if patterns['job_suffix_remove'] and new_val.endswith(patterns['job_suffix_remove']):
                new_val = new_val[:-len(patterns['job_suffix_remove'])]
            if patterns['job_suffix_add'] and not new_val.endswith(patterns['job_suffix_add']):
                new_val += patterns['job_suffix_add']
        if new_val != current_val:
            element.set(attr_name, new_val)
            modified_count += 1
    return modified_count

def _promote_datacenter(element, patterns):
    """Promote DATACENTER attribute."""
    current_dc = element.get('DATACENTER')
    if current_dc is not None and patterns['source_dc_pattern']:
        new_dc = patterns['source_dc_pattern'].sub(patterns['target_dc_replace'], current_dc)
        if new_dc != current_dc:
            element.set('DATACENTER', new_dc)
            return 1
    return 0

def _promote_run_as(element, patterns):
    """Promote RUN_AS attribute."""
    current_run_as = element.get('RUN_AS')
    if current_run_as is not None and patterns['source_user_pattern']:
        new_run_as = patterns['source_user_pattern'].sub(patterns['target_user_suffix'], current_run_as)
        if new_run_as != current_run_as:
            element.set('RUN_AS', new_run_as)
            return 1
    return 0

def _promote_nodeid(element, patterns):
    """Promote NODEID attribute."""
    current_node = element.get('NODEID')
    if current_node is not None and patterns['source_node_pattern']:
        new_node = patterns['source_node_pattern'].sub(lambda m: f"{m.group(1)}{patterns['target_node_env_id']}{m.group(3)}", current_node)
        if new_node != current_node:
            element.set('NODEID', new_node)
            return 1
    return 0

def _promote_user_variable(element, patterns):
    """Promote %%user VARIABLE VALUE attribute."""
    if element.tag == 'VARIABLE' and element.get('NAME') == '%%user':
        current_user_val = element.get('VALUE')
        if current_user_val is not None and patterns['source_user_pattern']:
            new_user_val = patterns['source_user_pattern'].sub(patterns['target_user_suffix'], current_user_val)
            if new_user_val != current_user_val:
                element.set('VALUE', new_user_val)
                return 1
    return 0

def _promote_cond_names(element, patterns):
    """Promote OUTCOND and INCOND NAME attributes."""
    if element.tag in ('OUTCOND', 'INCOND'):
        cond_name = element.get('NAME')
        if cond_name and patterns['source_tag_pattern']:
            new_cond_name = patterns['source_tag_pattern'].sub(patterns['target_tag_replace'], cond_name)
            if new_cond_name != cond_name:
                element.set('NAME', new_cond_name)
                return 1
    return 0

def apply_environment_promotion(root: ET.Element, target_env: str) -> None:
    """
    Modifies XML attributes, names, and variables for environment promotion.
    Assumes promotion path is dev -> preprod -> prod. Modifies the tree in place.
    Also updates OUTCOND and INCOND NAME attributes to match promoted environment.
    """
    logging.info(f"Applying environment promotion modifications for target: {target_env}")
    if target_env not in ['preprod', 'prod']:
        logging.error(f"Invalid target env '{target_env}' for promotion.")
        return

    source_env_type = 'dev' if target_env == 'preprod' else 'preprod'
    source_cfg = ENV_CONFIG.get(source_env_type, {})
    target_cfg = ENV_CONFIG.get(target_env, {})
    if not source_cfg or not target_cfg:
        raise ControlMXmlError(f"Missing config for '{source_env_type}' or '{target_env}'.", step="apply_environment_promotion")

    patterns = _get_env_promotion_patterns(source_cfg, target_cfg)
    name_attributes = ['FOLDER_NAME', 'APPLICATION', 'SUB_APPLICATION', 'PARENT_FOLDER', 'JOBNAME']

    modified_count = 0
    for element in root.findall('.//*'):
        modified_count += _promote_element_attributes(element, patterns, name_attributes)
        modified_count += _promote_datacenter(element, patterns)
        modified_count += _promote_run_as(element, patterns)
        modified_count += _promote_nodeid(element, patterns)
        modified_count += _promote_user_variable(element, patterns)
        modified_count += _promote_cond_names(element, patterns)
    # print(f"  Environment promotion logic applied. Checked/modified approx {modified_count} instances.")

