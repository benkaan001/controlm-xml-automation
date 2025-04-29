import pytest
import xml.etree.ElementTree as ET
import os
import sys
import copy
import re
from src.xml_modifiers import activate_folders, standardize_notifications, standardize_resources, ENV_CONFIG

# --- Fixtures ---

@pytest.fixture
def sample_xml_root_for_activation():
    xml_string = """<DEFTABLE>
    <FOLDER FOLDER_NAME="FOLDER_A_ACTIVE" FOLDER_ORDER_METHOD="SYSTEM"/>
    <FOLDER FOLDER_NAME="FOLDER_B_MANUAL" FOLDER_ORDER_METHOD="MANUAL"/>
    <FOLDER FOLDER_NAME="FOLDER_C_MISSING_ATTR"/>
    </DEFTABLE>"""
    return ET.fromstring(xml_string)

@pytest.fixture
def sample_xml_root_for_notifications():
     xml_string = """<DEFTABLE>
    <FOLDER FOLDER_NAME="FOLDER_X">
        <JOB JOBNAME="JOB_X1_NO_ON"/>
        <JOB JOBNAME="JOB_X2_ONE_ON"><ON STMT="*"><DOMAIL DEST="old@example.com"/></ON></JOB>
    </FOLDER></DEFTABLE>"""
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
        <JOB JOBNAME="JOB-PREFIX-ADB-MISSING">
             <QUANTITATIVE NAME="CONTROLM-RESOURCE" QUANT="1"/>
        </JOB>
        <JOB JOBNAME="JOB-PREFIX-ADB-DEVRES">
             <QUANTITATIVE NAME="CONTROLM-RESOURCE" QUANT="1"/>
             <QUANTITATIVE NAME="DWDEV" QUANT="1"/>
             <QUANTITATIVE NAME="ADBDEV" QUANT="1"/>
             <OUTCOND NAME="COND1" ODATE="ODAT"/>
        </JOB>
        <JOB JOBNAME="JOB-PREFIX-ADF-DEVRES">
             <QUANTITATIVE NAME="CONTROLM-RESOURCE" QUANT="1"/>
             <QUANTITATIVE NAME="ADFDEV" QUANT="1"/>
        </JOB>
        <JOB JOBNAME="JOB-PREFIX-DW-ONLYCM">
             <QUANTITATIVE NAME="CONTROLM-RESOURCE" QUANT="1"/>
        </JOB>
        <JOB JOBNAME="JOB-PREFIX-DW-WRONGRES">
             <QUANTITATIVE NAME="CONTROLM-RESOURCE" QUANT="1"/>
             <QUANTITATIVE NAME="SOMETHING_ELSE" QUANT="1"/>
        </JOB>
         <JOB JOBNAME="JOB-PREFIX-ADF-CORRECTPROD">
             <QUANTITATIVE NAME="CONTROLM-RESOURCE" QUANT="1"/>
             <QUANTITATIVE NAME="{prod_adf_res}" QUANT="1"/>
        </JOB>
        <JOB JOBNAME="JOB_RES_OTHER_TYPE">
            <QUANTITATIVE NAME="CONTROLM-RESOURCE" QUANT="1"/>
            <QUANTITATIVE NAME="OTHER_RES" QUANT="1"/>
        </JOB>
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

# Helper to get resource names from a job element
def get_resource_names(job_element: ET.Element) -> set:
    return {q.get('NAME') for q in job_element.findall('QUANTITATIVE')}

@pytest.mark.parametrize("target_env", ['preprod', 'prod'])
def test_resources_adb_adds_missing(sample_xml_root_for_resources, target_env):
    """Verify ADB jobs get expected target resources added."""
    root = copy.deepcopy(sample_xml_root_for_resources)
    job = root.find(".//JOB[@JOBNAME='JOB-PREFIX-ADB-MISSING']")
    assert len(job.findall('QUANTITATIVE')) == 1 # Precondition

    standardize_resources(root, target_env)

    target_cfg = ENV_CONFIG[target_env]
    expected_resources = {
        "CONTROLM-RESOURCE",
        target_cfg['dw_resource'],
        target_cfg['adb_resource']
    }
    assert get_resource_names(job) == expected_resources

@pytest.mark.parametrize("target_env", ['preprod', 'prod'])
def test_resources_adb_ignores_dev_resources(sample_xml_root_for_resources, target_env):
    """Verify ADB jobs have expected target resources added, even if dev ones exist."""
    root = copy.deepcopy(sample_xml_root_for_resources)
    job = root.find(".//JOB[@JOBNAME='JOB-PREFIX-ADB-DEVRES']")
    initial_resources = get_resource_names(job)
    assert "DWDEV" in initial_resources # Precondition
    assert "ADBDEV" in initial_resources # Precondition

    standardize_resources(root, target_env)

    target_cfg = ENV_CONFIG[target_env]
    final_resources = get_resource_names(job)

    # Check that all expected target resources are now present
    assert target_cfg['dw_resource'] in final_resources
    assert target_cfg['adb_resource'] in final_resources
    assert "CONTROLM-RESOURCE" in final_resources

@pytest.mark.parametrize("target_env", ['preprod', 'prod'])
def test_resources_adf_updates_dev_resource(sample_xml_root_for_resources, target_env):
    """Verify ADF job has its dev resource updated to the target resource."""
    root = copy.deepcopy(sample_xml_root_for_resources)
    job = root.find(".//JOB[@JOBNAME='JOB-PREFIX-ADF-DEVRES']")
    initial_resources = get_resource_names(job)
    assert "ADFDEV" in initial_resources # Precondition

    standardize_resources(root, target_env)

    target_cfg = ENV_CONFIG[target_env]
    expected_resources = {"CONTROLM-RESOURCE", target_cfg['adf_resource']}
    assert get_resource_names(job) == expected_resources

@pytest.mark.parametrize("target_env", ['preprod', 'prod'])
def test_resources_dw_adds_missing(sample_xml_root_for_resources, target_env):
    """Verify DW job with only CONTROLM gets the target DW resource added."""
    root = copy.deepcopy(sample_xml_root_for_resources)
    job = root.find(".//JOB[@JOBNAME='JOB-PREFIX-DW-ONLYCM']")
    assert len(job.findall('QUANTITATIVE')) == 1 # Precondition

    standardize_resources(root, target_env)

    target_cfg = ENV_CONFIG[target_env]
    expected_resources = {"CONTROLM-RESOURCE", target_cfg['dw_resource']}
    assert get_resource_names(job) == expected_resources

@pytest.mark.parametrize("target_env", ['preprod', 'prod'])
def test_resources_dw_updates_wrong_resource(sample_xml_root_for_resources, target_env):
    """Verify DW job with an incorrect resource gets it updated."""
    root = copy.deepcopy(sample_xml_root_for_resources)
    job = root.find(".//JOB[@JOBNAME='JOB-PREFIX-DW-WRONGRES']")
    assert "SOMETHING_ELSE" in get_resource_names(job) # Precondition

    standardize_resources(root, target_env)

    target_cfg = ENV_CONFIG[target_env]
    expected_resources = {"CONTROLM-RESOURCE", target_cfg['dw_resource']}
    assert get_resource_names(job) == expected_resources

@pytest.mark.parametrize("target_env", ['preprod', 'prod'])
def test_resources_leaves_other_jobs_unchanged(sample_xml_root_for_resources, target_env):
    """Verify jobs not matching ADF/ADB/DW patterns are not changed."""
    root = copy.deepcopy(sample_xml_root_for_resources)
    job = root.find(".//JOB[@JOBNAME='JOB_RES_OTHER_TYPE']")
    initial_resources = get_resource_names(job)
    assert initial_resources == {"CONTROLM-RESOURCE", "OTHER_RES"} # Precondition

    standardize_resources(root, target_env)

    # Resources should remain the same
    assert get_resource_names(job) == initial_resources

def test_resources_skips_for_dev_env(sample_xml_root_for_resources):
    """Verify resource standardization is skipped for target_env='dev'."""
    root = copy.deepcopy(sample_xml_root_for_resources)
    original_xml_string = ET.tostring(root, encoding='unicode')

    standardize_resources(root, 'dev') # Target 'dev'

    modified_xml_string = ET.tostring(root, encoding='unicode')
    # XML should be unchanged
    assert modified_xml_string == original_xml_string

