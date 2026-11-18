(function () {
	function refresh_requested_values(frm) {
		const request_id = (frm._janyu_requested_by_request_id || 0) + 1;
		frm._janyu_requested_by_request_id = request_id;

		frappe.call({
			method: "janyutech_custom.material_request_requester.get_purchase_request_values",
			args: {
				doctype: frm.doc.doctype,
				name: frm.doc.name,
				doc: frm.doc,
			},
			callback: function (r) {
				if (frm._janyu_requested_by_request_id !== request_id) {
					return;
				}

				const values = r.message || {};
				set_automatic_value(frm, "custom_requested_by", values.requested_by);
				set_automatic_value(frm, "custom_purchase_req_no", values.purchase_req_no);
			},
		});
	}

	function set_automatic_value(frm, fieldname, value) {
		const current_value = frm.doc[fieldname] || "";
		const previous_automatic_value = frm[`_janyu_automatic_${fieldname}`] || "";
		if (!current_value || current_value === previous_automatic_value) {
			frm.set_value(fieldname, value || "");
			frm[`_janyu_automatic_${fieldname}`] = value || "";
		} else if (value === current_value) {
			frm[`_janyu_automatic_${fieldname}`] = current_value;
		}
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
			refresh: refresh_requested_values,
			total: recalculate_manual_payment_schedule,
			transaction_date: refresh_payment_schedule_terms,
			payment_schedule_add: refresh_payment_schedule_terms,
			onload: function (frm) {
				apply_company_addresses(frm, false);
			},
			company: function (frm) {
				apply_company_addresses(frm, false);
			},
			naming_series: function (frm) {
				apply_company_addresses(frm, true);
			},
			items_add: refresh_requested_values,
			items_remove: refresh_requested_values,
			items_move: refresh_requested_values,
		});
	}

	function register_item_handlers(doctype) {
		frappe.ui.form.on(doctype, {
			material_request: refresh_requested_values,
			material_request_item: refresh_requested_values,
			purchase_order: refresh_requested_values,
			purchase_order_item: refresh_requested_values,
			item_code: refresh_requested_values,
		});
	}

	register_purchase_address_handlers("Purchase Order");
	register_purchase_address_handlers("Purchase Receipt");
	register_item_handlers("Purchase Order Item");
	register_item_handlers("Purchase Receipt Item");

	frappe.ui.form.on("Payment Schedule", {
		payment_term: function (frm, cdt, cdn) {
			if (frm.doc.doctype !== "Purchase Order") {
				return;
			}

			fetch_payment_term_details(frm, cdt, cdn);
		},
		invoice_portion: function (frm, cdt, cdn) {
			if (frm.doc.doctype !== "Purchase Order" || is_updating_payment_schedule(frm)) {
				return;
			}

			const row = locals[cdt][cdn];
			if (!row) {
				return;
			}
			with_payment_schedule_update(frm, function () {
				set_payment_schedule_value(
					frm,
					cdt,
					cdn,
					"payment_amount",
					calculate_manual_payment_amount(frm, row)
				);
				set_payment_schedule_base_amount(frm, cdt, cdn);
			});
		},
		payment_amount: function (frm, cdt, cdn) {
			if (frm.doc.doctype !== "Purchase Order" || is_updating_payment_schedule(frm)) {
				return;
			}

			const row = locals[cdt][cdn];
			if (!row) {
				return;
			}
			with_payment_schedule_update(frm, function () {
				set_payment_schedule_value(
					frm,
					cdt,
					cdn,
					"invoice_portion",
					calculate_manual_invoice_portion(frm, row)
				);
				set_payment_schedule_base_amount(frm, cdt, cdn);
			});
		},
	});

	function recalculate_manual_payment_schedule(frm) {
		if (frm.doc.doctype !== "Purchase Order") {
			return;
		}

		with_payment_schedule_update(frm, function () {
			(frm.doc.payment_schedule || []).forEach(function (row) {
				set_payment_schedule_value(
					frm,
					row.doctype,
					row.name,
					"invoice_portion",
					calculate_manual_invoice_portion(frm, row)
				);
				set_payment_schedule_base_amount(frm, row.doctype, row.name);
			});
		});
	}

	function refresh_payment_schedule_terms(frm, cdt, cdn) {
		if (frm.doc.doctype !== "Purchase Order") {
			return;
		}

		if (cdt && cdn) {
			fetch_payment_term_details(frm, cdt, cdn);
			return;
		}

		(frm.doc.payment_schedule || []).forEach(function (row) {
			if (row.payment_term) {
				fetch_payment_term_details(frm, row.doctype, row.name);
			}
		});
	}

	function fetch_payment_term_details(frm, cdt, cdn) {
		const row = locals[cdt] && locals[cdt][cdn];
		if (!row || !row.payment_term) {
			return;
		}

		frm._janyu_payment_term_request_ids = frm._janyu_payment_term_request_ids || {};
		const request_id = (frm._janyu_payment_term_request_ids[cdn] || 0) + 1;
		frm._janyu_payment_term_request_ids[cdn] = request_id;

		frappe.call({
			method: "erpnext.controllers.accounts_controller.get_payment_term_details",
			args: {
				term: row.payment_term,
				bill_date: frm.doc.transaction_date,
				posting_date: frm.doc.transaction_date,
				grand_total: frm.doc.rounded_total || frm.doc.grand_total,
				base_grand_total: frm.doc.base_rounded_total || frm.doc.base_grand_total,
			},
			callback: function (r) {
				if (
					frm._janyu_payment_term_request_ids[cdn] !== request_id ||
					!r.message ||
					!locals[cdt] ||
					!locals[cdt][cdn] ||
					locals[cdt][cdn].payment_term !== row.payment_term
				) {
					return;
				}

				apply_payment_term_details(frm, cdt, cdn, r.message);

				// ERPNext's standard handler makes the same request. Reconcile after
				// all pending requests so its grand-total amount cannot win the race.
				frappe.after_ajax(function () {
					setTimeout(function () {
						if (frm._janyu_payment_term_request_ids[cdn] === request_id) {
							apply_payment_term_details(frm, cdt, cdn, r.message);
						}
					}, 0);
				});
			},
		});
	}

	function apply_payment_term_details(frm, cdt, cdn, details) {
		const row = locals[cdt] && locals[cdt][cdn];
		if (!row) {
			return;
		}

		with_payment_schedule_update(frm, function () {
			[
				"description",
				"invoice_portion",
				"discount_type",
				"discount",
				"mode_of_payment",
				"due_date_based_on",
				"credit_days",
				"credit_months",
				"discount_validity_based_on",
				"discount_validity",
				"due_date",
				"discount_date",
			].forEach(function (fieldname) {
				if (Object.prototype.hasOwnProperty.call(details, fieldname)) {
					set_payment_schedule_value(frm, cdt, cdn, fieldname, details[fieldname]);
				}
			});
			set_payment_schedule_value(
				frm,
				cdt,
				cdn,
				"payment_amount",
				calculate_manual_payment_amount(frm, row)
			);
			set_payment_schedule_base_amount(frm, cdt, cdn);
		});
	}

	function set_payment_schedule_value(frm, cdt, cdn, fieldname, value) {
		const row = locals[cdt] && locals[cdt][cdn];
		if (!row || row[fieldname] === value) {
			return;
		}
		frappe.model.set_value(cdt, cdn, fieldname, value);
	}

	function set_payment_schedule_base_amount(frm, cdt, cdn) {
		const row = locals[cdt] && locals[cdt][cdn];
		if (!row) {
			return;
		}
		set_payment_schedule_value(
			frm,
			cdt,
			cdn,
			"base_payment_amount",
			flt(flt(row.payment_amount) * flt(frm.doc.conversion_rate))
		);
	}

	function with_payment_schedule_update(frm, callback) {
		frm._janyu_updating_payment_schedule = true;
		try {
			callback();
		} finally {
			frm._janyu_updating_payment_schedule = false;
			frm.refresh_field("payment_schedule");
		}
	}

	function is_updating_payment_schedule(frm) {
		return Boolean(frm._janyu_updating_payment_schedule);
	}

	function calculate_manual_invoice_portion(frm, row) {
		const total = flt(frm.doc.total);
		return total ? flt((flt(row.payment_amount) * 100) / total) : 0;
	}

	function calculate_manual_payment_amount(frm, row) {
		return flt((flt(frm.doc.total) * flt(row.invoice_portion)) / 100);
	}
})();
