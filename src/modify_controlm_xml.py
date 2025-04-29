import xml.etree.ElementTree as ET
import argparse
import os
import sys
import copy
from typing import Optional
from errors import ControlMXmlError



# Attempt to import modifier functions
try:
    from xml_modifiers import activate_folders
    from xml_modifiers import apply_environment_promotion, standardize_resources, standardize_notifications
except ImportError as e:
    print(f"Warning: Could not import from xml_modifiers.py: {e}")
    # Define placeholder functions if import fails
    def activate_folders(root): print("  [Placeholder] activate_folders"); return 0
    def apply_environment_promotion(root, env): print("  [Placeholder] apply_environment_promotion")
    def standardize_resources(root, env): print("  [Placeholder] standardize_resources")
    def standardize_notifications(root, env): print("  [Placeholder] standardize_notifications")


def parse_xml(xml_path: str) -> Optional[ET.ElementTree]:
    """Parses the input XML file."""
    if not os.path.exists(xml_path):
        print(f"Error: Input XML file not found at {xml_path}", file=sys.stderr)
        return None
    try:
        tree = ET.parse(xml_path)
        return tree
    except ET.ParseError as e:
        raise ControlMXmlError(f"Failed to parse XML file {xml_path}. Details: {e}")
    except Exception as e:
        raise ControlMXmlError(f"Unexpected error during XML parsing: {e}")

def write_xml(tree: ET.ElementTree, output_path: str) -> bool:
    """Writes the XML tree to the output file."""
    try:
        output_dir = os.path.dirname(output_path)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)
            print(f"Created output directory: {output_dir}")

        tree.write(output_path, encoding='utf-8', xml_declaration=True)
        print(f"Successfully wrote modified XML to: {output_path}")
        return True
    except IOError as e:
        raise ControlMXmlError(f"Could not write output file {output_path}. Details: {e}")
    except Exception as e:
        raise ControlMXmlError(f"Unexpected error occurred while writing {output_path}: {e}")

def main() -> None:
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

    print(f"--- Starting Control-M XML Modification ---")
    print(f"Input file: {args.input}")
    print(f"Output file: {args.output}")
    print(f"Target Environment: {args.target_env}")
    print(f"Steps to apply: {', '.join(args.steps)}")

    try:
        xml_tree_original = parse_xml(args.input)
    except ControlMXmlError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
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
    for step in args.steps:
        print(f"\nApplying step: [{step}]...")
        func = step_function_map.get(step)
        if not func:
            print(f"Error: Unknown step '{step}'", file=sys.stderr)
            steps_failed.append(step)
            continue

        try:
            # Pass target_env only to functions that need it
            if step in ['promote', 'resources', 'notifications']:
                 func(root_modified, args.target_env)
            else:
                 func(root_modified)
            steps_applied_successfully.append(step)
            print(f"Step [{step}] applied.")
        except ControlMXmlError as e:
            print(f"Custom error during [{step}] step: {e}", file=sys.stderr)
            steps_failed.append(step)
            print("Exiting due to error in modification step.")
            sys.exit(1)
        except Exception as e:
            print(f"Error during [{step}] step: {e}", file=sys.stderr)
            steps_failed.append(step)
            print("Exiting due to error in modification step.")
            sys.exit(1)

    # Write the final result
    if not steps_applied_successfully:
        print("\nWarning: No modification steps were successfully applied. Output file not written.")
    elif steps_failed:
         print(f"\nWarning: Some steps failed ({', '.join(steps_failed)}). Output file may be incomplete.")
    else:
        print(f"\nWriting final modified XML after steps: {', '.join(steps_applied_successfully)}")
        try:
            if not write_xml(xml_tree_modified, args.output):
                sys.exit(1)
        except ControlMXmlError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)

    print(f"--- XML Modification Process Finished ---")
    if steps_failed:
        print(f"--- WARNING: Steps Failed: {', '.join(steps_failed)} ---")
        sys.exit(1)

if __name__ == "__main__":
    main()
