"""Interactive Streamlit dashboard for the Employee Onboarding Processor."""
import csv
import tempfile
from pathlib import Path

import plotly.graph_objects as go
import streamlit as st

from main import BASE_DIR, read_employee_records, setup_logging, process_employees

APP_TITLE = "Employee Onboarding Dashboard"
INPUT_DIR = BASE_DIR / "input"
TEMPLATE_PATH = BASE_DIR / "templates" / "onboarding_template.txt"
OUTPUT_DIR = BASE_DIR / "output"
REPORTS_DIR = BASE_DIR / "reports"
LOGS_DIR = BASE_DIR / "logs"
SUMMARY_PATH = REPORTS_DIR / "processing_summary.csv"

st.set_page_config(page_title=APP_TITLE, page_icon="📊", layout="wide")

st.markdown("""
<style>
    .main {background: #f6f8fc;}
    .block-container {padding-top: 1.6rem; padding-bottom: 2rem;}
    [data-testid="stMetric"] {background: white; border: 1px solid #e4e9f2; padding: 18px; border-radius: 14px;}
    h1, h2, h3 {color: #17365d;}
</style>
""", unsafe_allow_html=True)

st.title("📊 Employee Onboarding Dashboard")
st.caption("Click a chart segment or bar to highlight it. Use the filters below to narrow the employee table.")

# Filters are controlled by the widgets below. Chart clicks highlight chart items only;
# they do not replace or override the filters selected by the user.
if "status_filter" not in st.session_state:
    st.session_state.status_filter = "All"
if "mistake_filter" not in st.session_state:
    st.session_state.mistake_filter = "All mistakes"
if "department_filter" not in st.session_state:
    st.session_state.department_filter = "All departments"
if "search_term" not in st.session_state:
    st.session_state.search_term = ""
if "chart_selection_version" not in st.session_state:
    st.session_state.chart_selection_version = 0

def load_summary():
    if not SUMMARY_PATH.exists():
        return []
    with SUMMARY_PATH.open("r", newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def process_uploaded_file(uploaded_file):
    suffix = Path(uploaded_file.name).suffix.lower()
    if suffix not in {".csv", ".xlsx", ".xlsm"}:
        raise ValueError("Please upload a CSV, XLSX, or XLSM file.")
    INPUT_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as temp:
        temp.write(uploaded_file.getvalue())
        temp_path = Path(temp.name)
    try:
        records = read_employee_records(temp_path)
    finally:
        temp_path.unlink(missing_ok=True)
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    setup_logging(LOGS_DIR)
    return process_employees(records, template, OUTPUT_DIR, REPORTS_DIR)


with st.sidebar:
    st.header("⚙️ Controls")
    st.write("Run processing using the sample input file or upload your own employee data.")
    uploaded_file = st.file_uploader("Upload employee data", type=["csv", "xlsx", "xlsm"])
    run_label = "Process uploaded file" if uploaded_file else "Process default employees.csv"
    if st.button(run_label, type="primary", use_container_width=True):
        try:
            if not TEMPLATE_PATH.exists():
                raise FileNotFoundError(f"Template not found: {TEMPLATE_PATH}")
            if uploaded_file:
                result = process_uploaded_file(uploaded_file)
            else:
                input_path = INPUT_DIR / "employees.csv"
                records = read_employee_records(input_path)
                template = TEMPLATE_PATH.read_text(encoding="utf-8")
                setup_logging(LOGS_DIR)
                result = process_employees(records, template, OUTPUT_DIR, REPORTS_DIR)
            st.success(f"Processing complete: {result['success']} successful, {result['failed']} failed.")
            st.rerun()
        except Exception as exc:
            st.error(f"Could not process employees: {exc}")

    st.divider()
    st.caption("Expected columns")
    st.code("employee_id, name, department, role, joining_date, manager", language="text")

rows = load_summary()
if not rows:
    st.info("No processing report found yet. Click **Process default employees.csv** in the sidebar to generate your first dashboard report.")
    st.stop()

# Normalize fields so reports from older versions remain readable.
for row in rows:
    for key in ["row_number", "employee_id", "name", "department", "role", "joining_date", "manager", "status", "message", "txt_file", "pdf_file"]:
        row.setdefault(key, "")
    row["status"] = (row["status"] or "FAILED").upper()

# Read selected chart points only for visual highlighting. These selections never
# modify status, mistake, department, or search filters.
def chart_selection_points(widget_key):
    state = st.session_state.get(widget_key)
    if state is None:
        return []
    selection = getattr(state, "selection", None)
    if selection is not None and hasattr(selection, "points"):
        return selection.points
    if isinstance(selection, dict):
        return selection.get("points", [])
    if isinstance(state, dict):
        return state.get("selection", {}).get("points", [])
    return []


def selected_point_indices(widget_key):
    indices = []
    for point in chart_selection_points(widget_key):
        index = point.get("point_index")
        if index is None:
            index = point.get("pointNumber")
        if index is not None:
            try:
                indices.append(int(index))
            except (TypeError, ValueError):
                pass
    return sorted(set(indices))


status_chart_key = f"status_chart_{st.session_state.chart_selection_version}"
issue_chart_key = f"issue_chart_{st.session_state.chart_selection_version}"
department_chart_key = f"department_chart_{st.session_state.chart_selection_version}"
def issues_for_row(row):
    """Return individual validation issues from a summary row."""
    message = str(row.get("message", "")).strip()
    return [part.strip() for part in message.split(";") if part.strip()]


dashboard_rows = list(rows)
if st.session_state.status_filter != "All":
    dashboard_rows = [row for row in dashboard_rows if row["status"] == st.session_state.status_filter]
if st.session_state.mistake_filter != "All mistakes":
    dashboard_rows = [row for row in dashboard_rows if st.session_state.mistake_filter in issues_for_row(row)]
if st.session_state.department_filter != "All departments":
    dashboard_rows = [
        row for row in dashboard_rows
        if ((row.get("department") or "").strip() or "Not provided") == st.session_state.department_filter
    ]
if st.session_state.search_term.strip():
    query = st.session_state.search_term.casefold()
    dashboard_rows = [
        row for row in dashboard_rows
        if query in " ".join(
            str(row.get(key, ""))
            for key in ["employee_id", "name", "department", "role", "manager", "message"]
        ).casefold()
    ]

# Summary cards
total = len(dashboard_rows)
successful_rows = [r for r in dashboard_rows if r["status"] == "SUCCESS"]
failed_rows = [r for r in dashboard_rows if r["status"] != "SUCCESS"]
success_count = len(successful_rows)
failed_count = len(failed_rows)
success_rate = (success_count / total * 100) if total else 0

a, b, c, d = st.columns(4)
a.metric("👥 Total employees", total)
b.metric("✅ Successful", success_count)
with c:
    if st.button(f"❌ Failed records · {failed_count}", use_container_width=True, help="Show only failed employee records."):
        st.session_state.status_filter = "FAILED"
        st.session_state.mistake_filter = "All mistakes"
        st.rerun()
d.metric("📈 Success rate", f"{success_rate:.1f}%")

st.divider()
left, right = st.columns([1, 1.35], gap="large")

with left:
    st.subheader("Processing status")
    st.caption("Click a segment to highlight it; this does not change the table filters.")
    status_fig = go.Figure(data=[go.Pie(
        labels=["Successful", "Failed"],
        values=[success_count, failed_count],
        hole=0.62,
        marker={"colors": (
            ["#20a779" if i in selected_point_indices(status_chart_key) else "#d9dee7" for i in range(2)]
            if selected_point_indices(status_chart_key)
            else ["#20a779", "#e05d5d"]
        )},
        textinfo="label+value+percent",
        hovertemplate="%{label}: %{value}<extra></extra>",
    )])
    status_fig.update_layout(height=330, margin=dict(l=10, r=10, t=20, b=10), showlegend=False,
                            annotations=[dict(text=f"{total}<br>records", x=0.5, y=0.5, showarrow=False, font=dict(size=18))])
    st.plotly_chart(
        status_fig, use_container_width=True, key=status_chart_key,
        on_select="rerun", selection_mode="points",
    )

with right:
    st.subheader("Employees by department")
    st.caption("Click a bar to highlight a department without replacing your filters.")
    department_counts = {}
    for row in dashboard_rows:
        department = row["department"].strip() or "Not provided"
        department_counts[department] = department_counts.get(department, 0) + 1
    sorted_departments = sorted(department_counts.items(), key=lambda item: item[1], reverse=True)
    dept_fig = go.Figure(go.Bar(
        x=[item[1] for item in sorted_departments],
        y=[item[0] for item in sorted_departments],
        orientation="h",
        marker={"color": "#4677c8", "opacity": [1.0 if i in selected_point_indices(department_chart_key) else 0.35 for i in range(len(sorted_departments))] if selected_point_indices(department_chart_key) else 1.0},
        selectedpoints=selected_point_indices(department_chart_key) or None,
        selected={"marker": {"opacity": 1.0}},
        unselected={"marker": {"opacity": 0.35}},
        text=[item[1] for item in sorted_departments],
        textposition="outside",
        hovertemplate="%{y}: %{x} employee(s)<extra></extra>",
    ))
    dept_fig.update_layout(height=330, margin=dict(l=10, r=35, t=20, b=10),
                           xaxis_title="Number of employees", yaxis_title="", yaxis={"categoryorder": "total ascending"})
    st.plotly_chart(
        dept_fig, use_container_width=True, key=department_chart_key,
        on_select="rerun", selection_mode="points",
    )

if failed_rows:
    st.subheader("⚠️ Common validation issues")
    st.caption("Click an issue bar to highlight it. To filter the table by an error, choose it in the filters below.")
    issue_counts = {}
    for row in failed_rows:
        message = row["message"].strip() or "Unspecified processing error"
        # Split combined validation messages into individual issues.
        for issue in [part.strip() for part in message.split(";") if part.strip()]:
            issue_counts[issue] = issue_counts.get(issue, 0) + 1
    common = sorted(issue_counts.items(), key=lambda item: item[1], reverse=True)[:8]
    issue_fig = go.Figure(go.Bar(
        x=[item[1] for item in common],
        y=[item[0] for item in common],
        orientation="h",
        marker={"color": "#e5a044", "opacity": [1.0 if i in selected_point_indices(issue_chart_key) else 0.35 for i in range(len(common))] if selected_point_indices(issue_chart_key) else 1.0},
        selectedpoints=selected_point_indices(issue_chart_key) or None,
        selected={"marker": {"opacity": 1.0}},
        unselected={"marker": {"opacity": 0.35}},
        text=[item[1] for item in common],
        textposition="outside",
        hovertemplate="%{y}: %{x}<extra></extra>",
    ))
    issue_fig.update_layout(height=max(230, 45 * len(common)), margin=dict(l=10, r=35, t=10, b=10),
                            xaxis_title="Occurrences", yaxis_title="", yaxis={"categoryorder": "total ascending"})
    st.plotly_chart(
        issue_fig, use_container_width=True, key=issue_chart_key,
        on_select="rerun", selection_mode="points",
    )

st.divider()
st.subheader("📋 Employee processing details")
st.caption("Use the filters below to narrow the table to matching records.")

# Keep dropdown options based on the full report, not the currently filtered
# rows. This prevents an active filter from disappearing from its own dropdown.
all_failed_rows = [row for row in rows if row["status"] != "SUCCESS"]
all_issues = sorted(
    {issue for row in all_failed_rows for issue in issues_for_row(row)},
    key=str.casefold,
)
all_departments = sorted(
    {
        (row.get("department") or "Not provided").strip() or "Not provided"
        for row in rows
    },
    key=str.casefold,
)

reset_col, _active_col = st.columns([1, 3])
with reset_col:
    if st.button("↺ Clear all filters", use_container_width=True):
        st.session_state.status_filter = "All"
        st.session_state.mistake_filter = "All mistakes"
        st.session_state.department_filter = "All departments"
        st.session_state.search_term = ""
        # Recreate selectable charts without their previous point selection.
        st.session_state.chart_selection_version += 1
        st.rerun()

filter_col, mistake_col, dept_col = st.columns([1, 1.6, 1.2])
with filter_col:
    status_filter = st.selectbox("Status", ["All", "SUCCESS", "FAILED"], key="status_filter")
with mistake_col:
    mistake_filter = st.selectbox(
        "Mistake / validation error", ["All mistakes", *all_issues], key="mistake_filter",
        help="Choose an error to display only records containing that exact validation issue.",
    )
with dept_col:
    department_filter = st.selectbox("Department", ["All departments", *all_departments], key="department_filter")
search_term = st.text_input(
    "Search employee ID, name, role, manager, or error",
    placeholder="e.g. EMP001 or Employee Name is required", key="search_term",
)

filtered = list(rows)
if status_filter != "All":
    filtered = [row for row in filtered if row["status"] == status_filter]
if mistake_filter != "All mistakes":
    filtered = [row for row in filtered if mistake_filter in issues_for_row(row)]
if department_filter != "All departments":
    filtered = [row for row in filtered if ((row.get("department") or "").strip() or "Not provided") == department_filter]
if search_term.strip():
    query = search_term.casefold()
    filtered = [row for row in filtered if query in " ".join(str(row.get(key, "")) for key in ["employee_id", "name", "department", "role", "manager", "message"]).casefold()]

st.caption(f"Showing **{len(filtered)}** of **{len(rows)}** records")
visible_columns = ["row_number", "employee_id", "name", "department", "role", "joining_date", "status", "message", "txt_file", "pdf_file"]
if filtered:
    st.dataframe([{key: row.get(key, "") for key in visible_columns} for row in filtered], use_container_width=True, hide_index=True)
else:
    st.warning("No records match the selected filters. Try another mistake or clear the filters.")

report_bytes = SUMMARY_PATH.read_bytes() if SUMMARY_PATH.exists() else b""
st.download_button("⬇️ Download processing summary CSV", data=report_bytes,
                   file_name="processing_summary.csv", mime="text/csv", disabled=not report_bytes)

st.subheader("📄 Generated onboarding documents")
if successful_rows:
    options = {f"{r['employee_id']} — {r['name']}": r for r in successful_rows}
    selected_label = st.selectbox("Select an employee", list(options.keys()))
    selected = options[selected_label]
    download_col1, download_col2 = st.columns(2)
    for col, field, label, mime in [
        (download_col1, "txt_file", "Download onboarding TXT", "text/plain"),
        (download_col2, "pdf_file", "Download onboarding PDF", "application/pdf"),
    ]:
        path_value = selected.get(field, "")
        path = (BASE_DIR / path_value).resolve() if path_value else None
        # Only serve files located inside the configured output directory.
        try:
            path.relative_to(OUTPUT_DIR.resolve())
            safe_path = path.is_file()
        except (ValueError, AttributeError):
            safe_path = False
        if safe_path:
            with col:
                st.download_button(label, data=path.read_bytes(), file_name=path.name, mime=mime, key=f"{field}_download")
        else:
            with col:
                st.caption(f"{label}: file not found")
else:
    st.info("No successful employee documents are available yet. Review the validation issues above.")

st.caption("Dashboard data comes from reports/processing_summary.csv. Re-run processing after changing the input file to refresh charts and results.")
