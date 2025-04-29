import pytest
import xml.etree.ElementTree as ET
import os
import sys
import copy
from src.xml_modifiers import activate_folders

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

# --- Test Functions for activate_folders ---

def test_activate_folders_activates_missing(sample_xml_root_for_activation: ET.Element):
    """Check activation for folder missing FOLDER_ORDER_METHOD attribute."""
    root = copy.deepcopy(sample_xml_root_for_activation)
    folder_c = root.find("./FOLDER[@FOLDER_NAME='FOLDER_C_MISSING_ATTR']")
    assert folder_c.get('FOLDER_ORDER_METHOD') is None # Pre-check

    activate_folders(root)

    assert folder_c.get('FOLDER_ORDER_METHOD') == 'SYSTEM' # Post-check

def test_activate_folders_activates_manual(sample_xml_root_for_activation: ET.Element):
    """Check activation for folder with FOLDER_ORDER_METHOD='MANUAL'."""
    root = copy.deepcopy(sample_xml_root_for_activation)
    folder_b = root.find("./FOLDER[@FOLDER_NAME='FOLDER_B_MANUAL']")
    assert folder_b.get('FOLDER_ORDER_METHOD') == 'MANUAL' # Pre-check

    activate_folders(root)

    assert folder_b.get('FOLDER_ORDER_METHOD') == 'SYSTEM' # Post-check

def test_activate_folders_activates_empty_attr(sample_xml_root_for_activation: ET.Element):
    """Check activation for folder with empty FOLDER_ORDER_METHOD attribute."""
    root = copy.deepcopy(sample_xml_root_for_activation)
    folder_d = root.find("./FOLDER[@FOLDER_NAME='FOLDER_D_EMPTY_ATTR']")
    assert folder_d.get('FOLDER_ORDER_METHOD') == '' # Pre-check

    activate_folders(root)

    assert folder_d.get('FOLDER_ORDER_METHOD') == 'SYSTEM' # Post-check

def test_activate_folders_leaves_system_unchanged(sample_xml_root_for_activation: ET.Element):
    """Check that folders already set to SYSTEM are not modified."""
    root = copy.deepcopy(sample_xml_root_for_activation)
    folder_a = root.find("./FOLDER[@FOLDER_NAME='FOLDER_A_ACTIVE']")
    folder_e = root.find("./FOLDER[@FOLDER_NAME='FOLDER_E_SYSTEM']")
    assert folder_a.get('FOLDER_ORDER_METHOD') == 'SYSTEM' # Pre-check
    assert folder_e.get('FOLDER_ORDER_METHOD') == 'SYSTEM' # Pre-check

    activate_folders(root) # Run the function

    # Verify attributes remain unchanged
    assert folder_a.get('FOLDER_ORDER_METHOD') == 'SYSTEM'
    assert folder_e.get('FOLDER_ORDER_METHOD') == 'SYSTEM'

def test_activate_folders_returns_correct_count(sample_xml_root_for_activation: ET.Element):
    """Verify the returned count matches the number of activated folders."""
    root = copy.deepcopy(sample_xml_root_for_activation)
    # Expect folders B, C, D to be activated
    expected_count = 3
    actual_count = activate_folders(root)
    assert actual_count == expected_count

def test_activate_folders_empty_root():
    """Check behavior with an XML root containing no FOLDER elements."""
    root = ET.fromstring("<DEFTABLE></DEFTABLE>")
    count = activate_folders(root)
    assert count == 0

# --- Placeholder for future tests ---
# Add tests for other functions here as they are developed.

