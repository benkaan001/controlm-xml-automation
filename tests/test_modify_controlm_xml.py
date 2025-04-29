import pytest
import xml.etree.ElementTree as ET
import copy
from src.xml_modifiers import (
        activate_folders,
        standardize_notifications,
        standardize_resources,
        apply_environment_promotion,
        ENV_CONFIG
        )
# --- Fixtures ---

@pytest.fixture
def sample_xml_root_for_activation():
    """Provides XML root for testing folder activation scenarios."""
    xml_string = """
<DEFTABLE>
    <FOLDER FOLDER_NAME="FOLDER_A_ACTIVE" FOLDER_ORDER_METHOD="SYSTEM"/>
    <FOLDER FOLDER_NAME="FOLDER_B_MANUAL" FOLDER_ORDER_METHOD="MANUAL"/>
    <FOLDER FOLDER_NAME="FOLDER_C_MISSING_ATTR"/>
</DEFTABLE>
"""
    return ET.fromstring(xml_string)

@pytest.fixture
def sample_xml_root_for_notifications():
    """Provides XML root for testing notification standardization."""
    xml_string = """
<DEFTABLE>
    <FOLDER FOLDER_NAME="FOLDER_X">
        <JOB JOBNAME="JOB_X1_NO_ON"/>
        <JOB JOBNAME="JOB_X2_ONE_ON"><ON STMT="*"><DOMAIL DEST="old@example.com"/></ON></JOB>
    </FOLDER>
</DEFTABLE>"""
    return ET.fromstring(xml_string)

@pytest.fixture
def sample_xml_root_for_resources():
    """Provides XML root for testing resource standardization - FIXED JOB NAMES."""
    try:
        prod_adf_res = ENV_CONFIG.get('prod', {}).get('adf_resource', 'APP-AZ-ADF')
    except Exception:
         prod_adf_res = "APP-AZ-ADF" # Fallback

    xml_string = f"""
<DEFTABLE>
    <FOLDER FOLDER_NAME="FOLDER_RES">
        <JOB JOBNAME="JOB-PREFIX-ADB-MISSING"><QUANTITATIVE NAME="CONTROLM-RESOURCE" QUANT="1"/></JOB>
        <JOB JOBNAME="JOB-PREFIX-ADB-DEVRES"><QUANTITATIVE NAME="CONTROLM-RESOURCE" QUANT="1"/><QUANTITATIVE NAME="DWDEV" QUANT="1"/><QUANTITATIVE NAME="ADBDEV" QUANT="1"/><OUTCOND NAME="COND1" ODATE="ODAT"/></JOB>
        <JOB JOBNAME="JOB-PREFIX-ADF-DEVRES"><QUANTITATIVE NAME="CONTROLM-RESOURCE" QUANT="1"/><QUANTITATIVE NAME="ADFDEV" QUANT="1"/></JOB>
        <JOB JOBNAME="JOB-PREFIX-DW-ONLYCM"><QUANTITATIVE NAME="CONTROLM-RESOURCE" QUANT="1"/></JOB>
        <JOB JOBNAME="JOB-PREFIX-DW-WRONGRES"><QUANTITATIVE NAME="CONTROLM-RESOURCE" QUANT="1"/><QUANTITATIVE NAME="SOMETHING_ELSE" QUANT="1"/></JOB>
        <JOB JOBNAME="JOB-PREFIX-ADF-CORRECTPROD"><QUANTITATIVE NAME="CONTROLM-RESOURCE" QUANT="1"/><QUANTITATIVE NAME="{prod_adf_res}" QUANT="1"/></JOB>
        <JOB JOBNAME="JOB_RES_OTHER_TYPE"><QUANTITATIVE NAME="CONTROLM-RESOURCE" QUANT="1"/><QUANTITATIVE NAME="OTHER_RES" QUANT="1"/></JOB>
    </FOLDER>
</DEFTABLE>"""
    return ET.fromstring(xml_string)

@pytest.fixture
def dev_xml_root_for_promotion():
    """Provides a sample XML root in a 'dev' state for promotion tests."""
    xml_string = """
<DEFTABLE xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
    <FOLDER DATACENTER="dev_dc_1" FOLDER_NAME="FIN-DEV-GL-ETL-PROJCODE-001" FOLDER_ORDER_METHOD="SYSTEM">
        <JOB APPLICATION="FIN-DEV-GL" SUB_APPLICATION="FIN-DEV-GL-ETL" JOBNAME="FIN-DEV-GL-ETL-PROJCODE-001-ADF-LoadData" RUN_AS="svc_acct_fin_dev" NODEID="lnxdevapp01">
             <VARIABLE NAME="%%user" VALUE="svc_acct_fin_dev" />
             <OUTCOND NAME="FIN-DEV-GL-ETL-PROJCODE-001-ADF-OK" ODATE="ODAT"/>
        </JOB>
         <JOB APPLICATION="FIN-DEV-GL" SUB_APPLICATION="FIN-DEV-GL-ETL" JOBNAME="FIN-DEV-GL-ETL-PROJCODE-001-DW-ProcessData-preprod" RUN_AS="svc_acct_dw_dev" NODEID="lnxdevdb01">
              <INCOND NAME="FIN-DEV-GL-ETL-PROJCODE-001-ADF-OK" ODATE="ODAT"/>
         </JOB>
    </FOLDER>
    <FOLDER DATACENTER="dev_dc_2" FOLDER_NAME="OPS-DEV-SAFETY-PROJCODE-201" FOLDER_ORDER_METHOD="SYSTEM">
         <JOB APPLICATION="OPS-DEV-SAFETY" JOBNAME="OPS-DEV-SAFETY-PROJCODE-201-CMD-Util" RUN_AS="svc_acct_ops_util_dev" NODEID="winutilsdev01"/>
    </FOLDER>
</DEFTABLE>
"""
    return ET.fromstring(xml_string)


# --- Test Functions for activate_folders ---
def test_activate_folders_activates_missing(sample_xml_root_for_activation):
    root = copy.deepcopy(sample_xml_root_for_activation)
    folder_c = root.find("./FOLDER[@FOLDER_NAME='FOLDER_C_MISSING_ATTR']")
    activate_folders(root)
    assert folder_c.get('FOLDER_ORDER_METHOD') == 'SYSTEM'

def test_activate_folders_activates_manual(sample_xml_root_for_activation):
     root = copy.deepcopy(sample_xml_root_for_activation)
     folder_b = root.find("./FOLDER[@FOLDER_NAME='FOLDER_B_MANUAL']")
     activate_folders(root)
     assert folder_b.get('FOLDER_ORDER_METHOD') == 'SYSTEM'

# --- Test Functions for standardize_notifications ---
@pytest.mark.parametrize("target_env", ['preprod', 'prod'])
def test_notifications_applies_correct_template(sample_xml_root_for_notifications, target_env):
    root = copy.deepcopy(sample_xml_root_for_notifications)
    job = root.find(".//JOB[@JOBNAME='JOB_X1_NO_ON']")
    standardize_notifications(root, target_env)
    on_blocks = job.findall('ON')
    assert len(on_blocks) > 0
    domail = next((on.find('DOMAIL') for on in on_blocks if on.find('DOMAIL') is not None), None)
    assert domail is not None
    expected_dest = ENV_CONFIG[target_env]['notification_dest']
    assert domail.get('DEST') == expected_dest

def test_notifications_skips_for_dev_env(sample_xml_root_for_notifications):
    root = copy.deepcopy(sample_xml_root_for_notifications)
    original_xml_string = ET.tostring(root, encoding='unicode')
    standardize_notifications(root, 'dev')
    modified_xml_string = ET.tostring(root, encoding='unicode')
    assert modified_xml_string == original_xml_string

# --- Test Functions for standardize_resources ---
def get_resource_names(job_element: ET.Element) -> set:
    return {q.get('NAME') for q in job_element.findall('QUANTITATIVE')}

@pytest.mark.parametrize("target_env", ['preprod', 'prod'])
def test_resources_adb_adds_missing(sample_xml_root_for_resources, target_env):
    root = copy.deepcopy(sample_xml_root_for_resources)
    job = root.find(".//JOB[@JOBNAME='JOB-PREFIX-ADB-MISSING']")
    standardize_resources(root, target_env)
    target_cfg = ENV_CONFIG[target_env]
    expected_resources = {"CONTROLM-RESOURCE", target_cfg['dw_resource'], target_cfg['adb_resource']}
    assert get_resource_names(job) == expected_resources

@pytest.mark.parametrize("target_env", ['preprod', 'prod'])
def test_resources_adb_ignores_dev_resources(sample_xml_root_for_resources, target_env):
    root = copy.deepcopy(sample_xml_root_for_resources)
    job = root.find(".//JOB[@JOBNAME='JOB-PREFIX-ADB-DEVRES']")
    standardize_resources(root, target_env)
    target_cfg = ENV_CONFIG[target_env]
    final_resources = get_resource_names(job)
    assert target_cfg['dw_resource'] in final_resources
    assert target_cfg['adb_resource'] in final_resources
    assert "CONTROLM-RESOURCE" in final_resources

@pytest.mark.parametrize("target_env", ['preprod', 'prod'])
def test_resources_adf_updates_dev_resource(sample_xml_root_for_resources, target_env):
    root = copy.deepcopy(sample_xml_root_for_resources)
    job = root.find(".//JOB[@JOBNAME='JOB-PREFIX-ADF-DEVRES']")
    standardize_resources(root, target_env)
    target_cfg = ENV_CONFIG[target_env]
    expected_resources = {"CONTROLM-RESOURCE", target_cfg['adf_resource']}
    assert get_resource_names(job) == expected_resources

@pytest.mark.parametrize("target_env", ['preprod', 'prod'])
def test_resources_dw_adds_missing(sample_xml_root_for_resources, target_env):
    root = copy.deepcopy(sample_xml_root_for_resources)
    job = root.find(".//JOB[@JOBNAME='JOB-PREFIX-DW-ONLYCM']")
    standardize_resources(root, target_env)
    target_cfg = ENV_CONFIG[target_env]
    expected_resources = {"CONTROLM-RESOURCE", target_cfg['dw_resource']}
    assert get_resource_names(job) == expected_resources

@pytest.mark.parametrize("target_env", ['preprod', 'prod'])
def test_resources_dw_updates_wrong_resource(sample_xml_root_for_resources, target_env):
    root = copy.deepcopy(sample_xml_root_for_resources)
    job = root.find(".//JOB[@JOBNAME='JOB-PREFIX-DW-WRONGRES']")
    standardize_resources(root, target_env)
    target_cfg = ENV_CONFIG[target_env]
    expected_resources = {"CONTROLM-RESOURCE", target_cfg['dw_resource']}
    assert get_resource_names(job) == expected_resources

@pytest.mark.parametrize("target_env", ['preprod', 'prod'])
def test_resources_leaves_other_jobs_unchanged(sample_xml_root_for_resources, target_env):
    root = copy.deepcopy(sample_xml_root_for_resources)
    job = root.find(".//JOB[@JOBNAME='JOB_RES_OTHER_TYPE']")
    initial_resources = get_resource_names(job)
    standardize_resources(root, target_env)
    assert get_resource_names(job) == initial_resources

def test_resources_skips_for_dev_env(sample_xml_root_for_resources):
    root = copy.deepcopy(sample_xml_root_for_resources)
    original_xml_string = ET.tostring(root, encoding='unicode')
    standardize_resources(root, 'dev')
    modified_xml_string = ET.tostring(root, encoding='unicode')
    assert modified_xml_string == original_xml_string


# --- Test Functions for apply_environment_promotion ---

def test_promotion_dev_to_preprod_folder_name(dev_xml_root_for_promotion):
    root = copy.deepcopy(dev_xml_root_for_promotion)
    apply_environment_promotion(root, 'preprod')
    updated_folder = root.find("./FOLDER[@FOLDER_NAME='FIN-PREPROD-GL-ETL-PROJCODE-001']")
    assert updated_folder is not None
    assert updated_folder.get('FOLDER_NAME') == 'FIN-PREPROD-GL-ETL-PROJCODE-001'
    assert root.find("./FOLDER[@FOLDER_NAME='FIN-DEV-GL-ETL-PROJCODE-001']") is None

def test_promotion_dev_to_preprod_jobname_suffix(dev_xml_root_for_promotion):
    root = copy.deepcopy(dev_xml_root_for_promotion)
    apply_environment_promotion(root, 'preprod')
    expected_jobname = 'FIN-PREPROD-GL-ETL-PROJCODE-001-ADF-LoadData-preprod'
    updated_job = root.find(f".//JOB[@JOBNAME='{expected_jobname}']")
    assert updated_job is not None
    assert updated_job.get('JOBNAME') == expected_jobname

def test_promotion_dev_to_preprod_datacenter(dev_xml_root_for_promotion):
    root = copy.deepcopy(dev_xml_root_for_promotion)
    apply_environment_promotion(root, 'preprod')
    updated_folder = root.find("./FOLDER[@FOLDER_NAME='FIN-PREPROD-GL-ETL-PROJCODE-001']")
    assert updated_folder.get('DATACENTER') == ENV_CONFIG['preprod']['datacenter_replacement']

def test_promotion_dev_to_preprod_run_as(dev_xml_root_for_promotion):
    root = copy.deepcopy(dev_xml_root_for_promotion)
    apply_environment_promotion(root, 'preprod')
    updated_job = root.find(".//JOB[@JOBNAME='FIN-PREPROD-GL-ETL-PROJCODE-001-ADF-LoadData-preprod']")
    expected_run_as = 'svc_acct_fin' + ENV_CONFIG['preprod']['user_suffix']
    assert updated_job.get('RUN_AS') == expected_run_as

def test_promotion_dev_to_preprod_nodeid(dev_xml_root_for_promotion):
    root = copy.deepcopy(dev_xml_root_for_promotion)
    apply_environment_promotion(root, 'preprod')
    updated_job = root.find(".//JOB[@JOBNAME='FIN-PREPROD-GL-ETL-PROJCODE-001-ADF-LoadData-preprod']")
    assert updated_job.get('NODEID') == 'lnxppapp01' # Expect 'dev' -> 'pp'

def test_promotion_dev_to_preprod_user_variable(dev_xml_root_for_promotion):
    root = copy.deepcopy(dev_xml_root_for_promotion)
    apply_environment_promotion(root, 'preprod')
    updated_job = root.find(".//JOB[@JOBNAME='FIN-PREPROD-GL-ETL-PROJCODE-001-ADF-LoadData-preprod']")
    updated_var = updated_job.find("./VARIABLE[@NAME='%%user']")
    expected_user_val = 'svc_acct_fin' + ENV_CONFIG['preprod']['user_suffix']
    assert updated_var.get('VALUE') == expected_user_val

# --- Tests for Preprod -> Prod ---

def test_promotion_preprod_to_prod_folder_name(dev_xml_root_for_promotion):
    root = copy.deepcopy(dev_xml_root_for_promotion)
    apply_environment_promotion(root, 'preprod') # Go to preprod first
    apply_environment_promotion(root, 'prod') # Now promote to prod
    updated_folder = root.find("./FOLDER[@FOLDER_NAME='FIN-PROD-GL-ETL-PROJCODE-001']")
    assert updated_folder is not None
    assert updated_folder.get('FOLDER_NAME') == 'FIN-PROD-GL-ETL-PROJCODE-001'
    assert root.find("./FOLDER[@FOLDER_NAME='FIN-PREPROD-GL-ETL-PROJCODE-001']") is None

def test_promotion_preprod_to_prod_jobname_suffix(dev_xml_root_for_promotion):
    root = copy.deepcopy(dev_xml_root_for_promotion)
    apply_environment_promotion(root, 'preprod')
    apply_environment_promotion(root, 'prod')
    expected_jobname = 'FIN-PROD-GL-ETL-PROJCODE-001-ADF-LoadData' # Tag updated, suffix removed
    updated_job = root.find(f".//JOB[@JOBNAME='{expected_jobname}']")
    assert updated_job is not None
    assert not updated_job.get('JOBNAME').endswith('-preprod')

def test_promotion_preprod_to_prod_run_as(dev_xml_root_for_promotion):
    root = copy.deepcopy(dev_xml_root_for_promotion)
    apply_environment_promotion(root, 'preprod')
    apply_environment_promotion(root, 'prod')
    updated_job = root.find(".//JOB[@JOBNAME='FIN-PROD-GL-ETL-PROJCODE-001-ADF-LoadData']")
    expected_run_as = 'svc_acct_fin' # Prod has no suffix in example config
    assert updated_job.get('RUN_AS') == expected_run_as

def test_promotion_preprod_to_prod_nodeid(dev_xml_root_for_promotion):
    root = copy.deepcopy(dev_xml_root_for_promotion)
    apply_environment_promotion(root, 'preprod') # dev -> preprod
    apply_environment_promotion(root, 'prod') # preprod -> prod
    updated_job = root.find(".//JOB[@JOBNAME='FIN-PROD-GL-ETL-PROJCODE-001-ADF-LoadData']")
    assert updated_job.get('NODEID') == 'lnxprodapp01' # Expect 'pp' -> 'prod'

def test_promotion_preprod_to_prod_user_variable(dev_xml_root_for_promotion):
    root = copy.deepcopy(dev_xml_root_for_promotion)
    apply_environment_promotion(root, 'preprod')
    apply_environment_promotion(root, 'prod')
    updated_job = root.find(".//JOB[@JOBNAME='FIN-PROD-GL-ETL-PROJCODE-001-ADF-LoadData']")
    updated_var = updated_job.find("./VARIABLE[@NAME='%%user']")
    expected_user_val = 'svc_acct_fin' # Prod has no suffix in example config
    assert updated_var.get('VALUE') == expected_user_val

