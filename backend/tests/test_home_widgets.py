import unittest
from unittest.mock import patch

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database import HomeWidgetPreference
from services.auth import AccessProfile
from services.home_widgets import HomeWidgetPayload, get_home_widgets, set_home_widgets


def profile(username: str, permissions: dict[str, str]) -> AccessProfile:
    return AccessProfile(
        username=username,
        role="admin",
        promotorias=("TAIICO",),
        rfc="",
        aseguradoras=(),
        module_permissions=permissions,
    )


class HomeWidgetTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        HomeWidgetPreference.__table__.create(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.session_patch = patch("services.home_widgets.SessionLocal", self.Session)
        self.session_patch.start()

    def tearDown(self):
        self.session_patch.stop()
        self.engine.dispose()

    def test_default_cards_include_finanzas_only_when_permitted(self):
        finance_user = profile("finance@example.com", {"finanzas": "lectura", "clientes": "lectura"})
        other_user = profile("other@example.com", {"clientes": "lectura"})

        self.assertEqual(get_home_widgets(finance_user)["selected"], ["clientes", "finanzas"])
        self.assertEqual(get_home_widgets(other_user)["selected"], ["clientes"])

    def test_selection_persists_per_user_and_keeps_order(self):
        first = profile("first@example.com", {"finanzas": "lectura", "clientes": "lectura"})
        second = profile("second@example.com", {"finanzas": "lectura", "clientes": "lectura"})

        set_home_widgets(HomeWidgetPayload(module_keys=["finanzas", "clientes"]), first)
        set_home_widgets(HomeWidgetPayload(module_keys=["clientes"]), second)

        self.assertEqual(get_home_widgets(first)["selected"], ["finanzas", "clientes"])
        self.assertEqual(get_home_widgets(second)["selected"], ["clientes"])

    def test_removed_permission_cannot_expose_saved_card(self):
        original = profile("user@example.com", {"finanzas": "lectura", "clientes": "lectura"})
        restricted = profile("user@example.com", {"clientes": "lectura"})
        set_home_widgets(HomeWidgetPayload(module_keys=["finanzas", "clientes"]), original)

        self.assertEqual(get_home_widgets(restricted)["selected"], ["clientes"])
        with self.assertRaises(HTTPException) as error:
            set_home_widgets(HomeWidgetPayload(module_keys=["finanzas"]), restricted)
        self.assertEqual(error.exception.status_code, 403)

    def test_duplicate_card_is_rejected(self):
        user = profile("user@example.com", {"clientes": "lectura"})
        with self.assertRaises(HTTPException) as error:
            set_home_widgets(HomeWidgetPayload(module_keys=["clientes", "clientes"]), user)
        self.assertEqual(error.exception.status_code, 422)


if __name__ == "__main__":
    unittest.main()
