import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import nowdate

from erpnext.buying.doctype.purchase_order.test_purchase_order import create_purchase_order
from janyutech_custom.purchase_order import PurchaseOrderPaymentScheduleMixin


class TestPurchaseOrderManualPaymentSchedule(FrappeTestCase):
    def _purchase_order(self, manual=True, payment_amounts=(200,), invoice_portions=(50,)):
        purchase_order = create_purchase_order(qty=1, rate=400, do_not_save=True)
        purchase_order.custom_manual_payment_schedule = int(manual)
        purchase_order.payment_schedule = []
        for payment_amount, invoice_portion in zip(payment_amounts, invoice_portions):
            purchase_order.append(
                "payment_schedule",
                {
                    "due_date": nowdate(),
                    "payment_amount": payment_amount,
                    "invoice_portion": invoice_portion,
                },
            )
        return purchase_order

    def test_manual_amount_survives_save_reload_and_submit(self):
        purchase_order = self._purchase_order()
        purchase_order.save()

        self.assertEqual(purchase_order.payment_schedule[0].payment_amount, 200)
        self.assertEqual(purchase_order.payment_schedule[0].invoice_portion, 50)
        self.assertEqual(purchase_order.payment_schedule[0].base_payment_amount, 200)

        purchase_order.reload()
        self.assertEqual(purchase_order.payment_schedule[0].payment_amount, 200)
        purchase_order.submit()
        self.assertEqual(purchase_order.payment_schedule[0].payment_amount, 200)

    def test_manual_amounts_use_total_for_invoice_portion(self):
        purchase_order = self._purchase_order(
            payment_amounts=(100, 300), invoice_portions=(25, 75)
        )
        purchase_order.save()

        self.assertEqual(purchase_order.payment_schedule[0].payment_amount, 100)
        self.assertEqual(purchase_order.payment_schedule[1].payment_amount, 300)

    def test_zero_total_sets_invoice_portion_to_zero(self):
        self.assertEqual(PurchaseOrderPaymentScheduleMixin._calculate_invoice_portion(200, 0, 2), 0)

    def test_invoice_portion_uses_total_when_totals_differ(self):
        self.assertEqual(
            PurchaseOrderPaymentScheduleMixin._calculate_invoice_portion(100, 300, 2),
            33.33,
        )

    def test_manual_payment_change_reverse_calculates_invoice_portion(self):
        payment_amount, invoice_portion = PurchaseOrderPaymentScheduleMixin._resolve_manual_values(
            {"payment_amount": 100, "invoice_portion": 50},
            {"payment_amount": 200, "invoice_portion": 50},
            400,
            2,
        )
        self.assertEqual(payment_amount, 100)
        self.assertEqual(invoice_portion, 25)

    def test_partial_schedule_saves_without_total_equality_validation(self):
        purchase_order = self._purchase_order(manual=False)
        purchase_order.save()
        self.assertEqual(purchase_order.payment_schedule[0].payment_amount, 200)

    def test_manual_mode_rejects_negative_amount(self):
        purchase_order = self._purchase_order(payment_amounts=(-1,))
        self.assertRaises(frappe.ValidationError, purchase_order.save)

    def test_manual_mode_rejects_amount_above_total(self):
        purchase_order = self._purchase_order(payment_amounts=(401,))
        self.assertRaises(frappe.ValidationError, purchase_order.save)
