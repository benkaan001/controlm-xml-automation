import argparse
from modify_controlm_xml import main

def parse_args():
    """
    Parse command-line arguments for the Control-M XML automation tool.
    """
    parser = argparse.ArgumentParser(
        description="Modify Control-M XML files for different environments.",
        epilog="""
Example usage:
  python3 src/cli.py \\
    --input sample_data/sample_controlm_dev.xml \\
    --output sample_output/sample_controlm_preprod.xml \\
    --target-env preprod \\
    --steps activate promote resources notifications
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument('--input', required=True, help='Path to input XML file')
    parser.add_argument('--output', required=True, help='Path to output XML file')
    parser.add_argument('--target-env', required=True, help='Target environment (e.g., preprod)')
    parser.add_argument('--steps', nargs='+', required=True, help='Steps to apply in order (e.g., activate promote resources notifications)')
    return parser.parse_args()

def cli():
    """
    Entry point for the CLI.
    """
    args = parse_args()
    main(
        input_path=args.input,
        output_path=args.output,
        target_env=args.target_env,
        steps=args.steps
    )

if __name__ == "__main__":
    cli()
