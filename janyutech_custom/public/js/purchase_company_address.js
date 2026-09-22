(function () {
	function apply_company_addresses(frm) {
		if (!frm.doc.company || !frm.doc.naming_series) {
			return;
		}

		const lookup_key = [frm.doc.doctype, frm.doc.company, frm.doc.naming_series].join("::");
		if (frm._janyu_company_address_lookup_key === lookup_key) {
			return;
		}
		frm._janyu_company_address_lookup_key = lookup_key;

		frappe.call({
			method: "janyutech_custom.company_address.get_company_addresses_for_series",
			args: {
				doctype: frm.doc.doctype,
				company: frm.doc.company,
				naming_series: frm.doc.naming_series,
			},
			callback: function (r) {
				if (frm._janyu_company_address_lookup_key !== lookup_key) {
					return;
				}

				if (!r.message || !r.message.location) {
					frm._janyu_company_address_lookup_key = null;
					return;
				}

				if (r.message.billing_address) {
					frm.set_value({
						billing_address: r.message.billing_address,
						billing_address_display: r.message.billing_address_display || "",
					});
				}

				if (r.message.shipping_address) {
					frm.set_value({
						shipping_address: r.message.shipping_address,
						shipping_address_display: r.message.shipping_address_display || "",
					});
				}
			},
		});
	}

	function register_purchase_address_handlers(doctype) {
		frappe.ui.form.on(doctype, {
			onload: apply_company_addresses,
			refresh: apply_company_addresses,
			company: apply_company_addresses,
			naming_series: apply_company_addresses,
		});
	}

	register_purchase_address_handlers("Purchase Order");
	register_purchase_address_handlers("Purchase Receipt");
})();
