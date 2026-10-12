"""Interactive Streamlit dashboard for the Employee Onboarding Processor.

Chart clicks highlight the selected category and update the Employee processing
details table. Manual filters remain active and combine with chart selections.
"""

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
st.markdown(
    """
    <style>
        .main {background: #f6f8fc;}
        .block-container {padding-top: 1.6rem; padding-bottom: 2rem;}
        [data-testid="stMetric"] {
            background: white; border: 1px solid #e4e9f2;
            padding: 18px; border-radius: 14px;
        }
        h1, h2, h3 {color: #17365d;}
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("📊 Employee Onboarding Dashboard")
st.caption(
    "Click a chart category to highlight it and filter the employee table. "
    "Chart selections combine with the manual filters; KPI totals reflect matching records."
)

# Persistent filters and chart-widget keys.
DEFAULT_STATE = {
    "status_filter": "All",
    "mistake_filter": "All mistakes",
    "department_filter": "All departments",
    "search_term": "",
    "chart_selection_version": 0,
    "last_status_chart_selection": None,
    "last_issue_chart_selection": None,
    "last_department_chart_selection": None,
}
for state_key, default_value in DEFAULT_STATE.items():
    if state_key not in st.session_state:
        st.session_state[state_key] = default_value


def load_summary():
    """Read the latest processing summary, if one exists."""
    if not SUMMARY_PATH.exists():
        return []
    with SUMMARY_PATH.open("r", newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def process_uploaded_file(uploaded_file):
    """Process an uploaded CSV or Excel file using the project's main module."""
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


def issues_for_row(row):
    """Return the individual validation issues stored in a summary row."""
    message = str(row.get("message", "")).strip()
    return [part.strip() for part in message.split(";") if part.strip()]


def chart_selection_points(widget_key):
    """Return selected Plotly points from Streamlit's chart widget state."""
    state = st.session_state.get(widget_key)
    if state is None:
        return []

    selection = getattr(state, "selection", None)
    if selection is not None and hasattr(selection, "points"):
        return list(selection.points)
    if isinstance(selection, dict):
        return selection.get("points", [])
    if isinstance(state, dict):
        return state.get("selection", {}).get("points", [])
    return []


def apply_chart_selections(status_key, issue_key, department_key):
    """Apply a newly clicked chart category to the matching filter state.

    Existing unrelated filters are preserved. Validation issues necessarily
    refer to failed records, so choosing an issue also selects FAILED status.
    """
    status_points = chart_selection_points(status_key)
    status_selection = tuple(
        (point.get("label"), point.get("point_index")) for point in status_points
    ) or None
    if status_selection != st.session_state.last_status_chart_selection:
        st.session_state.last_status_chart_selection = status_selection
        if status_points:
            point = status_points[0]
            selected_status = point.get("label")
            if not selected_status and point.get("point_index") is not None:
                labels = ["Successful", "Failed"]
                index = point["point_index"]
                if 0 <= index < len(labels):
                    selected_status = labels[index]
            if selected_status == "Successful":
                st.session_state.status_filter = "SUCCESS"
            elif selected_status == "Failed":
                st.session_state.status_filter = "FAILED"

    issue_points = chart_selection_points(issue_key)
    issue_selection = tuple(point.get("y") for point in issue_points) or None
    if issue_selection != st.session_state.last_issue_chart_selection:
        st.session_state.last_issue_chart_selection = issue_selection
        if issue_points and issue_points[0].get("y"):
            st.session_state.status_filter = "FAILED"
            st.session_state.mistake_filter = str(issue_points[0]["y"])

    department_points = chart_selection_points(department_key)
    department_selection = tuple(point.get("y") for point in department_points) or None
    if department_selection != st.session_state.last_department_chart_selection:
        st.session_state.last_department_chart_selection = department_selection
        if department_points and department_points[0].get("y"):
            st.session_state.department_filter = str(department_points[0]["y"])


with st.sidebar:
    st.header("⚙️ Controls")
    st.write("Process the sample employee file or upload your own CSV/Excel data.")
    uploaded_file = st.file_uploader(
        "Upload employee data", type=["csv", "xlsx", "xlsm"]
    )
    run_label = (
        "Process uploaded file" if uploaded_file else "Process default employees.csv"
    )
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

            # Processing a new report should not leave old chart filters active.
            st.session_state.status_filter = "All"
            st.session_state.mistake_filter = "All mistakes"
            st.session_state.department_filter = "All departments"
            st.session_state.search_term = ""
            st.session_state.chart_selection_version += 1
            st.session_state.last_status_chart_selection = None
            st.session_state.last_issue_chart_selection = None
            st.session_state.last_department_chart_selection = None
            st.success(
                f"Processing complete: {result['success']} successful, "
                f"{result['failed']} failed."
            )
            st.rerun()
        except Exception as exc:
            st.error(f"Could not process employees: {exc}")

    st.divider()
    st.caption("Expected columns")
    st.code(
        "employee_id, name, department, role, joining_date, manager",
        language="text",
    )

rows = load_summary()
if not rows:
    st.info(
        "No processing report found yet. Click **Process default employees.csv** "
        "in the sidebar to generate your first dashboard report."
    )
    st.stop()

# Normalize report fields to support summaries generated by earlier versions.
for row in rows:
    for field in [
        "row_number", "employee_id", "name", "department", "role",
        "joining_date", "manager", "status", "message", "txt_file", "pdf_file",
    ]:
        row.setdefault(field, "")
    row["status"] = (row["status"] or "FAILED").strip().upper()
    for field in ["employee_id", "name", "department", "role", "joining_date", "manager", "message"]:
        row[field] = str(row.get(field, "") or "").strip()

# Chart keys are versioned so Clear all filters can clear Plotly's remembered selection.
version = st.session_state.chart_selection_version
status_chart_key = f"status_chart_{version}"
issue_chart_key = f"issue_chart_{version}"
department_chart_key = f"department_chart_{version}"
apply_chart_selections(status_chart_key, issue_chart_key, department_chart_key)

all_issues = sorted(
    {issue for row in rows if row["status"] != "SUCCESS" for issue in issues_for_row(row)},
    key=str.casefold,
)
all_departments = sorted(
    {(row.get("department") or "Not provided").strip() or "Not provided" for row in rows},
    key=str.casefold,
)

# Build the table's result set from all active filters. Chart clicks update these
# same session-state values, so the table and KPI cards respond to chart clicks.
filtered = list(rows)
if st.session_state.status_filter != "All":
    filtered = [r for r in filtered if r["status"] == st.session_state.status_filter]
if st.session_state.mistake_filter != "All mistakes":
    filtered = [r for r in filtered if st.session_state.mistake_filter in issues_for_row(r)]
if st.session_state.department_filter != "All departments":
    filtered = [
        r for r in filtered
        if ((r.get("department") or "").strip() or "Not provided")
        == st.session_state.department_filter
    ]
if st.session_state.search_term.strip():
    query = st.session_state.search_term.casefold().strip()
    searchable_fields = ["employee_id", "name", "department", "role", "manager", "message"]
    filtered = [
        r for r in filtered
        if query in " ".join(str(r.get(field, "")) for field in searchable_fields).casefold()
    ]

# KPI cards reflect the rows currently matching the filters.
total = len(filtered)
successful_rows = [r for r in filtered if r["status"] == "SUCCESS"]
failed_rows = [r for r in filtered if r["status"] != "SUCCESS"]
success_count = len(successful_rows)
failed_count = len(failed_rows)
success_rate = (success_count / total * 100) if total else 0.0

a, b, c, d = st.columns(4)
a.metric("👥 Matching records", total)
b.metric("✅ Successful", success_count)
with c:
    if st.button(
        f"❌ Failed records · {failed_count}",
        use_container_width=True,
        help="Add the failed-only filter while keeping department and search filters.",
    ):
        st.session_state.status_filter = "FAILED"
        st.rerun()
d.metric("📈 Success rate", f"{success_rate:.1f}%")

st.divider()
left, right = st.columns([1, 1.35], gap="large")

# Charts show the full report for context. The active category is visually
# emphasized, while the table/KPIs show the records matching active filters.
all_success_count = sum(1 for r in rows if r["status"] == "SUCCESS")
all_failed_count = len(rows) - all_success_count
status_active = st.session_state.status_filter
status_colors = [
    "#20a779" if status_active in ("All", "SUCCESS") else "#d8dee9",
    "#e05d5d" if status_active in ("All", "FAILED") else "#d8dee9",
]
status_pull = [0.08 if status_active == "SUCCESS" else 0,
               0.08 if status_active == "FAILED" else 0]

with left:
    st.subheader("Processing status")
    status_fig = go.Figure(
        data=[go.Pie(
            labels=["Successful", "Failed"],
            values=[all_success_count, all_failed_count],
            hole=0.62,
            marker={
                "colors": status_colors,
                "line": {"color": "white", "width": 2},
            },
            pull=status_pull,
            textinfo="label+value+percent",
            hovertemplate="%{label}: %{value}<extra></extra>",
        )]
    )
    status_fig.update_layout(
        height=330,
        margin=dict(l=10, r=10, t=20, b=10),
        showlegend=False,
        clickmode="event+select",
        annotations=[
            dict(
                text=f"{len(rows)}<br>all records",
                x=0.5, y=0.5, showarrow=False, font=dict(size=18),
            )
        ],
    )
    st.plotly_chart(
        status_fig,
        use_container_width=True,
        key=status_chart_key,
        on_select="rerun",
        selection_mode="points",
    )

with right:
    st.subheader("Employees by department")
    department_counts = {}
    for row in rows:
        department = (row.get("department") or "").strip() or "Not provided"
        department_counts[department] = department_counts.get(department, 0) + 1
    sorted_departments = sorted(
        department_counts.items(), key=lambda item: item[1], reverse=True
    )
    active_department = st.session_state.department_filter
    department_colors = [
        "#214e9c" if active_department == department else "#a9bddf"
        for department, _ in sorted_departments
    ]
    department_lines = [
        {"color": "#17365d", "width": 2}
        if active_department == department else {"color": "#a9bddf", "width": 0.5}
        for department, _ in sorted_departments
    ]
    dept_fig = go.Figure(
        go.Bar(
            x=[item[1] for item in sorted_departments],
            y=[item[0] for item in sorted_departments],
            orientation="h",
            marker={"color": department_colors, "line": {"color": "#ffffff", "width": 1}},
            text=[item[1] for item in sorted_departments],
            textposition="outside",
            hovertemplate="%{y}: %{x} employee(s)<extra></extra>",
        )
    )
    dept_fig.update_layout(
        height=330,
        margin=dict(l=10, r=35, t=20, b=10),
        xaxis_title="Number of employees",
        yaxis_title="",
        yaxis={"categoryorder": "total ascending"},
        clickmode="event+select",
    )
    st.plotly_chart(
        dept_fig,
        use_container_width=True,
        key=department_chart_key,
        on_select="rerun",
        selection_mode="points",
    )

# The issue chart remains available based on all failed records even when a
# different filter is active, so it can be used to change/add a validation issue.
all_failed_rows = [r for r in rows if r["status"] != "SUCCESS"]
if all_failed_rows:
    st.subheader("⚠️ Common validation issues")
    st.caption(
        "Click an issue bar to highlight that issue and show matching failed records. "
        "Your department and search filters remain active."
    )
    issue_counts = {}
    for row in all_failed_rows:
        individual_issues = issues_for_row(row) or ["Unspecified processing error"]
        for issue in individual_issues:
            issue_counts[issue] = issue_counts.get(issue, 0) + 1
    common = sorted(issue_counts.items(), key=lambda item: item[1], reverse=True)[:8]
    active_issue = st.session_state.mistake_filter
    issue_colors = [
        "#b86a0b" if active_issue == issue else "#f0c58c"
        for issue, _ in common
    ]
    issue_fig = go.Figure(
        go.Bar(
            x=[item[1] for item in common],
            y=[item[0] for item in common],
            orientation="h",
            marker={"color": issue_colors, "line": {"color": "#ffffff", "width": 1}},
            text=[item[1] for item in common],
            textposition="outside",
            hovertemplate="%{y}: %{x} occurrence(s)<extra></extra>",
        )
    )
    issue_fig.update_layout(
        height=max(230, 45 * len(common)),
        margin=dict(l=10, r=35, t=10, b=10),
        xaxis_title="Occurrences",
        yaxis_title="",
        yaxis={"categoryorder": "total ascending"},
        clickmode="event+select",
    )
    st.plotly_chart(
        issue_fig,
        use_container_width=True,
        key=issue_chart_key,
        on_select="rerun",
        selection_mode="points",
    )

st.divider()
st.subheader("📋 Employee processing details")
st.caption("Choose filters below or click a chart category above. Filters combine together.")

reset_col, _active_col = st.columns([1, 3])
with reset_col:
    if st.button("↺ Clear all filters", use_container_width=True):
        st.session_state.status_filter = "All"
        st.session_state.mistake_filter = "All mistakes"
        st.session_state.department_filter = "All departments"
        st.session_state.search_term = ""
        st.session_state.chart_selection_version += 1
        st.session_state.last_status_chart_selection = None
        st.session_state.last_issue_chart_selection = None
        st.session_state.last_department_chart_selection = None
        st.rerun()

filter_col, mistake_col, dept_col = st.columns([1, 1.6, 1.2])
with filter_col:
    st.selectbox("Status", ["All", "SUCCESS", "FAILED"], key="status_filter")
with mistake_col:
    st.selectbox(
        "Mistake / validation error",
        ["All mistakes", *all_issues],
        key="mistake_filter",
        help="Choose an error to display only records containing that validation issue.",
    )
with dept_col:
    st.selectbox(
        "Department",
        ["All departments", *all_departments],
        key="department_filter",
    )
st.text_input(
    "Search employee ID, name, department, role, manager, or error",
    placeholder="e.g. EMP001 or Employee Name is required",
    key="search_term",
)

# Recompute after manual filter widgets have been rendered/read.
filtered = list(rows)
if st.session_state.status_filter != "All":
    filtered = [r for r in filtered if r["status"] == st.session_state.status_filter]
if st.session_state.mistake_filter != "All mistakes":
    filtered = [r for r in filtered if st.session_state.mistake_filter in issues_for_row(r)]
if st.session_state.department_filter != "All departments":
    filtered = [
        r for r in filtered
        if ((r.get("department") or "").strip() or "Not provided")
        == st.session_state.department_filter
    ]
if st.session_state.search_term.strip():
    query = st.session_state.search_term.casefold().strip()
    searchable_fields = ["employee_id", "name", "department", "role", "manager", "message"]
    filtered = [
        r for r in filtered
        if query in " ".join(str(r.get(field, "")) for field in searchable_fields).casefold()
    ]

st.caption(f"Showing **{len(filtered)}** of **{len(rows)}** records")
visible_columns = [
    "row_number", "employee_id", "name", "department", "role", "joining_date",
    "status", "message", "txt_file", "pdf_file",
]
if filtered:
    st.dataframe(
        [{key: row.get(key, "") for key in visible_columns} for row in filtered],
        use_container_width=True,
        hide_index=True,
    )
else:
    st.warning("No records match the selected filters. Try another filter or clear all filters.")

report_bytes = SUMMARY_PATH.read_bytes() if SUMMARY_PATH.exists() else b""
st.download_button(
    "⬇️ Download processing summary CSV",
    data=report_bytes,
    file_name="processing_summary.csv",
    mime="text/csv",
    disabled=not report_bytes,
)

st.subheader("📄 Generated onboarding documents")
# Documents are offered for successful records in the current filtered table.
if successful_rows:
    options = {
        f"{r['employee_id']} — {r['name']}": r
        for r in successful_rows
    }
    selected_label = st.selectbox("Select an employee", list(options.keys()))
    selected = options[selected_label]
    download_col1, download_col2 = st.columns(2)
    for col, field, label, mime in [
        (download_col1, "txt_file", "Download onboarding TXT", "text/plain"),
        (download_col2, "pdf_file", "Download onboarding PDF", "application/pdf"),
    ]:
        path_value = selected.get(field, "")
        path = (BASE_DIR / path_value).resolve() if path_value else None
        try:
            path.relative_to(OUTPUT_DIR.resolve())
            safe_path = path.is_file()
        except (ValueError, AttributeError):
            safe_path = False
        if safe_path:
            with col:
                st.download_button(
                    label,
                    data=path.read_bytes(),
                    file_name=path.name,
                    mime=mime,
                    key=f"{field}_download",
                )
        else:
            with col:
                st.caption(f"{label}: file not found")
else:
    st.info("No successful employee documents match the current filters.")

st.caption(
    "Dashboard charts summarize the full processing report and highlight active chart categories. "
    "KPI totals and the Employee processing details table reflect active filters. "
    "Re-run processing after changing the input file to refresh the report."
)
