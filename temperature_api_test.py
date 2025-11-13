"""CLI helpers for exercising the GeoVision temperature API."""
from __future__ import annotations

from geovision.temperature import TemperatureClient


def main() -> None:
    client = TemperatureClient()

    print("--- 1. ROI Statistics ---")
    roi_stats = client.get_roi_stats()
    if roi_stats:
        print(f"ROI stats: {roi_stats}")
    else:
        print("Failed to fetch ROI statistics (ensure ROIs are configured).")

    print("\n--- 2. Dot Temperature ---")
    x, y = 192, 144
    dot_temp = client.get_dot_temperature(x, y)
    if dot_temp:
        temp_c, resp_x, resp_y = dot_temp
        print(f"Requested ({x}, {y}) -> Camera reported ({resp_x}, {resp_y}) = {temp_c:.2f} °C")
    else:
        print("Failed to fetch dot temperature.")


if __name__ == "__main__":
    main()
