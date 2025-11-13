import cv2
import time
import os



#---Parameters---

IP_ADDRESS = '192.168.0.10'
USERNAME = 'admin'
PASSWORD = 'admin123'
THERMAL_PROFILE= 'profile4'
RGB_PROFILE= 'profile1'


os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp"
print("Set 'OPENCV_FFMPEG_CAPTURE_OPTIONS=rtsp_transport;tcp' to force TCP.")

RTSP_THERMAL = f"rtsp://{USERNAME}:{PASSWORD}@{IP_ADDRESS}:554/{RGB_PROFILE}"


print(f"Attempting to connect to {RTSP_THERMAL}")


#FFMPEG backend
cap = cv2.VideoCapture(RTSP_THERMAL, cv2.CAP_FFMPEG)

#small buffer value
cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)


if not cap.isOpened():
    print("Unable to open camera.")


    exit(-1)

print("Successfully opened camera.")

while True:
    ok, frame = cap.read()

    if not ok:
        print("Error: Cannot read frame from Stream. Reconnecting...")

        cap.release()
        time.sleep(2)

        cap = cv2.VideoCapture(RTSP_THERMAL, cv2.CAP_FFMPEG)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        if not cap.isOpened():
            print("Failed to reconnect and open camera.")
            break
        continue


    cv2.imshow(" Stream from GeoVision camera:", frame)

    if cv2.waitKey(1) == 27:
        print("Exiting...")
        break


cap.release()
cv2.destroyAllWindows()

print("Successfully closed camera.")






