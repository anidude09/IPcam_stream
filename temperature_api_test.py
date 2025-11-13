import requests
import xml.etree.ElementTree as ET
from requests.auth import HTTPBasicAuth

# --- Configuration ---
IP_ADDRESS = "192.168.0.10"
USERNAME = "admin"
PASSWORD = "admin123"
THERMAL_CHANNEL = 2  # Typically 2 for the thermal channel



# 1. Function to get ROI (Region of Interest) summary stats
def get_roi_stats(channel=THERMAL_CHANNEL):
    """
    Fetches the current min/max/avg temperature stats for pre-configured ROIs.
    """
    url = f"http://{IP_ADDRESS}/GetTemperatureCurrentInfo/{channel}"
    print(f"Querying ROI stats from: {url}")
    try:
        r = requests.get(url, auth=HTTPBasicAuth(USERNAME, PASSWORD), timeout=3)
        r.raise_for_status()

        print("--- ROI Stats XML Response ---")
        print(r.text)
        print("------------------------------")

        root = ET.fromstring(r.text)

        # FIX: We must search for the <value> tag *inside* the temp tags.
        # The .// search finds the *first* matching tag in the document,
        # which corresponds to the first <item> (ruleId 0).
        max_v = root.find(".//{*}maxTemper/{*}value")
        min_v = root.find(".//{*}minTemper/{*}value")
        avg_v = root.find(".//{*}avgTemper/{*}value")

        results = {}
        # FIX: Check for None and divide by 100.0 (based on dot temp)
        if max_v is not None and max_v.text:
            results['max'] = float(max_v.text) / 100.0
        if min_v is not None and min_v.text:
            results['min'] = float(min_v.text) / 100.0
        if avg_v is not None and avg_v.text:
            results['avg'] = float(avg_v.text) / 100.0

        if not results:
            print("Warning: Could not parse any ROI temps. Are ROIs configured in the web UI?")
            return None

        return results

    except requests.exceptions.HTTPError as errh:
        print(f"Http Error: {errh}")
    except requests.exceptions.ConnectionError as errc:
        print(f"Error Connecting: {errc}")
    except requests.exceptions.Timeout as errt:
        print(f"Timeout Error: {errt}")
    except requests.exceptions.RequestException as err:
        print(f"OOps: Something Else: {err}")
    except ET.ParseError as perr:
        print(f"XML Parse Error: {perr}. Response was: {r.text}")
    return None


# 2. Function to get a specific (x, y) dot temperature
def get_dot_temp(x, y, channel=THERMAL_CHANNEL):
    """
    Fetches the temperature for a specific (x, y) pixel coordinate.
    Returns a tuple: (temp_c, response_x, response_y)
    """
    url = f"http://{IP_ADDRESS}/GetDotTemperature/{channel}"

    # This is the XML payload we SEND to the camera
    xml_payload = f"""<?xml version="1.0" encoding="UTF-8"?>
    <config version="1.0" xmlns="http://www.ipc.com/ver10">
        <dotTemperature>
            <hotX>{x}</hotX>
            <hotY>{y}</hotY>
        </dotTemperature>
    </config>"""

    headers = {'Content-Type': 'application/xml'}
    print(f"Querying dot temp from: {url} at ({x}, {y})")

    try:
        r = requests.post(url,
                          auth=HTTPBasicAuth(USERNAME, PASSWORD),
                          data=xml_payload,
                          headers=headers,
                          timeout=3)
        r.raise_for_status()

        print(f"--- Dot Temp XML Response ({x},{y}) ---")
        print(r.text)
        print("-----------------------------------")

        root = ET.fromstring(r.text)

        val = root.find(".//{*}temperature")
        hot_x_val = root.find(".//{*}hotX")
        hot_y_val = root.find(".//{*}hotY")

        if val is None or val.text is None or \
                hot_x_val is None or hot_x_val.text is None or \
                hot_y_val is None or hot_y_val.text is None:
            print("Warning: Could not find 'temperature', 'hotX', or 'hotY' in XML response.")
            return None

        temp_c = float(val.text) / 100.0

        # Get the confirmed coordinates from the camera's response
        response_x = int(hot_x_val.text)
        response_y = int(hot_y_val.text)

        # Return all three values
        return (temp_c, response_x, response_y)

    except requests.exceptions.HTTPError as errh:
        print(f"Http Error: {errh}")
    except requests.exceptions.ConnectionError as errc:
        print(f"Error Connecting: {errc}")
    except requests.exceptions.Timeout as errt:
        print(f"Timeout Error: {errt}")
    except requests.exceptions.RequestException as err:
        print(f"OOps: Something Else: {err}")
    except ET.ParseError as perr:
        print(f"XML Parse Error: {perr}. Response was: {r.text}")
    return None


# --- Main execution block to test the functions ---
if __name__ == "__main__":
    print("--- 1. Testing ROI Statistics ---")
    roi_data = get_roi_stats()
    if roi_data:
        print(f"Successfully fetched ROI stats: {roi_data}")
    else:
        print("Failed to fetch ROI stats. (This is normal if no ROIs are configured on the camera).")

    print("\n" + "=" * 30 + "\n")

    print("--- 2. Testing Dot Temperature ---")
    # Test coordinate from your document's example
    test_x, test_y = (192, 144)
    dot_data = get_dot_temp(test_x, test_y)

    if dot_data:
        temp, x, y = dot_data
        print(f"Successfully fetched dot temperature.")
        print(f"  > Requested: ({test_x}, {test_y})")
        print(f"  > Responded: ({x}, {y})")
        print(f"  > Temperature: {temp}°C")
    else:
        print(f"Failed to fetch dot temperature for ({test_x}, {test_y}).")