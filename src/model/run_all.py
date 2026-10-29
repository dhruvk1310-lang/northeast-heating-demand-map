"""Run the demand model and county scoring.

Needs the interim tables from `python -m src.extract.run_all`. Run from the project root:
    python -m src.model.run_all
"""

from src.model import demand, score


def main() -> None:
    print("[1/2] Demand model and calibration")
    demand.run()
    print("[2/2] County scores and sensitivity check")
    score.run()
    print("Done.")


if __name__ == "__main__":
    main()
