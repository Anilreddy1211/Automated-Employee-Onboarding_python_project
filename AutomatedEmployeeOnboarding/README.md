# Automated Employee Onboarding Document Processor

A Python automation project that reads employee data from CSV/Excel, validates records, creates personalized onboarding documents in TXT and PDF formats, records errors, and displays processing results in an interactive dashboard.

## Features

- Read `.csv`, `.xlsx`, and `.xlsm` employee files.
- Validate required fields, employee IDs, duplicate IDs, and joining dates.
- Create a separate output folder for each valid employee.
- Generate `onboarding.txt` and `onboarding.pdf` using a reusable template.
- Export a processing summary to `reports/processing_summary.csv`.
- Record events and errors in `logs/onboarding.log`.
- Show KPIs, success/failure donut chart, department-wise bar chart, validation issue chart, searchable records, and TXT/PDF downloads in a Streamlit dashboard.
- Run automated unit tests with `unittest`.

## Project structure

```text
AutomatedEmployeeOnboarding/
├── main.py
├── dashboard.py
├── requirements.txt
├── input/
│   └── employees.csv
├── templates/
│   └── onboarding_template.txt
├── output/
├── reports/
│   └── processing_summary.csv
├── logs/
│   └── onboarding.log
└── tests/
    └── test_main.py
```

## Setup on macOS

Run these commands from the project root (the folder containing `main.py`):

```bash
python3 -m venv venv
source venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Run the processor in Terminal

```bash
python main.py
```

By default, the processor reads `input/employees.csv` and `templates/onboarding_template.txt`. It generates employee documents under `output/`, a CSV report under `reports/`, and a log under `logs/`.

## Launch the interactive dashboard

```bash
streamlit run dashboard.py
```

Streamlit will print a local URL (usually `http://localhost:8501`). Open that URL in your browser. Use the sidebar to process the default CSV or upload your own CSV/Excel file. The charts and report table are based on the latest processing summary.

Expected input columns:

```text
employee_id,name,department,role,joining_date,manager
```

Accepted joining-date formats include `YYYY-MM-DD`, `DD-MM-YYYY`, `DD/MM/YYYY`, and `MM/DD/YYYY`.

## Run tests

```bash
python -m unittest discover -s tests -v
```

## Technologies

- Python standard library: `csv`, `pathlib`, `datetime`, `re`, `logging`, `argparse`, `unittest`, `tempfile`
- `openpyxl`: Excel input
- `ReportLab`: PDF document generation
- `Streamlit`: interactive dashboard UI
- `Plotly`: interactive charts

## Privacy note

Use synthetic employee records for demonstrations. Do not commit real employee data or generated documents containing personal information to a public repository.

## Interactive dashboard filters

Run the dashboard with `python -m streamlit run dashboard.py`. In **Employee processing details**, use:

- **Status**: select `FAILED` to show only failed records, or `SUCCESS` to show successful records.
- **Mistake / validation error**: select a specific validation error (for example, `Employee Name is required`) to show only records containing that issue.
- **Department**: show records for one department.
- **Search**: search IDs, names, roles, managers, or error messages.
- **Clear all filters**: restore the full record list.

Filters combine together, so selecting `FAILED` and a specific mistake narrows the table to failed records with that mistake. The charts continue to show overall processing statistics for context.

