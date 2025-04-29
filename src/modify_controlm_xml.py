import xml.etree.ElementTree as ET
import argparse
import os
import sys
import copy
from typing import Optional
import logging
from errors import ControlMXmlError



# Attempt to import modifier functions
try:
    from xml_modifiers import activate_folders
    from xml_modifiers import apply_environment_promotion, standardize_resources, standardize_notifications
except ImportError as e:
    logging.warning(f"Could not import from xml_modifiers.py: {e}")
    # Define placeholder functions if import fails
    def activate_folders(root): print("  [Placeholder] activate_folders"); return 0
    def apply_environment_promotion(root, env): print("  [Placeholder] apply_environment_promotion")
    def standardize_resources(root, env): print("  [Placeholder] standardize_resources")
    def standardize_notifications(root, env): print("  [Placeholder] standardize_notifications")


def parse_xml(xml_path: str) -> Optional[ET.ElementTree]:
    """Parses the input XML file."""
    if not os.path.exists(xml_path):
        logging.error(f"Input XML file not found at {xml_path}")
        return None
    try:
        tree = ET.parse(xml_path)
        return tree
    except ET.ParseError as e:
        logging.error(f"Failed to parse XML file {xml_path}. Details: {e}")
        return None
    except Exception as e:
        logging.error(f"An unexpected error occurred during XML parsing: {e}")
        return None

def write_xml(tree: ET.ElementTree, output_path: str) -> bool:
    """Writes the XML tree to the output file."""
    try:
        output_dir = os.path.dirname(output_path)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)
            logging.info(f"Created output directory: {output_dir}")

        tree.write(output_path, encoding='utf-8', xml_declaration=True)
        logging.info(f"Successfully wrote modified XML to: {output_path}")
        return True
    except IOError as e:
        logging.error(f"Could not write output file {output_path}. Details: {e}")
        return False
    except Exception as e:
        logging.error(f"An unexpected error occurred while writing {output_path}: {e}")
        return False

def main(input_path, output_path, target_env, steps):
    """
    Main function to modify a Control-M XML file.

    Args:
        input_path (str): Path to the input XML file.
        output_path (str): Path to the output XML file.
        target_env (str): Target environment name.
        steps (list): List of steps to apply in order.

    The steps are applied in the order provided.
    """
    logging.info(f"--- Starting Control-M XML Modification ---")
    logging.info(f"Input file: {input_path}")
    logging.info(f"Output file: {output_path}")
    logging.info(f"Target Environment: {target_env}")
    logging.info(f"Steps to apply: {', '.join(steps)}")

    xml_tree_original = parse_xml(input_path)
    if xml_tree_original is None:
        sys.exit(1)

    # Work on a copy to allow sequential modifications safely
    xml_tree_modified = copy.deepcopy(xml_tree_original)
    root_modified = xml_tree_modified.getroot()

    steps_applied_successfully = []
    steps_failed = []

    step_function_map = {
        'promote': apply_environment_promotion,
        'activate': activate_folders,
        'resources': standardize_resources,
        'notifications': standardize_notifications
    }

    # Apply steps in the user-specified order
    for step in steps:
        logging.info(f"Applying step: [{step}]...")
        func = step_function_map.get(step)
        if not func:
            logging.error(f"Unknown step '{step}'")
            steps_failed.append(step)
            continue

        try:
            # Pass target_env only to functions that need it
            if step in ['promote', 'resources', 'notifications']:
                 func(root_modified, target_env)
            else:
                 func(root_modified)
            steps_applied_successfully.append(step)
            logging.info(f"Step [{step}] applied.")
        except ControlMXmlError as e:
            logging.error(f"Custom error during [{step}] step: {e}")
            steps_failed.append(step)
            logging.error("Exiting due to error in modification step.")
            sys.exit(1)
        except Exception as e:
            logging.error(f"Error during [{step}] step: {e}")
            steps_failed.append(step)
            logging.error("Exiting due to error in modification step.")
            sys.exit(1)

    # Write the final result
    if not steps_applied_successfully:
        logging.warning("No modification steps were successfully applied. Output file not written.")
    elif steps_failed:
         logging.warning(f"Some steps failed ({', '.join(steps_failed)}). Output file may be incomplete.")
    else:
        logging.info(f"Writing final modified XML after steps: {', '.join(steps_applied_successfully)}")
        if not write_xml(xml_tree_modified, output_path):
            sys.exit(1)

    logging.info("--- XML Modification Process Finished ---")
    if steps_failed:
        logging.warning(f"--- WARNING: Steps Failed: {', '.join(steps_failed)} ---")
        sys.exit(1)

if __name__ == "__main__":
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)]
    )

    parser = argparse.ArgumentParser(
        description="Modify Control-M XML definitions for environment promotion and standardization.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("-i", "--input", required=True, help="Path to the input Control-M XML file.")
    parser.add_argument("-o", "--output", required=True, help="Path for the output modified XML file.")
    parser.add_argument(
        "-t", "--target-env",
        required=True,
        choices=['dev', 'preprod', 'prod'],
        help="Target environment ('dev', 'preprod', or 'prod'). Needed for env-specific steps."
    )
    parser.add_argument(
        "-s", "--steps",
        required=True,
        nargs='+',
        choices=['promote', 'activate', 'resources', 'notifications'],
        help=(
            "Modification steps to apply (space-separated):\n"
            "  promote       : Update env-specific attributes.\n"
            "  activate      : Set FOLDER_ORDER_METHOD='SYSTEM'.\n"
            "  resources     : Standardize QUANTITATIVE resources.\n"
            "  notifications : Standardize ON blocks."
        )
    )

    args = parser.parse_args()

    main(args.input, args.output, args.target_env, args.steps)
