import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import base64
import mysql.connector
from datetime import datetime

# Function to set background image and white text styling
def set_background(image_path):
    with open(image_path, "rb") as f:
        encoded = base64.b64encode(f.read()).decode()
    bg_image = f"""
    <style>
    .stApp {{
        background-image: url("data:image/jpg;base64,{encoded}");
        background-size: cover;
        background-position: center;
        background-attachment: fixed;
        color: white;
    }}
    .stMarkdown, .stTextInput label, .stMultiSelect label, .stNumberInput label, .stButton button {{
        color: white !important;
    }}
    table, th, td {{
        color: white !important;
        border: 1px solid white !important;
    }}
    .stButton > button {{
        background-color: lightcoral !important;
        color: white !important;
    }}
    </style>
    """
    st.markdown(bg_image, unsafe_allow_html=True)

def get_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="12345",
        database="smart_power",
        port=2306
    )

def user_exists(user_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users WHERE user_id = %s", (user_id,))
    exists = cursor.fetchone()[0] > 0
    conn.close()
    return exists

def validate_password(password):
    return len(password) >= 8

def register_user(user_id, password):
    if not user_exists(user_id):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO users (user_id, password) VALUES (%s, %s)", (user_id, password))
        conn.commit()
        conn.close()

def validate_login(user_id, password):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT password FROM users WHERE user_id = %s", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return row and row[0] == password

def insert_consumption(user_id, appliance_data):
    conn = get_connection()
    cursor = conn.cursor()
    for appliance, values in appliance_data.items():
        num_appliances, total_power = values
        cursor.execute("""
            INSERT INTO consumption (user_id, appliance_name, num_appliances, total_power_wh)
            VALUES (%s, %s, %s, %s)
        """, (user_id, appliance, num_appliances, total_power))
    conn.commit()
    conn.close()

def fetch_previous_data(user_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT appliance_name, num_appliances, total_power_wh FROM consumption WHERE user_id = %s", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return rows

def calculate_power(appliances, quantities, total_eb):
    power_ratings = {
        "Air Conditioner": 2000, "Refrigerator": 150, "Washing Machine": 500,
        "Microwave": 1200, "TV": 100, "Laptop": 50, "Fan": 75, "Light": 10, "Mobile": 5,
        "Air Purifier": 60, "Air Fryer": 1500, "Oven": 1800, "Kettle": 1200,
        "Ironbox": 1000, "Heater": 1500
    }
    raw_weights = {}
    total_weight = 0
    for i, appliance in enumerate(appliances):
        qty = quantities[i]
        wattage = power_ratings.get(appliance, 0)
        weight = wattage * qty
        raw_weights[appliance] = (qty, weight)
        total_weight += weight
    results = {}
    total_allocated_power = 0
    for appliance, (qty, weight) in raw_weights.items():
        proportion = weight / total_weight if total_weight else 0
        allocated_power = proportion * total_eb
        total_allocated_power += allocated_power
        results[appliance] = (qty, allocated_power)

    # Adjust last appliance to ensure total equals EB reading
    if results:
        last_key = list(results.keys())[-1]
        qty, _ = results[last_key]
        results[last_key] = (qty, results[last_key][1] + (total_eb - total_allocated_power))

    return results

set_background("smart.jpg")
st.markdown(
    """
    <div style='text-align: center;'>
        <img src='data:image/png;base64,{}' width='300'>
    </div>
    """.format(base64.b64encode(open("logo.jpg", "rb").read()).decode()),
    unsafe_allow_html=True
)
st.markdown("<h1 style='text-align: center; color: white;'>SMART POWER ANALYTICS</h1>", unsafe_allow_html=True)

if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.subheader("Login / Register")
    user_id = st.text_input("User ID")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        if validate_login(user_id, password):
            st.session_state.logged_in = True
            st.session_state.user_id = user_id
            st.success("Login successful")
        else:
            st.warning("Invalid credentials or user not found")
    elif st.button("Register"):
        if user_exists(user_id):
            st.warning("User already exists")
        elif not validate_password(password):
            st.error("Password too short")
        else:
            register_user(user_id, password)
            st.success("Registration successful, please login")

if st.session_state.logged_in:
    st.header("Smart Energy Consumption Calculator")
    total_eb = st.number_input("Enter total EB reading (in Kwh):", min_value=0.0)

    appliances_selected = st.multiselect(
        "Select appliances:",
        ["Air Conditioner", "Refrigerator", "Washing Machine", "Microwave", "TV", "Laptop", "Fan", "Light", "Mobile",
         "Air Purifier", "Air Fryer", "Oven", "Kettle", "Ironbox", "Heater"]
    )

    quantities = []
    if appliances_selected:
        st.subheader("Enter quantity per appliance:")
        for app in appliances_selected:
            qty = st.number_input(f"Number of {app}s:", min_value=1, value=1)
            quantities.append(qty)

    if st.button("Calculate"):
        if not appliances_selected:
            st.warning("Select at least one appliance")
        else:
            appliance_data = calculate_power(appliances_selected, quantities, total_eb)
            insert_consumption(st.session_state.user_id, appliance_data)

            df = pd.DataFrame([
                [app, vals[0], vals[1]] for app, vals in appliance_data.items()
            ], columns=["Appliance", "Quantity", "Total Power (Wh)"])
            st.dataframe(df)

            st.subheader("Usage Visualization")
            fig, ax = plt.subplots()
            ax.barh(df["Appliance"], df["Total Power (Wh)"], color='skyblue')
            ax.set_xlabel("Power Consumption (Wh)")
            ax.set_title("Power Usage by Appliance")
            st.pyplot(fig)

            st.markdown(f"**Total EB Reading Used:** {total_eb:.2f} KWh")
            cost_per_kwh = 10.90
            monthly_cost = total_eb  * cost_per_kwh
            st.markdown(f"**Estimated Monthly Cost (based on total EB reading):** ₹{monthly_cost:.2f}")

            st.markdown("### Energy-Saving Tips")
            for app, val in appliance_data.items():
                if val[1] > 1500:
                    st.warning(f"High usage of {app}. Consider reducing usage or using efficient models.")

    st.subheader("Previous Usage Records")
    prev = fetch_previous_data(st.session_state.user_id)
    if prev:
        df_prev = pd.DataFrame(prev, columns=["Appliance", "Quantity", "Power (Wh)"])
        st.dataframe(df_prev)
        fig2, ax2 = plt.subplots()
        ax2.barh(df_prev["Appliance"], df_prev["Power (Wh)"], color='lightgreen')
        ax2.set_xlabel("Power Consumption (Wh)")
        ax2.set_title("Past Power Usage")
        st.pyplot(fig2)

        csv = df_prev.to_csv(index=False).encode('utf-8')
        st.download_button("Download Previous Report as CSV", csv, "usage_report.csv", "text/csv")
       # Refresh Button
    if st.button("🔄 Refresh Page"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()


