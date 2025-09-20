# -*- coding: utf-8 -*-
"""
ReMeDi Nova Spirometer Calibration UI - Complete Corrected Version
Created on Mon Sep 15 12:44:43 2025
@author: Tejaswini
"""
import streamlit as st
import re
import asyncio
import sys
from bleak import BleakScanner, BleakClient
import numpy as np
import matplotlib.pyplot as plt
from calibration_check import run_calibration
from calibration_check import coeffs as default_coeffs
import subprocess
import os
import time
import pandas as pd
import json
from pathlib import Path
from db import add_device, get_device, update_device_coeffs, list_devices, list_calibrations, revert_to_last_success, get_last_successful_coeffs
from recalibration import generate_coefficients
import io
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
from bleak.backends.characteristic import BleakGATTCharacteristic
import threading
from threading import Event
import base64
from PIL import Image

# Page Configuration
st.set_page_config(
    page_title="ReMeDi Nova Spirometer Calibration",
    page_icon="🫁",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ✅ COMPLETE SESSION STATE INITIALIZATION - FIXES AttributeError
if 'connection_status' not in st.session_state:
    st.session_state.connection_status = "No device connected"
if 'device_connected' not in st.session_state:
    st.session_state.device_connected = False
if 'device_name' not in st.session_state:
    st.session_state.device_name = None
if 'ble_client' not in st.session_state:
    st.session_state.ble_client = None
if 'bluetooth_devices' not in st.session_state:
    st.session_state.bluetooth_devices = []
if 'btclient' not in st.session_state:
    st.session_state.btclient = None
if 'connected_device' not in st.session_state:
    st.session_state.connected_device = None
if 'samples' not in st.session_state:
    st.session_state.samples = {}
if 'device_registered' not in st.session_state:
    st.session_state.device_registered = False
if 'calibration_result' not in st.session_state:
    st.session_state.calibration_result = None
if 'coeffs' not in st.session_state:
    st.session_state.coeffs = None
if 'recording' not in st.session_state:
    st.session_state.recording = False
if 'stop_recording' not in st.session_state:
    st.session_state.stop_recording = Event()
if 'auto_reconnect_active' not in st.session_state:
    st.session_state.auto_reconnect_active = False
if 'current_recording' not in st.session_state:
    st.session_state.current_recording = None
if 'device_address' not in st.session_state:
    st.session_state.device_address = None
if "monitoring_active" not in st.session_state:
    st.session_state.monitoring_active = False
if "last_connection_check" not in st.session_state:
    st.session_state.last_connection_check = time.time()
if "reconnection_attempts" not in st.session_state:
    st.session_state.reconnection_attempts = 0
if "auto_connect_attempted" not in st.session_state:
    st.session_state.auto_connect_attempted = False
if 'recalibration_performed' not in st.session_state:
    st.session_state.recalibration_performed = False
if 'original_coefficients' not in st.session_state:
    from calibration_check import coeffs as original_coeffs
    st.session_state.original_coefficients = original_coeffs.copy()
if 'current_coefficients' not in st.session_state:
    st.session_state.current_coefficients = None
if 'app_initialized' not in st.session_state:
    try:
        from calibration_check import coeffs as original_coeffs
        st.session_state.original_coefficients = original_coeffs.copy()
        st.session_state.recalibration_performed = False
        st.session_state.current_coefficients = None
        st.session_state.app_initialized = True
    except ImportError:
        st.error("Could not import original coefficients from calibration_check.py")

# Global constants
client = None
char_uuid = "00003a05-0000-1000-8000-00805f9b34fb"
STOP_NOTIFY_DELAY = 13
DEVICE_NAME = "SMSensor"
sample_types = ["pull_fast", "push_fast", "pull_mid", "push_mid", "pull_slow", "push_slow"]

# Ensure a compatible event loop policy on Windows for Bleak
if sys.platform.startswith('win'):
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    except Exception:
        pass
    # Initialize a persistent loop once on startup (used by run_async wrappers)
    if 'persistent_event_loop' not in st.session_state or st.session_state.persistent_event_loop is None:
        st.session_state.persistent_event_loop = asyncio.new_event_loop()

# Logo and header functions
def get_base64_of_logo(logo_path):
    try:
        with open(logo_path, "rb") as f:
            data = f.read()
        mime = "image/jpeg" if str(logo_path).lower().endswith((".jpg", ".jpeg")) else "image/png"
        return base64.b64encode(data).decode(), mime
    except FileNotFoundError:
        # Fallback: try loading from app directory
        try:
            fallback = Path(__file__).parent / "neurosynaptic-logo.jpg"
            with open(fallback, "rb") as f:
                data = f.read()
            return base64.b64encode(data).decode(), "image/jpeg"
        except Exception:
            return None, None

def create_header():
    try:
        logo_base64, logo_mime = get_base64_of_logo(r"d:\Users\Tejaswini\Desktop\neurosyn\calibration\Calibration app\neurosynaptic-logo.jpg")
        if logo_base64:
            st.markdown(f"""
            <div class="main-header">
                <div class="logo-container">
                    <img src="data:{logo_mime};base64,{logo_base64}" width="60" height="60" alt="ReMeDi Logo">
                </div>
                <h1 class="app-title">ReMeDi Nova Spirometer Calibration</h1>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown("""
            <div class="main-header">
                <h1 class="app-title">ReMeDi Nova Spirometer Calibration</h1>
            </div>
            """, unsafe_allow_html=True)
    except Exception:
        st.markdown("""
        <div class="main-header">
            <h1 class="app-title">ReMeDi Nova Spirometer Calibration</h1>
        </div>
        """, unsafe_allow_html=True)

# Complete CSS styling with all button styles
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,100..1000;1,9..40,100..1000&display=swap');

/* Global font application */
*, .stApp, .stApp * {
    font-family: 'DM Sans', sans-serif !important;
}

.stApp {
    background-color: white;
}

/* Hide streamlit elements */
.stDeployButton {display:none;}
footer {visibility: hidden;}
.stApp > header {visibility: hidden;}

/* Make text elements black, but exclude buttons */
.stApp p, .stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5, .stApp h6, 
.stApp label, .stApp div:not([data-testid="stButton"]) {
    color: black !important;
}

/* Main header */
.main-header {
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 1rem;
    background: white;
    border-bottom: 2px solid #e0e0e0;
    margin-bottom: 2rem;
}

.app-title {
    font-size: 2.5rem;
    font-weight: bold;
    color: black !important;
    margin: 0;
}

.logo-container {
    display: flex !important;
    align-items: center;
    justify-content: center;
    margin-right: 1rem;
}

.logo-container img {
    filter: none !important;
}

/* Bluetooth section */
.bluetooth-section {
    text-align: center;
    margin: 3rem 0;
    padding: 2rem;
    background-color: #f8f9fa;
    border-radius: 10px;
}

.bluetooth-title {
    font-size: 1.5rem;
    font-weight: bold;
    margin-bottom: 0.5rem;
    color: black;
}

.status-text {
    font-size: 1.1rem;
    color: black;
    margin: 0.5rem 0;
}

/* Force center alignment with higher specificity */
div[data-testid="column"] .connect-button,
div[data-testid="column"] .disconnect-button {
    display: flex !important;
    justify-content: center !important;
    align-items: center !important;
    width: 100% !important;
    margin: 20px 0 !important;
    text-align: center !important;
}

.connect-button button,
.disconnect-button button {
    background-color: #70a1ff !important;
    color: black !important;
    border: none !important;
    border-radius: 5px !important;
    font-weight: bold !important;
    padding: 0.75rem 2rem !important;
    font-size: 1rem !important;
    width: 200px !important;
    margin: 0 auto !important;
    display: block !important;
}

.disconnect-button button {
    background-color: #ff6b6b !important;
}


/* Red record buttons */
.record-button button {
    background-color: #ff6b6b !important;
    color: black !important;
    border: none !important;
    border-radius: 5px !important;
    font-weight: bold !important;
    padding: 0.5rem 1.5rem !important;
    font-size: 1rem !important;
    width: 120px !important;
}

/* Connection indicator */
.connection-indicator {
    display: inline-block;
    width: 12px;
    height: 12px;
    border-radius: 50%;
    margin-right: 8px;
}

.connected { background-color: #28a745; }
.disconnected { background-color: #dc3545; }

/* RED BUTTONS (Record) */
.red-button button {
    background-color: #dc3545 !important;
    color: white !important;
    border: none !important;
    border-radius: 5px !important;
    font-weight: bold !important;
}

.red-button button:hover {
    background-color: #c82333 !important;
    color: white !important;
}

/* BLUE BUTTONS (Bluetooth) */
.blue-button button {
    background-color: #007bff !important;
    color: white !important;
    border: none !important;
    border-radius: 5px !important;
    font-weight: bold !important;
}

.blue-button button:hover {
    background-color: #0056b3 !important;
    color: white !important;
}

/* GREEN BUTTONS (Calibration) */
.green-button button {
    background-color: #28a745 !important;
    color: white !important;
    border: none !important;
    border-radius: 5px !important;
    font-weight: bold !important;
}

.green-button button:hover {
    background-color: #218838 !important;
    color: white !important;
}

/* Default Streamlit buttons */
div[data-testid="stButton"] > button {
    background-color: #6c757d !important;
    color: white !important;
    border: none !important;
    border-radius: 8px !important;
    font-weight: bold !important;
    padding: 0.5rem 1rem !important;
}

div[data-testid="stButton"] > button:hover {
    background-color: #5a6268 !important;
    color: white !important;
}

/* Force ALL button text to be white */
div[data-testid="stButton"] > button,
div[data-testid="stButton"] > button * {
    color: white !important;
}

/* Center connect/disconnect buttons */
.connect-container div[data-testid="stButton"] {
    display: flex !important;
    justify-content: center !important;
}

.connect-container div[data-testid="stButton"] > button {
    width: 220px !important;  /* fixed width for uniform look */
    font-weight: bold !important;
}

</style>
""", unsafe_allow_html=True)

# Helper Functions for Colored Buttons
def default_button(label, key=None):
    st.markdown('<div class="default-button">', unsafe_allow_html=True)
    result = st.button(label, key=key)
    st.markdown('</div>', unsafe_allow_html=True)
    return result

def red_button(label, key=None):
    st.markdown('<div class="red-button">', unsafe_allow_html=True)
    result = st.button(label, key=key)
    st.markdown('</div>', unsafe_allow_html=True)
    return result

def blue_button(label, key=None):
    st.markdown('<div class="blue-button">', unsafe_allow_html=True)
    result = st.button(label, key=key)
    st.markdown('</div>', unsafe_allow_html=True)
    return result

def green_button(label, key=None):
    st.markdown('<div class="green-button">', unsafe_allow_html=True)
    result = st.button(label, key=key)
    st.markdown('</div>', unsafe_allow_html=True)
    return result

# Async utility functions
def run_asynccoro(coro):
    """Run an async coroutine in a synchronous context (Streamlit safe)."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)

def run_async(coro):
    """Run async coroutine in a new event loop."""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(coro)
        return result
    finally:
        loop.close()

# Bluetooth Functions - All consolidated to avoid duplicates
async def scan_bluetooth():
    """Scan for available Bluetooth devices."""
    devices = await BleakScanner.discover(timeout=10.0)
    return devices

async def connect_device(address, timeout: float = 10.0):
    global client
    client = BleakClient(address)
    await client.connect(timeout=timeout)
    
    if not client.is_connected:
        raise RuntimeError("Connected attempt reported success but client is not connected")    
    return client

async def scan_and_connect_smsensor():
    """Scan for and connect to SMSensor device with autoconnect"""
    try:
        st.session_state.connection_status = "Scanning for devices..."
        devices = await BleakScanner.discover(timeout=10.0)
        
        # Look for SMSensor device
        target_device = None
        for device in devices:
            print(f"Found device: {device.name} - {device.address}")
            if device.name and ("SMSensor" in device.name):
                target_device = device
                break
        
        if target_device:
            st.session_state.connection_status = f"Connecting to {target_device.name}..."
            client = BleakClient(target_device.address)
            
            if await client.connect():
                st.session_state.device_connected = True
                st.session_state.device_name = target_device.name
                st.session_state.ble_client = client
                st.session_state.btclient = client  # For compatibility
                st.session_state.connected_device = f"{target_device.name} - {target_device.address}"
                st.session_state.device_address = target_device.address
                st.session_state.connection_status = f"Connected to {target_device.name}"
                return client
            else:
                st.session_state.connection_status = "Connection failed"
                return None
        else:
            st.session_state.connection_status = "No SMSensor device found"
            return None
            
    except Exception as e:
        st.session_state.connection_status = f"Error: {str(e)}"
        return None

async def disconnect_smsensor():
    """Disconnect from SMSensor device"""
    try:
        if st.session_state.ble_client and st.session_state.ble_client.is_connected:
            await st.session_state.ble_client.disconnect()
        st.session_state.device_connected = False
        st.session_state.device_name = None
        st.session_state.ble_client = None
        st.session_state.btclient = None
        st.session_state.connected_device = None
        st.session_state.connection_status = "Disconnected"
    except Exception as e:
        st.session_state.connection_status = f"Disconnect error: {str(e)}"

def monitor_smsensor_connection():
    """Monitor SMSensor connection status in background"""
    while st.session_state.device_connected and st.session_state.ble_client:
        try:
            if not st.session_state.ble_client.is_connected:
                st.session_state.device_connected = False
                st.session_state.connection_status = "Device disconnected"
                break
        except:
            st.session_state.device_connected = False
            st.session_state.connection_status = "Connection lost"
            break
        time.sleep(2)

async def autoconnect_to_smsensor():
    """Enhanced auto-connect that preserves existing samples"""
    try:
        print("Auto-scanning for SMSensor devices...")
        devices = await BleakScanner.discover(timeout=8.0)
        print('devices', devices)
        
        smsensor_device = None
        for device in devices:
            device_name = device.name or "Unknown"
            print(f"Found device: {device_name} - {device.address}")
            
            if "SMSensor" in device_name or "SM" in device_name:
                smsensor_device = device
                print(f"SMSensor found: {device_name}")
                break
        
        if smsensor_device is None:
            print("No SMSensor device found during auto-scan")
            return None
        
        print(f"Auto-connecting to {smsensor_device.name}...")
        client = await connect_device(smsensor_device.address, timeout=15.0)
        print("check", client)
        
        if client and client.is_connected:
            # Force service discovery to ensure characteristics are available
            try:
                services = await client.get_services()
                print(f"Services discovered: {len(services)} services")
                # Verify our characteristic exists
                char_found = False
                for service in services:
                    for char in service.characteristics:
                        if str(char.uuid) == char_uuid:
                            char_found = True
                            print(f"Verified characteristic {char_uuid} available")
                            break
                if not char_found:
                    print(f"Warning: Characteristic {char_uuid} not found after connection")
            except Exception as e:
                print(f"Service discovery warning: {e}")
            
            st.session_state.btclient = client
            st.session_state.ble_client = client
            st.session_state.connected_device = f"{smsensor_device.name} - {smsensor_device.address}"
            st.session_state.device_address = smsensor_device.address
            st.session_state.monitoring_active = True
            st.session_state.device_connected = True
            st.session_state.device_name = smsensor_device.name
            st.session_state.connection_status = f"Connected to {smsensor_device.name}"
            
            print(f"Successfully auto-connected to SMSensor: {smsensor_device.name}")
            print(f"Preserved {len(st.session_state.samples)} existing samples")
            return client
        else:
            print("Failed to establish connection to SMSensor")
            return None
            
    except Exception as e:
        print(f"Auto-connect error: {str(e)}")
        return None

async def record_sample(sample_type, device_id, client):
    """Record a sample from the Bluetooth device and save to log file."""
    print(f"Starting sample recording: {sample_type} for device: {device_id}")

    # Validate connection before starting
    if not client or not client.is_connected:
        print("❌ Client not connected - attempting reconnection")
        return {'error': 'Device not connected'}

    print(f"✅ Device connection confirmed for {sample_type} recording")
    recorded_data = []
    data_received = False
    
    def notification_handler(characteristic: BleakGATTCharacteristic, data: bytearray):
        """Handle incoming Bluetooth notifications and collect data."""
        nonlocal data_received
        timestamp = time.time()
        hex_data = ":".join(hex(b)[2:].upper().zfill(2) for b in data)
        recorded_data.append(f"[{hex_data}]")
        data_received = True
        print(f"Received: {hex_data}")
    
    try:
        # Wait before starting
        await asyncio.sleep(1)
        
        # Ensure services are discovered and available
        services = await client.get_services()
        print(f"Available services: {[str(s.uuid) for s in services]}")
        
        # Find the characteristic in available services
        char_found = False
        for service in services:
            for char in service.characteristics:
                if str(char.uuid) == char_uuid:
                    char_found = True
                    print(f"Found characteristic {char_uuid} in service {service.uuid}")
                    break
            if char_found:
                break
        
        if not char_found:
            raise RuntimeError(f"Characteristic {char_uuid} not found in any service")
        
        # Start notifications
        await client.start_notify(char_uuid, notification_handler)
        print("Notifications started - recording...")
        
        # Record with proper duration and monitoring
        recording_duration = 13
        check_interval = 1
        elapsed = 0
        
        while elapsed < recording_duration:
            await asyncio.sleep(check_interval)
            elapsed += check_interval

            # Show progress every second
            if elapsed % 1 == 0:
                if data_received and len(recorded_data) > 0:
                    print(f"Recording progress: {len(recorded_data)} samples after {elapsed}s")
                else:
                    print(f"Recording time: {elapsed}s - waiting for data...")

            if not client.is_connected:
                print("Device disconnected during recording")
                break
        
        # Stop notifications properly but keep connection alive
        try:
            await client.stop_notify(char_uuid)
            await asyncio.sleep(0.5)
            print("✅ Notifications stopped, connection kept alive")
        except Exception as stop_error:
            print(f"⚠️ Error stopping notifications: {stop_error}")
        
        print(f"Recording complete: {len(recorded_data)} samples collected")

        if len(recorded_data) == 0:
            print("⚠️ Warning: No data received during recording - check device connection")
            return {'error': 'No data received from device'}

        # Save data to log file in app directory
        logs_dir = Path(__file__).parent / "logs"
        print(f"Creating log directory: {logs_dir}")
        logs_dir.mkdir(parents=True, exist_ok=True)

        timestamp = int(time.time())
        log_filename = f"{device_id}_{sample_type}_{timestamp}.log"
        log_filepath = logs_dir / log_filename

        print(f"Attempting to save log file: {log_filepath}")
        try:
            with open(log_filepath, 'w') as f:
                for line in recorded_data:
                    f.write(f"{line}\n")
            print(f"✅ File saved successfully: {log_filepath}")
            print(f"✅ File exists: {log_filepath.exists()}")
            print(f"✅ File size: {log_filepath.stat().st_size} bytes")
        except Exception as e:
            print(f"❌ Failed to save file to {log_filepath}: {e}")
            # Try fallback to current directory
            log_filepath = Path(f"{device_id}_{sample_type}_{timestamp}.log")
            print(f"Trying fallback location: {log_filepath.absolute()}")
            try:
                with open(log_filepath, 'w') as f:
                    for line in recorded_data:
                        f.write(f"{line}\n")
                print(f"✅ File saved to fallback location: {log_filepath.absolute()}")
                print(f"✅ Fallback file size: {log_filepath.stat().st_size} bytes")
            except Exception as fallback_e:
                print(f"❌ Fallback save also failed: {fallback_e}")
                return {'error': f'File saving failed: {str(e)}, fallback: {str(fallback_e)}'}
        
        # Parse the recorded data to extract pressures
        pressures_pa = []
        for line in recorded_data:
            start_pos = line.find('[')
            end_pos = line.find(']')
            if start_pos != -1 and end_pos != -1:
                frame_data = line[start_pos + 1:end_pos]
                frame_data_split = frame_data.split(":")
                try:
                    ADCvalues_array = [int(x, 16) for x in frame_data_split]
                    
                    OS_dig = 0.5 * (2**24)
                    FSS_inH2O = 120
                    
                    for i in range(7, 107, 5):
                        if i + 4 < len(ADCvalues_array):
                            pos3 = ADCvalues_array[i + 2] & 0xFF
                            pos2 = ADCvalues_array[i + 3] & 0xFF
                            pos1 = ADCvalues_array[i + 4] & 0xFF
                            pos3 = pos3 << 16
                            pos2 = pos2 << 8
                            decimal_count = pos3 | pos2 | pos1
                            pressure_inH2O = 1.25 * ((decimal_count - OS_dig) / (2**24)) * FSS_inH2O
                            pressure_pa = pressure_inH2O * 249.089
                            pressures_pa.append(pressure_pa)
                except ValueError:
                    continue
        
        return {
            "time": list(range(len(pressures_pa))),
            "pressure": pressures_pa,
            "file_path": str(log_filepath),
            "sample_count": len(recorded_data),
            "duration": 30
        }
        
    except Exception as e:
        print(f"Recording error: {str(e)}")
        try:
            await client.stop_notify(char_uuid)
            print("🔧 Cleaned up notifications after error")
        except Exception as cleanup_error:
            print(f"⚠️ Cleanup error: {cleanup_error}")

        # Check if connection is still alive
        try:
            if client.is_connected:
                print("✅ Connection still alive after error")
            else:
                print("❌ Connection lost after error")
        except:
            print("❌ Cannot check connection status")

        return {'error': str(e)}

def read_log_file(file_path):
    """Read recorded file and extract time and pressure data."""
    try:
        suffix = file_path.suffix.lower()

        # Try reading as CSV regardless of extension if possible
        try:
            df = pd.read_csv(file_path)
            if df.shape[1] >= 2:
                cols = list(df.columns)
                lower_cols = [str(c).strip().lower() for c in cols]
                time_candidates = ["time", "timestamp", "t", "seconds", "sec"]
                pressure_candidates = ["pressure", "p", "value", "pa"]
                time_col = next((cols[i] for i, lc in enumerate(lower_cols) if lc in time_candidates), cols[0])
                pressure_col = next((cols[i] for i, lc in enumerate(lower_cols) if lc in pressure_candidates and cols[i] != time_col), None)
                if pressure_col is None:
                    fallback_cols = [c for c in cols if c != time_col]
                    if not fallback_cols:
                        raise ValueError("CSV needs at least 2 columns (time, pressure)")
                    pressure_col = fallback_cols[0]
                dt_series = pd.to_numeric(df[time_col], errors='coerce')
                pr_series = pd.to_numeric(df[pressure_col], errors='coerce')
                valid = (~dt_series.isna()) & (~pr_series.isna())
                dt_list = dt_series[valid].tolist()
                pr_list = pr_series[valid].tolist()
                if len(pr_list) == 0:
                    raise ValueError("No numeric pressure data found in uploaded file")
                return {"time": dt_list, "pressure": pr_list}
        except Exception:
            pass
        
        # Fallback for plain text .log format
        if suffix == '.log':
            with open(file_path, 'r') as f:
                lines = f.readlines()
            
            time_data = []
            pressure_data = []
            
            for line in lines:
                if line.strip() and not line.startswith('#'):
                    parts = line.strip().split()
                    if len(parts) >= 2:
                        try:
                            time_data.append(float(parts[0]))
                            pressure_data.append(float(parts[1]))
                        except ValueError:
                            continue
            
            return {
                "time": time_data,
                "pressure": pressure_data
            }
            
        raise RuntimeError("Unsupported file format for reading recorded data")
    except Exception as e:
        raise RuntimeError(f"Failed to read log file {file_path}: {str(e)}")

# Create header
create_header()

# NEW UI DESIGN - Bluetooth Device Discovery Section
st.markdown("""
<div class="bluetooth-section">
    <h2 class="bluetooth-title">Bluetooth Device Discovery</h2>
    <p class="status-text">Autoconnection enabled</p>
</div>
""", unsafe_allow_html=True)

# Dynamic status display - NOW WORKS because session state is initialized
current_status = st.session_state.connection_status
status_color = "connected" if st.session_state.device_connected else "disconnected"

# st.markdown(f"""
# <div style="text-align: center;">
#     <p class="status-text">
#         <span class="connection-indicator {status_color}"></span>
#         Status: {current_status}
#     </p>
# </div>
# """, unsafe_allow_html=True)

# # Connect/Disconnect button with dynamic styling
# col1, col2, col3 = st.columns([1, 1, 1])
# with col2:
#     if st.session_state.device_connected:
#         st.markdown('<div class="disconnect-button">', unsafe_allow_html=True)
#         if st.button("Disconnect from Remedi", key="disconnect_btn"):
#             with st.spinner("Disconnecting..."):
#                 run_asynccoro(disconnect_smsensor())
#             st.rerun()
#     else:
#         st.markdown('<div class="connect-button">', unsafe_allow_html=True)
#         if st.button("Connect to Remedi", key="connect_btn"):
#             with st.spinner("Connecting..."):
#                 client = run_asynccoro(scan_and_connect_smsensor())
#                 if client and st.session_state.device_connected:
#                     # Start background monitoring
#                     monitor_thread = threading.Thread(target=monitor_smsensor_connection)
#                     monitor_thread.daemon = True
#                     monitor_thread.start()
#             st.rerun()
#     st.markdown('</div>', unsafe_allow_html=True)

# Center Connect/Disconnect button using 5 columns (middle column)
c1, c2, c3, c4, c5 = st.columns([0.35,0.5,1,1.5,1])
with c4:
    if st.session_state.device_connected:
        if st.button("Disconnect from Remedi Nova", key="disconnect_btn"):
            with st.spinner("Disconnecting..."):
                run_asynccoro(disconnect_smsensor())
            st.rerun()
    else:
        if st.button("Connect to Remedi Nova", key="connect_btn"):
            with st.spinner("Connecting..."):
                client = run_asynccoro(scan_and_connect_smsensor())
                if client and st.session_state.device_connected:
                    monitor_thread = threading.Thread(target=monitor_smsensor_connection)
                    monitor_thread.daemon = True
                    monitor_thread.start()
            st.rerun()


# Auto-connect logic - only run in Streamlit context
def perform_auto_connect():
    """Perform auto-connect only when Streamlit is properly initialized"""
    try:
        # Check if we're in a proper Streamlit context and runtime is active
        if hasattr(st, 'session_state') and hasattr(st.runtime, 'get_instance') and st.runtime.get_instance() is not None:
            if not st.session_state.auto_connect_attempted:
                st.session_state.auto_connect_attempted = True
                if st.session_state.btclient is None:
                    with st.spinner("🔍 Auto-scanning for SMSensor device..."):
                        try:
                            client = run_asynccoro(autoconnect_to_smsensor())
                            if client:
                                st.session_state.btclient = client
                                st.success("✅ Automatically connected to SMSensor!")
                                st.snow()
                            else:
                                st.warning("⚠️ SMSensor not found. Please use manual scan below.")
                        except Exception as e:
                            st.warning(f"Auto-connect failed. Please use manual scan below.")

            # Fallback auto-connect for disconnected devices
            if st.session_state.btclient is None or not st.session_state.btclient.is_connected:
                try:
                    with st.spinner("🔍 Looking for SMSensor..."):
                        client = run_asynccoro(autoconnect_to_smsensor())
                        if client:
                            st.session_state.btclient = client
                            st.success("✅ SMSensor connected automatically!")
                except Exception as e:
                    st.info("ℹ️ SMSensor not found. Manual connection available below.")
    except Exception as e:
        # Silently ignore if not in Streamlit context
        pass

# Only perform auto-connect if in proper Streamlit context
def safe_auto_connect():
    """Safely attempt auto-connect only when Streamlit runtime is available"""
    try:
        # Check if Streamlit runtime is active
        from streamlit.runtime import get_instance
        if get_instance() is not None:
            perform_auto_connect()
    except:
        # Skip auto-connect if Streamlit runtime isn't available
        pass

# Call safe auto-connect
safe_auto_connect()

# Show connection status
if st.session_state.btclient and st.session_state.btclient.is_connected:
    st.success(f"🟢 Connected to {st.session_state.connected_device}")
    
    # Show preserved samples count
    if st.session_state.samples:
        st.info(f"📊 {len(st.session_state.samples)} samples preserved from previous sessions")
else:
    st.info("🔴 No device connected")

# Manual Bluetooth scanning section
st.subheader("📡 Manual Bluetooth Device Discovery")

if st.button("🔍 Scan for Bluetooth Devices"):
    with st.spinner("Scanning for devices..."):
        try:
            devices = run_asynccoro(scan_bluetooth())
            st.session_state.bluetooth_devices = devices
            st.success(f"Found {len(devices)} devices")
        except Exception as e:
            st.error(f"Scanning failed: {e}")

# Device Selection and Connection
if st.session_state.bluetooth_devices:
    st.subheader("🔗 Device Connection")
    device_options = {}
    
    for d in st.session_state.bluetooth_devices:
        name = d.name or "Unknown Device"
        address = d.address
        
        if "SMSensor" in name:
            device_key = f"🎯 {name} (SMSensor) - {address}"
        else:
            device_key = f"{name} - {address}"
            
        device_options[device_key] = address
    
    selected_device = st.selectbox(
        "Select Bluetooth Device", 
        list(device_options.keys()),
        help="🎯 indicates SMSensor devices"
    )
    selected_address = device_options[selected_device]
    
    if "SMSensor" in selected_device:
        st.info("🎯 SMSensor device selected - ready for spirometer calibration!")
    
    if st.button("Connect to Device"):
        try:
            with st.spinner("Connecting..."):
                client = run_asynccoro(connect_device(selected_address))
                
                # Ensure services are discovered after manual connection
                if client and client.is_connected:
                    try:
                        services = run_asynccoro(client.get_services())
                        print(f"Manual connection: {len(services)} services discovered")
                    except Exception as e:
                        print(f"Manual connection service discovery warning: {e}")
                
                st.session_state.btclient = client
                st.session_state.ble_client = client
                st.session_state.connected_device = selected_device
                st.session_state.device_connected = True
                st.session_state.device_name = selected_device.split(' - ')[0]
                st.session_state.connection_status = f"Connected to {st.session_state.device_name}"
            st.success(f"✅ Connected to {selected_device}")
        except Exception as e:
            st.error(f"❌ Connection failed: {e}")

# NEW RECORD SAMPLES DESIGN
st.markdown("""
<div style="margin-top: 3rem;">
    <h2 style="font-size: 1.5rem; font-weight: bold; color: black; margin-bottom: 2rem; text-align: left;">Record Samples</h2>
</div>
""", unsafe_allow_html=True)

# First Row
col1, col2, col3 = st.columns(3)

with col1:
    st.markdown('<div style="text-align: center;"><p style="font-size: 1.1rem; font-weight: bold; color: black; margin-bottom: 0.5rem;">Pull fast</p>', unsafe_allow_html=True)
    st.markdown('<div class="record-button">', unsafe_allow_html=True)
    pull_fast = st.button("Record", key="pull_fast")
    st.markdown('</div>', unsafe_allow_html=True)
    st.markdown('<p style="font-size: 0.85rem; color: #666; margin-top: 0.5rem; line-height: 1.3;">Graphs, sample saved, stats<br>(of the above sample only)</p></div>', unsafe_allow_html=True)

with col2:
    st.markdown('<div style="text-align: center;"><p style="font-size: 1.1rem; font-weight: bold; color: black; margin-bottom: 0.5rem;">Push fast</p>', unsafe_allow_html=True)
    st.markdown('<div class="record-button">', unsafe_allow_html=True)
    push_fast = st.button("Record", key="push_fast")
    st.markdown('</div>', unsafe_allow_html=True)
    st.markdown('<p style="font-size: 0.85rem; color: #666; margin-top: 0.5rem; line-height: 1.3;">Graphs, sample saved, stats<br>(of the above sample only)</p></div>', unsafe_allow_html=True)

with col3:
    st.markdown('<div style="text-align: center;"><p style="font-size: 1.1rem; font-weight: bold; color: black; margin-bottom: 0.5rem;">Pull Mid</p>', unsafe_allow_html=True)
    st.markdown('<div class="record-button">', unsafe_allow_html=True)
    pull_mid = st.button("Record", key="pull_mid")
    st.markdown('</div>', unsafe_allow_html=True)
    st.markdown('<p style="font-size: 0.85rem; color: #666; margin-top: 0.5rem; line-height: 1.3;">Graphs, sample saved, stats<br>(of the above sample only)</p></div>', unsafe_allow_html=True)

# Second Row
col1, col2, col3 = st.columns(3)

with col1:
    st.markdown('<div style="text-align: center;"><p style="font-size: 1.1rem; font-weight: bold; color: black; margin-bottom: 0.5rem;">Push mid</p>', unsafe_allow_html=True)
    st.markdown('<div class="record-button">', unsafe_allow_html=True)
    push_mid = st.button("Record", key="push_mid")
    st.markdown('</div>', unsafe_allow_html=True)
    st.markdown('<p style="font-size: 0.85rem; color: #666; margin-top: 0.5rem; line-height: 1.3;">Graphs, sample saved, stats<br>(of the above sample only)</p></div>', unsafe_allow_html=True)

with col2:
    st.markdown('<div style="text-align: center;"><p style="font-size: 1.1rem; font-weight: bold; color: black; margin-bottom: 0.5rem;">Pull slow</p>', unsafe_allow_html=True)
    st.markdown('<div class="record-button">', unsafe_allow_html=True)
    pull_slow = st.button("Record", key="pull_slow")
    st.markdown('</div>', unsafe_allow_html=True)
    st.markdown('<p style="font-size: 0.85rem; color: #666; margin-top: 0.5rem; line-height: 1.3;">Graphs, sample saved, stats<br>(of the above sample only)</p></div>', unsafe_allow_html=True)

with col3:
    st.markdown('<div style="text-align: center;"><p style="font-size: 1.1rem; font-weight: bold; color: black; margin-bottom: 0.5rem;">Push slow</p>', unsafe_allow_html=True)
    st.markdown('<div class="record-button">', unsafe_allow_html=True)
    push_slow = st.button("Record", key="push_slow")
    st.markdown('</div>', unsafe_allow_html=True)
    st.markdown('<p style="font-size: 0.85rem; color: #666; margin-top: 0.5rem; line-height: 1.3;">Graphs, sample saved, stats<br>(of the above sample only)</p></div>', unsafe_allow_html=True)

# Button click handlers with connection check
if pull_fast:
    if st.session_state.device_connected and st.session_state.ble_client:
        with st.spinner("Recording Pull fast sample..."):
            device_id = st.session_state.get('device_id', 'unknown_device')
            st.session_state.samples['pull_fast'] = run_asynccoro(record_sample('pull_fast', device_id, st.session_state.ble_client))
        st.success("Pull fast sample recorded!")
    else:
        st.error("Please connect to SMSensor device first")

if push_fast:
    if st.session_state.device_connected and st.session_state.ble_client:
        with st.spinner("Recording Push fast sample..."):
            device_id = st.session_state.get('device_id', 'unknown_device')
            st.session_state.samples['push_fast'] = run_asynccoro(record_sample('push_fast', device_id, st.session_state.ble_client))
        st.success("Push fast sample recorded!")
    else:
        st.error("Please connect to SMSensor device first")

if pull_mid:
    if st.session_state.device_connected and st.session_state.ble_client:
        with st.spinner("Recording Pull Mid sample..."):
            device_id = st.session_state.get('device_id', 'unknown_device')
            st.session_state.samples['pull_mid'] = run_asynccoro(record_sample('pull_mid', device_id, st.session_state.ble_client))
        st.success("Pull Mid sample recorded!")
    else:
        st.error("Please connect to SMSensor device first")

if push_mid:
    if st.session_state.device_connected and st.session_state.ble_client:
        with st.spinner("Recording Push mid sample..."):
            device_id = st.session_state.get('device_id', 'unknown_device')
            st.session_state.samples['push_mid'] = run_asynccoro(record_sample('push_mid', device_id, st.session_state.ble_client))
        st.success("Push mid sample recorded!")
    else:
        st.error("Please connect to SMSensor device first")

if pull_slow:
    if st.session_state.device_connected and st.session_state.ble_client:
        with st.spinner("Recording Pull slow sample..."):
            device_id = st.session_state.get('device_id', 'unknown_device')
            st.session_state.samples['pull_slow'] = run_asynccoro(record_sample('pull_slow', device_id, st.session_state.ble_client))
        st.success("Pull slow sample recorded!")
    else:
        st.error("Please connect to SMSensor device first")

if push_slow:
    if st.session_state.device_connected and st.session_state.ble_client:
        with st.spinner("Recording Push slow sample..."):
            device_id = st.session_state.get('device_id', 'unknown_device')
            st.session_state.samples['push_slow'] = run_asynccoro(record_sample('push_slow', device_id, st.session_state.ble_client))
        st.success("Push slow sample recorded!")
    else:
        st.error("Please connect to SMSensor device first")

# Coefficient and calibration management functions
def get_active_coefficients():
    """Return coefficients based on recalibration status"""
    if st.session_state.recalibration_performed and st.session_state.current_coefficients is not None:
        return st.session_state.current_coefficients
    else:
        return st.session_state.original_coefficients

def update_calibration_file_with_coefficients(coeffs_to_use):
    """Update calibration_check.py with specified coefficients"""
    try:
        # Method 1: Try regex method first
        success = updatecalibrationcoeffsfile(coeffs_to_use)
        
        # Method 2: If regex fails, try direct method
        if not success:
            success = updatecalibrationcoeffsfile_direct(coeffs_to_use)
        
        return success
    except Exception as e:
        st.error(f"Failed to update coefficients in file: {e}")
        return False

def update_coefficients_conditionally(new_coeffs=None):
    """Update coefficients based on recalibration status"""
    if new_coeffs is not None:
        # Recalibration was performed
        st.session_state.recalibration_performed = True
        st.session_state.current_coefficients = new_coeffs
        active_coeffs = new_coeffs
        st.success("✅ Using newly calibrated coefficients")
    else:
        # No recalibration, use original
        st.session_state.recalibration_performed = False
        st.session_state.current_coefficients = None
        active_coeffs = st.session_state.original_coefficients
        st.info("ℹ️ Using original coefficients (no recalibration performed)")
    
    # Update the calibration_check.py file with active coefficients
    success = update_calibration_file_with_coefficients(active_coeffs)
    return success, active_coeffs

def check_calibration(samples, device_id):
    """Run calibration analysis using active coefficients"""
    log_folder = Path(__file__).parent / "logs"
    if not os.path.exists(log_folder):
        st.error(f"Log folder does not exist: {log_folder}")
        return False, None, None
    
    try:
        # Get active coefficients instead of importing from calibration_check
        active_coeffs = get_active_coefficients()
        
        # Temporarily update calibration_check.py with active coefficients
        temp_update_success = update_calibration_file_with_coefficients(active_coeffs)
        
        if not temp_update_success:
            st.warning("Could not update calibration file - using file coefficients as-is")
        
        # Run calibration analysis
        df, success, failed = run_calibration(log_folder)
        return success, df, failed
        
    except Exception as e:
        st.error(f"Calibration check failed: {str(e)}")
        return False, None, None

def check_sdk_availability(sdk_jar_path=None):
    """Check if the SDK JAR file is available and Java is installed."""
    try:
        java_result = subprocess.run(["java", "-version"], capture_output=True, text=True)
        if java_result.returncode != 0:
            return False, "Java not installed or not in PATH"
        
        if sdk_jar_path is None:
            sdk_jar_path = r"d:\Users\Tejaswini\Downloads\JettyServer_1.67_SpiroCalibration.jar"
        
        if not Path(sdk_jar_path).exists():
            return False, f"SDK JAR file not found: {sdk_jar_path}"
        
        return True, "SDK available"
        
    except Exception as e:
        return False, f"Error checking SDK: {str(e)}"

# Device Registration UI Section
if st.session_state.btclient and st.session_state.connected_device:
    st.subheader("🔗 Device Registration")
    
    # Check if device is already registered
    if "device_id" in st.session_state and st.session_state.device_id:
        existing_device = get_device(st.session_state.device_id)
        if existing_device:
            st.success(f"✅ Device {st.session_state.device_id} is already registered")
            st.session_state.device_registered = True
        else:
            st.warning(f"Device {st.session_state.device_id} not found in database. Please re-register.")
            st.session_state.device_registered = False
    
    if not st.session_state.get('device_registered', False):
        device_id = st.text_input("Enter Device ID", key="device_id_input")
        
        if st.button("Register Device"):
            if device_id:
                try:
                    # Ensure device exists in DB with empty coefficients initially
                    existing = get_device(device_id)
                    if not existing:
                        add_device(device_id, coeffs=[])
                        st.success(f"✅ New device {device_id} registered successfully!")
                    else:
                        st.info(f"Device {device_id} already exists in database")
                    
                    # Set session state
                    st.session_state.device_registered = True
                    st.session_state.device_id = device_id
                    st.rerun()  # Refresh to show next steps
                except Exception as e:
                    st.error(f"Registration failed: {e}")
            else:
                st.error("Please enter a Device ID")

# Display recorded samples if any exist
if st.session_state.samples:
    completed_samples = len(st.session_state.samples)
    st.subheader("📊 Recorded Samples")
    st.info(f"Completed: {completed_samples}/6 samples")
    
    # Display each sample with its data
    for sample_type, data in st.session_state.samples.items():
        with st.expander(f"{sample_type.replace('_', ' ').title()}", expanded=False):
            if "pressure" in data and data["pressure"]:
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.line_chart({"Pressure (Pa)": data["pressure"]})
                with col2:
                    st.metric("Data Points", len(data["pressure"]))
                    if "file_path" in data:
                        st.text("File Location:")
                        st.code(data["file_path"], language=None)
    
    # Show progress toward calibration
    if completed_samples < 6:
        remaining = 6 - completed_samples
        st.warning(f"{remaining} more sample{'s' if remaining > 1 else ''} needed for calibration check")
    else:
        st.success("All samples completed! Ready for calibration check.")

# Enhanced Calibration Check with Auto-Recalibration
if len(st.session_state.samples) == 6:
    st.subheader("🧪 Calibration Results")
    
    if green_button("✅ Run Calibration Check", key="calibrate_now"):
        with st.spinner("Analyzing calibration data..."):
            device_id = st.session_state.get('device_id', 'unknown_device')
            success, df, failed = check_calibration(st.session_state.samples, device_id)
        
        if df is not None:
            # Display results table
            st.subheader("📊 Calibration Analysis Results")
            st.dataframe(df)
            
            # Show metrics
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Total Tests", len(df))
                st.metric("Passed Tests", len(df) - len(failed) if not failed.empty else len(df))
            with col2:
                st.metric("Failed Tests", len(failed) if not failed.empty else 0)
                avg_error = abs(df["Error (%)"]).mean()
                st.metric("Average Error", f"{avg_error:.2f}%")

        print("checking for success",success)
        
        if success:
            st.success("🎉 **CALIBRATION SUCCESSFUL!**")
            st.info("All volume errors are within ±3% tolerance")
            st.snow()
            
            # Update database with current coefficients as successful
            try:
                from calibration_check import coeffs as current_coeffs
                update_device_coeffs(device_id, current_coeffs, 
                                    samples=st.session_state.get('samples', {}), 
                                    status="success")
                st.info("✅ Coefficients saved to database")
            except Exception as e:
                st.warning(f"Could not save coefficients: {e}")
                
        else:
            st.error("**❌ CALIBRATION FAILED!**")
            st.warning("One or more tests exceeded ±3% error tolerance")
            
            if failed is not None and not failed.empty:
                st.subheader("❌ Failed Tests")
                st.dataframe(failed[["Filename", "Volume (L)", "Error (%)", "Time (s)"]])
            
            # AUTO-RECALIBRATION OPTION
            st.subheader("🔄 Auto-Recalibration")
            col1, col2 = st.columns(2)

            with col1:
                if st.button("🤖 Auto-Recalibrate", type="primary"):
                    try:
                        with st.spinner("Recalibrating coefficients..."):
                            logs_dir = Path(__file__).parent / "logs"
                            device_id = st.session_state.get('device_id', 'unknown_device')
                            
                            # Generate new coefficients
                            new_coeffs = generate_coefficients(str(logs_dir))
                            
                            if new_coeffs is not None and len(new_coeffs) > 0:
                                # Update database first
                                update_device_coeffs(device_id, new_coeffs, 
                                                samples=st.session_state.get("samples", {}), 
                                                status="auto_recalibrated")
                                
                                # Use conditional coefficient update
                                success, active_coeffs = update_coefficients_conditionally(new_coeffs)
                                
                                if success:
                                    st.success("🎉 Auto-recalibration complete!")
                                    st.info("✅ New coefficients generated and saved to database")
                                    st.info("✅ Using newly calibrated coefficients")
                                    st.info("🔄 Click 'Run Calibration Check' again to test with new coefficients")
                                else:
                                    st.warning("⚠️ Database updated but file update failed")
                            else:
                                # No new coefficients generated - use original
                                st.warning("⚠️ Failed to generate new coefficients - using original coefficients")
                                success, active_coeffs = update_coefficients_conditionally(None)
                                
                    except Exception as e:
                        st.error(f"Auto-recalibration failed: {e}")
                        # Fallback to original coefficients on error
                        success, active_coeffs = update_coefficients_conditionally(None)

            with col2:
                if st.button("📋 Use Original Coefficients"):
                    try:
                        # Explicitly use original coefficients
                        success, active_coeffs = update_coefficients_conditionally(None)
                        if success:
                            st.success("✅ Reverted to original coefficients")
                            st.info("🔄 Click 'Run Calibration Check' to test with original coefficients")
                    except Exception as e:
                        st.error(f"Failed to revert to original coefficients: {e}")

# Coefficient Details Section
with st.expander("🔍 Coefficient Details", expanded=False):
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📊 Original Coefficients")
        if st.session_state.original_coefficients is not None:
            for i, coeff in enumerate(st.session_state.original_coefficients):
                st.text(f"[{i}]: {coeff:.8e}")
    
    with col2:
        st.subheader("⚡ Current Active Coefficients")
        active_coeffs = get_active_coefficients()
        for i, coeff in enumerate(active_coeffs):
            st.text(f"[{i}]: {coeff:.8e}")
    
    # Show difference if recalibration was performed
    if st.session_state.recalibration_performed and st.session_state.current_coefficients is not None:
        st.subheader("🔄 Coefficient Changes")
        orig = np.array(st.session_state.original_coefficients)
        new = np.array(st.session_state.current_coefficients)
        diff = new - orig
        
        for i, change in enumerate(diff):
            if abs(change) > 1e-10:  # Only show significant changes
                st.text(f"[{i}]: {change:+.8e}")

# PDF report generation utilities
def generate_device_report(device):
    """Generate detailed PDF report for a single device"""
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    margin = 1 * inch
    y = height - margin
    
    # Title
    #c.setFont("DM-Sans", 16)
    c.drawString(margin, y, f"Calibration Report - Device {device.device_id}")
    y -= 0.4 * inch
    
    # Device info
    #c.setFont("DM-Sans", 12)
    c.drawString(margin, y, f"Device ID: {device.device_id}")
    y -= 0.3 * inch
    c.drawString(margin, y, f"Last Calibration: {device.date_of_calibration}")
    y -= 0.3 * inch
    c.drawString(margin, y, f"Report Generated: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}")
    y -= 0.4 * inch
    
    # Coefficients
    #c.setFont("DM-Sans", 12)
    c.drawString(margin, y, "Current Coefficients:")
    y -= 0.3 * inch
    
    #c.setFont("DM-Sans", 10)
    if device.coefficients:
        coeffs_text = ", ".join([f"{float(v):.8g}" for v in device.coefficients])
        max_chars = 80
        for i in range(0, len(coeffs_text), max_chars):
            line = coeffs_text[i:i+max_chars]
            c.drawString(margin, y, line)
            y -= 0.2 * inch
    else:
        c.drawString(margin, y, "No coefficients available")
        y -= 0.2 * inch
    
    # ✅ Finalize PDF
    c.save()
    pdf_data = buffer.getvalue()
    buffer.close()
    return pdf_data

def generate_all_devices_report(devices):
    """Generate PDF report for all devices"""
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    margin = 1 * inch
    y = height - margin
    
    # Title
    #c.setFont("DM-Sans", 16)
    c.drawString(margin, y, "All Devices Calibration Report")
    y -= 0.4 * inch
    
    #c.setFont("DM-Sans", 12)
    c.drawString(margin, y, f"Report Generated: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}")
    c.drawString(margin, y - 0.2 * inch, f"Total Devices: {len(devices)}")
    y -= 0.6 * inch
    
    # Device summary table
    for device in devices:
        if y < margin + 2 * inch:
            c.showPage()
            y = height - margin
        
        #c.setFont("DM-Sans", 12)
        c.drawString(margin, y, f"Device: {device.device_id}")
        y -= 0.3 * inch
        
        #c.setFont("DM-Sans", 10)
        c.drawString(margin, y, f"Last Calibration: {device.date_of_calibration}")
        y -= 0.2 * inch
        
        # Show coefficient count
        coeff_count = len(device.coefficients) if device.coefficients else 0
        c.drawString(margin, y, f"Coefficients: {coeff_count} values")
        y -= 0.2 * inch
        
        # Show last calibration status
        calibs = list_calibrations(device.device_id)
        if calibs:
            last_status = calibs[0].status
            status_symbol = "✅" if last_status == "success" else "❌" if last_status == "failed" else "🔄"
            c.drawString(margin, y, f"Last Status: {status_symbol} {last_status}")
        else:
            c.drawString(margin, y, "Last Status: No calibrations")
        
        y -= 0.4 * inch
    
    c.save()
    pdf_data = buffer.getvalue()
    buffer.close()
    return pdf_data

def generate_pdf(df, success):
    """Generate simple PDF report"""
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer)
    c.drawString(100, 800, "Calibration Report")
    c.drawString(100, 780, f"Status: {'SUCCESS' if success else 'FAILURE'}")
    y = 750
    for i, row in df.iterrows():
        c.drawString(100, y, f"{row['Push/Pull']} {row['Time(s)']}s: "
                             f"Vol={row['Volume(L)']}L, Error={row['Error(%)']}%")
        y -= 20
    c.save()
    buffer.seek(0)
    return buffer

def updatecalibrationcoeffsfile_direct(new_coeffs):
    """Direct method to update coefficients in calibration_check.py"""
    try:
        calib_file = Path("calibration_check.py")
        if not calib_file.exists():
            st.warning("calibration_check.py not found")
            return False
            
        # Read all lines
        with open(calib_file, 'r') as f:
            lines = f.readlines()
        
        # Find the coeffs line (should be around line 9-10)
        coeffs_line_idx = None
        for i, line in enumerate(lines):
            if line.strip().startswith('coeffs = np.array'):
                coeffs_line_idx = i
                break
        
        if coeffs_line_idx is None:
            st.warning("Could not find coeffs line in calibration_check.py")
            return False
        
        # Create new coefficients line
        coeffs_str = "[" + ", ".join(f"{coeff:.8e}" for coeff in new_coeffs) + "]"
        new_line = f"coeffs = np.array({coeffs_str})\n"
        
        # Replace the line
        lines[coeffs_line_idx] = new_line
        
        # Write back
        with open(calib_file, 'w') as f:
            f.writelines(lines)
            
        st.success("✅ Coefficients updated in calibration_check.py (direct method)")
        return True
        
    except Exception as e:
        st.warning(f"Direct update failed: {e}")
        return False

def verify_coefficients_updated(expected_coeffs):
    """Verify that coefficients were actually updated in the file"""
    try:
        # Force reload the module to get updated coefficients
        import importlib
        import calibration_check
        importlib.reload(calibration_check)
        from calibration_check import coeffs as updated_coeffs
        
        # Compare coefficients (with some tolerance for floating point)
        if np.allclose(updated_coeffs, expected_coeffs, rtol=1e-6):
            st.success("✅ Verified: Coefficients successfully updated in file")
            return True
        else:
            st.warning("⚠️ Coefficients in file don't match expected values")
            return False
            
    except Exception as e:
        st.warning(f"Could not verify coefficient update: {e}")
        return False

def updatecalibrationcoeffsfile(new_coeffs):
    """Enhanced regex method to update coefficients in calibration_check.py"""
    try:
        calib_file = Path("calibration_check.py")
        if not calib_file.exists():
            st.warning("calibration_check.py not found, coefficients not updated in file")
            return False
            
        # Read the current file
        with open(calib_file, 'r') as f:
            content = f.read()
        
        # Format new coefficients properly
        coeffs_str = "np.array([" + ", ".join(f"{coeff:.8e}" for coeff in new_coeffs) + "])"
        
        # More specific regex pattern to match the exact coeffs line
        pattern = r'coeffs\s*=\s*np\.array\s*\(\s*\[[\s\S]*?\]\s*\)'
        
        # Check if pattern exists
        if not re.search(pattern, content):
            st.warning("Could not find coeffs array pattern in calibration_check.py")
            return False
            
        # Replace with new coefficients
        replacement = f"coeffs = {coeffs_str}"
        new_content = re.sub(pattern, replacement, content)
        
        # Write back to file
        with open(calib_file, 'w') as f:
            f.write(new_content)
            
        st.success("✅ Coefficients updated in calibration_check.py")
        return True
        
    except Exception as e:
        st.warning(f"Could not update calibration file: {e}")
        return False

# Download Reports Section
current_device_id = st.session_state.get("device_id")
devices = list_devices()

if devices:
    # Filter for current device if available
    if current_device_id:
        devices = [d for d in devices if d.device_id == current_device_id]
            
    # Download options
    st.subheader("📥 Download Reports")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Individual device report
        if current_device_id:
            device = get_device(current_device_id)
            if device:
                pdf_data = generate_device_report(device)
                st.download_button(
                    label=f"📄 Download Report for {current_device_id}",
                    data=pdf_data,
                    file_name=f"calibration_report_{current_device_id}_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                    mime="application/pdf"
                )
    
    with col2:
        # All devices report
        if len(devices) > 1:
            all_pdf_data = generate_all_devices_report(devices)
            st.download_button(
                label="📋 Download All Devices Report",
                data=all_pdf_data,
                file_name=f"all_devices_report_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                mime="application/pdf"
            )

# Manual recalibration option
if st.session_state.get('device_id') and st.session_state.get('samples'):
    if st.button("🔧 Manual Recalibration"):
        try:
            logs_dir = Path(__file__).parent / "logs"
            new_coeffs = generate_coefficients(str(logs_dir))
            # Ensure device exists before updating
            if not get_device(st.session_state['device_id']):
                add_device(st.session_state['device_id'], coeffs=list(new_coeffs))
            update_device_coeffs(st.session_state['device_id'], new_coeffs, samples=st.session_state.get('samples', {}), status="recalibrated")
            st.success("✅ Manual recalibration complete. Coefficients updated.")
        except Exception as e:
            st.error(f"Manual recalibration failed: {e}")

# Test file saving function
def test_file_saving():
    """Test if file saving works in the expected directory"""
    try:
        logs_dir = Path(__file__).parent / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        
        test_file = logs_dir / "test_save.log"
        with open(test_file, 'w') as f:
            f.write("Test file saving\n")
        
        if test_file.exists():
            st.success(f"✅ File saving works! Test file created at: {test_file}")
            test_file.unlink()  # Clean up test file
            return True
        else:
            st.error("❌ File saving failed - test file not created")
            return False
    except Exception as e:
        st.error(f"❌ File saving test failed: {e}")
        return False

# Add file saving test button
if st.button("🔧 Test File Saving", key="test_button"):
    test_file_saving()

# Connection monitoring and auto-reconnect functions
async def check_device_connection():
    """Check if the current device is still connected"""
    if st.session_state.btclient is None:
        return False
    try:
        return st.session_state.btclient.is_connected
    except:
        return False

async def auto_reconnect_after_power_cycle():
    """Enhanced auto-reconnect that preserves samples and handles power cycling"""
    max_attempts = 5
    attempt = 0
    
    while attempt < max_attempts:
        try:
            print(f"Reconnection attempt {attempt + 1}/{max_attempts}")
            
            # Scan for the same device address if we have it
            if st.session_state.device_address:
                try:
                    # Try direct reconnection first
                    client = BleakClient(st.session_state.device_address)
                    await client.connect(timeout=10.0)
                    if client.is_connected:
                        st.session_state.btclient = client
                        st.session_state.ble_client = client
                        st.session_state.device_connected = True
                        st.session_state.connection_status = f"Reconnected to {st.session_state.device_name}"
                        print(f"Successfully reconnected to device at {st.session_state.device_address}")
                        return True
                except Exception as e:
                    print(f"Direct reconnection failed: {e}")
            
            # If direct reconnection fails, scan for SMSensor devices
            client = await autoconnect_to_smsensor()
            if client:
                print("Successfully reconnected via auto-scan")
                return True
                
            attempt += 1
            if attempt < max_attempts:
                await asyncio.sleep(3)  # Wait before retry
                
        except Exception as e:
            print(f"Reconnection attempt {attempt + 1} failed: {e}")
            attempt += 1
            
    return False

async def monitor_connection_and_reconnect():
    """Monitor connection status and auto-reconnect when device comes back online"""
    if not st.session_state.monitoring_active:
        return

    # Check connection status
    is_connected = await check_device_connection()

    if not is_connected and st.session_state.btclient is not None:
        print("⚠️ Device disconnection detected. Starting auto-reconnect monitoring...")
        st.session_state.btclient = None
        st.session_state.ble_client = None
        st.session_state.connected_device = None
        st.session_state.device_connected = False
        st.session_state.connection_status = "Device disconnected - attempting reconnect..."

        # Try to reconnect
        reconnect_success = await auto_reconnect_after_power_cycle()

        if reconnect_success:
            # Refresh services so characteristics are available again
            try:
                await st.session_state.btclient.get_services()
                print("✅ Services refreshed after reconnect")
            except Exception as e:
                print(f"[ERROR] Failed to refresh services: {e}")

            st.success("🔄 Device automatically reconnected after power cycle!")
            st.session_state.reconnection_attempts = 0
        else:
            st.warning("⚠️ Auto-reconnection failed. Please manually reconnect.")
            st.session_state.reconnection_attempts += 1

def run_connection_monitor():
    """Run connection monitoring in the background"""
    current_time = time.time()
    
    # Check every 5 seconds
    if current_time - st.session_state.last_connection_check > 5:
        st.session_state.last_connection_check = current_time
        
        if st.session_state.monitoring_active:
            try:
                # Execute coroutine in a fresh event loop to avoid await issues
                run_asynccoro(monitor_connection_and_reconnect())
            except Exception as e:
                print(f"Connection monitoring error: {e}")

# Auto-reconnect for existing connections
if st.session_state.btclient is None or not st.session_state.btclient.is_connected:
    # Try auto-reconnect if we have a previous device address
    if st.session_state.device_address and not st.session_state.get("auto_reconnect_attempted", False):
        st.session_state.auto_reconnect_attempted = True
        with st.spinner("🔄 Attempting to reconnect to previous device..."):
            try:
                client = run_asynccoro(auto_reconnect_after_power_cycle())
                if client:
                    st.success("✅ Successfully reconnected!")
                    st.rerun()
                else:
                    st.warning("⚠️ Auto-reconnection failed. Device may be powered off.")
            except Exception as e:
                st.error(f"Reconnection error: {e}")

    # Add reconnect button for manual reconnection if needed
    if blue_button("🔄 Connect to ReMeDi Nova Spirometer", key="connect_bluetooth"):
        try:
            with st.spinner("Reconnecting... Please ensure device is powered on."):
                if st.session_state.btclient:
                    try:
                        run_asynccoro(st.session_state.btclient.disconnect())
                    except:
                        pass
                
                client = run_asynccoro(autoconnect_to_smsensor())
                if client:
                    st.success("✅ Reconnected successfully!")
                    st.success(f"📊 All {len(st.session_state.samples)} previous samples preserved!")
                    st.rerun()
                else:
                    st.error("❌ Reconnection failed")
        except Exception as e:
            st.error(f"Reconnection error: {str(e)}")

# Sidebar for additional options
with st.sidebar:
    st.header("🎛️ App Controls")
    
    # Connection Status
    st.subheader("🔗 Connection Status")
    if st.session_state.device_connected:
        st.success("🟢 Connected")
        st.text(f"Device: {st.session_state.device_name}")
        st.text(f"Samples: {len(st.session_state.samples)}/6")
    else:
        st.error("🔴 Disconnected")
    
    st.divider()
    
    # App Controls
    if st.button("🔄 Reset All Data"):
        # Keep essential state but clear data
        keys_to_keep = ['auto_connect_attempted', 'app_initialized', 'original_coefficients']
        keys_to_delete = [key for key in st.session_state.keys() if key not in keys_to_keep]
        
        for key in keys_to_delete:
            del st.session_state[key]
            
        st.success("✅ All data cleared!")
        st.rerun()
    
    if st.button("🐛 Show Debug Info"):
        with st.expander("Debug Information", expanded=True):
            debug_info = {
                "Device Connected": st.session_state.device_connected,
                "Connection Status": st.session_state.connection_status,
                "Device Name": st.session_state.device_name,
                "Samples Count": len(st.session_state.samples),
                "Device Registered": st.session_state.get('device_registered', False),
                "Monitoring Active": st.session_state.monitoring_active,
                "Auto Connect Attempted": st.session_state.auto_connect_attempted
            }
            st.json(debug_info)
    
    st.divider()
    
    # Quick Actions
    st.subheader("⚡ Quick Actions")
    
    if st.button("🔄 Force Reconnect"):
        st.session_state.auto_connect_attempted = False
        st.rerun()
    
    if st.button("📊 Show Sample Summary"):
        if st.session_state.samples:
            st.write("**Recorded Samples:**")
            for sample_type, data in st.session_state.samples.items():
                if isinstance(data, dict) and 'pressure' in data:
                    st.text(f"• {sample_type}: {len(data['pressure'])} points")
                else:
                    st.text(f"• {sample_type}: Invalid data")
        else:
            st.text("No samples recorded yet")

# Run connection monitoring for active connections
if st.session_state.btclient and st.session_state.btclient.is_connected:
    run_connection_monitor()

# Auto-refresh disabled to prevent interrupting user inputs
