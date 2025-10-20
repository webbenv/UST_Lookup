import streamlit as st
import pandas as pd
from pandas.errors import EmptyDataError
from pathlib import Path

st.set_page_config(page_title="Webb Environmental - UST Lookup", layout="wide")
st.title("🛢️ Webb Environmental – UST Facility Lookup")

st.sidebar.header("Upload CSV Files")
tanks_file = st.sidebar.file_uploader("tanks.csv")
owner_file = st.sidebar.file_uploader("owner.csv")
# Updated label for clarity
pipe_file = st.sidebar.file_uploader("ustpipematerials.xlsx")
materials_file = st.sidebar.file_uploader("usttankmaterials.csv")
release_file = st.sidebar.file_uploader("usttankpipereleasedetection.csv")
# Optional Site Info file for physical site address
siteinfo_file = st.sidebar.file_uploader("SiteInfo.csv")

# Optional Debug Mode
debug_mode = st.sidebar.checkbox("Debug Mode", value=False, help="Show loaded CSV columns for verification.")

# Search input
facility_input = st.text_input("Search by Facility ID, Site Name, or Address:")

def read_csv_safe(file):
    """
    Reads a CSV file robustly, returns an empty DataFrame if empty or error, and normalizes columns.
    """
    if file is None:
        return pd.DataFrame()
    try:
        df = pd.read_csv(file, low_memory=False)
    except EmptyDataError:
        return pd.DataFrame()
    except Exception:
        try:
            df = pd.read_csv(file, encoding="latin1", low_memory=False)
        except EmptyDataError:
            return pd.DataFrame()
        except Exception:
            return pd.DataFrame()
    # Normalize columns to string and lowercase, strip spaces
    df.columns = df.columns.map(str).str.strip().str.lower()
    return df

# Centralized function to check if DataFrame is empty and warn/skip
def check_empty_df(df, label):
    if df is None or df.empty:
        st.warning(f"CSV '{label}' is empty or could not be loaded. Skipping downstream steps for this file.")
        return True
    return False

# Enhanced helper function to find facility id column, supporting more variations and fallback to owner id
import re
def find_facility_column(df):
    """
    Attempts to find the facility id column in a DataFrame by checking for common variations.
    Falls back to owner id if no facility id column is found.
    Includes debug logging if debug_mode is enabled.
    """
    if df is None or df.empty or not hasattr(df, "columns"):
        return None
    # Collect all columns for debug
    detected_cols = list(df.columns)
    decision_path = []
    # Common patterns for facility id columns (broader matching)
    facility_patterns = [
        "facility id", "facilityid", "facid", "fac_id", "fac id", "fac-id",
        "facility_number", "facility number", "facility_no", "facilityno", "facno", "fac no"
    ]
    # Try exact matches first
    for pat in facility_patterns:
        if pat in df.columns:
            decision_path.append(f"Exact match: '{pat}'")
            if 'debug_mode' in globals() and debug_mode:
                st.write(f"DEBUG: find_facility_column: Exact match found: {pat}")
            return pat
    # Try regex and broader patterns (allow spaces, underscores, hyphens, merged words, mixed case)
    regexes = [
        r"^fac[\s_\-]*id$",           # fac id, fac_id, fac-id
        r"^facility[\s_\-]*id$",      # facility id, facility_id, facility-id
        r"^facilityid$",              # facilityid (merged)
        r"^facid$",                   # facid
        r"^facility[\s_\-]*number$",  # facility number, facility_number
        r"^facilityno$",              # facilityno
        r"^facility[\s_\-]*no$",      # facility no, facility_no
        r"^facno$",                   # facno
        r"^fac[\s_\-]*no$",           # fac no, fac_no
    ]
    for col in df.columns:
        col_lc = col.lower().strip()
        for rex in regexes:
            if re.match(rex, col_lc):
                decision_path.append(f"Regex match: '{col}' via {rex}")
                if 'debug_mode' in globals() and debug_mode:
                    st.write(f"DEBUG: find_facility_column: Regex match found: {col} (pattern {rex})")
                return col
    # Try partial/inclusive matches (e.g., "facilityidnumber")
    for col in df.columns:
        col_lc = col.lower().replace("_", " ").replace("-", " ")
        if (("facility" in col_lc or "fac" in col_lc) and "id" in col_lc):
            decision_path.append(f"Partial/inclusive match: '{col}'")
            if 'debug_mode' in globals() and debug_mode:
                st.write(f"DEBUG: find_facility_column: Partial/inclusive match found: {col}")
            return col
    # Fallback: check for 'owner id'
    for owner_pat in ["owner id", "ownerid", "ownid"]:
        if owner_pat in df.columns:
            decision_path.append(f"Fallback match: '{owner_pat}' (owner id)")
            if 'debug_mode' in globals() and debug_mode:
                st.write(f"DEBUG: find_facility_column: Fallback to owner id: {owner_pat}")
            return owner_pat
    # Fallback: check for 'site id'
    for site_pat in ["site id", "siteid"]:
        if site_pat in df.columns:
            decision_path.append(f"Fallback match: '{site_pat}' (site id)")
            if 'debug_mode' in globals() and debug_mode:
                st.write(f"DEBUG: find_facility_column: Fallback to site id: {site_pat}")
            return site_pat
    # Debug output for not found
    if 'debug_mode' in globals() and debug_mode:
        st.write("DEBUG: find_facility_column: No facility column found.")
        st.write("DEBUG: find_facility_column: Columns checked:", detected_cols)
        st.write("DEBUG: find_facility_column: Decision path:", decision_path)
    return None

if facility_input and all([tanks_file, owner_file, pipe_file, materials_file, release_file]):
    # Load and normalize all files up front
    tanks = read_csv_safe(tanks_file)
    owner = read_csv_safe(owner_file)
    # Try to load SiteInfo.csv (optional). If not uploaded, attempt local fallback in UST_Lookup or project root.
    from pathlib import Path as _Path
    siteinfo = pd.DataFrame()
    if siteinfo_file is not None:
        siteinfo = read_csv_safe(siteinfo_file)
    else:
        try:
            _base = _Path(__file__).resolve().parent
            for cand in [
                _base / "SiteInfo.csv",
                _base.parent / "SiteInfo.csv",
            ]:
                if cand.exists():
                    try:
                        tmp = pd.read_csv(cand, low_memory=False)
                    except Exception:
                        tmp = pd.read_csv(cand, encoding="latin1", low_memory=False)
                    tmp.columns = tmp.columns.map(str).str.strip().str.lower()
                    siteinfo = tmp
                    if debug_mode:
                        st.info(f"Loaded SiteInfo from: {cand.name}")
                    break
        except Exception:
            siteinfo = pd.DataFrame()

    # Improved loading for ustpipematerials: prefer local CSV if present, else use uploaded XLSX
    # NOTE: You must have 'openpyxl' installed to read Excel files when XLSX path is used.
    if pipe_file is not None:
        try:
            pipe_file.seek(0)
        except Exception:
            pipe_file = pipe_file
        try:
            # Prefer on-disk CSV if available
            from pathlib import Path as _Path
            ustpipe = None
            try:
                base_dir = _Path(__file__).parent
                for candidate in ["ustpipematerials.csv", "ustpipematerials 2.csv"]:
                    csv_path = base_dir / candidate
                    if csv_path.exists():
                        try:
                            tmp = pd.read_csv(csv_path, low_memory=False)
                        except Exception:
                            tmp = pd.read_csv(csv_path, encoding="latin1", low_memory=False)
                        tmp.columns = tmp.columns.map(str).str.strip().str.lower().str.replace(r"\s+", " ", regex=True)
                        ustpipe = tmp
                        if debug_mode:
                            st.info(f"Using local pipe materials CSV: {candidate}")
                        break
            except Exception:
                ustpipe = None
            # If no CSV fallback, read the uploaded XLSX
            if ustpipe is None:
                # NOTE: Use openpyxl engine for .xlsx files.
                ustpipe = pd.read_excel(pipe_file, engine="openpyxl")
            # Normalize columns to string, lowercase, collapse internal whitespace, and strip spaces
            ustpipe.columns = ustpipe.columns.map(str).str.strip().str.lower().str.replace(r"\s+", " ", regex=True)
            # Add cleaned id helper columns for robust joins
            if "facility id" in ustpipe.columns:
                ustpipe["clean_facility_id"] = ustpipe["facility id"].astype(str).str.replace(r"\D", "", regex=True)
            if "owner id" in ustpipe.columns:
                ustpipe["clean_owner_id"] = ustpipe["owner id"].astype(str).str.replace(r"\D", "", regex=True)
            # DEBUG: Only show when Debug Mode is enabled
            if debug_mode:
                st.write("DEBUG: ustpipe columns:", list(ustpipe.columns))
                st.write("DEBUG: ustpipe first 5 rows:")
                st.write(ustpipe.head(5))
                st.markdown("### 🧪 Diagnostic: ustpipematerials.xlsx")
                st.write("Shape:", ustpipe.shape)
                st.write("Columns:", list(ustpipe.columns))
                st.write("First 10 rows:")
                st.write(ustpipe.head(10))
            # Print unique values for key columns (Debug Mode only)
            if debug_mode:
                key_columns = [
                    col for col in ["facility id", "owner id", "tank number", "tank status"]
                    if col in ustpipe.columns
                ]
                for col in key_columns:
                    st.write(f"Unique values for '{col}':", sorted(ustpipe[col].dropna().unique()))
        except Exception:
            ustpipe = pd.DataFrame()
    else:
        ustpipe = pd.DataFrame()

    # Enhanced loading for usttankpipereleasedetection.csv with auto-detect header and delimiter
    try:
        try:
            release_file.seek(0)
        except Exception:
            release_file = release_file
        preview_df_release = pd.read_csv(release_file, header=None, nrows=10, low_memory=False)
        header_row_release = None
        for idx, row in preview_df_release.iterrows():
            if any(str(cell).strip() != '' and str(cell).lower() != 'nan' for cell in row):
                header_row_release = idx
                break
        if header_row_release is None:
            st.warning("Could not detect header row in usttankpipereleasedetection.csv. Using default header.")
            ustpipe_release = read_csv_safe(release_file)
        else:
            delimiters = [',', '\t']
            ustpipe_release = None
            for delim in delimiters:
                try:
                    release_file.seek(0)
                except Exception:
                    release_file = release_file
                try:
                    release_candidate = pd.read_csv(release_file, header=header_row_release, delimiter=delim, low_memory=False)
                    if not all(str(col).lower().startswith("unnamed") for col in release_candidate.columns):
                        ustpipe_release = release_candidate
                        break
                except Exception:
                    continue
            if ustpipe_release is None:
                st.warning("Auto-detection of header and delimiter for usttankpipereleasedetection.csv failed. Using default read.")
                ustpipe_release = read_csv_safe(release_file)
            else:
                ustpipe_release.columns = ustpipe_release.columns.map(str).str.strip().str.lower()
    except EmptyDataError:
        st.warning("usttankpipereleasedetection.csv appears empty. Skipping this file.")
        ustpipe_release = pd.DataFrame()
    except Exception as e:
        st.warning(f"An error occurred while reading usttankpipereleasedetection.csv: {e}. Using default read.")
        ustpipe_release = read_csv_safe(release_file)

    usttankmaterials = read_csv_safe(materials_file)

    # Check for empty files and warn/skip downstream
    any_empty = False
    if check_empty_df(tanks, "tanks.csv"):
        any_empty = True
    if check_empty_df(owner, "owner.csv"):
        any_empty = True
    if check_empty_df(usttankmaterials, "usttankmaterials.csv"):
        any_empty = True
    if check_empty_df(ustpipe_release, "usttankpipereleasedetection.csv"):
        any_empty = True
    # ustpipe is allowed to be empty, so don't set any_empty on it
    if any_empty:
        st.info("Please check your CSV files. At least one is empty or could not be loaded. Skipping search.")
    else:
        # Debug mode: Show loaded columns for verification
        if debug_mode:
            st.sidebar.markdown("**Loaded CSV Columns:**")
            st.sidebar.markdown(f"* tanks.csv: {list(tanks.columns)}")
            st.sidebar.markdown(f"* owner.csv: {list(owner.columns)}")
            st.sidebar.markdown(f"* ustpipematerials.xlsx: {list(ustpipe.columns)}")
            st.sidebar.markdown(f"* usttankmaterials.csv: {list(usttankmaterials.columns)}")
            st.sidebar.markdown(f"* usttankpipereleasedetection.csv: {list(ustpipe_release.columns)}")
            if not siteinfo.empty:
                st.sidebar.markdown(f"* SiteInfo.csv: {list(siteinfo.columns)}")

        # Find facility id columns dynamically
        facility_col_tanks = find_facility_column(tanks)
        facility_col_owner = find_facility_column(owner)
        facility_col_pipe = find_facility_column(ustpipe) if not ustpipe.empty else None
        facility_col_materials = find_facility_column(usttankmaterials)
        facility_col_release = find_facility_column(ustpipe_release)
        facility_col_site = find_facility_column(siteinfo) if not siteinfo.empty else None

        # --- DEBUG OUTPUT: Show facility_col_pipe, facility_id, and unique Facility IDs in ustpipematerials.csv ---
        if debug_mode:
            st.write("DEBUG: facility_col_pipe in ustpipematerials.csv:", facility_col_pipe)
            # Show unique Facility IDs in ustpipematerials.csv if possible
            if facility_col_pipe is not None and facility_col_pipe in ustpipe.columns:
                st.write("DEBUG: Unique Facility IDs in ustpipematerials.csv:", sorted(ustpipe[facility_col_pipe].unique()))

        # Try matching Facility ID or name
        tanks_filtered = pd.DataFrame()
        # Track candidate facility IDs from owner/site searches if multiple hits
        candidate_fids = []
        try:
            fid = int(facility_input)
            if facility_col_tanks is not None and facility_col_tanks in tanks.columns:
                tanks_filtered = tanks[tanks[facility_col_tanks] == fid]
        except ValueError:
            # Fallbacks: facility name (in tanks), then owner/site name and address (in owner)
            if "facility name" in tanks.columns:
                tanks_filtered = tanks[tanks["facility name"].astype(str).str.contains(facility_input, case=False, na=False)]
            # If still empty, try searching owner.csv by site/owner name and address components
            if tanks_filtered.empty and not owner.empty:
                owner_search = owner.copy()
                # Build a full address column if components exist
                if all(x in owner_search.columns for x in ["owner address 1", "owner city", "owner state", "owner zip"]):
                    owner_search["full_address"] = (
                        owner_search["owner address 1"].astype(str).str.strip() + ", " +
                        owner_search["owner city"].astype(str).str.strip() + ", " +
                        owner_search["owner state"].astype(str).str.strip() + " " +
                        owner_search["owner zip"].astype(str).str.strip()
                    )
                else:
                    owner_search["full_address"] = ""
                # Candidate columns to search
                name_cols = [c for c in ["name", "owner name", "site name"] if c in owner_search.columns]
                search_cols = name_cols + ["full_address"]
                if search_cols:
                    mask = None
                    for col in search_cols:
                        col_mask = owner_search[col].astype(str).str.contains(facility_input, case=False, na=False)
                        mask = col_mask if mask is None else (mask | col_mask)
                    owner_matches = owner_search[mask] if mask is not None else pd.DataFrame()
                    if not owner_matches.empty and facility_col_owner in owner_matches.columns and facility_col_tanks in tanks.columns:
                        matched_fids = owner_matches[facility_col_owner].dropna().unique().tolist()
                        if matched_fids:
                            if len(matched_fids) == 1:
                                tanks_filtered = tanks[tanks[facility_col_tanks] == matched_fids[0]]
                            else:
                                candidate_fids.extend(matched_fids)
            # If still empty, try SiteInfo by name/address
            if tanks_filtered.empty and 'siteinfo' in locals() and not siteinfo.empty and facility_col_site is not None and facility_col_tanks in tanks.columns:
                site_search = siteinfo.copy()
                # Build site full address from available columns
                def pick(df, candidates):
                    for c in candidates:
                        if c in df.columns:
                            return c
                    return None
                street_col = pick(site_search, ["site address 1", "site address", "address 1", "address", "facility address 1", "facility address"]) 
                city_col = pick(site_search, ["site city", "city", "facility city"]) 
                state_col = pick(site_search, ["site state", "state", "facility state"]) 
                zip_col = pick(site_search, ["site zip", "zip", "zipcode", "zip code", "zip 5", "facility zip"]) 
                site_search["full_address"] = ""
                if all([street_col, city_col, state_col, zip_col]):
                    site_search["full_address"] = (
                        site_search[street_col].astype(str).str.strip() + ", " +
                        site_search[city_col].astype(str).str.strip() + ", " +
                        site_search[state_col].astype(str).str.strip() + " " +
                        site_search[zip_col].astype(str).str.strip()
                    )
                site_name_cols = [c for c in ["name", "site name"] if c in site_search.columns]
                site_search_cols = site_name_cols + ["full_address"]
                if site_search_cols:
                    mask = None
                    for col in site_search_cols:
                        col_mask = site_search[col].astype(str).str.contains(facility_input, case=False, na=False)
                        mask = col_mask if mask is None else (mask | col_mask)
                    site_matches = site_search[mask] if mask is not None else pd.DataFrame()
                    if not site_matches.empty and facility_col_site in site_matches.columns:
                        site_fids = site_matches[facility_col_site].dropna().unique().tolist()
                        if site_fids:
                            if len(site_fids) == 1:
                                tanks_filtered = tanks[tanks[facility_col_tanks] == site_fids[0]]
                            else:
                                candidate_fids.extend(site_fids)

        # If still not resolved and we have multiple candidates, let user pick
        if tanks_filtered.empty and candidate_fids and facility_col_tanks in tanks.columns:
            unique_fids = list(dict.fromkeys(candidate_fids))  # preserve order, remove dupes
            # Build labels with SiteInfo address if available
            def _pick(df, candidates):
                for c in candidates:
                    if c in df.columns:
                        return c
                return None
            labels = []
            for fid in unique_fids:
                # Name: prefer owner 'name', else siteinfo 'name'
                name_val = ""
                try:
                    o = owner[owner[facility_col_owner] == fid] if facility_col_owner in owner.columns else pd.DataFrame()
                    if not o.empty and "name" in o.columns:
                        name_val = str(o["name"].iloc[-1])
                except Exception:
                    pass
                if not name_val and not siteinfo.empty and facility_col_site in siteinfo.columns:
                    srow = siteinfo[siteinfo[facility_col_site] == fid]
                    if not srow.empty and "name" in srow.columns:
                        name_val = str(srow["name"].iloc[-1])
                # Site address from SiteInfo
                site_addr_val = ""
                if not siteinfo.empty and facility_col_site in siteinfo.columns:
                    srow = siteinfo[siteinfo[facility_col_site] == fid]
                    if not srow.empty:
                        street_col = _pick(srow, ["site address 1", "site address", "address 1", "address", "facility address 1", "facility address"]) 
                        city_col = _pick(srow, ["site city", "city", "facility city"]) 
                        state_col = _pick(srow, ["site state", "state", "facility state"]) 
                        zip_col = _pick(srow, ["site zip", "zip", "zipcode", "zip code", "zip 5", "facility zip"]) 
                        if all([street_col, city_col, state_col, zip_col]):
                            z = str(srow[zip_col].iloc[-1]).strip()
                            if z.endswith('.0'):
                                z = z[:-2]
                            if z.isdigit() and len(z) <= 5:
                                z = z.zfill(5)
                            site_addr_val = f"{srow[street_col].iloc[-1]}, {srow[city_col].iloc[-1]}, {srow[state_col].iloc[-1]} {z}"
                label = f"{fid} — {name_val or 'N/A'} — {site_addr_val or 'N/A'}"
                labels.append(label)
            selection = st.selectbox("Multiple facilities matched your search. Choose one:", labels, index=0)
            chosen_index = labels.index(selection) if selection in labels else 0
            chosen_fid = unique_fids[chosen_index]
            tanks_filtered = tanks[tanks[facility_col_tanks] == chosen_fid]

        if not tanks_filtered.empty:
            facility_id = tanks_filtered[facility_col_tanks].iloc[0]
            if debug_mode:
                st.write("DEBUG: facility_id selected for filtering:", facility_id)

            # Filter owner
            if facility_col_owner is not None and facility_col_owner in owner.columns:
                owner_filtered = owner[owner[facility_col_owner] == facility_id]
            else:
                st.warning("Facility ID column not found in owner.csv. Skipping owner filtering.")
                owner_filtered = pd.DataFrame()

            # Filter pipe with strengthened fallback logic: prefer facility id, then facility_col_pipe, then owner id, then tank number
            if ustpipe.empty:
                pipe_filtered = pd.DataFrame()
            else:
                # Try to use facility_col_pipe if present and matches
                pipe_filtered = None
                base_filtered = None
                # First: if a canonical 'facility id' column exists, use it directly (prefer cleaned digits-only)
                if 'facility id' in ustpipe.columns:
                    # Diagnostics for matching by facility id
                    if debug_mode:
                        try:
                            st.write("DEBUG: ustpipe dtypes:", {c: str(t) for c, t in ustpipe.dtypes.items()})
                        except Exception:
                            pass
                        st.write("DEBUG: target facility_id:", facility_id, type(facility_id))
                    # Multiple strategies to match
                    fid_series = ustpipe['facility id']
                    # Strategy 0: digits-only compare via precomputed column
                    if 'clean_facility_id' in ustpipe.columns:
                        import re as _re
                        target_digits = _re.sub(r"\D", "", str(facility_id))
                        mask_clean = ustpipe['clean_facility_id'] == target_digits
                        if debug_mode:
                            st.write("DEBUG: ustpipe facility-id clean digits matches:", int(mask_clean.sum()))
                        if mask_clean.any():
                            base_filtered = ustpipe[mask_clean]
                    # Strategy A: numeric compare
                    try:
                        fid_num = pd.to_numeric(fid_series, errors='coerce')
                        fid_target = int(pd.to_numeric(facility_id))
                        mask_num = (fid_num == fid_target)
                        if debug_mode:
                            st.write("DEBUG: ustpipe facility-id numeric matches:", int(mask_num.sum()))
                        if mask_num.any():
                            base_filtered = ustpipe[mask_num]
                    except Exception:
                        pass
                    # Strategy B: normalized string compare (strip .0)
                    if base_filtered is None or base_filtered.empty:
                        def norm_id(x):
                            s = str(x).strip()
                            if s.endswith('.0'):
                                s = s[:-2]
                            return s
                        mask_norm = fid_series.apply(norm_id) == norm_id(facility_id)
                        if debug_mode:
                            try:
                                st.write("DEBUG: ustpipe facility-id normalized string matches:", int(mask_norm.sum()))
                            except Exception:
                                pass
                        if mask_norm.any():
                            base_filtered = ustpipe[mask_norm]
                    # Strategy C: raw string compare
                    if base_filtered is None or base_filtered.empty:
                        mask_str = fid_series.astype(str).str.strip() == str(facility_id)
                        if debug_mode:
                            try:
                                st.write("DEBUG: ustpipe facility-id raw string matches:", int(mask_str.sum()))
                            except Exception:
                                pass
                        if mask_str.any():
                            base_filtered = ustpipe[mask_str]
                    # Strategy D: digits-only compare (handles thousand separators or formatting)
                    if base_filtered is None or base_filtered.empty:
                        def digits_only(x):
                            return re.sub(r"\D", "", str(x))
                        mask_digits = fid_series.apply(digits_only) == digits_only(facility_id)
                        if debug_mode:
                            try:
                                st.write("DEBUG: ustpipe facility-id digits-only matches:", int(mask_digits.sum()))
                            except Exception:
                                pass
                        if mask_digits.any():
                            base_filtered = ustpipe[mask_digits]
                    if debug_mode:
                        st.write("DEBUG: ustpipe filtering by explicit 'facility id'. Rows matched:", 0 if base_filtered is None else len(base_filtered))
                # Second: use detected facility column if provided
                if (base_filtered is None or base_filtered.empty) and facility_col_pipe is not None and facility_col_pipe in ustpipe.columns:
                    try:
                        ustpipe[facility_col_pipe] = pd.to_numeric(ustpipe[facility_col_pipe], errors='coerce')
                        base_filtered = ustpipe[ustpipe[facility_col_pipe] == int(facility_id)]
                        if debug_mode:
                            st.write(f"DEBUG: ustpipe filtering by detected column '{facility_col_pipe}'. Rows matched:", len(base_filtered))
                    except Exception:
                        base_filtered = ustpipe[ustpipe[facility_col_pipe].astype(str) == str(facility_id)]
                # Third: fallback to 'owner id' but compare to the actual owner id, not facility id
                if (base_filtered is None or base_filtered.empty) and 'owner id' in ustpipe.columns:
                    current_owner_id = None
                    if not owner_filtered.empty and 'owner id' in owner_filtered.columns:
                        try:
                            current_owner_id = pd.to_numeric(owner_filtered['owner id'], errors='coerce').dropna().astype(int).iloc[-1]
                        except Exception:
                            current_owner_id = owner_filtered['owner id'].iloc[-1]
                    if current_owner_id is not None:
                        # Normalize owner id comparison (clean digits, numeric, raw string)
                        series = ustpipe['owner id']
                        matched = None
                        # 0) cleaned digits-only
                        if 'clean_owner_id' in ustpipe.columns:
                            import re as _re
                            target_digits = _re.sub(r"\D", "", str(current_owner_id))
                            mask = ustpipe['clean_owner_id'] == target_digits
                            matched = ustpipe[mask]
                            if debug_mode:
                                st.write("DEBUG: ustpipe owner-id clean digits matches:", int(mask.sum()))
                        # A) numeric compare
                        try:
                            ser_num = pd.to_numeric(series, errors='coerce')
                            oid_num = int(pd.to_numeric(current_owner_id))
                            mask = (ser_num == oid_num)
                            matched = ustpipe[mask]
                            if debug_mode:
                                st.write("DEBUG: ustpipe owner-id numeric matches:", int(mask.sum()))
                        except Exception:
                            matched = None
                        # B) raw string compare
                        if matched is None or matched.empty:
                            mask = series.astype(str).str.strip() == str(current_owner_id)
                            matched = ustpipe[mask]
                            if debug_mode:
                                st.write("DEBUG: ustpipe owner-id raw string matches:", int(mask.sum()))
                        # C) digits-only compare
                        if matched is None or matched.empty:
                            def digits_only(x):
                                return re.sub(r"\D", "", str(x))
                            mask = series.apply(digits_only) == digits_only(current_owner_id)
                            matched = ustpipe[mask]
                            if debug_mode:
                                st.write("DEBUG: ustpipe owner-id digits-only matches:", int(mask.sum()))
                        base_filtered = matched
                        if debug_mode:
                            st.write("DEBUG: ustpipe fallback: used 'owner id' with value",
                                     current_owner_id, "Rows matched:", 0 if matched is None else len(matched))
                # Fourth: last resort, try matching tank number directly (rarely useful)
                if (base_filtered is None or base_filtered.empty) and 'tank number' in ustpipe.columns:
                    base_filtered = ustpipe[ustpipe['tank number'].astype(str) == str(facility_id)]
                    if debug_mode:
                        st.write("DEBUG: ustpipe fallback: used 'tank number' vs facility_id (may be empty). Rows matched:", len(base_filtered))
                # If no base filter available, attempt on-disk CSV fallback for ustpipematerials
                if base_filtered is None or (hasattr(base_filtered, 'empty') and base_filtered.empty):
                    try:
                        base_dir = Path(__file__).parent
                        fallback_paths = [
                            base_dir / 'ustpipematerials.csv',
                            base_dir / 'ustpipematerials 2.csv'
                        ]
                        fallback_df = None
                        for p in fallback_paths:
                            if p.exists():
                                try:
                                    tmp = pd.read_csv(p, low_memory=False)
                                except Exception:
                                    tmp = pd.read_csv(p, encoding='latin1', low_memory=False)
                                tmp.columns = tmp.columns.map(str).str.strip().str.lower()
                                fallback_df = tmp
                                st.info(f"Loaded pipe materials from fallback CSV: {p.name}")
                                break
                        if fallback_df is not None:
                            # Repeat facility/owner matching against fallback_df
                            base_filtered = None
                            if 'facility id' in fallback_df.columns:
                                fid_series = fallback_df['facility id']
                                # numeric
                                try:
                                    fid_num = pd.to_numeric(fid_series, errors='coerce')
                                    fid_target = int(pd.to_numeric(facility_id))
                                    mask_num = (fid_num == fid_target)
                                    if mask_num.any():
                                        base_filtered = fallback_df[mask_num]
                                except Exception:
                                    pass
                                if base_filtered is None or base_filtered.empty:
                                    def norm_id(x):
                                        s = str(x).strip()
                                        return s[:-2] if s.endswith('.0') else s
                                    mask_norm = fid_series.apply(norm_id) == norm_id(facility_id)
                                    if mask_norm.any():
                                        base_filtered = fallback_df[mask_norm]
                                if base_filtered is None or base_filtered.empty:
                                    def digits_only(x):
                                        import re as _re
                                        return _re.sub(r"\D", "", str(x))
                                    mask_digits = fid_series.apply(digits_only) == digits_only(facility_id)
                                    if mask_digits.any():
                                        base_filtered = fallback_df[mask_digits]
                            if (base_filtered is None or base_filtered.empty) and 'owner id' in fallback_df.columns and not owner_filtered.empty and 'owner id' in owner_filtered.columns:
                                try:
                                    current_owner_id = pd.to_numeric(owner_filtered['owner id'], errors='coerce').dropna().astype(int).iloc[-1]
                                except Exception:
                                    current_owner_id = owner_filtered['owner id'].iloc[-1]
                                series = fallback_df['owner id']
                                try:
                                    ser_num = pd.to_numeric(series, errors='coerce')
                                    oid_num = int(pd.to_numeric(current_owner_id))
                                    mask = (ser_num == oid_num)
                                    if mask.any():
                                        base_filtered = fallback_df[mask]
                                except Exception:
                                    pass
                                if base_filtered is None or base_filtered.empty:
                                    mask = series.astype(str).str.strip() == str(current_owner_id)
                                    if mask.any():
                                        base_filtered = fallback_df[mask]
                                if base_filtered is None or base_filtered.empty:
                                    def digits_only2(x):
                                        import re as _re
                                        return _re.sub(r"\D", "", str(x))
                                    mask = series.apply(digits_only2) == digits_only2(current_owner_id)
                                    if mask.any():
                                        base_filtered = fallback_df[mask]
                        else:
                            if debug_mode:
                                st.info("No local CSV fallback for ustpipematerials found.")
                    except Exception as _e:
                        if debug_mode:
                            st.warning(f"CSV fallback for ustpipematerials failed: {_e}")
                # If still no base filter
                if base_filtered is None:
                    if debug_mode:
                        st.warning("No suitable column found in ustpipematerials to join on. Skipping pipe filtering.")
                    pipe_filtered = pd.DataFrame()
                # Now apply tank status filter if possible, but don't over-filter
                if base_filtered is not None:
                    pipe_filtered = base_filtered
                    if 'tank status' in ustpipe.columns:
                        tmp = base_filtered[base_filtered["tank status"] == "CURR IN USE"]
                        # If filtering by status removes all rows, fall back to base_filtered
                        if not tmp.empty:
                            pipe_filtered = tmp
                if pipe_filtered is None:
                    pipe_filtered = pd.DataFrame()
            # Additional debug: show resulting pipe_filtered tanks
            if debug_mode and (isinstance(pipe_filtered, pd.DataFrame)):
                if not pipe_filtered.empty and 'tank number' in pipe_filtered.columns:
                    st.write("DEBUG: Unique tank numbers in pipe_filtered:", sorted(pipe_filtered['tank number'].astype(str).unique()))

            # Filter tank materials
            if facility_col_materials is not None and facility_col_materials in usttankmaterials.columns:
                tank_materials_filtered = usttankmaterials[usttankmaterials[facility_col_materials] == facility_id]
            else:
                st.warning("Facility ID column not found in usttankmaterials.csv. Skipping tank materials filtering.")
                tank_materials_filtered = pd.DataFrame()

            # Filter release
            if facility_col_release is not None and facility_col_release in ustpipe_release.columns:
                release_filtered = ustpipe_release[ustpipe_release[facility_col_release] == facility_id]
            else:
                st.warning("Facility ID column not found in usttankpipereleasedetection.csv. Skipping release filtering.")
                release_filtered = pd.DataFrame()

            # ---- INFO BOX ----
            dealer_id = owner_filtered["owner id"].max() if not owner_filtered.empty and "owner id" in owner_filtered.columns else "N/A"
            owner_name = owner_filtered["owner name"].iloc[-1] if not owner_filtered.empty and "owner name" in owner_filtered.columns else "N/A"
            site_name = owner_filtered["name"].iloc[-1] if not owner_filtered.empty and "name" in owner_filtered.columns else "N/A"
            # Helper: normalize ZIP (remove trailing .0, keep leading zeros)
            def _normalize_zip(val):
                s = str(val).strip()
                if s.endswith('.0'):
                    s = s[:-2]
                # If digits and length <= 5, left-pad to 5 to preserve leading zeros
                if s.isdigit() and len(s) <= 5:
                    s = s.zfill(5)
                return s

            # Owner Address
            owner_address = (
                f"{owner_filtered['owner address 1'].iloc[-1]}, "
                f"{owner_filtered['owner city'].iloc[-1]}, "
                f"{owner_filtered['owner state'].iloc[-1]} {_normalize_zip(owner_filtered['owner zip'].iloc[-1])}"
                if not owner_filtered.empty
                and all(x in owner_filtered.columns for x in ["owner address 1", "owner city", "owner state", "owner zip"])
                else "N/A"
            )
            # Site Address from SiteInfo.csv (optional)
            site_address = "N/A"
            if facility_col_site is not None and facility_col_site in siteinfo.columns:
                site_filtered = siteinfo[siteinfo[facility_col_site] == facility_id]
                if not site_filtered.empty:
                    def pick(df, candidates):
                        for c in candidates:
                            if c in df.columns:
                                return c
                        return None
                    street_col = pick(site_filtered, [
                        "site address 1", "site address", "address 1", "address", "facility address 1", "facility address"
                    ])
                    city_col = pick(site_filtered, ["site city", "city", "facility city"]) 
                    state_col = pick(site_filtered, ["site state", "state", "facility state"]) 
                    # Include common variants like "zip 5" used in SiteInfo.csv
                    zip_col = pick(site_filtered, ["site zip", "zip", "zipcode", "zip code", "zip 5", "facility zip"]) 
                    if all([street_col, city_col, state_col, zip_col]):
                        site_zip_val = site_filtered[zip_col].iloc[-1]
                        site_address = (
                            f"{site_filtered[street_col].iloc[-1]}, "
                            f"{site_filtered[city_col].iloc[-1]}, "
                            f"{site_filtered[state_col].iloc[-1]} {_normalize_zip(site_zip_val)}"
                        )

            st.markdown(
                f"### 🧾 Facility Summary\n"
                f"**Owner:** {owner_name}\n\n"
                f"**Site Name:** {site_name}\n\n"
                f"**Owner Address:** {owner_address}\n\n"
                f"**Site Address:** {site_address}\n\n"
                f"**Facility ID:** {facility_id}\n\n"
                f"**Dealer ID:** {dealer_id}\n"
            )

            # ---- ACTIVE TANKS ----
            st.markdown("### ⛽ Active Tanks")

            active_tanks = tanks_filtered[tanks_filtered["tank status"] == "CURR IN USE"] if "tank status" in tanks_filtered.columns else pd.DataFrame()

            # RD method mapping dictionary (for readability)
            rd_method_map = {
                "automatic tank gauging": "Automatic Tank Gauging (ATG)",
                "interstitial monitoring": "Interstitial Monitoring",
                "statistical inventory reconciliation": "Statistical Inventory Reconciliation (SIR)",
                "tank tightness testing": "Tank Tightness Testing",
                "line tightness testing": "Line Tightness Testing",
                "vapor monitoring": "Vapor Monitoring",
                "groundwater monitoring": "Groundwater Monitoring",
                "inventory control": "Inventory Control",
                "secondary containment": "Secondary Containment",
                "visual inspection": "Visual Inspection",
                "line leak detector": "Line Leak Detector",
                "pressure/vacuum monitoring": "Pressure/Vacuum Monitoring",
                "automatic line leak detector": "Automatic Line Leak Detector",
                "cathodic protection": "Cathodic Protection",
                "manual tank gauging": "Manual Tank Gauging",
                "manual line leak detector": "Manual Line Leak Detector",
                "statistical inventory reconciliation (sir)": "Statistical Inventory Reconciliation (SIR)"
            }

            # Helper to extract RD methods from usttankpipereleasedetection.csv for a tank and type ('tank' or 'pipe')
            def extract_rd_methods(release_df, tank_num, rd_type_prefix):
                if release_df.empty or "tank number" not in release_df.columns:
                    return []
                # Find the row for this tank
                release_row = release_df[release_df["tank number"] == tank_num]
                rd_methods = []
                if not release_row.empty:
                    for col in release_row.columns:
                        # Only match columns that start with the correct prefix
                        if col.lower().startswith(rd_type_prefix) and str(release_row[col].iloc[0]).strip().upper() == "Y":
                            clean_name = col[len(rd_type_prefix):].strip().lower()
                            mapped_name = rd_method_map.get(clean_name, None)
                            if mapped_name:
                                rd_methods.append(mapped_name)
                            else:
                                rd_methods.append(clean_name.title())
                return rd_methods

            # --- DEBUG OUTPUT: Compare tank numbers in tanks_filtered and pipe_filtered ---
            if debug_mode:
                st.write("DEBUG: Unique tank numbers in tanks_filtered:", sorted(tanks_filtered["tank number"].unique()) if "tank number" in tanks_filtered.columns else [])
                st.write("DEBUG: Unique tank numbers in pipe_filtered:", sorted(pipe_filtered["tank number"].unique()) if not pipe_filtered.empty and "tank number" in pipe_filtered.columns else [])

            # --- Normalization Step: Unify tank number formats for tanks, usttankmaterials, ustpipematerials, and usttankpipereleasedetection ---
            import re
            def clean_tank_number(val):
                """Normalize tank number to digits only (e.g., R1 -> 1, 1M -> 1, RA2 -> 2)."""
                if pd.isna(val):
                    return ""
                s = str(val).strip()
                # Keep digits only to harmonize variants
                s = re.sub(r"[^0-9]", "", s)
                return s

            # Helper to safely format capacity with thousands separators
            def format_capacity(value):
                try:
                    num = pd.to_numeric(value, errors="coerce")
                    if pd.isna(num):
                        return str(value)
                    # Cast to int for display (capacities are whole gallons)
                    return f"{int(num):,}"
                except Exception:
                    return str(value)

            # Truthy checker used for Y/Yes/True/1/X
            def is_truthy(val):
                s = str(val).strip().lower()
                return s in {"y", "yes", "true", "t", "1", "x"}

            # Add cleaned tank number columns (if they exist)
            if "tank number" in active_tanks.columns:
                active_tanks = active_tanks.copy()
                active_tanks["clean_tank_number"] = active_tanks["tank number"].apply(clean_tank_number)
            if not tank_materials_filtered.empty and "tank number" in tank_materials_filtered.columns:
                tank_materials_filtered = tank_materials_filtered.copy()
                tank_materials_filtered["clean_tank_number"] = tank_materials_filtered["tank number"].apply(clean_tank_number)
            if not pipe_filtered.empty and "tank number" in pipe_filtered.columns:
                pipe_filtered = pipe_filtered.copy()
                pipe_filtered["clean_tank_number"] = pipe_filtered["tank number"].apply(clean_tank_number)
            if not release_filtered.empty and "tank number" in release_filtered.columns:
                release_filtered = release_filtered.copy()
                release_filtered["clean_tank_number"] = release_filtered["tank number"].apply(clean_tank_number)

            for idx, row in active_tanks.iterrows():
                tank_num = row["tank number"] if "tank number" in row else "N/A"
                clean_num = row["clean_tank_number"] if "clean_tank_number" in row else str(tank_num)
                contents = row["contents"] if "contents" in row else "N/A"
                capacity = row["capacity"] if "capacity" in row else "N/A"
                install_date = row["install date"] if "install date" in row else "N/A"
                status = row["tank status"] if "tank status" in row else "N/A"

                # Double Wall
                if not tank_materials_filtered.empty and "clean_tank_number" in tank_materials_filtered.columns:
                    material_row = tank_materials_filtered[tank_materials_filtered["clean_tank_number"] == clean_num]
                else:
                    material_row = pd.DataFrame()
                double_wall = "No"
                if not material_row.empty and material_row.shape[1] > 11:
                    col_L = material_row.iloc[0, 11]  # Column L
                    double_wall = "Yes" if str(col_L).strip().upper() == "Y" else "No"

                # Piping (Normalized matching for tank number)
                pipe_material = "Unknown"
                pipe_row = pd.DataFrame()
                if not pipe_filtered.empty and "clean_tank_number" in pipe_filtered.columns:
                    pipe_row = pipe_filtered[
                        pipe_filtered["clean_tank_number"] == clean_num
                    ]
                # Improved: scan all "pipe material ..." columns, collect those with a truthy value
                materials_detected = []
                if not pipe_row.empty:
                    for col in pipe_row.columns:
                        col_lc = str(col).lower()
                        if col_lc.startswith("pipe material"):
                            val = pipe_row.iloc[0][col]
                            if is_truthy(val):
                                # Extract material name after the prefix and strip punctuation like ':' or '-'
                                raw_name = str(col)[len("pipe material"):].strip()
                                raw_name = re.sub(r"^[\s:,-]+", "", raw_name)
                                material_name = raw_name.title() if raw_name else "Unknown"
                                materials_detected.append(material_name)
                    if materials_detected:
                        pipe_material = ", ".join(materials_detected)
                    else:
                        # Fallback: look for "fiberglass" anywhere for legacy logic
                        found_fiberglass = False
                        for col in pipe_row.columns:
                            if "fiberglass" in str(col).lower():
                                val = str(pipe_row.iloc[0][col]).strip().lower()
                                if val in ("y", "yes", "fiberglass"):
                                    pipe_material = "Fiberglass (Double Wall)"
                                    found_fiberglass = True
                                    break
                        if not found_fiberglass:
                            # Fallback: check all cells for value 'fiberglass'
                            for col in pipe_row.columns:
                                val = str(pipe_row.iloc[0][col]).strip().lower()
                                if val == "fiberglass":
                                    pipe_material = "Fiberglass (Double Wall)"
                                    found_fiberglass = True
                                    break
                        if not found_fiberglass:
                            # Fallback: check for "pipe material unknown"
                            unknown_cols = [col for col in pipe_row.columns if "pipe material unknown" in str(col).lower()]
                            for col in unknown_cols:
                                val = str(pipe_row.iloc[0][col]).strip().lower()
                                if val in ("y", "yes", "unknown"):
                                    pipe_material = "Unknown"
                                    break
                        if not found_fiberglass and pipe_material == "Unknown":
                            # Additional fallback: single descriptive column like 'piping material'
                            for candidate in ["piping material", "pipe material", "pipe materials"]:
                                if candidate in map(str.lower, pipe_row.columns):
                                    try:
                                        val = str(pipe_row.iloc[0][candidate]).strip()
                                        if val:
                                            pipe_material = val
                                            break
                                    except Exception:
                                        pass
                # --- Debug output for pipe_material still "Unknown"
                if pipe_material == "Unknown" and debug_mode:
                    st.write(f"DEBUG: pipe_material is 'Unknown' for Tank #{tank_num} ({contents})")
                    st.write("DEBUG: pipe_row columns:", list(pipe_row.columns))
                    st.write("DEBUG: pipe_row values:", pipe_row.to_dict(orient='records'))

                # --- RD METHODS Extraction ---
                # Use usttankpipereleasedetection.csv for both Tank RD and Pipe RD, using normalized tank number
                def extract_rd_methods_clean(release_df, clean_tank_num, rd_type_prefix):
                    if release_df.empty or "clean_tank_number" not in release_df.columns:
                        return []
                    release_row = release_df[release_df["clean_tank_number"] == clean_tank_num]
                    rd_methods = []
                    if not release_row.empty:
                        for col in release_row.columns:
                            if col.lower().startswith(rd_type_prefix) and str(release_row[col].iloc[0]).strip().upper() == "Y":
                                clean_name = col[len(rd_type_prefix):].strip().lower()
                                mapped_name = rd_method_map.get(clean_name, None)
                                if mapped_name:
                                    rd_methods.append(mapped_name)
                                else:
                                    rd_methods.append(clean_name.title())
                    return rd_methods

                tank_rd_methods = extract_rd_methods_clean(release_filtered, clean_num, "tank rd ")
                pipe_rd_methods = extract_rd_methods_clean(release_filtered, clean_num, "pipe rd ")

                tank_rd_method_str = ", ".join(tank_rd_methods) if tank_rd_methods else "Not Listed"
                pipe_rd_method_str = ", ".join(pipe_rd_methods) if pipe_rd_methods else "Not Listed"

                # Improved output formatting for readability
                st.markdown(
                    f"#### Tank #{tank_num}: {contents}\n"
                    f"- **Capacity:** {format_capacity(capacity)} gallons\n"
                    f"- **Install Date:** {install_date}\n"
                    f"- **Status:** {status}\n"
                    f"- **Double Wall:** {double_wall}\n"
                    f"- **Tank Material:** Fiberglass\n"
                    f"- **Piping Material:** {pipe_material}\n\n"
                    f"**Tank RD Methods:** {tank_rd_method_str}\n\n"
                    f"**Pipe RD Methods:** {pipe_rd_method_str}\n"
                )
                # Add spacing between tanks for clarity
                st.markdown("---\n")
        else:
            st.warning("No facility found for that ID or name.")
else:
    st.info("Upload CSVs and enter a search term to begin.")
