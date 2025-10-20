import streamlit as st
import pandas as pd
import re
from pathlib import Path

# ---------------------------------------------------------
# Streamlit config
# ---------------------------------------------------------
st.set_page_config(page_title="Webb Environmental - UST Lookup", layout="wide")
st.title("🛢️ Webb Environmental – UST Facility Lookup")

# ---------------------------------------------------------
# 🔧 Toggle to see diagnostics (no sidebar UI)
# Set to True if you want the debug prints
# ---------------------------------------------------------
DEBUG = False

# ---------------------------------------------------------
# 🌐 Auto-load data from your GitHub /data folder
# ---------------------------------------------------------
BASE_URL = "https://raw.githubusercontent.com/webbenv/UST_Lookup/main/data/"

@st.cache_data
def load_data():
    try:
        tanks = pd.read_csv(BASE_URL + "tanks.csv", low_memory=False)
        owner = pd.read_csv(BASE_URL + "owner.csv", low_memory=False)
        ustpipe = pd.read_excel(BASE_URL + "ustpipematerials.xlsx", engine="openpyxl")
        usttankmaterials = pd.read_csv(BASE_URL + "usttankmaterials.csv", low_memory=False)
        ustpipe_release = pd.read_csv(BASE_URL + "usttankpipereleasedetection.csv", low_memory=False)
        return tanks, owner, ustpipe, usttankmaterials, ustpipe_release
    except Exception as e:
        st.error(f"⚠️ Error loading data: {e}")
        return (pd.DataFrame(),)*5

tanks, owner, ustpipe, usttankmaterials, ustpipe_release = load_data()

# Normalize columns for reliable matching
for df in [tanks, owner, ustpipe, usttankmaterials, ustpipe_release]:
    if not df.empty:
        df.columns = df.columns.str.lower().str.strip().str.replace(r"\s+", " ", regex=True)

# ---------------------------------------------------------
# Search input
# ---------------------------------------------------------
facility_input = st.text_input("Search by Facility ID, Site Name, or Address:")

# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------
def find_facility_column(df: pd.DataFrame):
    if df is None or df.empty or not hasattr(df, "columns"):
        return None
    # Prefer canonical names
    for col in df.columns:
        cl = col.lower()
        if "facility" in cl and "id" in cl:
            return col
    # Fallback common variants
    for cand in ["facid", "facilityid", "fac_id", "fac id"]:
        if cand in df.columns:
            return cand
    return None

def normalize_zip(val):
    s = str(val).strip()
    if s.endswith(".0"):
        s = s[:-2]
    if s.isdigit() and len(s) <= 5:
        s = s.zfill(5)
    return s

def clean_tank_number(val):
    if pd.isna(val):
        return ""
    return re.sub(r"[^0-9]", "", str(val).strip())

def is_truthy(val):
    return str(val).strip().lower() in {"y", "yes", "true", "t", "1", "x"}

def format_capacity(value):
    try:
        num = pd.to_numeric(value, errors="coerce")
        if pd.isna(num):
            return str(value)
        return f"{int(num):,}"
    except Exception:
        return str(value)

# ---------------------------------------------------------
# Main flow (no sidebar dependencies)
# ---------------------------------------------------------
if facility_input:
    if tanks.empty or owner.empty:
        st.error("Data not loaded — verify your GitHub /data folder.")
        st.stop()

    fac_col_tanks = find_facility_column(tanks)
    fac_col_owner = find_facility_column(owner)

    fid_str = str(facility_input).strip()
    tanks_filtered = pd.DataFrame()

    # 1) Try Facility ID (string compare)
    if fac_col_tanks in tanks.columns:
        tanks_filtered = tanks[tanks[fac_col_tanks].astype(str).str.strip() == fid_str]

    # 2) Fallback: search by name/address
    if tanks_filtered.empty:
        if "facility name" in tanks.columns:
            tanks_filtered = tanks[
                tanks["facility name"].astype(str).str.contains(fid_str, case=False, na=False)
            ]
        elif "address" in tanks.columns:
            tanks_filtered = tanks[
                tanks["address"].astype(str).str.contains(fid_str, case=False, na=False)
            ]

    if tanks_filtered.empty:
        st.warning("No facility found for that ID or name.")
        st.stop()

    facility_id = tanks_filtered[fac_col_tanks].iloc[0] if fac_col_tanks else "Unknown"

    # ----------------- Owner info -----------------
    owner_filtered = pd.DataFrame()
    if fac_col_owner in owner.columns and fac_col_tanks in tanks.columns:
        owner_filtered = owner[owner[fac_col_owner].astype(str).str.strip() == str(facility_id)]

    owner_name = owner_filtered["owner name"].iloc[-1] if not owner_filtered.empty and "owner name" in owner_filtered.columns else "N/A"
    site_name  = owner_filtered["name"].iloc[-1]        if not owner_filtered.empty and "name" in owner_filtered.columns       else "N/A"
    owner_addr = "N/A"
    if not owner_filtered.empty and all(c in owner_filtered.columns for c in ["owner address 1","owner city","owner state","owner zip"]):
        owner_addr = f"{owner_filtered['owner address 1'].iloc[-1]}, {owner_filtered['owner city'].iloc[-1]}, {owner_filtered['owner state'].iloc[-1]} {normalize_zip(owner_filtered['owner zip'].iloc[-1])}"

    dealer_id = owner_filtered["owner id"].max() if not owner_filtered.empty and "owner id" in owner_filtered.columns else "N/A"

    # ----------------- Facility Summary -----------------
    st.markdown(
        f"### 🧾 Facility Summary for ID: **`{facility_id}`**"
    )
    st.markdown(
        f"**Owner:** {owner_name}  \n"
        f"**Site Name:** {site_name}  \n"
        f"**Owner Address:** {owner_addr}  \n"
        f"**Facility ID:** {facility_id}  \n"
        f"**Dealer ID:** {dealer_id}"
    )

    # ----------------- Active Tanks -----------------
    st.markdown("### ⛽ Active Tanks")
    active_tanks = tanks_filtered[tanks_filtered.get("tank status","").astype(str).str.contains("CURR IN USE", case=False, na=False)] \
                   if "tank status" in tanks_filtered.columns else pd.DataFrame()

    # Normalize tank numbers for joins later
    if "tank number" in active_tanks.columns:
        active_tanks = active_tanks.copy()
        active_tanks["clean_tank_number"] = active_tanks["tank number"].apply(clean_tank_number)

    # Render each active tank as a clean block
    if active_tanks.empty:
        st.info("No active tanks found for this facility.")
    else:
        # Pre-normalize aux tables
        if not usttankmaterials.empty and "tank number" in usttankmaterials.columns:
            usttankmaterials = usttankmaterials.copy()
            usttankmaterials["clean_tank_number"] = usttankmaterials["tank number"].apply(clean_tank_number)

        if not ustpipe.empty and "tank number" in ustpipe.columns:
            ustpipe = ustpipe.copy()
            ustpipe["clean_tank_number"] = ustpipe["tank number"].apply(clean_tank_number)

        if not ustpipe_release.empty and "tank number" in ustpipe_release.columns:
            ustpipe_release = ustpipe_release.copy()
            ustpipe_release["clean_tank_number"] = ustpipe_release["tank number"].apply(clean_tank_number)

        for _, row in active_tanks.iterrows():
            tank_num = row.get("tank number", "N/A")
            clean_num = row.get("clean_tank_number", str(tank_num))
            contents = row.get("contents", "N/A")
            capacity = format_capacity(row.get("capacity", "N/A"))
            install_date = row.get("install date", "N/A")
            status = row.get("tank status", "N/A")

            # Double Wall from usttankmaterials (Column L logic already encoded previously)
            double_wall = "Unknown"
            mat_row = pd.DataFrame()
            if not usttankmaterials.empty and "clean_tank_number" in usttankmaterials.columns:
                mat_row = usttankmaterials[usttankmaterials["clean_tank_number"] == clean_num]
            if not mat_row.empty and mat_row.shape[1] > 11:
                # Column index 11 ~ original "Column L"
                col_L = mat_row.iloc[0, 11]
                double_wall = "Yes" if str(col_L).strip().upper() == "Y" else "No"

            # Pipe Materials (scan all Pipe Material ... columns)
            pipe_material = "Unknown"
            if not ustpipe.empty and "clean_tank_number" in ustpipe.columns:
                pr = ustpipe[ustpipe["clean_tank_number"] == clean_num]
                mats = []
                if not pr.empty:
                    for col in pr.columns:
                        cl = str(col).lower()
                        if cl.startswith("pipe material"):
                            if is_truthy(pr.iloc[0][col]):
                                name = str(col)[len("pipe material"):].strip()
                                name = re.sub(r"^[\s:,-]+", "", name).title() or "Unknown"
                                mats.append(name)
                if mats:
                    pipe_material = ", ".join(mats)
                else:
                    # Legacy fallbacks for fiberglass
                    if not pr.empty:
                        for col in pr.columns:
                            if "fiberglass" in str(col).lower():
                                val = str(pr.iloc[0][col]).strip().lower()
                                if val in {"y","yes","fiberglass"}:
                                    pipe_material = "Fiberglass (Double Walled)"
                                    break

            # RD Methods from release table (both tank and pipe)
            def extract_rd(df, tn, prefix):
                if df.empty or "clean_tank_number" not in df.columns:
                    return []
                r = df[df["clean_tank_number"] == tn]
                if r.empty:
                    return []
                methods = []
                for c in r.columns:
                    cl = str(c).lower()
                    if cl.startswith(prefix) and str(r.iloc[0][c]).strip().upper() == "Y":
                        pretty = c[len(prefix):].strip().title()
                        methods.append(pretty)
                return methods

            tank_rd = extract_rd(ustpipe_release, clean_num, "tank rd ")
            pipe_rd = extract_rd(ustpipe_release, clean_num, "pipe rd ")

            st.markdown(
                f"**Tank #{tank_num}: {contents}**  \n"
                f"- **Capacity:** {capacity} gallons  \n"
                f"- **Install Date:** {install_date}  \n"
                f"- **Status:** {status}  \n"
                f"- **Double Wall:** {double_wall}  \n"
                f"- **Piping Material:** {pipe_material}  \n"
                f"**Tank RD Methods:** {', '.join(tank_rd) if tank_rd else 'Not Listed'}  \n"
                f"**Pipe RD Methods:** {', '.join(pipe_rd) if pipe_rd else 'Not Listed'}"
            )
            st.markdown("---")

else:
    st.info("Type a Facility ID, Site Name, or Address to begin.")