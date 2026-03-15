import bluetooth
import struct
import time
import network
import ujson
import math
from umqtt.simple import MQTTClient

# WIFI configuration
WIFI_SSID = "YOUR_SSID"
WIFI_PASSWORD = "YOUR_PASSWORD"

# Ruuvitag MAC adresses and tags (replace with your own)
RUUVI_TAGS = {
    b'\xAB\xBB\xCC\xDD\xEE\xFF': "house",
    b'\xAA\xBB\xCC\xDD\xEE\xFF': "garage"
}

# MQTT configuration
MQTT_BROKER = "broker.mqttdashboard.com"
MQTT_PORT = 1883
MQTT_CLIENT_ID = "pico2w_gateway"
MQTT_RUUVI_TOPIC_BASE = "ruuvitag"

# BLE
_IRQ_SCAN_RESULT = 5
ble = bluetooth.BLE()
ble.active(True)

# Globals
wlan = None
client = None
last_publish = 0
last_net_check = 0
last_scan_restart = 0
latest_measurements = {}
last_sequence = {}

NET_CHECK_INTERVAL = 10000
SCAN_RESTART_INTERVAL = 60000
PUBLISH_INTERVAL = 2000


def ensure_wifi():
    """
    Ensure that WiFi is connected.
    If not initialized or disconnected, attempt to connect.
    """
    global wlan

    if wlan is None:
        wlan = network.WLAN(network.STA_IF)
        wlan.active(True)
        print("WiFi initialized")

    if not wlan.isconnected():
        print("Connecting to WiFi")
        wlan.connect(WIFI_SSID, WIFI_PASSWORD)

        timeout = 10
        while not wlan.isconnected() and timeout > 0:
            time.sleep(1)
            timeout -= 1

        if wlan.isconnected():
            print("WiFi connected")
        else:
            print("WiFi connection failed")


def ensure_mqtt():
    """
    Ensure that an MQTT connection exists.
    """
    global client

    if client is None:
        reconnect_mqtt()


def reconnect_mqtt():
    """
    Attempt to connect to the MQTT broker.
    """
    global client

    try:
        print("Connecting to MQTT broker")
        client = MQTTClient(MQTT_CLIENT_ID, MQTT_BROKER, port=MQTT_PORT)
        client.connect()
        print("MQTT connected")
    except Exception as e:
        print("MQTT connection failed:", e)
        client = None


def send_mqtt(tag, data):
    """
    Publish sensor data to the MQTT broker.
    If publishing fails, the client is reset so the
    reconnect logic can run during the next cycle.
    """
    global client

    if client is None:
        return

    try:
        msg = ujson.dumps(data)
        topic = "{}/{}".format(MQTT_RUUVI_TOPIC_BASE, tag)
        client.publish(topic.encode(), msg.encode())

    except Exception as e:

        print("MQTT publish failed:", e)

        try:
            client.disconnect()
        except:
            pass

        client = None


def decode_ruuvi(payload):
    """
    Decode RuuviTag Data Format 5 (RAWv2) payload.
    https://docs.ruuvi.com/communication/bluetooth-advertisements/data-format-5-rawv2
    
    Returns a dictionary with:
        temperature (°C)
        humidity (%)
        pressure (hPa)
        acceleration (vector magnitude)
        acceleration_x/y/z (mg)
        battery (mV)
        tx_power (dBm)
        movement_counter
        measurement_sequence
    """

    # Check that payload is right size and DF5
    if len(payload) < 24 or payload[0] != 0x05:
        return None

    # Temperature (°C)
    temp_raw = struct.unpack(">h", payload[1:3])[0]
    temperature = temp_raw / 200.0

    # Humidity (%)
    humidity_raw = struct.unpack(">H", payload[3:5])[0]
    humidity = humidity_raw / 400.0

    # Pressure (hPa)
    pressure_raw = struct.unpack(">H", payload[5:7])[0]
    pressure = (pressure_raw + 50000) / 100.0

    # Acceleration (X/Y/Z)
    acc_x = struct.unpack(">h", payload[7:9])[0]
    acc_y = struct.unpack(">h", payload[9:11])[0]
    acc_z = struct.unpack(">h", payload[11:13])[0]
    acceleration = (acc_x**2 + acc_y**2 + acc_z**2)**0.5

    # Battery (mV) and TX power (dBm)
    raw_power = struct.unpack(">H", payload[13:15])[0]
    battery_raw = (raw_power >> 5) & 0x07FF
    tx_power_raw = raw_power & 0x1F
    battery = battery_raw + 1600             # to mV
    tx_power = -40 + (tx_power_raw * 2)      # to dBm

    # Movement counter
    movement_counter = payload[16]

    # Measurement sequence number
    meas_sequence = payload[17]

    return {
        "temperature": temperature,
        "humidity": humidity,
        "pressure": pressure,
        "acceleration": acceleration,
        "acceleration_x": acc_x,
        "acceleration_y": acc_y,
        "acceleration_z": acc_z,
        "battery": battery,
        "tx_power": tx_power,
        "movement_counter": movement_counter,
        "measurement_sequence": meas_sequence
    }

            
def irq(event, data):
    """
    Handle BLE scan events.
    When a BLE advertisement is received, check if it
    belongs to the RuuviTag. If so, decode
    the payload and publish over MQTT.
    """

    if event != _IRQ_SCAN_RESULT:
        return

    addr_type, addr, adv_type, rssi, adv_data = data

    # Return id advertisement not from Ruuvitag
    addr_bytes = bytes(addr)
    tag = RUUVI_TAGS.get(addr_bytes)
    if tag is None:
        return
    
    # Parse Ruuvitag advertisement
    i = 0
    while i < len(adv_data):

        length = adv_data[i]
        if length == 0:
            break

        type_ = adv_data[i + 1]
        field = adv_data[i + 2:i + 1 + length]

        if type_ == 0xFF and len(field) >= 3:

            mac = bytes(addr)
            payload = field[2:]   # skip manufacturer ID
            result = decode_ruuvi(payload)

            if result:
                seq = result["measurement_sequence"]

                if mac not in last_sequence or seq != last_sequence[mac]:
                    latest_measurements[mac] = result
                    last_sequence[mac] = seq

        # Move to the next advertisement field
        i += length + 1


# Connect WiFi and MQTT at beginning
ensure_wifi()
ensure_mqtt()

ble.irq(irq)

# Start scanning
ble.gap_scan(0, 30000, 30000)


while True:
    
    now = time.ticks_ms()
    
    # Publish every publish interval
    if time.ticks_diff(now, last_publish) > PUBLISH_INTERVAL:
        last_publish = now

        for mac, data in latest_measurements.items():
            tag = RUUVI_TAGS.get(mac)
            send_mqtt(tag, data)

        latest_measurements.clear()
    
    # Periodic network check
    if time.ticks_diff(now, last_net_check) > NET_CHECK_INTERVAL:
        last_net_check = now
        ensure_wifi()
        ensure_mqtt()

    # Periodic BLE scan restart for reliability
    if time.ticks_diff(now, last_scan_restart) > SCAN_RESTART_INTERVAL:
        last_scan_restart = now

        try:
            ble.gap_scan(0, 30000, 30000)
        except:
            print("Restarting BLE")
            ble.active(False)
            ble.active(True)
            ble.irq(irq)
            ble.gap_scan(0, 30000, 30000)

    time.sleep(0.2)