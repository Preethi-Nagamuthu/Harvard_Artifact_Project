%%writefile app.py
import streamlit as st
import mysql.connector
import extra_streamlit_components as stx
import pandas as pd
import requests
import time
import numpy as np

url = "https://api.harvardartmuseums.org/object"

def fetch_classification(API_key, classification, target=2500, page_size=100):

    results = []
    
    page = 1

    while len(results) < target:
        params = {
            "apikey": API_key,
            "classification": classification,
            "size": page_size,
            "page": page
        }
        r = requests.get(url, params=params, timeout=60)
        r.raise_for_status()
        data = r.json()

        records = data.get("records", [])
        if not records:
            break  # no more data

        results.extend(records)
        page += 1
        time.sleep(0.15)  # polite delay

        # stop when we've reached the last page (if info.pages exists)
        info = data.get("info") or {}
        if page > int(info.get("pages", page)):
            break

    return results[:target]


def fetch_all_classifications(API_key, classifications, target=2500):

    all_records = {}
    for c in classifications:
        print(f"Fetching {c}...")
        all_records[c] = fetch_classification(API_key, c, target=target)
        print(f"{c}: {len(all_records[c])} records fetched")
    return all_records

st.markdown(f"""
    <style>
    .stApp {{
        background-image: url("https://live.staticflickr.com/5590/14418116179_6f8536c5bc_b.jpg");
        background-size: cover;
        background-attachment: fixed;
    }}
    </style>
""", unsafe_allow_html=True)
st.markdown("<h1 style='text-align: center; color: black;'>🏦Harvard Artifacts Dashboard</h1>", unsafe_allow_html=True)

def styled_header(text, size=1):
    st.markdown(f"<h{size} style='color: orange; font-weight: bold; margin: 0.2rem 0 0.6rem;'>{text}</h{size}>",
                unsafe_allow_html=True)


def get_connection():
    return mysql.connector.connect(
    host="localhost",
    port=3306,
    user="root",
    password="",
    database = "harvard_artifact",
    connection_timeout=300
    

)
    
def get_columns(table_name, limit=1):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(f"SELECT * FROM {table_name} LIMIT {limit}")
    rows = cur.fetchall()
    cols = [desc[0] for desc in cur.description]
    cur.close()
    conn.close()
    return pd.DataFrame(rows, columns=cols)

    
api_key = st.text_input("Enter your Harvard API Key:", type="password")

classifications = ["Coins", "Drawings", "Prints","Fragments","Photographs"]
classification = st.selectbox("Select Classification", classifications)

META_COLS = ["id","title","culture","period","century","medium","dimensions","description","department","classification","accessionyear","accessionmethod"]
MEDIA_COLS = ["objectid","imagecount","mediacount","colorcount","ranks","datebegin","dateend"]
COLOR_COLS = ["objectid","color","spectrum","hue","percent","css3"]

def prepare_dataframes(records, fallback_classification=None):
    rows_meta, rows_media, rows_colors = [], [], []

    for obj in records:
        oid = obj.get("id")

        # Skip if id is missing or not an integer
        if oid is None or not str(oid).isdigit():
            continue

        oid = int(oid)  # force integer

        # --- Metadata ---
        rows_meta.append({
            "id": oid,
            "title": obj.get("title"),
            "culture": obj.get("culture"),
            "period": obj.get("period"),
            "century": obj.get("century"),
            "medium": obj.get("medium"),
            "dimensions": obj.get("dimensions"),
            "description": obj.get("description") or obj.get("labeltext") or obj.get("creditline"),
            "department": obj.get("department"),
            "classification": obj.get("classification") or fallback_classification,
            "accessionyear": obj.get("accessionyear"),
            "accessionmethod": obj.get("accessionmethod"),
        })

        # --- Media ---
        rows_media.append({
            "objectid": oid,
            "imagecount": obj.get("imagecount"),
            "mediacount": obj.get("mediacount") if obj.get("mediacount") is not None else obj.get("imagecount"),
            "colorcount": len(obj.get("colors") or []),
            "ranks": obj.get("rank"),
            "datebegin": obj.get("datebegin"),
            "dateend": obj.get("dateend"),
        })

        # --- Colors ---
        for c in (obj.get("colors") or []):
            rows_colors.append({
                "objectid": oid,
                "color": c.get("color"),
                "spectrum": c.get("spectrum"),
                "hue": c.get("hue"),
                "percent": c.get("percent"),
                "css3": c.get("css3") or c.get("closest_palette_color_parent"),
            })

    df_meta = pd.DataFrame(rows_meta)[META_COLS]
    df_media = pd.DataFrame(rows_media)[MEDIA_COLS]
    df_colors = pd.DataFrame(rows_colors)[COLOR_COLS] if rows_colors else pd.DataFrame(columns=COLOR_COLS)
    return df_meta, df_media, df_colors

if st.button("Collect Data"):
    if api_key:
        data = fetch_classification(api_key, classification)
        st.session_state["data"] = data
        # NEW: also build the three DFs so Insert step finds them
        df_meta, df_media, df_colors = prepare_dataframes(data, fallback_classification=classification)
        st.session_state["df_meta"] = df_meta
        st.session_state["df_media"] = df_media
        st.session_state["df_colors"] = df_colors
        st.success(f"✅ Fetched {len(data)} records for {classification}")
    else:
        st.error("Please enter a valid API Key")

def clean_for_sql(df, cols):

    out = df.reindex(columns=cols)
    int_cols = ["id", "objectid", "accessionyear",
                "imagecount", "mediacount", "colorcount",
                "ranks", "datebegin", "dateend"]

    float_cols = ["percent"]

    for col in int_cols:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")
            out[col] = out[col].where(pd.notnull(out[col]), None).astype(object)

    for col in float_cols:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")
            out[col] = out[col].where(pd.notnull(out[col]), None).astype(object)
    out = out.where(pd.notnull(out), None).astype(object)
    return out

def insert_metadata(cur, df):
    META_COLS = ["id","title","culture","period","century","medium","dimensions","description","department","classification","accessionyear","accessionmethod"]
    df = df.drop_duplicates(subset=["id"], keep="first")
    data = clean_for_sql(df, META_COLS).values.tolist()
    cur.executemany(
        "INSERT IGNORE INTO artifact_metadata (id,title,culture,period,century,medium,dimensions,description,department,classification,accessionyear,accessionmethod) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
        data
    )

def insert_media(cur, df):
    MEDIA_COLS = ["objectid","imagecount","mediacount","colorcount","ranks","datebegin","dateend"]
    data = clean_for_sql(df, MEDIA_COLS).values.tolist()
    cur.executemany(
        "INSERT INTO artifact_media (objectid,imagecount,mediacount,colorcount,ranks,datebegin,dateend) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s)",
        data
    )

def insert_colors(cur, df):
    COLOR_COLS = ["objectid","color","spectrum","hue","percent","css3"]
    if df is None or df.empty:
        return
    data = clean_for_sql(df, COLOR_COLS).values.tolist()
    cur.executemany(
        "INSERT INTO artifact_colors (objectid,color,spectrum,hue,percent,css3) "
        "VALUES (%s,%s,%s,%s,%s,%s)",
        data
    )
tabs = st.tabs(["Select Your Choice", "Migrate to SQL", "SQL Queries"])



with tabs[0]:

    if "data" in st.session_state and st.session_state["data"]:
        first_obj = st.session_state["data"][0]  # first record from API fetch

        col1, col2, col3 = st.columns(3)

        # --- Metadata ---
        with col1:
            st.subheader("🗂️Metadata")
            meta_display = {
                "id": first_obj.get("id"),
                "title": first_obj.get("title"),
                "culture": first_obj.get("culture"),
                "period": first_obj.get("period"),
                "century": first_obj.get("century"),
                "medium": first_obj.get("medium"),
                "dimensions": first_obj.get("dimensions"),
                "description": first_obj.get("description") or first_obj.get("labeltext") or first_obj.get("creditline"),
                "department": first_obj.get("department"),
                "classification": first_obj.get("classification"),
                "accessionyear": first_obj.get("accessionyear"),
                "accessionmethod": first_obj.get("accessionmethod")
            }
            st.json(meta_display)

        # --- Media ---
        with col2:
            st.subheader("📽️Media")
            media_display = {
                "id": first_obj.get("id"),
                "imagecount": first_obj.get("imagecount"),
                "mediacount": first_obj.get("mediacount") if first_obj.get("mediacount") is not None else first_obj.get("imagecount"),
                "colorcount": len(first_obj.get("colors") or []),
                "ranks": first_obj.get("rank"),
                "datebegin": first_obj.get("datebegin"),
                "dateend": first_obj.get("dateend")

            }
            st.json(media_display)

        # --- Colours ---
        with col3:
            st.subheader("🗃️Colours")
            colors = first_obj.get("colors") or []
            st.json(colors)



    else:
        st.info("Click 'Collect Data' to fetch records for the selected classification.")
    


with tabs[1]:
    styled_header("📥Insert the collected data", 2)
    st.write("Click below to insert Artifacts Metadata, Media, and Colours into MySQL.")

    if st.button("Insert", key="insert_all"):

        df_meta = None; df_media = None; df_colors = None
        if 'df_meta' in st.session_state: df_meta = st.session_state['df_meta']
        if 'df_media' in st.session_state: df_media = st.session_state['df_media']
        if 'df_colors' in st.session_state: df_colors = st.session_state['df_colors']

        glb = globals()
        if df_meta is None and 'df_meta' in glb and isinstance(glb['df_meta'], pd.DataFrame):
            df_meta = glb['df_meta']
        if df_media is None and 'df_media' in glb and isinstance(glb['df_media'], pd.DataFrame):
            df_media = glb['df_media']
        if df_colors is None and 'df_colors' in glb and isinstance(glb['df_colors'], pd.DataFrame):
            df_colors = glb['df_colors']

        try:
            if df_meta is None or df_media is None or df_colors is None:
                st.warning("No dataframes found to insert (df_meta, df_media, df_colors). Prepare/collect data first.")
            else:
                conn = get_connection()
                cur = conn.cursor()
                insert_metadata(cur, df_meta)
                insert_media(cur, df_media)
                insert_colors(cur, df_colors)
                conn.commit()
                st.success("Data inserted successfully")

                styled_header("Inserted Data:", 2)
                st.markdown("**Artifacts Metadata**"); st.dataframe(df_meta[META_COLS].head(10), use_container_width=True)
                st.markdown("**Media**"); st.dataframe(df_media[MEDIA_COLS].head(10), use_container_width=True)
                st.markdown("**Colours**"); st.dataframe(df_colors[COLOR_COLS].head(10), use_container_width=True)
        except Exception as e:
            st.error(f"Insert failed: {e}")
        finally:
            try:
                cur.close(); conn.close()
            except:
                pass


with tabs[2]:
    styled_header("🖇️SQL Queries", 2)

    queries = {
        "Q1. List all artifacts from the 11th century": "SELECT id, title, culture, century FROM artifact_metadata WHERE century = '11th century';",
        "Q2. Unique cultures represented": "SELECT DISTINCT culture FROM artifact_metadata WHERE culture IS NOT NULL;",
        "Q3. List all artifacts from the Archaic Period": "SELECT id, title FROM artifact_metadata WHERE period = 'Archaic';",
        "Q4. Titles ordered by accession year (desc)": "SELECT title, accessionyear FROM artifact_metadata WHERE accessionyear IS NOT NULL ORDER BY accessionyear DESC;",
        "Q5. Artifacts per department": "SELECT department, COUNT(*) as artifacts FROM artifact_metadata GROUP BY department;",
        "Q6. Artifacts with more than 3 images": "SELECT m.objectid FROM artifact_media m WHERE m.imagecount > 3;",
        "Q7. Average rank of all artifacts": "SELECT AVG(ranks) AS avg_rank FROM artifact_media;",
        "Q8. Higher mediacount than colorcount": "SELECT objectid FROM artifact_media WHERE mediacount > colorcount;",
        "Q9. Colors > 50%": "SELECT objectid, color, percent FROM artifact_colors WHERE percent > 50;",
        "Q10. Top 10 newest accession years": "SELECT id, title, accessionyear FROM artifact_metadata WHERE accessionyear IS NOT NULL ORDER BY accessionyear DESC LIMIT 10;",
        "Q11. Distinct hues": "SELECT DISTINCT hue FROM artifact_colors WHERE hue IS NOT NULL ORDER BY hue;",
        "Q12. Top 5 most used colors": "SELECT color, COUNT(*) AS color_count FROM artifact_colors GROUP BY color ORDER BY color_count DESC LIMIT 5;",
        "Q13. Average coverage per hue": "SELECT hue, AVG(percent) AS avg_coverage FROM artifact_colors GROUP BY hue;",
        "Q14. Colors for a given artifact ID": "SELECT color, spectrum, hue, percent, css3 FROM artifact_colors WHERE objectid = 12345;",
        "Q15. Total number of color entries": "SELECT COUNT(*) AS total_color_entries FROM artifact_colors;",
        "Q16. Artifact titles and hues (Byzantine culture)": "SELECT a.title, c.hue FROM artifact_metadata a JOIN artifact_colors c ON a.id=c.objectid  WHERE a.culture='Byzantine';",
        "Q17. Each artifact title with hues": "SELECT a.title, GROUP_CONCAT(c.hue) AS hues FROM artifact_metadata a JOIN artifact_colors c ON a.id=c.objectid WHERE c.hue IS NOT NULL GROUP BY a.title;",
        "Q18. Titles, cultures, media ranks (period not null)": "SELECT a.title, a.culture, b.ranks FROM artifact_metadata a JOIN artifact_media b ON a.id=b.objectid WHERE a.period IS NOT NULL;",
        "Q19. Top 10 ranked artifacts with hue Grey": "SELECT a.title, c.hue, b.ranks FROM artifact_metadata a JOIN artifact_media b ON a.id=b.objectid JOIN artifact_colors c ON a.id=c.objectid WHERE c.hue='Grey' ORDER BY b.ranks DESC LIMIT 10;",
        "Q20. Artifacts per classification with avg media count": "SELECT a.classification, COUNT(*) AS artifact_count, AVG(b.mediacount) AS avg_media_count FROM artifact_metadata a JOIN artifact_media b ON a.id=b.objectid GROUP BY a.classification;",
        "Q21. Byzantine artifacts by centuries (desc)": "SELECT title,culture,century FROM artifact_metadata WHERE culture='Byzantine' ORDER BY century DESC;",
        "Q22. Top 5 cultures with most artifacts": "SELECT culture, COUNT(*) AS artifact_count FROM artifact_metadata GROUP BY culture ORDER BY artifact_count DESC LIMIT 5;",
        "Q23. Earliest and latest accession year": "SELECT MIN(accessionyear) AS earliest_year, MAX(accessionyear) AS latest_year FROM artifact_metadata WHERE accessionyear != 0;",
        "Q24. Classification with highest avg color count": "SELECT a.classification, AVG(b.colorcount) AS avg_colorcount FROM artifact_metadata a JOIN artifact_media b ON a.id=b.objectid GROUP BY a.classification ORDER BY avg_colorcount DESC;",
        "Q25. Classification with top avg color count (limit 1)": "SELECT a.classification, AVG(b.colorcount) AS avg_colorcount FROM artifact_metadata a JOIN artifact_media b ON a.id=b.objectid GROUP BY a.classification ORDER BY avg_colorcount DESC LIMIT 1;",
        "Q26. Average accession year per classification": "SELECT classification, AVG(accessionyear) AS avg_accessionyear FROM artifact_metadata GROUP BY classification;"
    }

    query_choice = st.selectbox("Choose a query", list(queries.keys()))
    if st.button("Run Query"):
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(queries[query_choice])
        rows = cur.fetchall()
        df = pd.DataFrame(rows, columns=[c[0] for c in cur.description])
        st.dataframe(df, use_container_width=True)
        cur.close(); conn.close()


