# Control-M XML Automation

## Overview

This Python-based command-line tool automates the complex and often error-prone process of modifying BMC Control-M job definition XML files for environment promotion (e.g., Dev -> PreProd -> Prod) and standardization. By parsing Control-M XML exports, applying targeted modifications based on environment-specific rules, and generating updated XML files, this tool significantly reduces manual effort, ensures consistency, and minimizes deployment risks associated with manual XML editing.

This project demonstrates proficiency in Python scripting, XML manipulation, configuration management, modular design, and automated testing, directly addressing common challenges in enterprise workload automation workflows. This script is adapted from real-world automation tasks, using anonymized sample data.

## The Problem Solved

Manually updating Control-M XML definitions when promoting jobs between environments (Development, Pre-Production, Production) is tedious, time-consuming, and highly susceptible to human error. Inconsistencies in naming conventions, resource allocation, notification settings, server nodes, user accounts, and activation status can lead to job failures, deployment delays, and operational instability. This tool provides a reliable, repeatable, and automated solution to these challenges.

## Features

- **Environment Promotion (`promote`):** Intelligently updates environment-specific attributes within the XML, including:
  - Folder, Application, Sub-Application, and Job names (e.g., replacing `-DEV-` with `-PREPROD-`).
  - `RUN_AS` user accounts (e.g., appending `_pp` suffix).
  - `NODEID` / Agent hostnames (e.g., changing `dev` host patterns to `pp`).
  - `DATACENTER` attributes based on target environment rules.
  - `INCOND`/`OUTCOND` condition names to match promoted job/folder names.
  - Environment-specific job name suffixes (adding/removing as needed).
  - Specific `VARIABLE` values (e.g., `%%user`).
- **Folder Activation (`activate`):** Ensures all folders are set to be ordered automatically by setting `FOLDER_ORDER_METHOD="SYSTEM"`.
- **Resource Standardization (`resources`):** Standardizes Quantitative Resources (`QUANTITATIVE`) based on job name patterns (e.g., `-ADF-`, `-DW-`, `-ADB-`) and target environment configurations. Ensures required resources exist and updates names (e.g., `ADFDEV` -> `APP-AZ-ADF-PP`).
- **Notification Standardization (`notifications`):** Replaces existing job notification blocks (`ON`/`DO*` statements) with standardized templates tailored for Pre-Production or Production environments, ensuring consistent alerting and escalation procedures.
- **Configurable Steps:** Allows users to specify which modification steps to apply and in what order.
- **Robust Error Handling:** Includes specific error checking and logging for clear diagnostics.
- **Modular Design:** Logic is separated into distinct modules for clarity and maintainability (`cli.py`, `modify_controlm_xml.py`, `xml_modifiers.py`, `errors.py`).
- **Tested:** Includes unit tests (`pytest`) to verify the core modification logic.

## Technical Details

* **Language:** Python 3
* **Core Libraries:**
  * `xml.etree.ElementTree`: For parsing and manipulating XML data.
  * `argparse`: For creating a user-friendly command-line interface.
  * `re`: For pattern matching and substitution during promotion.
  * `logging`: For informative output and diagnostics.
  * `copy`: For safely modifying XML structures.
* **Testing:** `pytest` framework for unit testing modification functions.
* **Configuration:** Environment-specific rules (resource names, naming patterns, notification details) are centralized within the `ENV_CONFIG` dictionary in `src/xml_modifiers.py`, making it easy to adapt to different environment standards.

## Installation

```bash
git clone <your-repository-url>
cd controlm-xml-automation
# Create and activate a virtual environment (Recommended)
python3 -m venv .venv
source .venv/bin/activate
# On Windows
python -m venv .venv
.\.venv\Scripts\activate
# Install dependencies
pip install -r requirements.txt
```

## Usage

```bash
python3 src/modify_controlm_xml.py \
  --input <path_to_source_xml> \
  --output <path_for_modified_xml> \
  --target-env <dev|preprod|prod> \
  --steps <step1> [<step2> ...]
```

## Configuration

Environment-specific rules (resource names, naming patterns, notification details) are centralized within the `ENV_CONFIG` dictionary in `src/xml_modifiers.py`, making it easy to adapt to different environment standards.

## Examples

```bash
# To promote a Development XML file (sample_controlm_dev.xml) to Pre-Production (sample_controlm_preprod.xml), applying activation, promotion, resource standardization, and notification standardization in that specific order:
# Ensure your virtual environment is active: source .venv/bin/activate
(.venv) benkaan@Bens-MacBook-Pro-2 controlm-xml-automation % python3 src/modify_controlm_xml.py \
  --input sample_data/sample_controlm_dev.xml \
  --output sample_output/sample_controlm_preprod.xml \
  --target-env preprod \
  --steps activate promote resources notifications
```

## Contributing

Contributions are welcome! Please follow these steps:

1. Fork the repository.
2. Create a new branch for your feature or bug fix (git checkout -b feature/your-feature-name).
3. Make your changes, ensuring code is well-commented and follows existing style.
4. Add or update unit tests for your changes in the tests/ directory (e.g., test_modify_controlm_xml.py).
5. Ensure all tests pass (pytest).
6. Commit your changes (git commit -m 'Add some feature').
7. Push to the branch (git push origin feature/your-feature-name).
8. Open a Pull Request against the main branch of the original repository.

## License

[MIT License](https://opensource.org/licenses/MIT)
