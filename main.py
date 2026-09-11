"""Command-line entry point for the shared BerryLens verification service."""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(dotenv_path=Path(__file__).resolve().with_name('.env'))

from verification_service import VerificationService


def run_berrylens_pipeline():
    print("\n==========================================")
    print("         BERRYLENS AI PIPELINE")
    print("==========================================\n")

    claim = input("Enter a news claim: ").strip()
    if not claim:
        print("No claim provided. Exiting.")
        return

    report = VerificationService().verify(claim)
    print("\n---------------- RESULTS ----------------")
    print(f"VERDICT: {report.verdict.value}")
    print(f"CONFIDENCE: {report.confidence_pct}%")
    print(f"STATUS: {report.research_status.value}")
    print(f"EXPLANATION: {report.summary}")
    print(f"SOURCES CHECKED: {report.sources_checked}")
    print("-----------------------------------------\n")


if __name__ == "__main__":
    run_berrylens_pipeline()
