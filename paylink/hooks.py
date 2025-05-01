app_name = "paylink"
app_title = "Paylink Integration"
app_publisher = "Mostafa Yasin"
app_description = "Paylink provides you with a competitive payment gateway and solutions that are suitable for you."
app_email = "mostafa.a.yasin@gmail.com"
app_license = "mit"


fixtures = [
    {
        "dt": "Custom Field",
        "filters": [
            [
                "name",
                "in",
                [
                    "Sales Invoice-custom_paylink_details",
                    "ales Invoice-custom_paylink_payment_link",
                    "Sales Invoice-custom_paylink_transaction_id",
                    "Sales Invoice-custom_column_break_pcmhh",
                    "Sales Invoice-custom_paylink_payment_status",
                    "Sales Invoice-custom_paylink"
                ],
            ]
        ],
    },
    
    {
        "dt": "DocType",
        "filters": [
            [
                "name",
                "in",
                ["Paylink Settings"],
            ]
        ],
    }
]


#------------------------Actions------------------------#

doc_events = {
    "before_submit": {
        "paylink.sales_invoice_hooks.before_submit_action"
    }
}


