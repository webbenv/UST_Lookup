import streamlit as st
import pandas as pd
import re

# ---------------------------------------------------------
# 🧱 Streamlit configuration
# ---------------------------------------------------------
st.set_page_config(page_title="Webb Environmental - UST Facility Lookup", layout="wide")
st.title("🛢️ Webb Environmental – UST Facility Lookup")

# ---------------------------------------------------------
# 🌐 Base URL for hosted GitHub data
# ---------------------------------------------------------
BASE_URL = "https://raw.githubusercontent.com/webbenv/UST_Lookup/main/data/"

@st.cache_data
def load_data():
    """Loads all data files automatically from GitHub."""
    try:
        tanks = pd.read_csv(BASE_URL + "tanks.csv", low_memory=False)
        owner = pd.read_csv(BASE_URL + "owner.csv", low_memory=False)
        ustpipe = pd.read_excel(BASE_URL + "ustpipematerials.xlsx", engine="openpyxl")
        usttankmaterials = pd.read_csv(BASE_URL + "usttankmaterials.csv", low_memory=False)
        ustrelease = pd.read_csv(BASE_URL + "usttankpipereleasedetection.csv", low_memory=False)
        return tanks, owner, ustpipe, usttankmaterials, ustrelease
    except Exception as e:
        st.error(f"⚠️ Error loading data: {e}")
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

tanks, owner, ustpipe, usttankmaterials, ustrelease = load_data()

# ---------------------------------------------------------
# 🧹 Normalize columns (important for search consistency)
# ---------------------------------------------------------
for df in [tanks, owner, ustpipe, usttankmaterials, ustrelease]:
    if not df.empty:
        df.columns = df.columns.str.lower().str.strip()

# ---------------------------------------------------------
# 🔍 Search box
# ---------------------------------------------------------
facility_input = st.text_input("Search by Facility ID, Site Name, or Address:")

# ---------------------------------------------------------
# 🧠 Helper: find correct facility id column dynamically
# ---------------------------------------------------------
def find_facility_column(df):
    if df is None or df.empty or not hasattr(df, "columns"):
        return None
    for col in df.columns:
        if "facility" in col.lower() and "id" in col.lower():
            return col
    for col in df.columns:
        if col.lower() in ["facid", "facilityid", "fac_id", "fac id"]:
            return col
    return None

# ---------------------------------------------------------
# 🧾 Facility lookup
# ---------------------------------------------------------
if facility_input:
    if tanks.empty or owner.empty:
        st.error("Data not loaded — please verify your GitHub data folder.")
    else:
        facility_col_tanks = find_facility_column(tanks)
        facility_col_owner = find_facility_column(owner)

        fid = str(facility_input).strip()
        tanks_filtered = pd.DataFrame()

        # Match by Facility ID (as string)
        if facility_col_tanks in tanks.columns:
            tanks_filtered = tanks[tanks[facility_col_tanks].astype(str).str.strip() == fid]

        # Fallback: search by name or address if ID not found
        if tanks_filtered.empty:
            if "facility name" in tanks.columns:
                tanks_filtered = tanks[tanks["facility name"].astype(str).str.contains(fid, case=False, na=False)]
            elif "address" in tanks.columns:
                tanks_filtered = tanks[tanks["address"].astype(str).str.contains(fid, case=False, na=False)]

        if tanks_filtered.empty:
            st.warning("No facility found for that ID or name.")
        else:
            facility_id = tanks_filtered[facility_col_tanks].iloc[0] if facility_col_tanks else "Unknown"

            st.markdown(f"### 🧾 Facility Summary for ID: `{facility_id}`")
            st.dataframe(tanks_filtered.head(10))

            # ---------------------------------------------------------
            # 👤 Owner info
            # ---------------------------------------------------------
            if facility_col_owner in owner.columns:
                owner_filtered = owner[owner[facility_col_owner].astype(str).str.strip() == str(facility_id)]
                if not owner_filtered.empty:
                    st.markdown("### 👤 Owner Information")
                    st.dataframe(owner_filtered.head(10))

            # ---------------------------------------------------------
            # ⛽ Active tanks
            # ---------------------------------------------------------
            if "tank status" in tanks_filtered.columns:
                active_tanks = tanks_filtered[tanks_filtered["tank status"].astype(str).str.contains("CURR IN USE", case=False, na=False)]
                if not active_tanks.empty:
                    st.markdown("### ⛽ Active Tanks")
                    st.dataframe(active_tanks[["tank number", "contents", "capacity", "install date", "tank status"]])
                else:
                    st.info("No active tanks found for this facility.")
else:
    st.info("Enter a Facility ID, Site Name, or Address to begin your lookup.")