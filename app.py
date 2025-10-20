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
# Auto-load data from GitHub /data (NO SIDEBAR UPLOADS)
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
        # SiteInfo is optional but present per your note
        try:
            siteinfo = pd.read_csv(BASE_URL + "SiteInfo.csv", low_memory=False)
        except Exception:
            siteinfo = pd.DataFrame()
        return tanks, owner, ustpipe, usttankmaterials, ustpipe_release, siteinfo
    except Exception as e:
        st.error(f"⚠️ Error loading data: {e}")
        return (pd.DataFrame(),)*6

tanks, owner, ustpipe, usttankmaterials, ustpipe_release, siteinfo = load_data()

# Normalize column names everywhere (lowercase, strip, collapse spaces)
for df in [tanks, owner, ustpipe, usttankmaterials, ustpipe_release, siteinfo]:
    if not df.empty:
        df.columns = df.columns.str.lower().str.strip().str.replace(r"\s+", " ", regex=True)

# ---------------------------------------------------------
# Search input (main UI)
# ---------------------------------------------------------
facility_input = st.text_input("Search by Facility ID, Site Name, or Address:")

# ---------------------------------------------------------
# Helpers (kept consistent with your working code)
# ---------------------------------------------------------
def find_facility_column(df):
    if df is None or df.empty or not hasattr(df, "columns"):
        return None
    # Prefer any col containing facility + id
    for col in df.columns:
        cl = col.lower()
        if "facility" in cl and "id" in cl:
            return col
    # Fallback common variants
    for cand in ["facid", "facilityid", "fac_id", "fac id", "site id", "siteid"]:
        if cand in df.columns:
            return cand
    return None

def normalize_zip(val):
    s = str(val).strip()
    if s.endswith('.0'):
        s = s[:-2]
    if s.isdigit() and len(s) <= 5:
        s = s.zfill(5)
    return s

def clean_tank_number(val):
    if pd.isna(val):
        return ""
    s = str(val).strip()
    # digits-only so R1/RA2/1M → 1/2/1
    return re.sub(r"[^0-9]", "", s)

def is_truthy(val):
    s = str(val).strip().lower()
    return s in {"y","yes","true","t","1","x"}

def format_capacity(value):
    try:
        num = pd.to_numeric(value, errors="coerce")
        if pd.isna(num):
            return str(value)
        return f"{int(num):,}"
    except Exception:
        return str(value)

def pick(df, candidates):
    for c in candidates:
        if c in df.columns:
            return c
    return None

# ---------------------------------------------------------
# MAIN FLOW — replicate your working logic, without sidebar
# ---------------------------------------------------------
if facility_input:
    if tanks.empty or owner.empty:
        st.error("Data not loaded — verify your GitHub /data folder.")
        st.stop()

    fac_col_tanks = find_facility_column(tanks)
    fac_col_owner = find_facility_column(owner)
    fac_col_site  = find_facility_column(siteinfo) if not siteinfo.empty else None

    tanks_filtered = pd.DataFrame()
    fid_str = str(facility_input).strip()

    # 1) try Facility ID match (string-compare to be robust)
    if fac_col_tanks in tanks.columns:
        tanks_filtered = tanks[tanks[fac_col_tanks].astype(str).str.strip() == fid_str]

    # 2) fallback: facility name, then address
    if tanks_filtered.empty:
        if "facility name" in tanks.columns:
            tanks_filtered = tanks[tanks["facility name"].astype(str).str.contains(fid_str, case=False, na=False)]
        if tanks_filtered.empty and "address" in tanks.columns:
            tanks_filtered = tanks[tanks["address"].astype(str).str.contains(fid_str, case=False, na=False)]

    # 3) fallback via owner by name/address → get facility IDs → filter tanks
    if tanks_filtered.empty and not owner.empty and fac_col_owner in owner.columns:
        owner_search = owner.copy()
        if all(x in owner_search.columns for x in ["owner address 1","owner city","owner state","owner zip"]):
            owner_search["full_address"] = (
                owner_search["owner address 1"].astype(str).str.strip() + ", " +
                owner_search["owner city"].astype(str).str.strip() + ", " +
                owner_search["owner state"].astype(str).str.strip() + " " +
                owner_search["owner zip"].astype(str).str.strip()
            )
        else:
            owner_search["full_address"] = ""

        name_cols = [c for c in ["name","owner name","site name"] if c in owner_search.columns]
        search_cols = name_cols + ["full_address"]
        if search_cols:
            mask = None
            for col in search_cols:
                col_mask = owner_search[col].astype(str).str.contains(fid_str, case=False, na=False)
                mask = col_mask if mask is None else (mask | col_mask)
            owner_matches = owner_search[mask] if mask is not None else pd.DataFrame()
            if not owner_matches.empty and fac_col_owner in owner_matches.columns and fac_col_tanks in tanks.columns:
                matched_fids = owner_matches[fac_col_owner].dropna().unique().tolist()
                if matched_fids:
                    tanks_filtered = tanks[tanks[fac_col_tanks].isin(matched_fids)]

    # 4) fallback via SiteInfo (if present)
    if tanks_filtered.empty and not siteinfo.empty and fac_col_site and fac_col_tanks in tanks.columns:
        si = siteinfo.copy()
        street_col = pick(si, ["site address 1","site address","address 1","address","facility address 1","facility address"])
        city_col   = pick(si, ["site city","city","facility city"])
        state_col  = pick(si, ["site state","state","facility state"])
        zip_col    = pick(si, ["site zip","zip","zipcode","zip code","zip 5","facility zip"])
        si["full_address"] = ""
        if all([street_col,city_col,state_col,zip_col]):
            si["full_address"] = (
                si[street_col].astype(str).str.strip() + ", " +
                si[city_col].astype(str).str.strip() + ", " +
                si[state_col].astype(str).str.strip() + " " +
                si[zip_col].astype(str).str.strip()
            )
        name_cols = [c for c in ["name","site name"] if c in si.columns]
        search_cols = name_cols + ["full_address"]
        mask = None
        for col in search_cols:
            col_mask = si[col].astype(str).str.contains(fid_str, case=False, na=False)
            mask = col_mask if mask is None else (mask | col_mask)
        site_matches = si[mask] if mask is not None else pd.DataFrame()
        if not site_matches.empty and fac_col_site in site_matches.columns:
            site_fids = site_matches[fac_col_site].dropna().unique().tolist()
            if site_fids:
                tanks_filtered = tanks[tanks[fac_col_tanks].isin(site_fids)]

    if tanks_filtered.empty:
        st.warning("No facility found for that ID or name.")
        st.stop()

    # Facility ID selected
    facility_id = tanks_filtered[fac_col_tanks].iloc[0] if fac_col_tanks else "Unknown"

    # ----------------- Owner info -----------------
    if fac_col_owner in owner.columns:
        owner_filtered = owner[owner[fac_col_owner].astype(str).str.strip() == str(facility_id)]
    else:
        owner_filtered = pd.DataFrame()

    owner_name = owner_filtered["owner name"].iloc[-1] if not owner_filtered.empty and "owner name" in owner_filtered.columns else "N/A"
    site_name  = owner_filtered["name"].iloc[-1]        if not owner_filtered.empty and "name" in owner_filtered.columns       else "N/A"

    owner_address = "N/A"
    if not owner_filtered.empty and all(x in owner_filtered.columns for x in ["owner address 1","owner city","owner state","owner zip"]):
        owner_address = (
            f"{owner_filtered['owner address 1'].iloc[-1]}, "
            f"{owner_filtered['owner city'].iloc[-1]}, "
            f"{owner_filtered['owner state'].iloc[-1]} "
            f"{normalize_zip(owner_filtered['owner zip'].iloc[-1])}"
        )

    # ----------------- Site Address (from SiteInfo.csv if available) -----------------
    site_address = "N/A"
    if not siteinfo.empty and fac_col_site in siteinfo.columns:
        sirow = siteinfo[siteinfo[fac_col_site].astype(str).str.strip() == str(facility_id)]
        if not sirow.empty:
            street_col = pick(sirow, ["site address 1","site address","address 1","address","facility address 1","facility address"])
            city_col   = pick(sirow, ["site city","city","facility city"])
            state_col  = pick(sirow, ["site state","state","facility state"])
            zip_col    = pick(sirow, ["site zip","zip","zipcode","zip code","zip 5","facility zip"])
            if all([street_col,city_col,state_col,zip_col]):
                z = normalize_zip(sirow[zip_col].iloc[-1])
                site_address = f"{sirow[street_col].iloc[-1]}, {sirow[city_col].iloc[-1]}, {sirow[state_col].iloc[-1]} {z}"

    dealer_id = owner_filtered["owner id"].max() if not owner_filtered.empty and "owner id" in owner_filtered.columns else "N/A"

    # ----------------- Facility Summary -----------------
    st.markdown("### 🧾 Facility Summary")
    st.markdown(
        f"**Owner:** {owner_name}  \n"
        f"**Site Name:** {site_name}  \n"
        f"**Owner Address:** {owner_address}  \n"
        f"**Site Address:** {site_address}  \n"
        f"**Facility ID:** {facility_id}  \n"
        f"**Dealer ID:** {dealer_id}"
    )

    # ----------------- Active Tanks (render like your working layout) -----------------
    st.markdown("### ⛽ Active Tanks")
    active_tanks = tanks_filtered[tanks_filtered.get("tank status","").astype(str).str.contains("CURR IN USE", case=False, na=False)] \
                   if "tank status" in tanks_filtered.columns else pd.DataFrame()

    if "tank number" in active_tanks.columns:
        active_tanks = active_tanks.copy()
        active_tanks["clean_tank_number"] = active_tanks["tank number"].apply(clean_tank_number)

    # Pre-normalize joins for materials / RD
    if not usttankmaterials.empty and "tank number" in usttankmaterials.columns:
        usttankmaterials = usttankmaterials.copy()
        usttankmaterials["clean_tank_number"] = usttankmaterials["tank number"].apply(clean_tank_number)

    if not ustpipe.empty and "tank number" in ustpipe.columns:
        ustpipe = ustpipe.copy()
        ustpipe["clean_tank_number"] = ustpipe["tank number"].apply(clean_tank_number)

    if not ustpipe_release.empty and "tank number" in ustpipe_release.columns:
        ustpipe_release = ustpipe_release.copy()
        ustpipe_release["clean_tank_number"] = ustpipe_release["tank number"].apply(clean_tank_number)

    # RD extractor (Tank/ Pipe)
    def extract_rd(df, clean_num, prefix):
        if df.empty or "clean_tank_number" not in df.columns:
            return []
        subset = df[df["clean_tank_number"] == clean_num]
        # Prefer same facility if available
        if not subset.empty and "facility id" in subset.columns:
            try:
                target_digits = re.sub(r"\D", "", str(facility_id))
                ser_digits = subset["facility id"].astype(str).str.replace(r"\D", "", regex=True)
                subset2 = subset[ser_digits == target_digits]
                if not subset2.empty:
                    subset = subset2
            except Exception:
                subset2 = subset[subset["facility id"].astype(str).str.strip() == str(facility_id)]
                if not subset2.empty:
                    subset = subset2
        if subset.empty:
            return []
        methods = []
        for c in subset.columns:
            cl = str(c).lower()
            if cl.startswith(prefix):
                colvals = subset[c].astype(str).str.strip().str.upper()
                if (colvals == "Y").any():
                    methods.append(c[len(prefix):].strip().title())
        return methods

    if active_tanks.empty:
        st.info("No active tanks found for this facility.")
    else:
        for _, row in active_tanks.iterrows():
            tank_num = row.get("tank number", "N/A")
            clean_num = row.get("clean_tank_number", str(tank_num))
            contents = row.get("contents", "N/A")
            capacity = format_capacity(row.get("capacity", "N/A"))
            install_date = row.get("install date", "N/A")
            status = row.get("tank status", "N/A")

            # Tank Double Wall (robust): prefer named column and constrain by facility; prefer current/exact row
            double_wall = "No"
            mat_row = pd.DataFrame()
            if not usttankmaterials.empty and "clean_tank_number" in usttankmaterials.columns:
                mat_candidates = usttankmaterials[usttankmaterials["clean_tank_number"] == clean_num]
                # Narrow by facility if possible
                if not mat_candidates.empty and "facility id" in mat_candidates.columns:
                    try:
                        target_digits = re.sub(r"\D", "", str(facility_id))
                        ser_digits = mat_candidates["facility id"].astype(str).str.replace(r"\D", "", regex=True)
                        mr2 = mat_candidates[ser_digits == target_digits]
                        if not mr2.empty:
                            mat_candidates = mr2
                    except Exception:
                        mr2 = mat_candidates[mat_candidates["facility id"].astype(str).str.strip() == str(facility_id)]
                        if not mr2.empty:
                            mat_candidates = mr2
                elif not mat_candidates.empty and "owner id" in mat_candidates.columns and "owner id" in owner_filtered.columns and not owner_filtered.empty:
                    try:
                        oid = str(owner_filtered["owner id"].iloc[-1]).strip()
                        mr2 = mat_candidates[mat_candidates["owner id"].astype(str).str.strip() == oid]
                        if not mr2.empty:
                            mat_candidates = mr2
                    except Exception:
                        pass
                # Prefer exact tank number match over legacy prefixes (e.g., '1' over 'R1')
                if not mat_candidates.empty and "tank number" in mat_candidates.columns:
                    exact = mat_candidates[mat_candidates["tank number"].astype(str).str.strip() == str(tank_num)]
                    if not exact.empty:
                        mat_candidates = exact
                # Prefer current in-use status if available
                if not mat_candidates.empty and "tank status" in mat_candidates.columns:
                    cur = mat_candidates[mat_candidates["tank status"].astype(str).str.contains("CURR IN USE", case=False, na=False)]
                    if not cur.empty:
                        mat_candidates = cur
                # Choose first remaining
                mat_row = mat_candidates.head(1)
            # Determine double wall value
            if not mat_row.empty:
                # Prefer named column
                dw_col = None
                for cand in [
                    "tank material double walled",
                    "double walled",
                    "double wall",
                ]:
                    if cand in mat_row.columns:
                        dw_col = cand
                        break
                if dw_col:
                    double_wall = "Yes" if is_truthy(mat_row.iloc[0][dw_col]) else "No"
                elif mat_row.shape[1] > 11:
                    # Fallback to legacy Column L (index 11)
                    col_L = mat_row.iloc[0, 11]
                    double_wall = "Yes" if str(col_L).strip().upper() == "Y" else "No"

            # Piping Type + Material: scan columns with robust matching (constrain to this facility; prefer current/ exact row)
            pipe_material = "Unknown"
            piping_type = "Unknown"
            if not ustpipe.empty and "clean_tank_number" in ustpipe.columns:
                pr_candidates = ustpipe[ustpipe["clean_tank_number"] == clean_num]
                # Narrow by facility if possible to avoid cross-facility collisions on tank numbers
                if not pr_candidates.empty and "facility id" in pr_candidates.columns:
                    try:
                        target_digits = re.sub(r"\D", "", str(facility_id))
                        ser_digits = pr_candidates["facility id"].astype(str).str.replace(r"\D", "", regex=True)
                        pr2 = pr_candidates[ser_digits == target_digits]
                        if not pr2.empty:
                            pr_candidates = pr2
                    except Exception:
                        pr2 = pr_candidates[pr_candidates["facility id"].astype(str).str.strip() == str(facility_id)]
                        if not pr2.empty:
                            pr_candidates = pr2
                elif not pr_candidates.empty and "owner id" in pr_candidates.columns and "owner id" in owner_filtered.columns and not owner_filtered.empty:
                    # Fallback: use owner id if facility id is unavailable in ustpipe
                    try:
                        oid = str(owner_filtered["owner id"].iloc[-1]).strip()
                        pr2 = pr_candidates[pr_candidates["owner id"].astype(str).str.strip() == oid]
                        if not pr2.empty:
                            pr_candidates = pr2
                    except Exception:
                        pass
                # Prefer exact tank number row over legacy prefixes (e.g., '1' over 'R1')
                if not pr_candidates.empty and "tank number" in pr_candidates.columns:
                    exact = pr_candidates[pr_candidates["tank number"].astype(str).str.strip() == str(tank_num)]
                    if not exact.empty:
                        pr_candidates = exact
                # Prefer current in-use status if present
                if not pr_candidates.empty and "tank status" in pr_candidates.columns:
                    cur = pr_candidates[pr_candidates["tank status"].astype(str).str.contains("CURR IN USE", case=False, na=False)]
                    if not cur.empty:
                        pr_candidates = cur
                # Choose first remaining
                pr = pr_candidates.head(1)
                # Piping Type
                pt_col = pick(pr, ["pipingtype", "piping type"]) if not pr.empty else None
                if pt_col:
                    val = str(pr.iloc[0][pt_col]).strip()
                    piping_type = val.title() if val else "Unknown"
                # Piping Materials
                mats = []
                if not pr.empty:
                    for col in pr.columns:
                        cl = str(col).lower()
                        if cl.startswith("pipe material"):
                            if is_truthy(pr.iloc[0][col]):
                                raw = str(col)[len("pipe material"):].strip()
                                raw = re.sub(r"^[\s:,-]+", "", raw)
                                # Include "Other Specify" text when present
                                if raw.lower() == "other":
                                    spec = ""
                                    try:
                                        spec = str(pr.iloc[0].get("pipe material other specify", "")).strip()
                                    except Exception:
                                        spec = ""
                                    if spec:
                                        mats.append(f"Other ({spec})")
                                    else:
                                        mats.append("Other")
                                else:
                                    mats.append(raw.title() or "Unknown")
                if mats:
                    pipe_material = ", ".join(mats)
                else:
                    # Legacy fiberglass fallbacks
                    if not pr.empty:
                        for col in pr.columns:
                            if "fiberglass" in str(col).lower():
                                val = str(pr.iloc[0][col]).strip().lower()
                                if val in {"y","yes","fiberglass"}:
                                    pipe_material = "Fiberglass (Double Wall)"
                                    break

            # RD Methods
            tank_rd = extract_rd(ustpipe_release, clean_num, "tank rd ")
            pipe_rd = extract_rd(ustpipe_release, clean_num, "pipe rd ")

            st.markdown(
                f"**Tank #{tank_num}: {contents}**  \n"
                f"- **Capacity:** {capacity} gallons  \n"
                f"- **Install Date:** {install_date}  \n"
                f"- **Status:** {status}  \n"
                f"- **Double Wall:** {double_wall}  \n"
                f"- **Piping Type:** {piping_type}  \n"
                f"- **Tank Material:** Fiberglass  \n"
                f"- **Piping Material:** {pipe_material}  \n"
                f"**Tank RD Methods:** {', '.join(tank_rd) if tank_rd else 'Not Listed'}  \n"
                f"**Pipe RD Methods:** {', '.join(pipe_rd) if pipe_rd else 'Not Listed'}"
            )
            st.markdown("---")

else:
    st.info("Type a Facility ID, Site Name, or Address to begin.")
