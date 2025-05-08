import base64
import json
from typing import Any

import frappe
from erpnext.accounts.doctype.payment_entry.payment_entry import PaymentEntry
from erpnext.accounts.doctype.sales_invoice.sales_invoice import SalesInvoice
from frappe.utils import nowdate
from paylink_integration.paylink_integration.doctype.paylink_settings.paylink_settings import (
    PaylinkSettings,
)

_logger = frappe.logger("paylink_integration")


class PaylinkWebhookHandler:
    """
    Handler for Paylink payment webhook notifications.
    This class encapsulates all logic for processing webhook events from Paylink.
    """

    data: dict[str, Any] | None
    response: dict[str, Any]
    http_status_code: int

    def __init__(self, request=None):
        """
        Initialize the webhook handler.

        Args:
            request: The Frappe request object containing webhook data
        """
        self.request = request or frappe.request
        self.settings: PaylinkSettings = frappe.get_single("Paylink Settings")  # type: ignore
        self.data = None
        self.response = {"success": False}
        self.http_status_code = 200

    def process(self) -> dict[str, Any]:
        """
        Main entry point for processing the webhook.

        Returns:
            Dict containing success status and optional message
        """
        try:
            if not self._extract_data():
                return self.response

            if not self._validate_signature():
                return self.response

            if not self._validate_required_fields():
                return self.response

            if not self._check_payment_status():
                return self.response

            invoice = self._get_sales_invoice()
            if not invoice:
                return self.response

            if not self._validate_transaction(invoice):
                return self.response

            if not self._validate_amount(invoice):
                return self.response

            self._process_payment(invoice)

            self.response = {"success": True}
            _logger.info(
                f"Successfully processed payment for {self.data['merchantOrderNumber']}"  # type: ignore
            )

        except Exception as e:
            _logger.exception(f"Error processing Paylink webhook: {str(e)}")
            self.response = {"success": False, "message": str(e)}
            self.http_status_code = 500

        finally:
            frappe.local.response.http_status_code = self.http_status_code
            return self.response

    def _extract_data(self) -> bool:
        """Extract and parse the webhook data from the request."""
        try:
            if self.request and self.request.data:
                self.data = json.loads(self.request.data)
                _logger.debug(f"Received Paylink webhook: {self.data}")
                return True
            else:
                self.response = {"success": False, "message": "No data received"}
                self.http_status_code = 400
                return False
        except json.JSONDecodeError:
            self.response = {"success": False, "message": "Invalid JSON payload"}
            self.http_status_code = 400
            return False

    def _validate_signature(self) -> bool:
        """Validate the webhook signature if a secret is configured."""
        if hasattr(self.settings, "webhook_secret") and self.settings.webhook_secret:
            if not self._verify_webhook_signature(
                self.settings.get_password("webhook_secret") # type: ignore
            ):
                _logger.warning("Invalid webhook signature")
                self.response = {"success": False, "message": "Invalid signature"}
                self.http_status_code = 401
                return False
        return True

    def _validate_required_fields(self) -> bool:
        """Ensure all required fields are present in the webhook data."""
        required_fields = ["transactionNo", "merchantOrderNumber", "orderStatus"]
        if not self.data:
            _logger.error("No data received in webhook")
            self.response = {"success": False, "message": "No data received"}
            self.http_status_code = 400
            return False

        for field in required_fields:
            if field not in self.data:
                _logger.error(f"Missing required field: {field}")
                self.response = {
                    "success": False,
                    "message": f"Missing required field: {field}",
                }
                self.http_status_code = 400
                return False
        return True

    def _check_payment_status(self) -> bool:
        """Check if the order status is 'Paid'. Ignore other statuses."""
        if not self.data:
            _logger.error("No data received in webhook")
            self.response = {"success": False, "message": "No data received"}
            self.http_status_code = 400
            return False

        order_number = self.data["merchantOrderNumber"]
        order_status = self.data["orderStatus"]

        if order_status != "Paid":
            _logger.info(
                f"Order {order_number} status is {order_status}, not processing"
            )
            self.response = {
                "success": True,
                "message": f"Ignoring {order_status} status",
            }
            return False
        return True

    def _get_sales_invoice(self) -> SalesInvoice | None:
        """Retrieve the Sales Invoice referenced in the webhook data."""
        if not self.data:
            _logger.error("No data received in webhook")
            self.response = {"success": False, "message": "No data received"}
            self.http_status_code = 400
            return None

        order_number = self.data["merchantOrderNumber"]
        try:
            sales_invoice = frappe.get_doc("Sales Invoice", order_number)
            return sales_invoice  # type: ignore
        except frappe.DoesNotExistError:
            _logger.error(f"Sales Invoice {order_number} not found")
            self.response = {
                "success": False,
                "message": f"Sales Invoice {order_number} not found",
            }
            self.http_status_code = 404
            return None

    def _validate_transaction(self, invoice: SalesInvoice) -> bool:
        """Verify that the transaction ID matches the one stored in the Sales Invoice."""
        if not self.data:
            _logger.error("No data received in webhook")
            self.response = {"success": False, "message": "No data received"}
            self.http_status_code = 400
            return False

        transaction_no = self.data["transactionNo"]
        if invoice.paylink_transaction_id != transaction_no:  # type: ignore
            _logger.error(
                "Transaction ID mismatch for %s. Expected %s, got %s",
                invoice.name,
                invoice.paylink_transaction_id,  # type: ignore
                transaction_no,
            )
            self.response = {"success": False, "message": "Transaction ID mismatch"}
            self.http_status_code = 400
            return False
        return True

    def _validate_amount(self, invoice: SalesInvoice) -> bool:
        """Verify that the payment amount matches the invoice total if provided."""
        if not self.data:
            _logger.error("No data received in webhook")
            self.response = {"success": False, "message": "No data received"}
            self.http_status_code = 400
            return False

        amount = self.data["amount"]
        if (
            amount and abs(float(invoice.grand_total) - float(amount)) > 0.01
        ):  # Allow small rounding differences
            _logger.error(
                f"Amount mismatch for {invoice.name}. Expected {invoice.grand_total}, got {amount}"
            )
            self.response = {"success": False, "message": "Amount mismatch"}
            self.http_status_code = 400
            return False
        return True

    def _process_payment(self, invoice: SalesInvoice) -> None:
        """Process the payment for the Sales Invoice."""
        if not self.data:
            _logger.error("No data received in webhook")
            self.response = {"success": False, "message": "No data received"}
            self.http_status_code = 400
            return

        transaction_no = self.data["transactionNo"]
        payment_type = self.data.get("paymentType", "Unknown")

        self._create_payment_entry(invoice, transaction_no, payment_type)

    def _create_payment_entry(
        self, sales_invoice: SalesInvoice, transaction_no: str, payment_type: str
    ) -> None:
        """Create a Payment Entry for the paid Sales Invoice."""
        if sales_invoice.docstatus != 1:
            _logger.warning(
                f"Sales Invoice {sales_invoice.name} is not submitted, cannot process payment"
            )
            return

        if sales_invoice.status == "Paid":
            _logger.info(f"Sales Invoice {sales_invoice.name} is already paid")
            return

        try:
            # Create a Payment Entry
            payment_entry: PaymentEntry = frappe.get_doc(  # type: ignore
                {
                    "doctype": "Payment Entry",
                    "payment_type": "Receive",
                    "party_type": "Customer",
                    "party": sales_invoice.customer,
                    "paid_amount": sales_invoice.grand_total,
                    "received_amount": sales_invoice.grand_total,
                    "reference_no": transaction_no,
                    "reference_date": nowdate(),
                    "remarks": f"Payment via Paylink ({payment_type})",
                    "references": [
                        {
                            "reference_doctype": "Sales Invoice",
                            "reference_name": sales_invoice.name,
                            "allocated_amount": sales_invoice.grand_total,
                        }
                    ],
                }
            )

            # Set payment method and accounts
            mode_of_payment = self._get_payment_method_mapping(payment_type)
            payment_entry.mode_of_payment = mode_of_payment  # type: ignore

            payment_entry.paid_from = frappe.get_cached_value(  # type: ignore
                "Company", sales_invoice.company, "default_receivable_account"
            )
            payment_entry.paid_to = self._get_default_bank_cash_account(  # type: ignore
                sales_invoice.company, mode_of_payment
            )

            payment_entry.setup_party_account_field()
            payment_entry.set_missing_values()
            payment_entry.set_exchange_rate()
            payment_entry.set_amounts()

            # Submit the payment entry
            payment_entry.insert()
            payment_entry.submit()

            _logger.info(
                f"Created payment entry {payment_entry.name} for Sales Invoice {sales_invoice.name}"
            )
        except Exception as e:
            _logger.exception(
                f"Error creating payment entry for {sales_invoice.name}: {str(e)}"
            )
            raise

    def _verify_webhook_signature(self, secret: str) -> bool:
        """
        Verify the webhook using base64-encoded authentication.

        This checks if the Authorization header contains the base64-encoded webhook secret.
        """
        auth_header = self.request.headers.get("Authorization")
        if not auth_header:
            _logger.warning("No Authorization header in webhook request")
            return False

        # Check if it's a Bearer token
        if auth_header.startswith("Bearer "):
            received_token = auth_header[7:]  # Remove "Bearer " prefix

            # Create the expected token (base64 encoded webhook_secret)
            expected_token = base64.b64encode(secret.encode()).decode()

            # Compare the tokens
            return received_token == expected_token
        else:
            _logger.warning("Authorization header is not in Bearer format")
            return False

    def _get_payment_method_mapping(self, payment_type: str) -> str:
        """Map Paylink payment types to Frappe payment methods."""
        paylink_payment_method_mapping = {
            "mada": "Mada Card",
            "visaMastercard": "Credit Card",
            "stcpay": "STC Pay",
            "tabby": "Tabby",
            "tamara": "Tamara",
            "urpay": "UrPay",
            "a2a": "Bank Transfer",
            "amex": "American Express",
            "sadad": "Sadad",
        }
        return paylink_payment_method_mapping.get(payment_type, "Online Payment")

    def _get_default_bank_cash_account(self, company: str, mode_of_payment: str) -> str:
        """Get default bank or cash account for payment method."""
        account = frappe.get_value(
            "Mode of Payment Account",
            {"parent": mode_of_payment, "company": company},
            "default_account",
        )

        if not account:
            # Fallback to a default bank account
            account = frappe.get_value("Company", company, "default_bank_account")

        return account  # type: ignore
