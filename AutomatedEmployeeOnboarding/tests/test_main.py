import tempfile
import unittest
from pathlib import Path

from main import validate_employee, render_template, safe_folder_name, save_as_pdf, read_employee_records


class TestEmployeeOnboarding(unittest.TestCase):
    def valid_record(self):
        return {
            "employee_id": "EMP101", "name": "Sam Example",
            "department": "Engineering", "role": "Python Developer",
            "joining_date": "2026-10-15", "manager": "Taylor Manager",
        }

    def test_valid_employee(self):
        employee, errors = validate_employee(self.valid_record(), set())
        self.assertEqual(errors, [])
        self.assertEqual(employee["joining_date"], "2026-10-15")

    def test_missing_name(self):
        record = self.valid_record()
        record["name"] = ""
        employee, errors = validate_employee(record, set())
        self.assertIsNone(employee)
        self.assertTrue(any("Employee Name is required" in error for error in errors))

    def test_invalid_date(self):
        record = self.valid_record()
        record["joining_date"] = "not-a-date"
        employee, errors = validate_employee(record, set())
        self.assertIsNone(employee)
        self.assertTrue(any("Joining date is invalid" in error for error in errors))

    def test_duplicate_id_case_insensitive(self):
        seen = set()
        validate_employee(self.valid_record(), seen)
        record = self.valid_record()
        record["employee_id"] = "emp101"
        employee, errors = validate_employee(record, seen)
        self.assertIsNone(employee)
        self.assertTrue(any("Duplicate Employee ID" in error for error in errors))

    def test_template_rendering(self):
        rendered = render_template("Hi {{name}} {{employee_id}} {{processed_date}}", self.valid_record())
        self.assertIn("Sam Example", rendered)
        self.assertNotIn("{{", rendered)

    def test_unknown_template_placeholder(self):
        with self.assertRaises(ValueError):
            render_template("{{unknown}}", self.valid_record())

    def test_safe_folder_name(self):
        self.assertEqual(safe_folder_name("EMP 1/Anil Kumar"), "EMP_1_Anil_Kumar")

    def test_pdf_generation(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            pdf_path = Path(temp_dir) / "onboarding.pdf"
            save_as_pdf("Sample onboarding document", pdf_path, self.valid_record())
            self.assertTrue(pdf_path.exists())
            self.assertGreater(pdf_path.stat().st_size, 0)

    def test_csv_reader(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = Path(temp_dir) / "employees.csv"
            csv_path.write_text(
                "employee_id,name,department,role,joining_date,manager\n"
                "EMP1,Test User,IT,Developer,2026-10-15,Manager\n",
                encoding="utf-8",
            )
            records = read_employee_records(csv_path)
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0]["employee_id"], "EMP1")


if __name__ == "__main__":
    unittest.main()
