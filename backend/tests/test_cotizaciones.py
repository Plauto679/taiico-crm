import unittest

from pydantic import ValidationError

from backend.services.cotizaciones import QuoteCreate


class QuoteCreateTests(unittest.TestCase):
    def test_accepts_existing_client_with_matching_product(self):
        payload = QuoteCreate(client_id="client-1", ramo="GMM", producto="Primordial")
        self.assertEqual(payload.ramo, "GMM")

    def test_accepts_prospect_without_rfc(self):
        payload = QuoteCreate(prospect_name="Prospecto Uno", ramo="Vida", producto="Flexilife")
        self.assertEqual(payload.prospect_name, "Prospecto Uno")

    def test_rejects_product_from_other_branch(self):
        with self.assertRaises(ValidationError):
            QuoteCreate(prospect_name="Prospecto", ramo="GMM", producto="Totalife")

    def test_requires_exactly_one_client_source(self):
        with self.assertRaises(ValidationError):
            QuoteCreate(ramo="Vida", producto="Metalife")


if __name__ == "__main__":
    unittest.main()
