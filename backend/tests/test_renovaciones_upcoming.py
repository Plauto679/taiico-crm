import asyncio
import unittest
from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from services import renovaciones


class _Query:
    def __init__(self, rows):
        self.rows = rows
        self.filters = []

    def join(self, *_args, **_kwargs):
        return self

    def filter(self, *args, **_kwargs):
        self.filters.extend(args)
        return self

    def all(self):
        return self.rows


class UpcomingRenewalsTests(unittest.TestCase):
    def test_metlife_vida_and_gmm_include_client_rfc(self):
        client = SimpleNamespace(
            full_name="Cliente Prueba",
            rfc="RFC010101AAA",
            email="cliente@example.com",
        )
        common_policy = {
            "client": client,
            "effective_start_date": date(2026, 1, 1),
            "effective_end_date": date(2026, 12, 31),
            "payment_frequency": "mensual",
            "premium_amount": 12000,
            "document_link": "https://drive.google.com/drive/folders/example",
            "insurer_id": "metlife",
        }
        vida_policy = SimpleNamespace(
            **common_policy,
            policy_number="VIDA-1",
            product_id="prod_met_vida",
        )
        gmm_policy = SimpleNamespace(
            **common_policy,
            policy_number="GMM-1",
            product_id="prod_met_gmm",
        )
        rows = [
            SimpleNamespace(
                original_policy=vida_policy,
                renewal_deadline=date(2026, 10, 1),
                insurer_response="",
                paid_until=None,
            ),
            SimpleNamespace(
                original_policy=gmm_policy,
                renewal_deadline=date(2026, 10, 2),
                insurer_response="",
                paid_until=date(2026, 9, 30),
            ),
        ]
        db = MagicMock()
        query = _Query(rows)
        db.query.return_value = query

        with (
            patch.object(renovaciones, "SessionLocal", return_value=db),
            patch.object(
                renovaciones,
                "run_in_threadpool",
                new=AsyncMock(side_effect=[{}, {}, {}]),
            ),
        ):
            result = asyncio.run(
                renovaciones.get_upcoming_renewals(
                    start_date="2026-09-01",
                    end_date="2026-11-01",
                    insurer="Metlife",
                    type="ALL",
                )
            )

        self.assertEqual([row["RFC"] for row in result], ["RFC010101AAA", "RFC010101AAA"])
        self.assertEqual(query.filters[0].right.value, date(2026, 9, 1))
        self.assertEqual(query.filters[1].right.value, date(2026, 11, 1))
        db.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
