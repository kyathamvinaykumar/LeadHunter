"""Streamlit interactions for the session Prospect CRM."""

from __future__ import annotations

import unittest
from datetime import date
from pathlib import Path

from streamlit.testing.v1 import AppTest

from app.crm import Prospect


class StreamlitCrmTests(unittest.TestCase):
    def test_status_notes_and_dates_persist_in_session(self) -> None:
        prospect = Prospect(
            place_id="crm-ui",
            business_name="CRM Sample",
            phone="555-0100",
            website=None,
            address="Example Road",
            rating=4.4,
            reviews=130,
        )
        app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"))
        app.session_state["prospects"] = {prospect.place_id: prospect}
        app.run()
        app.sidebar.radio[0].set_value("Prospects").run()

        app.selectbox(key="crm_status_crm-ui").select("Contacted").run()
        self.assertEqual(app.session_state["prospects"][prospect.place_id].status, "Contacted")

        app.text_area(key="crm_notes_crm-ui").set_value("Owner answered call").run()
        self.assertEqual(app.session_state["prospects"][prospect.place_id].notes, "Owner answered call")

        app.button(key="crm_edit_crm-ui").click().run()
        app.date_input(key="crm_contacted_date_crm-ui").set_value(date(2026, 10, 1)).run()
        self.assertEqual(
            app.session_state["prospects"][prospect.place_id].contacted_date,
            date(2026, 10, 1),
        )
        self.assertFalse(app.exception)


if __name__ == "__main__":
    unittest.main()