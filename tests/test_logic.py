import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import classify
import db
import schedule

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class ClassifyTests(unittest.TestCase):
    def test_normalize(self):
        self.assertEqual(classify.normalize("أُصُولُ الفِقْهِ"), "اصول الفقه")
        self.assertEqual(classify.normalize("المجلس ١٢"), "المجلس 12")

    def test_sections(self):
        cases = {
            "شرح صحيح مسلم المجلس 5": "شرح صحيح مسلم",
            "شرح علم مصطلح الحديث": "مصطلح الحديث",
            "مناهج البيان في أصول التفسير": "أصول التفسير",
            "شرح العقيدة الواسطية": "عقائد أهل السنة والعقيدة الواسطية",
            "قواعد عقائد أهل السنة والجماعة": "عقائد أهل السنة والعقيدة الواسطية",
            "أصول الفقه الدرس 3": "أصول الفقه",
            "درس في الفقه": "الفقه",
            "من السيرة النبوية": "السيرة",
            "عظماء الإسلام: عمر": "عظماء الإسلام",
            "حوار مفتوح": "منوعات",
        }
        for title, want in cases.items():
            self.assertEqual(classify.classify(title), want, title)

    def test_session_number(self):
        self.assertEqual(classify.session_number("شرح صحيح مسلم المجلس 12"), 12)
        self.assertEqual(classify.session_number("صحيح مسلم - مجلس رقم ٧"), 7)
        self.assertIsNone(classify.session_number("شرح صحيح مسلم"))


class DbTests(unittest.TestCase):
    def setUp(self):
        self.conn = db.connect(":memory:")

    def test_auto_classify_and_duplicate(self):
        rid, cat = db.add_recording(self.conn, "شرح صحيح مسلم المجلس 2", "F1", "U1")
        self.assertEqual(cat, "شرح صحيح مسلم")
        self.assertIsNone(db.add_recording(self.conn, "نفس الملف", "F1", "U1"))

    def test_search_ignores_diacritics_and_hamza(self):
        db.add_recording(self.conn, "باب الإيمان بالله", "F1", "U1")
        db.add_recording(self.conn, "باب الصلاة", "F2", "U2")
        self.assertEqual(len(db.search(self.conn, "الايمان")), 1)
        self.assertEqual(len(db.search(self.conn, "باب")), 2)
        self.assertEqual(len(db.search(self.conn, "باب الصلاه")), 1)
        self.assertEqual(db.search(self.conn, "غير موجود"), [])
        self.assertEqual(db.search(self.conn, "%"), [])

    def test_muslim_ordered_by_session(self):
        for n in (3, 1, 2):
            db.add_recording(self.conn, f"شرح صحيح مسلم المجلس {n}", f"F{n}", f"U{n}")
        cid = db.category_id(self.conn, "شرح صحيح مسلم")
        got = [r["session_no"] for r in db.by_category(self.conn, cid)]
        self.assertEqual(got, [1, 2, 3])

    def test_admin_change_section(self):
        rid, _ = db.add_recording(self.conn, "حوار", "F1", "U1")
        self.assertTrue(db.set_category(self.conn, rid, "الفقه"))
        self.assertEqual(db.get(self.conn, rid)["category"], "الفقه")
        self.assertFalse(db.set_category(self.conn, rid, "قسم وهمي"))
        self.assertEqual(db.find_category(self.conn, "اصول الفقه")["name"], "أصول الفقه")

    def test_latest(self):
        db.add_recording(self.conn, "أ", "F1", "U1")
        db.add_recording(self.conn, "ب", "F2", "U2")
        self.assertEqual(db.latest(self.conn)[0]["title"], "ب")


class ScheduleTests(unittest.TestCase):
    def setUp(self):
        self.data = schedule.load(os.path.join(ROOT, "schedule.json"))

    def test_all_days_present(self):
        for day in schedule.WEEK_ORDER:
            self.assertIn(day, self.data["days"])

    def test_times(self):
        text = schedule.format_week(self.data)
        self.assertIn("19:00 بتوقيت مصر = 22:00 بتوقيت مكة", text)

    def test_weekday_mapping_and_today_mark(self):
        self.assertEqual(schedule.day_name(5), "السبت")
        self.assertEqual(schedule.day_name(0), "الإثنين")
        self.assertIn("شرح العقيدة الواسطية", schedule.format_day(self.data, "الثلاثاء"))
        self.assertIn("(اليوم)", schedule.format_week(self.data, 1))


if __name__ == "__main__":
    unittest.main()
