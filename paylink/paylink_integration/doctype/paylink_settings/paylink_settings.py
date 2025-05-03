# Copyright (c) 2025, Mostafa Yasin and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from paylink import Paylink, PaylinkProduct

class PaylinkSettings(Document):
    def get_paylink(self):
        if not self.enabled:
            frappe.throw("Paylink feature is not enabled")
        return Paylink(self.environment, self.api_key, self.api_secret)

    def create_invoice(self, amount, client_mobile, client_name, order_number, products, callback_url, currency):
        paylink = self.get_paylink()
        invoice_details = paylink.add_invoice(
            amount=amount,
            client_mobile=client_mobile,
            client_name=client_name,
            order_number=order_number,
            products=[PaylinkProduct(**p) for p in products],
            callback_url=callback_url,
            currency=currency,
        )
        return invoice_details

    def get_invoice(self, transaction_no):
        paylink = self.get_paylink()
        return paylink.get_invoice(transaction_no=transaction_no)

    def cancel_invoice(self, transaction_no):
        paylink = self.get_paylink()
        return paylink.cancel_invoice(transaction_no=transaction_no)

    def payment_status(self, transaction_no):
        paylink = self.get_paylink()
        return paylink.order_status(transaction_no=transaction_no)
