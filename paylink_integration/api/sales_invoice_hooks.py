import frappe


def before_submit_action(doc, method):
    frappe.log("log msg in order not to leave it blank")
