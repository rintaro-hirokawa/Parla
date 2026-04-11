"""Launch Parla: python -m parla [--state STATE]"""

import argparse

from parla.ui.app import main

parser = argparse.ArgumentParser(prog="parla", description="Parla language learning app")
parser.add_argument(
    "--state",
    default=None,
    help="Reset DB and seed to a predefined state (e.g. day1)",
)
args = parser.parse_args()
main(state=args.state)
