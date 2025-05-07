# Copyright (c) 2025, Mostafa Yasin and contributors
# For license information, please see license.txt

from __future__ import annotations

from enum import Enum
from typing import TypedDict

from paylink import Paylink, PaylinkProduct
from paylink.paylink_invoice_response import PaylinkInvoiceResponse

import frappe
from frappe.model.document import Document

MINIMUM_AMOUNT = 5.0


class Product(TypedDict):
    qty: int
    price: float
    title: str
    image_src: str | None


class EnvironmentOptions(Enum):
    TEST = "Test"
    PRODUCTION = "Production"


class PaylinkSettings(Document):
    enabled: bool
    environment: str
    api_key: str
    api_secret: str
    callback_url: str
    currency: str

    def validate(self) -> None:
        if not self.environment or self.environment not in [
            e.value for e in EnvironmentOptions
        ]:
            frappe.throw(
                f"Environment is required and must be one of {[e.value for e in EnvironmentOptions]}"
            )

        if self.environment == EnvironmentOptions.PRODUCTION.value:
            if not self.api_key:
                frappe.throw("API Key is required")

            if not self.api_secret:
                frappe.throw("API Secret is required")

            if not self.callback_url:
                frappe.throw("Callback URL is required")

            if not self.currency:
                frappe.throw("Currency is required")

    def get_paylink(self) -> Paylink:
        """
        Retrieve a Paylink instance configured with the current settings.

        Raises:
            ValueError: If the Paylink feature is not enabled.
            TypeError: If the secret key is not a string.

        Returns:
            Paylink: An instance of the Paylink class configured with the environment,
                     API key, and secret key.
        """
        if not self.enabled:
            raise ValueError("Paylink feature is not enabled")

        secret_key = self.get_password("api_secret")
        if not isinstance(secret_key, str):
            raise TypeError(f"Secret key must be a string, got {type(secret_key)}")

        return Paylink(
            environment=self.environment.lower(),
            api_id=self.api_key,
            secret_key=secret_key,
        )

    def create_invoice(
        self,
        amount: float,
        client_mobile: str,
        client_name: str,
        order_number: str,
        products: list[Product],
    ) -> PaylinkInvoiceResponse:
        """Create an invoice with the given details"""
        if amount < MINIMUM_AMOUNT:
            raise ValueError(f"Amount must be at least {MINIMUM_AMOUNT}")

        paylink = self.get_paylink()
        invoice_details = paylink.add_invoice(
            amount=amount,
            client_mobile=client_mobile,
            client_name=client_name,
            order_number=order_number,
            products=[PaylinkProduct(**p) for p in products],
            callback_url=self.callback_url,
            currency=self.currency,
        )
        return invoice_details

    def get_invoice(self, transaction_no: str) -> PaylinkInvoiceResponse:
        """Get invoice details by transaction number"""
        paylink = self.get_paylink()
        return paylink.get_invoice(transaction_no=transaction_no)

    def cancel_invoice(self, transaction_no: str) -> bool:
        """Cancel invoice by transaction number"""
        paylink = self.get_paylink()
        return paylink.cancel_invoice(transaction_no=transaction_no)

    def payment_status(self, transaction_no: str) -> str:
        """Get payment status by transaction number"""
        paylink = self.get_paylink()
        return paylink.order_status(transaction_no=transaction_no)
