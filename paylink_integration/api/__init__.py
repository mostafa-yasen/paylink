from typing import Any

import frappe
from paylink_integration.api.webhook import PaylinkWebhookHandler


@frappe.whitelist(allow_guest=True, methods=["POST"])
def callback(*args, **kwargs) -> dict[str, Any]:
    """
    Handle webhook events from Paylink.

    This endpoint processes payment notifications from Paylink when an invoice is paid.
    It verifies the authenticity of the request and updates the corresponding Sales Invoice.
    """
    handler = PaylinkWebhookHandler()
    return handler.process()
