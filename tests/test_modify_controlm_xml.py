import pytest
import xml.etree.ElementTree as ET
import os
import sys
import copy
from src.xml_modifiers import activate_folders, standardize_notifications, ENV_CONFIG

# --- Fixtures ---

@pytest.fixture
def sample_xml_root_for_activation():
    """Provides XML root for testing folder activation scenarios."""
    xml_string = """
<DEFTABLE>
    <FOLDER FOLDER_NAME="FOLDER_A_ACTIVE" FOLDER_ORDER_METHOD="SYSTEM"/>
    <FOLDER FOLDER_NAME="FOLDER_B_MANUAL" FOLDER_ORDER_METHOD="MANUAL"/>
    <FOLDER FOLDER_NAME="FOLDER_C_MISSING_ATTR"/>
    <FOLDER FOLDER_NAME="FOLDER_D_EMPTY_ATTR" FOLDER_ORDER_METHOD=""/>
    <FOLDER FOLDER_NAME="FOLDER_E_SYSTEM" FOLDER_ORDER_METHOD="SYSTEM"/>
</DEFTABLE>
"""
    return ET.fromstring(xml_string)

@pytest.fixture
def sample_xml_root_for_notifications():
    """Provides XML root for testing notification standardization."""
    xml_string = """
<DEFTABLE>
    <FOLDER FOLDER_NAME="FOLDER_X">
        <JOB JOBNAME="JOB_X1_NO_ON">
            <VARIABLE NAME="VAR1" VALUE="X"/>
        </JOB>
        <JOB JOBNAME="JOB_X2_ONE_ON">
            <VARIABLE NAME="VAR1" VALUE="Y"/>
            <ON STMT="*">
                <DOMAIL DEST="old@example.com"/>
            </ON>
        </JOB>
    </FOLDER>
</DEFTABLE>
"""
    return ET.fromstring(xml_string)


# --- Test Functions for activate_folders ---
def test_activate_folders_activates_missing(sample_xml_root_for_activation):
    root = copy.deepcopy(sample_xml_root_for_activation)
    folder_c = root.find("./FOLDER[@FOLDER_NAME='FOLDER_C_MISSING_ATTR']")
    assert folder_c.get('FOLDER_ORDER_METHOD') is None
    activate_folders(root)
    assert folder_c.get('FOLDER_ORDER_METHOD') == 'SYSTEM'

def test_activate_folders_activates_manual(sample_xml_root_for_activation):
    root = copy.deepcopy(sample_xml_root_for_activation)
    folder_b = root.find("./FOLDER[@FOLDER_NAME='FOLDER_B_MANUAL']")
    assert folder_b.get('FOLDER_ORDER_METHOD') == 'MANUAL'
    activate_folders(root)
    assert folder_b.get('FOLDER_ORDER_METHOD') == 'SYSTEM'

def test_activate_folders_activates_empty_attr(sample_xml_root_for_activation):
    root = copy.deepcopy(sample_xml_root_for_activation)
    folder_d = root.find("./FOLDER[@FOLDER_NAME='FOLDER_D_EMPTY_ATTR']")
    assert folder_d.get('FOLDER_ORDER_METHOD') == ''
    activate_folders(root)
    assert folder_d.get('FOLDER_ORDER_METHOD') == 'SYSTEM'

def test_activate_folders_leaves_system_unchanged(sample_xml_root_for_activation):
    root = copy.deepcopy(sample_xml_root_for_activation)
    folder_a = root.find("./FOLDER[@FOLDER_NAME='FOLDER_A_ACTIVE']")
    folder_e = root.find("./FOLDER[@FOLDER_NAME='FOLDER_E_SYSTEM']")
    assert folder_a.get('FOLDER_ORDER_METHOD') == 'SYSTEM'
    assert folder_e.get('FOLDER_ORDER_METHOD') == 'SYSTEM'
    activate_folders(root)
    assert folder_a.get('FOLDER_ORDER_METHOD') == 'SYSTEM'
    assert folder_e.get('FOLDER_ORDER_METHOD') == 'SYSTEM'

def test_activate_folders_returns_correct_count(sample_xml_root_for_activation):
    root = copy.deepcopy(sample_xml_root_for_activation)
    expected_count = 3
    actual_count = activate_folders(root)
    assert actual_count == expected_count

def test_activate_folders_empty_root():
    root = ET.fromstring("<DEFTABLE></DEFTABLE>")
    count = activate_folders(root)
    assert count == 0

# --- Test Functions for standardize_notifications ---

def test_notifications_removes_existing_on_blocks(sample_xml_root_for_notifications):
    """Verify existing ON blocks are removed before adding new ones."""
    root = copy.deepcopy(sample_xml_root_for_notifications)
    job_x2 = root.find(".//JOB[@JOBNAME='JOB_X2_ONE_ON']")
    assert len(job_x2.findall('ON')) == 1 # Precondition

    standardize_notifications(root, 'preprod') # Apply preprod template

    # Check that the number of ON blocks matches the preprod template now
    expected_on_count = 2
    assert len(job_x2.findall('ON')) == expected_on_count


def test_notifications_adds_to_job_with_no_on(sample_xml_root_for_notifications):
    """Verify notifications are added to jobs that initially had none."""
    root = copy.deepcopy(sample_xml_root_for_notifications)
    job_x1 = root.find(".//JOB[@JOBNAME='JOB_X1_NO_ON']")
    assert len(job_x1.findall('ON')) == 0

    standardize_notifications(root, 'prod') # Apply prod template


    expected_on_count = 1
    assert len(job_x1.findall('ON')) == expected_on_count

@pytest.mark.parametrize("target_env", ['preprod', 'prod'])
def test_notifications_applies_correct_template(sample_xml_root_for_notifications, target_env):
    """Check if the correct email destination from the template is applied."""
    root = copy.deepcopy(sample_xml_root_for_notifications)
    job = root.find(".//JOB[@JOBNAME='JOB_X1_NO_ON']")

    standardize_notifications(root, target_env)

    on_blocks = job.findall('ON')
    assert len(on_blocks) > 0
    # Find the first DOMAIL element across all added ON blocks
    domail = None
    for on_block in on_blocks:
        domail = on_block.find('DOMAIL')
        if domail is not None:
            break
    assert domail is not None

    # Check if the destination matches the config for the target environment
    expected_dest = ENV_CONFIG[target_env]['notification_dest']
    assert domail.get('DEST') == expected_dest

def test_notifications_handles_empty_root():
    """Test notification standardization with an empty DEFTABLE."""
    root = ET.fromstring("<DEFTABLE></DEFTABLE>")
    standardize_notifications(root, 'preprod')
    assert len(root.findall('.//JOB')) == 0

def test_notifications_skips_for_dev_env(sample_xml_root_for_notifications):
    """Verify that the function explicitly skips processing for 'dev' target."""
    root = copy.deepcopy(sample_xml_root_for_notifications)
    # Store the original XML string to compare against
    original_xml_string = ET.tostring(root, encoding='unicode')

    # Run the function targeting 'dev'
    standardize_notifications(root, 'dev')

    # Get the XML string after running the function
    modified_xml_string = ET.tostring(root, encoding='unicode')

    # Assert that the XML tree was not modified
    assert modified_xml_string == original_xml_string
    # Additionally check that no ON blocks were added to a job that had none
    job_x1 = root.find(".//JOB[@JOBNAME='JOB_X1_NO_ON']")
    assert len(job_x1.findall('ON')) == 0


# Add tests...

