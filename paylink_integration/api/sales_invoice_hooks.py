import frappe
from paylink_integration.paylink_integration.doctype.paylink_settings.paylink_settings import (
    PaylinkSettings,
)

_logger = frappe.logger("paylink_integration")


def before_submit(doc, *args, **kwargs) -> None:
    paylink_settings: PaylinkSettings = frappe.get_single("Paylink Settings")  # type: ignore
    invoice_details = paylink_settings.create_invoice(
        doc.grand_total,
        client_mobile="",
        client_name=doc.customer,
        order_number=doc.name,
        products=list(
            map(
                lambda row: {
                    "title": row.item_code,
                    "qty": row.qty,
                    "price": row.rate,
                    "image_src": row.image,
                },
                doc.items,
            )
        ),
    )
    _logger.info(
        "Paylink invoice created for %s with transaction no %s",
        doc.name,
        invoice_details.transaction_no,
    )
    doc.paylink_transaction_id = invoice_details.transaction_no
    doc.paylink_payment_link = invoice_details.url
