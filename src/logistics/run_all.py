"""Run the delivery logistics phase for one dealer.

Run from the project root (after src.extract.run_all, which builds the dealer list):
    python -m src.logistics.run_all
"""

from src.logistics import inputs, service_area, simulate


def main() -> None:
    print("[1/3] Service area and customer base")
    service_area.run()
    print("[2/3] Weather and road distances")
    inputs.run()
    print("[3/3] Season simulation and routing (several minutes)")
    simulate.run()
    print("Done.")


if __name__ == "__main__":
    main()
