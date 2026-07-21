import streamlit as st
import boto3
from boto3.dynamodb.conditions import Key
import pandas as pd

st.set_page_config(page_title="FleetSense", layout="wide")

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table("VehicleTelemetry")

COOLANT_THRESHOLD = 120
VOLTAGE_LOW = 11.0

def get_vehicles():
    resp = table.scan(ProjectionExpression="vehicle_id")
    return sorted({item["vehicle_id"] for item in resp["Items"]})

def get_recent(vehicle_id, n=60):
    resp = table.query(
        KeyConditionExpression=Key("vehicle_id").eq(vehicle_id),
        ScanIndexForward=False,
        Limit=n,
    )
    items = resp["Items"][::-1]
    if not items:
        return pd.DataFrame()
    df = pd.DataFrame(items)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    for col in ["speed_kmh", "coolant_temp_c", "battery_voltage", "rpm",
                "accel_x", "accel_y", "accel_z"]:
        if col in df:
            df[col] = df[col].astype(float)
    return df.set_index("timestamp")

st.title("FleetSense - Live Fleet Dashboard")

_vehicles = get_vehicles()
selected = st.selectbox("Vehicle detail view", _vehicles) if _vehicles else None

@st.fragment(run_every="3s")
def live_view():
    vehicles = get_vehicles()
    if not vehicles:
        st.info("No telemetry yet - start a simulator.")
        return

    st.subheader("Fleet overview")
    cols = st.columns(len(vehicles))
    any_alert = False
    for col, vid in zip(cols, vehicles):
        df = get_recent(vid, n=1)
        if df.empty:
            continue
        latest = df.iloc[-1]
        temp = float(latest.get("coolant_temp_c", 0))
        volt = float(latest.get("battery_voltage", 0))
        alert = temp > COOLANT_THRESHOLD or volt < VOLTAGE_LOW
        any_alert = any_alert or alert
        with col:
            st.metric(vid, f"{float(latest.get('speed_kmh', 0)):.0f} km/h")
            st.metric("Coolant C", f"{temp:.0f}",
                      delta="HIGH" if temp > COOLANT_THRESHOLD else None,
                      delta_color="inverse")
            st.metric("Battery V", f"{volt:.1f}",
                      delta="LOW" if volt < VOLTAGE_LOW else None,
                      delta_color="inverse")

    if any_alert:
        st.error("ANOMALY DETECTED - one or more vehicles out of safe range")

    if selected:
        st.subheader(f"Detail - {selected}")
        d = get_recent(selected, n=60)
        if not d.empty:
            chart_fields = [
                ("Speed (km/h)", "speed_kmh"),
                ("Coolant temp (C)", "coolant_temp_c"),
                ("Battery voltage (V)", "battery_voltage"),
                ("Accel X (m/s2)", "accel_x"),
                ("Accel Y (m/s2)", "accel_y"),
                ("Accel Z (m/s2)", "accel_z"),
            ]
            for label, col in chart_fields:
                if col in d.columns:
                    st.caption(label)
                    st.line_chart(d[[col]])

live_view()
