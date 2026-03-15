# Pico RuuviTag MQTT Gateway

A lightweight **Bluetooth → MQTT gateway** for RuuviTag sensors using a **Raspberry Pi Pico W / Pico 2 W running MicroPython**.

The gateway listens for Bluetooth advertisements from RuuviTags, decodes the **Data Format 5 (RAWv2)** payload, and publishes the measurements to an MQTT broker.

## Features

- Supports **multiple RuuviTags**
- Decodes **RuuviTag Data Format 5 (RAWv2)**
- Publishes sensor data via **MQTT**
- Automatic **WiFi reconnect**
- Automatic **MQTT reconnect**
- Prevents duplicate measurement publishing using the Ruuvi **measurement sequence**
- Stable long-running BLE scanning with automatic scan restart
- Configurable MQTT publishing interval

---

# Hardware

Required:

- Raspberry Pi **Pico W** or **Pico 2 W**
- One or more **RuuviTag sensors**

---

# Firmware

Install the right **MicroPython** for your board:

https://micropython.org/download/

Upload `main.py` to the board.

---

# Configuration

Edit the following section in `main.py`.

### WiFi

```python
WIFI_SSID = "YOUR_SSID"
WIFI_PASSWORD = "YOUR_PASSWORD"
```
> ⚠️ The Pico W & 2 W only support **2.4 GHz WiFi**.  
> They can't connect to **5 GHz networks**.

### MQTT Broker

```python
MQTT_BROKER = "broker.mqttdashboard.com"
MQTT_PORT = 1883
MQTT_CLIENT_ID = "pico2w_gateway"
MQTT_RUUVI_TOPIC_BASE = "ruuvitag"
```

### RuuviTag devices

Add your RuuviTag MAC addresses and tags:

```python
RUUVI_TAGS = {
    b'\xAB\xBB\xCC\xDD\xEE\xFF': "house",
    b'\xAA\xBB\xCC\xDD\xEE\xFF': "garage"
}
```
You can find your RuuviTag MAC address from the Ruuvi Station.

MAC addresses must be in **bytes format**.

Example:

```
AA:BB:CC:DD:EE:FF → b'\xAA\xBB\xCC\xDD\xEE\xFF'
```

---

# MQTT Topics

Each tag publishes to:

```
ruuvitag/<tag>
```

Example:

```
ruuvitag/house
ruuvitag/garage
```

Example message:

```json
{
  "temperature": 20.75,
  "humidity": 36.06,
  "pressure": 994.32,
  "acceleration": 1056.38,
  "acceleration_x": 28,
  "acceleration_y": 4,
  "acceleration_z": 1056,
  "battery": 3192,
  "tx_power": 4,
  "movement_counter": 1,
  "measurement_sequence": 103
}
```

---

# How it works

1. Pico continuously scans for BLE advertisements
2. RuuviTag broadcasts sensor data every second
3. Gateway decodes the **Data Format 5 payload**
4. Measurements are buffered
5. Data is periodically published to MQTT

The system prevents duplicate packets using the **Ruuvi measurement sequence number**.

---

# Reliability features

The gateway includes several mechanisms to improve stability:

- WiFi connection monitoring
- MQTT reconnection
- BLE scan restart every 60 seconds
- duplicate packet filtering
- network failure recovery

These allow the gateway to run continuously for long periods.

---

# Example Use Cases

- Home automation
- Environmental monitoring
- Home Assistant integration

---


# License

MIT License
