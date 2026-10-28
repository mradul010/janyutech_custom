(function () {
	function refresh_requested_by(frm) {
		const request_id = (frm._janyu_requested_by_request_id || 0) + 1;
		frm._janyu_requested_by_request_id = request_id;

		frappe.call({
			method: "janyutech_custom.material_request_requester.get_requested_by",
			args: {
				doctype: frm.doc.doctype,
				name: frm.doc.name,
				doc: frm.doc,
			},
			callback: function (r) {
				if (frm._janyu_requested_by_request_id !== request_id) {
					return;
				}

				frm.set_value("custom_requested_by", r.message || "");
			},
		});
	}

	function apply_company_addresses(frm, force) {
		if (!frm.doc.company || !frm.doc.naming_series) {
			return;
		}

		const lookup_key = [frm.doc.doctype, frm.doc.company, frm.doc.naming_series].join("::");
		if (!force && frm._janyu_company_address_lookup_key === lookup_key) {
			return;
		}
		frm._janyu_company_address_lookup_key = lookup_key;
		const addresses_at_request = {
			billing_address: frm.doc.billing_address,
			shipping_address: frm.doc.shipping_address,
		};
		const letter_head_at_request = frm.doc.letter_head;
		const automatic_addresses = frm._janyu_automatic_addresses || {};
		const automatic_letter_head = frm._janyu_automatic_letter_head;

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

				if (
					r.message.letter_head &&
					(!frm.doc.letter_head ||
						frm.doc.letter_head === automatic_letter_head ||
						(force && frm.doc.letter_head === letter_head_at_request))
				) {
					frm.set_value("letter_head", r.message.letter_head);
				}
				if (r.message.letter_head && frm.doc.letter_head === r.message.letter_head) {
					frm._janyu_automatic_letter_head = r.message.letter_head;
				}

				if (
					r.message.billing_address &&
					(!frm.doc.billing_address ||
						frm.doc.billing_address === automatic_addresses.billing_address ||
						(force && frm.doc.billing_address === addresses_at_request.billing_address))
				) {
					frm.set_value("billing_address", r.message.billing_address);
					frm._janyu_automatic_addresses = frm._janyu_automatic_addresses || {};
					frm._janyu_automatic_addresses.billing_address = r.message.billing_address;
				}

				if (
					r.message.shipping_address &&
					(!frm.doc.shipping_address ||
						frm.doc.shipping_address === automatic_addresses.shipping_address ||
						(force && frm.doc.shipping_address === addresses_at_request.shipping_address))
				) {
					frm.set_value("shipping_address", r.message.shipping_address);
					frm._janyu_automatic_addresses = frm._janyu_automatic_addresses || {};
					frm._janyu_automatic_addresses.shipping_address = r.message.shipping_address;
				}
			},
		});
	}

	function register_purchase_address_handlers(doctype) {
		frappe.ui.form.on(doctype, {
			refresh: refresh_requested_by,
			onload: function (frm) {
				apply_company_addresses(frm, false);
			},
			company: function (frm) {
				apply_company_addresses(frm, false);
			},
			naming_series: function (frm) {
				apply_company_addresses(frm, true);
			},
			items_add: refresh_requested_by,
			items_remove: refresh_requested_by,
			items_move: refresh_requested_by,
		});
	}

	function register_item_handlers(doctype) {
		frappe.ui.form.on(doctype, {
			material_request: refresh_requested_by,
			material_request_item: refresh_requested_by,
			purchase_order: refresh_requested_by,
			purchase_order_item: refresh_requested_by,
			item_code: refresh_requested_by,
		});
	}

	register_purchase_address_handlers("Purchase Order");
	register_purchase_address_handlers("Purchase Receipt");
	register_item_handlers("Purchase Order Item");
	register_item_handlers("Purchase Receipt Item");
})();
