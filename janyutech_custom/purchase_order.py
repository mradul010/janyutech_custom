from frappe import _, throw
from frappe.utils import flt


class PurchaseOrderPaymentScheduleMixin:
    def set_payment_schedule(self):
        manual_values = {
            self._payment_schedule_key(row): {
                "payment_amount": flt(row.payment_amount),
                "invoice_portion": flt(row.invoice_portion),
            }
            for row in self.get("payment_schedule")
        }
        previous_values = {}
        previous_doc = self.get_doc_before_save()
        if previous_doc:
            previous_values = {
                self._payment_schedule_key(row): {
                    "payment_amount": flt(row.payment_amount),
                    "invoice_portion": flt(row.invoice_portion),
                }
                for row in previous_doc.get("payment_schedule")
            }

        super().set_payment_schedule()

        total = flt(self.get("total"))
        conversion_rate = flt(self.get("conversion_rate"))
        for row in self.get("payment_schedule"):
            key = self._payment_schedule_key(row)
            if key in manual_values:
                payment_amount, invoice_portion = self._resolve_manual_values(
                    manual_values[key],
                    previous_values.get(key),
                    total,
                    row.precision("invoice_portion"),
                )
            else:
                invoice_portion = flt(row.invoice_portion)
                payment_amount = flt(
                    total * invoice_portion / 100,
                    row.precision("payment_amount"),
                ) if total else 0

            row.payment_amount = payment_amount
            row.invoice_portion = invoice_portion
            row.base_payment_amount = flt(
                row.payment_amount * conversion_rate,
                row.precision("base_payment_amount"),
            )
            self.set_term_outstanding(row, self.docstatus == 1 and getattr(self, "_action", None) != "submit")

    def validate_payment_schedule_amount(self):
        if not self.get("payment_schedule"):
            return

        conversion_rate = flt(self.get("conversion_rate"))
        tolerance = 0.1

        for row in self.get("payment_schedule"):
            payment_amount = flt(row.payment_amount, row.precision("payment_amount"))
            base_payment_amount = flt(row.base_payment_amount, row.precision("base_payment_amount"))
            if payment_amount < 0:
                throw(_("Payment Schedule row {0} cannot have a negative Payment Amount").format(row.idx))
            if base_payment_amount < 0:
                throw(_("Payment Schedule row {0} cannot have a negative base Payment Amount").format(row.idx))

            expected_base_amount = flt(
                payment_amount * conversion_rate,
                row.precision("base_payment_amount"),
            )
            if abs(base_payment_amount - expected_base_amount) > tolerance:
                throw(_("Payment Schedule row {0} has an invalid base Payment Amount").format(row.idx))

    @staticmethod
    def _payment_schedule_key(row):
        return row.name or row.idx

    @staticmethod
    def _calculate_invoice_portion(payment_amount, total, precision):
        if not total:
            return 0
        return flt(payment_amount * 100 / total, precision)

    @classmethod
    def _resolve_manual_values(cls, current, previous, total, precision):
        payment_amount = current["payment_amount"]
        invoice_portion = current["invoice_portion"]
        if not previous and payment_amount and not invoice_portion:
            invoice_portion = cls._calculate_invoice_portion(payment_amount, total, precision)
        if previous:
            payment_changed = payment_amount != previous["payment_amount"]
            portion_changed = invoice_portion != previous["invoice_portion"]
            if payment_changed and not portion_changed:
                invoice_portion = cls._calculate_invoice_portion(payment_amount, total, precision)

        if not total:
            return 0, 0

        payment_amount = flt(total * invoice_portion / 100, precision)
        return payment_amount, invoice_portion
