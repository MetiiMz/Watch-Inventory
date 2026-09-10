# -*- coding: utf-8 -*-
"""Tests for the versioned DRF layer under /api/v1/."""
import json

from django.test import TestCase

from inventory.models import Payment, Product, Sale, Tracking
from tests.helpers import make_product, product_payload, sale_payload


class ApiV1ProductsTests(TestCase):
    """CRUD + filters + pagination + validation shape."""

    def test_full_crud_cycle(self):
        r = self.client.post("/api/v1/products", product_payload(),
                             content_type="application/json")
        self.assertEqual(r.status_code, 201, r.content)
        pid = r.json()["id"]
        self.assertTrue(r.json()["is_available"])

        r = self.client.patch(f"/api/v1/products/{pid}",
                              data=json.dumps({"brand": "Rolex"}),
                              content_type="application/json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["brand"], "Rolex")
        self.assertEqual(r.json()["office_code"],
                         Product.objects.get(id=pid).office_code)

        r = self.client.get("/api/v1/products")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["count"], 1)

        r = self.client.delete(f"/api/v1/products/{pid}")
        self.assertEqual(r.status_code, 204)

    def test_validation_error_is_json_400(self):
        r = self.client.post("/api/v1/products", {"name": ""},
                             content_type="application/json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("error", r.json())
        self.assertIn("الزامی", r.json()["error"])

    def test_filters_and_summary(self):
        make_product(brand="Rolex")
        make_product(office_code="OF-2", website_code="WS-2", available=False)
        r = self.client.get("/api/v1/products", {"brand": "Rolex"})
        self.assertEqual(r.json()["count"], 1)
        r = self.client.get("/api/v1/products", {"status": "unavailable"})
        self.assertEqual(r.json()["count"], 1)
        r = self.client.get("/api/v1/products/summary")
        self.assertEqual(r.json(), {"count": 2, "available": 1})

    def test_pagination(self):
        for i in range(3):
            make_product(office_code=f"OF-PG{i}", website_code=f"WS-PG{i}")
        r = self.client.get("/api/v1/products", {"page": 1, "page_size": 2})
        self.assertEqual(r.json()["count"], 3)
        self.assertEqual(len(r.json()["results"]), 2)

    def test_404_is_json(self):
        r = self.client.get("/api/v1/products/999999")
        self.assertEqual(r.status_code, 404)
        self.assertIn("detail", r.json())


class ApiV1SalesTests(TestCase):
    """Sale endpoints — create/PATCH/delete + next_code preview."""

    def test_create_cash_sale_201(self):
        p = make_product()
        r = self.client.post("/api/v1/sales", sale_payload(p.id),
                             content_type="application/json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.json()["customer"], "علی")
        self.assertEqual(r.json()["payment_type_fa"], "نقدی")

    def test_create_deposit_201_and_receipt(self):
        p = make_product()
        r = self.client.post("/api/v1/sales", sale_payload(
            p.id, payment_type="deposit", paid_cash="400000"),
            content_type="application/json")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(Payment.objects.filter(sale_id=r.json()["id"]).count(), 1)

    def test_error_contract_matches_frontend(self):
        p = make_product()
        r = self.client.post("/api/v1/sales", sale_payload(p.id, customer=""),
                             content_type="application/json")
        self.assertEqual(r.status_code, 400)
        self.assertFalse(r.json()["ok"])
        self.assertIn("نام خریدار", r.json()["error"])

    def test_patch_preserves_fields(self):
        p = make_product()
        sid = self.client.post("/api/v1/sales", sale_payload(p.id),
                               content_type="application/json").json()["id"]
        r = self.client.patch(f"/api/v1/sales/{sid}",
                              data=json.dumps({"notes": "n"}),
                              content_type="application/json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["customer"], "علی")
        self.assertEqual(r.json()["notes"], "n")

    def test_next_code_and_delete(self):
        r = self.client.get("/api/v1/sales", {"next_code": "1"})
        self.assertEqual(r.status_code, 200)
        self.assertIn("next_invoice_code", r.json())
        p = make_product()
        sid = self.client.post("/api/v1/sales", sale_payload(p.id),
                               content_type="application/json").json()["id"]
        r = self.client.delete(f"/api/v1/sales/{sid}")
        self.assertEqual(r.status_code, 204)
        self.assertTrue(Product.objects.get(id=p.id).available)

    def test_bulk_delete(self):
        p = make_product()
        sid = self.client.post("/api/v1/sales", sale_payload(p.id),
                               content_type="application/json").json()["id"]
        r = self.client.post("/api/v1/sales/bulk-delete",
                             data=json.dumps({"ids": [sid]}),
                             content_type="application/json")
        self.assertEqual(r.json(), {"deleted": 1})


class ApiV1PaymentsRepairsTrackingTests(TestCase):
    """Remaining /api/v1/ resources."""

    def test_payments_crud_and_actions(self):
        r = self.client.post("/api/v1/payments", {
            "product_name": "W", "total_amount": "1000", "paid_amount": "100"},
            content_type="application/json")
        self.assertEqual(r.status_code, 201, r.content)
        pid = r.json()["id"]
        self.assertEqual(r.json()["remaining"], 900)

        r = self.client.post(f"/api/v1/payments/{pid}/add",
                             data=json.dumps({"amount": "900"}),
                             content_type="application/json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["paid_amount"], 1000)

        r = self.client.get("/api/v1/payments", {"status": "paid"})
        self.assertEqual(r.json()["count"], 1)

        r = self.client.delete(f"/api/v1/payments/{pid}")
        self.assertEqual(r.status_code, 204)

    def test_repairs_crud_and_status_action(self):
        r = self.client.post("/api/v1/repairs", {"watch_name": "Seiko R"},
                             content_type="application/json")
        self.assertEqual(r.status_code, 201, r.content)
        rid = r.json()["id"]
        r = self.client.post(f"/api/v1/repairs/{rid}/set-status",
                             data=json.dumps({"status": "delivered"}),
                             content_type="application/json")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["return_date"])
        r = self.client.post("/api/v1/repairs/bulk-delete",
                             data=json.dumps({"ids": [rid]}),
                             content_type="application/json")
        self.assertEqual(r.json(), {"deleted": 1})

    def test_tracking_crud(self):
        r = self.client.post("/api/v1/tracking", {"item_name": "Order A"},
                             content_type="application/json")
        self.assertEqual(r.status_code, 201)
        tid = r.json()["id"]
        r = self.client.put(f"/api/v1/tracking/{tid}",
                            data=json.dumps({"item_name": "Order A", "status": "ordered"}),
                            content_type="application/json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["status"], "ordered")
        self.assertEqual(Tracking.objects.get(id=tid).item_name, "Order A")


class ApiV1InfraTests(TestCase):
    """Brands, settings, calendar, reports under /api/v1/."""

    def test_brands_and_settings(self):
        r = self.client.post("/api/v1/brands", {"name": "برند"},
                             content_type="application/json")
        self.assertEqual(r.json(), {"ok": True})
        r = self.client.get("/api/v1/brands")
        self.assertEqual(r.json()["brands"], ["برند"])
        r = self.client.post("/api/v1/brands/delete", {"name": "برند"},
                             content_type="application/json")
        self.assertEqual(r.json(), {"ok": True})

        r = self.client.post("/api/v1/settings", {"store_name": "تیک"},
                             content_type="application/json")
        r = self.client.get("/api/v1/settings")
        self.assertEqual(r.json()["store_name"], "تیک")

    def test_calendar_and_report(self):
        make_product(purchase_date="2026-09-10")
        r = self.client.get("/api/v1/calendar", {"jy": 1405, "jm": 6})
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["ok"])
        events = [e for c in r.json()["cells"] if c for e in c["purchases"]]
        self.assertEqual(len(events), 1)

        r = self.client.get("/api/v1/reports/monthly-activity", {"year": 1404})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["year"], 1404)
        r = self.client.get("/api/v1/reports/monthly-activity", {"year": "x"})
        self.assertEqual(r.status_code, 400)
