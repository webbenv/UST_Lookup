import streamlit as st
import pandas as pd
from pandas.errors import EmptyDataError
import re
from pathlib import Path

# -----------------------------------------------------------------------------
# Streamlit config
# -----------------------------------------------------------------------------
st.set_page_config(page_title="Webb Environmental - UST Lookup", layout="wide")
st.title("🛢️ Webb Environmental – UST Facility Lookup")

# -----------------------------------------------------------------------------
# Auto-load CSV/XLSX data from GitHub (no uploads)
# -----------------------------------------------------------------------------
BASE_URL = "https://raw.githubusercontent.com/webbenv/UST_Lookup/main/data/"

@st.cache_data
def load_data():
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

# -----------------------------------------------------------------------------
# Search input
# -----------------------------------------------------------------------------
facility_input = st.text_input("Search by Facility ID, Site Name, or Address:")

# -----------------------------------------------------------------------------
# Helper: Find facility column dynamically
# -----------------------------------------------------------------------------
def find_facility_column(df):
    if df is None or df.empty or not hasattr(df, "columns"):
        return None
    facility_patterns = [
        "facility id", "facilityid", "facid", "fac_id", "fac id", "fac-id",
        "facility number", "facility_no", "fac no", "facno"
    ]
    for pat in facility_patterns:
        if pat in df.columns:
            return pat
    for col in df.columns:
        if "facility" in col.lower() and "id" in col.lower():
            return col
    return None

# -----------------------------------------------------------------------------
# Lookup logic
# -----------------------------------------------------------------------------
if facility_input:
    if tanks.empty or owner.empty:
        st.error("Data not loaded — please verify your GitHub data folder.")
    else:
        facility_col_tanks = find_facility_column(tanks)
        facility_col_owner = find_facility_column(owner)

        tanks_filtered = pd.DataFrame()
        try:
            fid = int(facility_input)
            if facility_col_tanks in tanks.columns:
                tanks_filtered = tanks[tanks[facility_col_tanks] == fid]
        except ValueError:
            if "facility name" in tanks.columns:
                tanks_filtered = tanks[
                    tanks["facility name"].astype(str).str.contains(facility_input, case=False, na=False)
                ]

        if tanks_filtered.empty:
            st.warning("No facility found for that ID or name.")
        else:
            st.markdown("### 🧾 Facility Summary")
            st.write(tanks_filtered.head(10))

            if facility_col_owner and facility_col_tanks:
                owner_filtered = owner[
                    owner[facility_col_owner].isin(tanks_filtered[facility_col_tanks])
                ]
                if not owner_filtered.empty:
                    st.markdown("### 👤 Owner Information")
                    st.write(owner_filtered.head(10))

            st.success("✅ Lookup completed successfully.")
else:
    st.info("Enter a Facility ID, Site Name, or Address to begin your lookup.")