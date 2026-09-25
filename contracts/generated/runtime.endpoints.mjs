//#region \0rolldown/runtime.js
var e = (e, t) => () => (t || (e((t = { exports: {} }).exports, t), e = null), t.exports), t = /* @__PURE__ */ e(((e) => {
	Object.defineProperty(e, "__esModule", { value: !0 });
	function t(e) {
		let t = e.length, n = 0, r = 0, i;
		for (; r < t;) n++, i = e.charCodeAt(r++), i >= 55296 && i <= 56319 && r < t && (i = e.charCodeAt(r), (i & 64512) == 56320 && r++);
		return n;
	}
	e.default = t, t.code = "require(\"ajv/dist/runtime/ucs2length\").default";
})), n = /* @__PURE__ */ e(((e) => {
	e.v3 = r;
	var n = Object.prototype.hasOwnProperty;
	function r(e, { instancePath: t = "", parentData: i, parentDataProperty: a, rootData: o = e, dynamicAnchors: s = {} } = {}) {
		let c = r.evaluated;
		if (c.dynamicProps && (c.props = void 0), c.dynamicItems && (c.items = void 0), e && typeof e == "object" && !Array.isArray(e)) {
			let i;
			if ((e.state === void 0 || !n.call(e, "state")) && (i = "state")) return r.errors = [{
				instancePath: t,
				schemaPath: "#/required",
				keyword: "required",
				params: { missingProperty: i }
			}], !1;
			for (let n of Object.keys(e)) if (n !== "notice_version" && n !== "state") return r.errors = [{
				instancePath: t,
				schemaPath: "#/additionalProperties",
				keyword: "additionalProperties",
				params: { additionalProperty: n }
			}], !1;
			if (e.notice_version !== void 0 && n.call(e, "notice_version")) {
				let n = e.notice_version;
				if (typeof n != "string") return r.errors = [{
					instancePath: t + "/notice_version",
					schemaPath: "#/properties/notice_version/type",
					keyword: "type",
					params: { type: "string" }
				}], !1;
				if (n !== "DEMO-POLICY-1") return r.errors = [{
					instancePath: t + "/notice_version",
					schemaPath: "#/properties/notice_version/const",
					keyword: "const",
					params: { allowedValue: "DEMO-POLICY-1" }
				}], !1;
				var l = !0;
			} else var l = !0;
			if (l) {
				if (e.state !== void 0 && n.call(e, "state")) {
					let n = e.state;
					if (typeof n != "string") return r.errors = [{
						instancePath: t + "/state",
						schemaPath: "#/properties/state/type",
						keyword: "type",
						params: { type: "string" }
					}], !1;
					if (n !== "anonymous") return r.errors = [{
						instancePath: t + "/state",
						schemaPath: "#/properties/state/const",
						keyword: "const",
						params: { allowedValue: "anonymous" }
					}], !1;
					var l = !0;
				} else var l = !0;
			}
		} else return r.errors = [{
			instancePath: t,
			schemaPath: "#/type",
			keyword: "type",
			params: { type: "object" }
		}], !1;
		return r.errors = null, !0;
	}
	r.evaluated = {
		props: !0,
		dynamicProps: !1,
		dynamicItems: !1
	}, e.v9 = d;
	var i = /* @__PURE__ */ RegExp("^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}(?:\\.\\d{1,6})?Z$", "u");
	function a(e, { instancePath: t = "", parentData: r, parentDataProperty: o, rootData: s = e, dynamicAnchors: c = {} } = {}) {
		let l = a.evaluated;
		if (l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), e && typeof e == "object" && !Array.isArray(e)) {
			let r;
			if ((e.starts_at_utc === void 0 || !n.call(e, "starts_at_utc")) && (r = "starts_at_utc")) return a.errors = [{
				instancePath: t,
				schemaPath: "#/required",
				keyword: "required",
				params: { missingProperty: r }
			}], !1;
			for (let n of Object.keys(e)) if (n !== "appointment_type" && n !== "starts_at_utc" && n !== "timezone") return a.errors = [{
				instancePath: t,
				schemaPath: "#/additionalProperties",
				keyword: "additionalProperties",
				params: { additionalProperty: n }
			}], !1;
			if (e.appointment_type !== void 0 && n.call(e, "appointment_type")) {
				let n = e.appointment_type;
				if (typeof n != "string") return a.errors = [{
					instancePath: t + "/appointment_type",
					schemaPath: "#/properties/appointment_type/type",
					keyword: "type",
					params: { type: "string" }
				}], !1;
				if (n !== "viewing") return a.errors = [{
					instancePath: t + "/appointment_type",
					schemaPath: "#/properties/appointment_type/const",
					keyword: "const",
					params: { allowedValue: "viewing" }
				}], !1;
				var u = !0;
			} else var u = !0;
			if (u) {
				if (e.starts_at_utc !== void 0 && n.call(e, "starts_at_utc")) {
					let n = e.starts_at_utc;
					if (typeof n == "string") {
						if (!i.test(n)) return a.errors = [{
							instancePath: t + "/starts_at_utc",
							schemaPath: "#/properties/starts_at_utc/pattern",
							keyword: "pattern",
							params: { pattern: "^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}(?:\\.\\d{1,6})?Z$" }
						}], !1;
					} else return a.errors = [{
						instancePath: t + "/starts_at_utc",
						schemaPath: "#/properties/starts_at_utc/type",
						keyword: "type",
						params: { type: "string" }
					}], !1;
					var u = !0;
				} else var u = !0;
				if (u) {
					if (e.timezone !== void 0 && n.call(e, "timezone")) {
						let n = e.timezone;
						if (typeof n != "string") return a.errors = [{
							instancePath: t + "/timezone",
							schemaPath: "#/properties/timezone/type",
							keyword: "type",
							params: { type: "string" }
						}], !1;
						if (n !== "Asia/Dubai") return a.errors = [{
							instancePath: t + "/timezone",
							schemaPath: "#/properties/timezone/const",
							keyword: "const",
							params: { allowedValue: "Asia/Dubai" }
						}], !1;
						var u = !0;
					} else var u = !0;
				}
			}
		} else return a.errors = [{
			instancePath: t,
			schemaPath: "#/type",
			keyword: "type",
			params: { type: "object" }
		}], !1;
		return a.errors = null, !0;
	}
	a.evaluated = {
		props: !0,
		dynamicProps: !1,
		dynamicItems: !1
	};
	var o = /* @__PURE__ */ RegExp("^[a-z0-9_-]{1,64}$", "u"), s = /* @__PURE__ */ RegExp("^[0-9a-f]{64}$", "u"), c = /* @__PURE__ */ RegExp("^[A-Za-z0-9._-]{1,128}$", "u");
	function l(e, { instancePath: t = "", parentData: r, parentDataProperty: i, rootData: a = e, dynamicAnchors: u = {} } = {}) {
		let d = l.evaluated;
		if (d.dynamicProps && (d.props = void 0), d.dynamicItems && (d.items = void 0), e && typeof e == "object" && !Array.isArray(e)) {
			let r;
			if ((e.namespace === void 0 || !n.call(e, "namespace")) && (r = "namespace") || (e.snapshot_id === void 0 || !n.call(e, "snapshot_id")) && (r = "snapshot_id") || (e.source_id === void 0 || !n.call(e, "source_id")) && (r = "source_id")) return l.errors = [{
				instancePath: t,
				schemaPath: "#/required",
				keyword: "required",
				params: { missingProperty: r }
			}], !1;
			for (let n of Object.keys(e)) if (n !== "namespace" && n !== "snapshot_id" && n !== "source_id") return l.errors = [{
				instancePath: t,
				schemaPath: "#/additionalProperties",
				keyword: "additionalProperties",
				params: { additionalProperty: n }
			}], !1;
			if (e.namespace !== void 0 && n.call(e, "namespace")) {
				let n = e.namespace;
				if (typeof n == "string") {
					if (!o.test(n)) return l.errors = [{
						instancePath: t + "/namespace",
						schemaPath: "#/properties/namespace/pattern",
						keyword: "pattern",
						params: { pattern: "^[a-z0-9_-]{1,64}$" }
					}], !1;
				} else return l.errors = [{
					instancePath: t + "/namespace",
					schemaPath: "#/properties/namespace/type",
					keyword: "type",
					params: { type: "string" }
				}], !1;
				var f = !0;
			} else var f = !0;
			if (f) {
				if (e.snapshot_id !== void 0 && n.call(e, "snapshot_id")) {
					let n = e.snapshot_id;
					if (typeof n == "string") {
						if (!s.test(n)) return l.errors = [{
							instancePath: t + "/snapshot_id",
							schemaPath: "#/properties/snapshot_id/pattern",
							keyword: "pattern",
							params: { pattern: "^[0-9a-f]{64}$" }
						}], !1;
					} else return l.errors = [{
						instancePath: t + "/snapshot_id",
						schemaPath: "#/properties/snapshot_id/type",
						keyword: "type",
						params: { type: "string" }
					}], !1;
					var f = !0;
				} else var f = !0;
				if (f) {
					if (e.source_id !== void 0 && n.call(e, "source_id")) {
						let n = e.source_id;
						if (typeof n == "string") {
							if (!c.test(n)) return l.errors = [{
								instancePath: t + "/source_id",
								schemaPath: "#/properties/source_id/pattern",
								keyword: "pattern",
								params: { pattern: "^[A-Za-z0-9._-]{1,128}$" }
							}], !1;
						} else return l.errors = [{
							instancePath: t + "/source_id",
							schemaPath: "#/properties/source_id/type",
							keyword: "type",
							params: { type: "string" }
						}], !1;
						var f = !0;
					} else var f = !0;
				}
			}
		} else return l.errors = [{
			instancePath: t,
			schemaPath: "#/type",
			keyword: "type",
			params: { type: "object" }
		}], !1;
		return l.errors = null, !0;
	}
	l.evaluated = {
		props: !0,
		dynamicProps: !1,
		dynamicItems: !1
	};
	var u = /* @__PURE__ */ RegExp("^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$", "u");
	function d(e, { instancePath: t = "", parentData: r, parentDataProperty: i, rootData: o = e, dynamicAnchors: s = {} } = {}) {
		let c = null, f = 0, p = d.evaluated;
		if (p.dynamicProps && (p.props = void 0), p.dynamicItems && (p.items = void 0), f === 0) {
			if (e && typeof e == "object" && !Array.isArray(e)) {
				let r;
				if ((e.client_action_id === void 0 || !n.call(e, "client_action_id")) && (r = "client_action_id") || (e.session_id === void 0 || !n.call(e, "session_id")) && (r = "session_id") || (e.expected_session_revision === void 0 || !n.call(e, "expected_session_revision")) && (r = "expected_session_revision") || (e.ref === void 0 || !n.call(e, "ref")) && (r = "ref")) return d.errors = [{
					instancePath: t,
					schemaPath: "#/required",
					keyword: "required",
					params: { missingProperty: r }
				}], !1;
				{
					let r = f;
					for (let n of Object.keys(e)) if (n !== "appointment" && n !== "client_action_id" && n !== "expected_session_revision" && n !== "ref" && n !== "session_id") return d.errors = [{
						instancePath: t,
						schemaPath: "#/additionalProperties",
						keyword: "additionalProperties",
						params: { additionalProperty: n }
					}], !1;
					if (r === f) {
						if (e.appointment !== void 0 && n.call(e, "appointment")) {
							let n = e.appointment, r = f, i = f, l = !1, u = f;
							a(n, {
								instancePath: t + "/appointment",
								parentData: e,
								parentDataProperty: "appointment",
								rootData: o,
								dynamicAnchors: s
							}) || (c = c === null ? a.errors : c.concat(a.errors), f = c.length);
							var m = u === f;
							l ||= m;
							let p = f;
							if (n !== null) {
								let e = {
									instancePath: t + "/appointment",
									schemaPath: "#/properties/appointment/anyOf/1/type",
									keyword: "type",
									params: { type: "null" }
								};
								c === null ? c = [e] : c.push(e), f++;
							}
							var m = p === f;
							if (l ||= m, l) f = i, c !== null && (i ? c.length = i : c = null);
							else {
								let e = {
									instancePath: t + "/appointment",
									schemaPath: "#/properties/appointment/anyOf",
									keyword: "anyOf",
									params: {}
								};
								return c === null ? c = [e] : c.push(e), f++, d.errors = c, !1;
							}
							var h = r === f;
						} else var h = !0;
						if (h) {
							if (e.client_action_id !== void 0 && n.call(e, "client_action_id")) {
								let n = e.client_action_id, r = f;
								if (f === r) {
									if (typeof n == "string") {
										if (!u.test(n)) return d.errors = [{
											instancePath: t + "/client_action_id",
											schemaPath: "#/properties/client_action_id/pattern",
											keyword: "pattern",
											params: { pattern: "^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$" }
										}], !1;
									} else return d.errors = [{
										instancePath: t + "/client_action_id",
										schemaPath: "#/properties/client_action_id/type",
										keyword: "type",
										params: { type: "string" }
									}], !1;
								}
								var h = r === f;
							} else var h = !0;
							if (h) {
								if (e.expected_session_revision !== void 0 && n.call(e, "expected_session_revision")) {
									let n = e.expected_session_revision, r = f;
									if (typeof n != "number" || n % 1 || isNaN(n) || !isFinite(n)) return d.errors = [{
										instancePath: t + "/expected_session_revision",
										schemaPath: "#/properties/expected_session_revision/type",
										keyword: "type",
										params: { type: "integer" }
									}], !1;
									if (f === r && typeof n == "number" && isFinite(n)) {
										if (n > 2147483647 || isNaN(n)) return d.errors = [{
											instancePath: t + "/expected_session_revision",
											schemaPath: "#/properties/expected_session_revision/maximum",
											keyword: "maximum",
											params: {
												comparison: "<=",
												limit: 2147483647
											}
										}], !1;
										if (n < 0 || isNaN(n)) return d.errors = [{
											instancePath: t + "/expected_session_revision",
											schemaPath: "#/properties/expected_session_revision/minimum",
											keyword: "minimum",
											params: {
												comparison: ">=",
												limit: 0
											}
										}], !1;
									}
									var h = r === f;
								} else var h = !0;
								if (h) {
									if (e.ref !== void 0 && n.call(e, "ref")) {
										let n = f;
										l(e.ref, {
											instancePath: t + "/ref",
											parentData: e,
											parentDataProperty: "ref",
											rootData: o,
											dynamicAnchors: s
										}) || (c = c === null ? l.errors : c.concat(l.errors), f = c.length);
										var h = n === f;
									} else var h = !0;
									if (h) {
										if (e.session_id !== void 0 && n.call(e, "session_id")) {
											let n = e.session_id, r = f;
											if (f === r) {
												if (typeof n == "string") {
													if (!u.test(n)) return d.errors = [{
														instancePath: t + "/session_id",
														schemaPath: "#/properties/session_id/pattern",
														keyword: "pattern",
														params: { pattern: "^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$" }
													}], !1;
												} else return d.errors = [{
													instancePath: t + "/session_id",
													schemaPath: "#/properties/session_id/type",
													keyword: "type",
													params: { type: "string" }
												}], !1;
											}
											var h = r === f;
										} else var h = !0;
									}
								}
							}
						}
					}
				}
			} else return d.errors = [{
				instancePath: t,
				schemaPath: "#/type",
				keyword: "type",
				params: { type: "object" }
			}], !1;
		}
		return d.errors = c, f === 0;
	}
	d.evaluated = {
		props: !0,
		dynamicProps: !1,
		dynamicItems: !1
	}, e.v10 = p;
	var f = {
		additionalProperties: !1,
		properties: {
			appointment: { anyOf: [{ $ref: "urn:car-shopping-assistant:contract:1#/$defs/AppointmentSelection" }, { type: "null" }] },
			client_action_id: {
				pattern: "^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$",
				title: "Client Action Id",
				type: "string"
			},
			expected_revision: {
				maximum: 2147483647,
				minimum: 0,
				title: "Expected Revision",
				type: "integer"
			},
			intent: {
				enum: [
					"edit",
					"suspend",
					"discard",
					"refresh_review"
				],
				title: "Intent",
				type: "string"
			},
			ref: { anyOf: [{ $ref: "urn:car-shopping-assistant:contract:1#/$defs/InventoryRef" }, { type: "null" }] }
		},
		required: [
			"client_action_id",
			"expected_revision",
			"intent"
		],
		title: "BookingDraftUpdate",
		type: "object"
	};
	function p(e, { instancePath: t = "", parentData: r, parentDataProperty: i, rootData: o = e, dynamicAnchors: s = {} } = {}) {
		let c = null, d = 0, m = p.evaluated;
		if (m.dynamicProps && (m.props = void 0), m.dynamicItems && (m.items = void 0), d === 0) {
			if (e && typeof e == "object" && !Array.isArray(e)) {
				let r;
				if ((e.client_action_id === void 0 || !n.call(e, "client_action_id")) && (r = "client_action_id") || (e.expected_revision === void 0 || !n.call(e, "expected_revision")) && (r = "expected_revision") || (e.intent === void 0 || !n.call(e, "intent")) && (r = "intent")) return p.errors = [{
					instancePath: t,
					schemaPath: "#/required",
					keyword: "required",
					params: { missingProperty: r }
				}], !1;
				{
					let r = d;
					for (let n of Object.keys(e)) if (n !== "appointment" && n !== "client_action_id" && n !== "expected_revision" && n !== "intent" && n !== "ref") return p.errors = [{
						instancePath: t,
						schemaPath: "#/additionalProperties",
						keyword: "additionalProperties",
						params: { additionalProperty: n }
					}], !1;
					if (r === d) {
						if (e.appointment !== void 0 && n.call(e, "appointment")) {
							let n = e.appointment, r = d, i = d, l = !1, u = d;
							a(n, {
								instancePath: t + "/appointment",
								parentData: e,
								parentDataProperty: "appointment",
								rootData: o,
								dynamicAnchors: s
							}) || (c = c === null ? a.errors : c.concat(a.errors), d = c.length);
							var h = u === d;
							l ||= h;
							let f = d;
							if (n !== null) {
								let e = {
									instancePath: t + "/appointment",
									schemaPath: "#/properties/appointment/anyOf/1/type",
									keyword: "type",
									params: { type: "null" }
								};
								c === null ? c = [e] : c.push(e), d++;
							}
							var h = f === d;
							if (l ||= h, l) d = i, c !== null && (i ? c.length = i : c = null);
							else {
								let e = {
									instancePath: t + "/appointment",
									schemaPath: "#/properties/appointment/anyOf",
									keyword: "anyOf",
									params: {}
								};
								return c === null ? c = [e] : c.push(e), d++, p.errors = c, !1;
							}
							var g = r === d;
						} else var g = !0;
						if (g) {
							if (e.client_action_id !== void 0 && n.call(e, "client_action_id")) {
								let n = e.client_action_id, r = d;
								if (d === r) {
									if (typeof n == "string") {
										if (!u.test(n)) return p.errors = [{
											instancePath: t + "/client_action_id",
											schemaPath: "#/properties/client_action_id/pattern",
											keyword: "pattern",
											params: { pattern: "^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$" }
										}], !1;
									} else return p.errors = [{
										instancePath: t + "/client_action_id",
										schemaPath: "#/properties/client_action_id/type",
										keyword: "type",
										params: { type: "string" }
									}], !1;
								}
								var g = r === d;
							} else var g = !0;
							if (g) {
								if (e.expected_revision !== void 0 && n.call(e, "expected_revision")) {
									let n = e.expected_revision, r = d;
									if (typeof n != "number" || n % 1 || isNaN(n) || !isFinite(n)) return p.errors = [{
										instancePath: t + "/expected_revision",
										schemaPath: "#/properties/expected_revision/type",
										keyword: "type",
										params: { type: "integer" }
									}], !1;
									if (d === r && typeof n == "number" && isFinite(n)) {
										if (n > 2147483647 || isNaN(n)) return p.errors = [{
											instancePath: t + "/expected_revision",
											schemaPath: "#/properties/expected_revision/maximum",
											keyword: "maximum",
											params: {
												comparison: "<=",
												limit: 2147483647
											}
										}], !1;
										if (n < 0 || isNaN(n)) return p.errors = [{
											instancePath: t + "/expected_revision",
											schemaPath: "#/properties/expected_revision/minimum",
											keyword: "minimum",
											params: {
												comparison: ">=",
												limit: 0
											}
										}], !1;
									}
									var g = r === d;
								} else var g = !0;
								if (g) {
									if (e.intent !== void 0 && n.call(e, "intent")) {
										let n = e.intent, r = d;
										if (typeof n != "string") return p.errors = [{
											instancePath: t + "/intent",
											schemaPath: "#/properties/intent/type",
											keyword: "type",
											params: { type: "string" }
										}], !1;
										if (n !== "edit" && n !== "suspend" && n !== "discard" && n !== "refresh_review") return p.errors = [{
											instancePath: t + "/intent",
											schemaPath: "#/properties/intent/enum",
											keyword: "enum",
											params: { allowedValues: f.properties.intent.enum }
										}], !1;
										var g = r === d;
									} else var g = !0;
									if (g) {
										if (e.ref !== void 0 && n.call(e, "ref")) {
											let n = e.ref, r = d, i = d, a = !1, u = d;
											l(n, {
												instancePath: t + "/ref",
												parentData: e,
												parentDataProperty: "ref",
												rootData: o,
												dynamicAnchors: s
											}) || (c = c === null ? l.errors : c.concat(l.errors), d = c.length);
											var _ = u === d;
											a ||= _;
											let f = d;
											if (n !== null) {
												let e = {
													instancePath: t + "/ref",
													schemaPath: "#/properties/ref/anyOf/1/type",
													keyword: "type",
													params: { type: "null" }
												};
												c === null ? c = [e] : c.push(e), d++;
											}
											var _ = f === d;
											if (a ||= _, a) d = i, c !== null && (i ? c.length = i : c = null);
											else {
												let e = {
													instancePath: t + "/ref",
													schemaPath: "#/properties/ref/anyOf",
													keyword: "anyOf",
													params: {}
												};
												return c === null ? c = [e] : c.push(e), d++, p.errors = c, !1;
											}
											var g = r === d;
										} else var g = !0;
									}
								}
							}
						}
					}
				}
			} else return p.errors = [{
				instancePath: t,
				schemaPath: "#/type",
				keyword: "type",
				params: { type: "object" }
			}], !1;
		}
		return p.errors = c, d === 0;
	}
	p.evaluated = {
		props: !0,
		dynamicProps: !1,
		dynamicItems: !1
	}, e.v22 = m;
	function m(e, { instancePath: t = "", parentData: r, parentDataProperty: i, rootData: a = e, dynamicAnchors: o = {} } = {}) {
		let s = null, c = 0, u = m.evaluated;
		if (u.dynamicProps && (u.props = void 0), u.dynamicItems && (u.items = void 0), c === 0) {
			if (e && typeof e == "object" && !Array.isArray(e)) {
				let r;
				if ((e.refs === void 0 || !n.call(e, "refs")) && (r = "refs")) return m.errors = [{
					instancePath: t,
					schemaPath: "#/required",
					keyword: "required",
					params: { missingProperty: r }
				}], !1;
				{
					let r = c;
					for (let n of Object.keys(e)) if (n !== "refs") return m.errors = [{
						instancePath: t,
						schemaPath: "#/additionalProperties",
						keyword: "additionalProperties",
						params: { additionalProperty: n }
					}], !1;
					if (r === c && e.refs !== void 0 && n.call(e, "refs")) {
						let n = e.refs;
						if (c === c) {
							if (Array.isArray(n)) {
								if (n.length > 3) return m.errors = [{
									instancePath: t + "/refs",
									schemaPath: "#/properties/refs/maxItems",
									keyword: "maxItems",
									params: { limit: 3 }
								}], !1;
								if (n.length < 2) return m.errors = [{
									instancePath: t + "/refs",
									schemaPath: "#/properties/refs/minItems",
									keyword: "minItems",
									params: { limit: 2 }
								}], !1;
								{
									let e = n.length;
									for (let r = 0; r < e; r++) {
										let e = c;
										if (l(n[r], {
											instancePath: t + "/refs/" + r,
											parentData: n,
											parentDataProperty: r,
											rootData: a,
											dynamicAnchors: o
										}) || (s = s === null ? l.errors : s.concat(l.errors), c = s.length), e !== c) break;
									}
								}
							} else return m.errors = [{
								instancePath: t + "/refs",
								schemaPath: "#/properties/refs/type",
								keyword: "type",
								params: { type: "array" }
							}], !1;
						}
					}
				}
			} else return m.errors = [{
				instancePath: t,
				schemaPath: "#/type",
				keyword: "type",
				params: { type: "object" }
			}], !1;
		}
		return m.errors = s, c === 0;
	}
	m.evaluated = {
		props: !0,
		dynamicProps: !1,
		dynamicItems: !1
	}, e.v24 = _;
	var h = t().default, g = /* @__PURE__ */ RegExp("^[A-Za-z0-9_-]{43}$", "u");
	function _(e, { instancePath: t = "", parentData: r, parentDataProperty: i, rootData: a = e, dynamicAnchors: o = {} } = {}) {
		let s = _.evaluated;
		if (s.dynamicProps && (s.props = void 0), s.dynamicItems && (s.items = void 0), e && typeof e == "object" && !Array.isArray(e)) {
			let r;
			if ((e.review_id === void 0 || !n.call(e, "review_id")) && (r = "review_id") || (e.expected_draft_revision === void 0 || !n.call(e, "expected_draft_revision")) && (r = "expected_draft_revision") || (e.operation_key === void 0 || !n.call(e, "operation_key")) && (r = "operation_key") || (e.rules_version === void 0 || !n.call(e, "rules_version")) && (r = "rules_version") || (e.store_generation === void 0 || !n.call(e, "store_generation")) && (r = "store_generation") || (e.confirmation === void 0 || !n.call(e, "confirmation")) && (r = "confirmation")) return _.errors = [{
				instancePath: t,
				schemaPath: "#/required",
				keyword: "required",
				params: { missingProperty: r }
			}], !1;
			for (let n of Object.keys(e)) if (n !== "confirmation" && n !== "expected_draft_revision" && n !== "operation_key" && n !== "review_id" && n !== "rules_version" && n !== "store_generation") return _.errors = [{
				instancePath: t,
				schemaPath: "#/additionalProperties",
				keyword: "additionalProperties",
				params: { additionalProperty: n }
			}], !1;
			if (e.confirmation !== void 0 && n.call(e, "confirmation")) {
				let n = e.confirmation;
				if (typeof n != "string") return _.errors = [{
					instancePath: t + "/confirmation",
					schemaPath: "#/properties/confirmation/type",
					keyword: "type",
					params: { type: "string" }
				}], !1;
				if (n !== "confirm_simulated_viewing") return _.errors = [{
					instancePath: t + "/confirmation",
					schemaPath: "#/properties/confirmation/const",
					keyword: "const",
					params: { allowedValue: "confirm_simulated_viewing" }
				}], !1;
				var c = !0;
			} else var c = !0;
			if (c) {
				if (e.expected_draft_revision !== void 0 && n.call(e, "expected_draft_revision")) {
					let n = e.expected_draft_revision;
					if (typeof n != "number" || n % 1 || isNaN(n) || !isFinite(n)) return _.errors = [{
						instancePath: t + "/expected_draft_revision",
						schemaPath: "#/properties/expected_draft_revision/type",
						keyword: "type",
						params: { type: "integer" }
					}], !1;
					if (typeof n == "number" && isFinite(n)) {
						if (n > 2147483647 || isNaN(n)) return _.errors = [{
							instancePath: t + "/expected_draft_revision",
							schemaPath: "#/properties/expected_draft_revision/maximum",
							keyword: "maximum",
							params: {
								comparison: "<=",
								limit: 2147483647
							}
						}], !1;
						if (n < 0 || isNaN(n)) return _.errors = [{
							instancePath: t + "/expected_draft_revision",
							schemaPath: "#/properties/expected_draft_revision/minimum",
							keyword: "minimum",
							params: {
								comparison: ">=",
								limit: 0
							}
						}], !1;
					}
					var c = !0;
				} else var c = !0;
				if (c) {
					if (e.operation_key !== void 0 && n.call(e, "operation_key")) {
						let n = e.operation_key;
						if (typeof n == "string") {
							if (!g.test(n)) return _.errors = [{
								instancePath: t + "/operation_key",
								schemaPath: "#/properties/operation_key/pattern",
								keyword: "pattern",
								params: { pattern: "^[A-Za-z0-9_-]{43}$" }
							}], !1;
						} else return _.errors = [{
							instancePath: t + "/operation_key",
							schemaPath: "#/properties/operation_key/type",
							keyword: "type",
							params: { type: "string" }
						}], !1;
						var c = !0;
					} else var c = !0;
					if (c) {
						if (e.review_id !== void 0 && n.call(e, "review_id")) {
							let n = e.review_id;
							if (typeof n == "string") {
								if (!u.test(n)) return _.errors = [{
									instancePath: t + "/review_id",
									schemaPath: "#/properties/review_id/pattern",
									keyword: "pattern",
									params: { pattern: "^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$" }
								}], !1;
							} else return _.errors = [{
								instancePath: t + "/review_id",
								schemaPath: "#/properties/review_id/type",
								keyword: "type",
								params: { type: "string" }
							}], !1;
							var c = !0;
						} else var c = !0;
						if (c) {
							if (e.rules_version !== void 0 && n.call(e, "rules_version")) {
								let n = e.rules_version;
								if (typeof n == "string") {
									if (h(n) > 200) return _.errors = [{
										instancePath: t + "/rules_version",
										schemaPath: "#/properties/rules_version/maxLength",
										keyword: "maxLength",
										params: { limit: 200 }
									}], !1;
									if (h(n) < 1) return _.errors = [{
										instancePath: t + "/rules_version",
										schemaPath: "#/properties/rules_version/minLength",
										keyword: "minLength",
										params: { limit: 1 }
									}], !1;
								} else return _.errors = [{
									instancePath: t + "/rules_version",
									schemaPath: "#/properties/rules_version/type",
									keyword: "type",
									params: { type: "string" }
								}], !1;
								var c = !0;
							} else var c = !0;
							if (c) {
								if (e.store_generation !== void 0 && n.call(e, "store_generation")) {
									let n = e.store_generation;
									if (typeof n == "string") {
										if (!u.test(n)) return _.errors = [{
											instancePath: t + "/store_generation",
											schemaPath: "#/properties/store_generation/pattern",
											keyword: "pattern",
											params: { pattern: "^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$" }
										}], !1;
									} else return _.errors = [{
										instancePath: t + "/store_generation",
										schemaPath: "#/properties/store_generation/type",
										keyword: "type",
										params: { type: "string" }
									}], !1;
									var c = !0;
								} else var c = !0;
							}
						}
					}
				}
			}
		} else return _.errors = [{
			instancePath: t,
			schemaPath: "#/type",
			keyword: "type",
			params: { type: "object" }
		}], !1;
		return _.errors = null, !0;
	}
	_.evaluated = {
		props: !0,
		dynamicProps: !1,
		dynamicItems: !1
	}, e.v31 = ee;
	function v(e, { instancePath: t = "", parentData: r, parentDataProperty: a, rootData: o = e, dynamicAnchors: s = {} } = {}) {
		let c = null, l = 0, d = v.evaluated;
		if (d.dynamicProps && (d.props = void 0), d.dynamicItems && (d.items = void 0), l === 0) {
			if (e && typeof e == "object" && !Array.isArray(e)) {
				let r;
				if ((e.state === void 0 || !n.call(e, "state")) && (r = "state") || (e.context_id === void 0 || !n.call(e, "context_id")) && (r = "context_id") || (e.csrf_token === void 0 || !n.call(e, "csrf_token")) && (r = "csrf_token") || (e.expires_at === void 0 || !n.call(e, "expires_at")) && (r = "expires_at") || (e.display_name === void 0 || !n.call(e, "display_name")) && (r = "display_name")) return v.errors = [{
					instancePath: t,
					schemaPath: "#/required",
					keyword: "required",
					params: { missingProperty: r }
				}], !1;
				{
					let r = l;
					for (let n of Object.keys(e)) if (n !== "context_id" && n !== "continuity" && n !== "csrf_token" && n !== "display_name" && n !== "expires_at" && n !== "state") return v.errors = [{
						instancePath: t,
						schemaPath: "#/additionalProperties",
						keyword: "additionalProperties",
						params: { additionalProperty: n }
					}], !1;
					if (r === l) {
						if (e.context_id !== void 0 && n.call(e, "context_id")) {
							let n = e.context_id, r = l;
							if (l === r) {
								if (typeof n == "string") {
									if (!u.test(n)) return v.errors = [{
										instancePath: t + "/context_id",
										schemaPath: "#/properties/context_id/pattern",
										keyword: "pattern",
										params: { pattern: "^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$" }
									}], !1;
								} else return v.errors = [{
									instancePath: t + "/context_id",
									schemaPath: "#/properties/context_id/type",
									keyword: "type",
									params: { type: "string" }
								}], !1;
							}
							var f = r === l;
						} else var f = !0;
						if (f) {
							if (e.continuity !== void 0 && n.call(e, "continuity")) {
								let n = e.continuity, r = l;
								if (typeof n != "string") return v.errors = [{
									instancePath: t + "/continuity",
									schemaPath: "#/properties/continuity/type",
									keyword: "type",
									params: { type: "string" }
								}], !1;
								if (n !== "this_browser_only") return v.errors = [{
									instancePath: t + "/continuity",
									schemaPath: "#/properties/continuity/const",
									keyword: "const",
									params: { allowedValue: "this_browser_only" }
								}], !1;
								var f = r === l;
							} else var f = !0;
							if (f) {
								if (e.csrf_token !== void 0 && n.call(e, "csrf_token")) {
									let n = e.csrf_token, r = l;
									if (l === r) {
										if (typeof n == "string") {
											if (!g.test(n)) return v.errors = [{
												instancePath: t + "/csrf_token",
												schemaPath: "#/properties/csrf_token/pattern",
												keyword: "pattern",
												params: { pattern: "^[A-Za-z0-9_-]{43}$" }
											}], !1;
										} else return v.errors = [{
											instancePath: t + "/csrf_token",
											schemaPath: "#/properties/csrf_token/type",
											keyword: "type",
											params: { type: "string" }
										}], !1;
									}
									var f = r === l;
								} else var f = !0;
								if (f) {
									if (e.display_name !== void 0 && n.call(e, "display_name")) {
										let n = e.display_name, r = l, i = l, a = !1, o = l;
										if (l === o) {
											if (typeof n == "string") {
												if (h(n) > 100) {
													let e = {
														instancePath: t + "/display_name",
														schemaPath: "#/properties/display_name/anyOf/0/maxLength",
														keyword: "maxLength",
														params: { limit: 100 }
													};
													c === null ? c = [e] : c.push(e), l++;
												}
											} else {
												let e = {
													instancePath: t + "/display_name",
													schemaPath: "#/properties/display_name/anyOf/0/type",
													keyword: "type",
													params: { type: "string" }
												};
												c === null ? c = [e] : c.push(e), l++;
											}
										}
										var p = o === l;
										a ||= p;
										let s = l;
										if (n !== null) {
											let e = {
												instancePath: t + "/display_name",
												schemaPath: "#/properties/display_name/anyOf/1/type",
												keyword: "type",
												params: { type: "null" }
											};
											c === null ? c = [e] : c.push(e), l++;
										}
										var p = s === l;
										if (a ||= p, a) l = i, c !== null && (i ? c.length = i : c = null);
										else {
											let e = {
												instancePath: t + "/display_name",
												schemaPath: "#/properties/display_name/anyOf",
												keyword: "anyOf",
												params: {}
											};
											return c === null ? c = [e] : c.push(e), l++, v.errors = c, !1;
										}
										var f = r === l;
									} else var f = !0;
									if (f) {
										if (e.expires_at !== void 0 && n.call(e, "expires_at")) {
											let n = e.expires_at, r = l;
											if (l === r) {
												if (typeof n == "string") {
													if (!i.test(n)) return v.errors = [{
														instancePath: t + "/expires_at",
														schemaPath: "#/properties/expires_at/pattern",
														keyword: "pattern",
														params: { pattern: "^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}(?:\\.\\d{1,6})?Z$" }
													}], !1;
												} else return v.errors = [{
													instancePath: t + "/expires_at",
													schemaPath: "#/properties/expires_at/type",
													keyword: "type",
													params: { type: "string" }
												}], !1;
											}
											var f = r === l;
										} else var f = !0;
										if (f) {
											if (e.state !== void 0 && n.call(e, "state")) {
												let n = e.state, r = l;
												if (typeof n != "string") return v.errors = [{
													instancePath: t + "/state",
													schemaPath: "#/properties/state/type",
													keyword: "type",
													params: { type: "string" }
												}], !1;
												if (n !== "recognized") return v.errors = [{
													instancePath: t + "/state",
													schemaPath: "#/properties/state/const",
													keyword: "const",
													params: { allowedValue: "recognized" }
												}], !1;
												var f = r === l;
											} else var f = !0;
										}
									}
								}
							}
						}
					}
				}
			} else return v.errors = [{
				instancePath: t,
				schemaPath: "#/type",
				keyword: "type",
				params: { type: "object" }
			}], !1;
		}
		return v.errors = c, l === 0;
	}
	v.evaluated = {
		props: !0,
		dynamicProps: !1,
		dynamicItems: !1
	};
	function y(e, { instancePath: t = "", parentData: r, parentDataProperty: i, rootData: a = e, dynamicAnchors: o = {} } = {}) {
		let c = null, l = 0, d = y.evaluated;
		if (d.dynamicProps && (d.props = void 0), d.dynamicItems && (d.items = void 0), l === 0) {
			if (e && typeof e == "object" && !Array.isArray(e)) {
				let r;
				if ((e.request_id === void 0 || !n.call(e, "request_id")) && (r = "request_id")) return y.errors = [{
					instancePath: t,
					schemaPath: "#/required",
					keyword: "required",
					params: { missingProperty: r }
				}], !1;
				{
					let r = l;
					for (let n of Object.keys(e)) if (n !== "contract_version" && n !== "entity_revision" && n !== "identity_context_id" && n !== "inventory_snapshot_id" && n !== "policy_version" && n !== "request_id" && n !== "store_generation") return y.errors = [{
						instancePath: t,
						schemaPath: "#/additionalProperties",
						keyword: "additionalProperties",
						params: { additionalProperty: n }
					}], !1;
					if (r === l) {
						if (e.contract_version !== void 0 && n.call(e, "contract_version")) {
							let n = e.contract_version, r = l;
							if (typeof n != "string") return y.errors = [{
								instancePath: t + "/contract_version",
								schemaPath: "#/properties/contract_version/type",
								keyword: "type",
								params: { type: "string" }
							}], !1;
							if (n !== "1.0.0") return y.errors = [{
								instancePath: t + "/contract_version",
								schemaPath: "#/properties/contract_version/const",
								keyword: "const",
								params: { allowedValue: "1.0.0" }
							}], !1;
							var f = r === l;
						} else var f = !0;
						if (f) {
							if (e.entity_revision !== void 0 && n.call(e, "entity_revision")) {
								let n = e.entity_revision, r = l, i = l, a = !1, o = l;
								if (typeof n != "number" || n % 1 || isNaN(n) || !isFinite(n)) {
									let e = {
										instancePath: t + "/entity_revision",
										schemaPath: "#/properties/entity_revision/anyOf/0/type",
										keyword: "type",
										params: { type: "integer" }
									};
									c === null ? c = [e] : c.push(e), l++;
								}
								if (l === o && typeof n == "number" && isFinite(n)) {
									if (n > 2147483647 || isNaN(n)) {
										let e = {
											instancePath: t + "/entity_revision",
											schemaPath: "#/properties/entity_revision/anyOf/0/maximum",
											keyword: "maximum",
											params: {
												comparison: "<=",
												limit: 2147483647
											}
										};
										c === null ? c = [e] : c.push(e), l++;
									} else if (n < 0 || isNaN(n)) {
										let e = {
											instancePath: t + "/entity_revision",
											schemaPath: "#/properties/entity_revision/anyOf/0/minimum",
											keyword: "minimum",
											params: {
												comparison: ">=",
												limit: 0
											}
										};
										c === null ? c = [e] : c.push(e), l++;
									}
								}
								var p = o === l;
								a ||= p;
								let s = l;
								if (n !== null) {
									let e = {
										instancePath: t + "/entity_revision",
										schemaPath: "#/properties/entity_revision/anyOf/1/type",
										keyword: "type",
										params: { type: "null" }
									};
									c === null ? c = [e] : c.push(e), l++;
								}
								var p = s === l;
								if (a ||= p, a) l = i, c !== null && (i ? c.length = i : c = null);
								else {
									let e = {
										instancePath: t + "/entity_revision",
										schemaPath: "#/properties/entity_revision/anyOf",
										keyword: "anyOf",
										params: {}
									};
									return c === null ? c = [e] : c.push(e), l++, y.errors = c, !1;
								}
								var f = r === l;
							} else var f = !0;
							if (f) {
								if (e.identity_context_id !== void 0 && n.call(e, "identity_context_id")) {
									let n = e.identity_context_id, r = l, i = l, a = !1, o = l;
									if (l === o) {
										if (typeof n == "string") {
											if (!u.test(n)) {
												let e = {
													instancePath: t + "/identity_context_id",
													schemaPath: "#/properties/identity_context_id/anyOf/0/pattern",
													keyword: "pattern",
													params: { pattern: "^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$" }
												};
												c === null ? c = [e] : c.push(e), l++;
											}
										} else {
											let e = {
												instancePath: t + "/identity_context_id",
												schemaPath: "#/properties/identity_context_id/anyOf/0/type",
												keyword: "type",
												params: { type: "string" }
											};
											c === null ? c = [e] : c.push(e), l++;
										}
									}
									var m = o === l;
									a ||= m;
									let s = l;
									if (n !== null) {
										let e = {
											instancePath: t + "/identity_context_id",
											schemaPath: "#/properties/identity_context_id/anyOf/1/type",
											keyword: "type",
											params: { type: "null" }
										};
										c === null ? c = [e] : c.push(e), l++;
									}
									var m = s === l;
									if (a ||= m, a) l = i, c !== null && (i ? c.length = i : c = null);
									else {
										let e = {
											instancePath: t + "/identity_context_id",
											schemaPath: "#/properties/identity_context_id/anyOf",
											keyword: "anyOf",
											params: {}
										};
										return c === null ? c = [e] : c.push(e), l++, y.errors = c, !1;
									}
									var f = r === l;
								} else var f = !0;
								if (f) {
									if (e.inventory_snapshot_id !== void 0 && n.call(e, "inventory_snapshot_id")) {
										let n = e.inventory_snapshot_id, r = l, i = l, a = !1, o = l;
										if (l === o) {
											if (typeof n == "string") {
												if (!s.test(n)) {
													let e = {
														instancePath: t + "/inventory_snapshot_id",
														schemaPath: "#/properties/inventory_snapshot_id/anyOf/0/pattern",
														keyword: "pattern",
														params: { pattern: "^[0-9a-f]{64}$" }
													};
													c === null ? c = [e] : c.push(e), l++;
												}
											} else {
												let e = {
													instancePath: t + "/inventory_snapshot_id",
													schemaPath: "#/properties/inventory_snapshot_id/anyOf/0/type",
													keyword: "type",
													params: { type: "string" }
												};
												c === null ? c = [e] : c.push(e), l++;
											}
										}
										var h = o === l;
										a ||= h;
										let u = l;
										if (n !== null) {
											let e = {
												instancePath: t + "/inventory_snapshot_id",
												schemaPath: "#/properties/inventory_snapshot_id/anyOf/1/type",
												keyword: "type",
												params: { type: "null" }
											};
											c === null ? c = [e] : c.push(e), l++;
										}
										var h = u === l;
										if (a ||= h, a) l = i, c !== null && (i ? c.length = i : c = null);
										else {
											let e = {
												instancePath: t + "/inventory_snapshot_id",
												schemaPath: "#/properties/inventory_snapshot_id/anyOf",
												keyword: "anyOf",
												params: {}
											};
											return c === null ? c = [e] : c.push(e), l++, y.errors = c, !1;
										}
										var f = r === l;
									} else var f = !0;
									if (f) {
										if (e.policy_version !== void 0 && n.call(e, "policy_version")) {
											let n = e.policy_version, r = l;
											if (typeof n != "string") return y.errors = [{
												instancePath: t + "/policy_version",
												schemaPath: "#/properties/policy_version/type",
												keyword: "type",
												params: { type: "string" }
											}], !1;
											if (n !== "DEMO-POLICY-1") return y.errors = [{
												instancePath: t + "/policy_version",
												schemaPath: "#/properties/policy_version/const",
												keyword: "const",
												params: { allowedValue: "DEMO-POLICY-1" }
											}], !1;
											var f = r === l;
										} else var f = !0;
										if (f) {
											if (e.request_id !== void 0 && n.call(e, "request_id")) {
												let n = e.request_id, r = l;
												if (l === r) {
													if (typeof n == "string") {
														if (!u.test(n)) return y.errors = [{
															instancePath: t + "/request_id",
															schemaPath: "#/properties/request_id/pattern",
															keyword: "pattern",
															params: { pattern: "^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$" }
														}], !1;
													} else return y.errors = [{
														instancePath: t + "/request_id",
														schemaPath: "#/properties/request_id/type",
														keyword: "type",
														params: { type: "string" }
													}], !1;
												}
												var f = r === l;
											} else var f = !0;
											if (f) {
												if (e.store_generation !== void 0 && n.call(e, "store_generation")) {
													let n = e.store_generation, r = l, i = l, a = !1, o = l;
													if (l === o) {
														if (typeof n == "string") {
															if (!u.test(n)) {
																let e = {
																	instancePath: t + "/store_generation",
																	schemaPath: "#/properties/store_generation/anyOf/0/pattern",
																	keyword: "pattern",
																	params: { pattern: "^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$" }
																};
																c === null ? c = [e] : c.push(e), l++;
															}
														} else {
															let e = {
																instancePath: t + "/store_generation",
																schemaPath: "#/properties/store_generation/anyOf/0/type",
																keyword: "type",
																params: { type: "string" }
															};
															c === null ? c = [e] : c.push(e), l++;
														}
													}
													var g = o === l;
													a ||= g;
													let s = l;
													if (n !== null) {
														let e = {
															instancePath: t + "/store_generation",
															schemaPath: "#/properties/store_generation/anyOf/1/type",
															keyword: "type",
															params: { type: "null" }
														};
														c === null ? c = [e] : c.push(e), l++;
													}
													var g = s === l;
													if (a ||= g, a) l = i, c !== null && (i ? c.length = i : c = null);
													else {
														let e = {
															instancePath: t + "/store_generation",
															schemaPath: "#/properties/store_generation/anyOf",
															keyword: "anyOf",
															params: {}
														};
														return c === null ? c = [e] : c.push(e), l++, y.errors = c, !1;
													}
													var f = r === l;
												} else var f = !0;
											}
										}
									}
								}
							}
						}
					}
				}
			} else return y.errors = [{
				instancePath: t,
				schemaPath: "#/type",
				keyword: "type",
				params: { type: "object" }
			}], !1;
		}
		return y.errors = c, l === 0;
	}
	y.evaluated = {
		props: !0,
		dynamicProps: !1,
		dynamicItems: !1
	};
	function ee(e, { instancePath: t = "", parentData: i, parentDataProperty: a, rootData: o = e, dynamicAnchors: s = {} } = {}) {
		let c = null, l = 0, u = ee.evaluated;
		if (u.dynamicProps && (u.props = void 0), u.dynamicItems && (u.items = void 0), l === 0) {
			if (e && typeof e == "object" && !Array.isArray(e)) {
				let i;
				if ((e.data === void 0 || !n.call(e, "data")) && (i = "data") || (e.meta === void 0 || !n.call(e, "meta")) && (i = "meta")) return ee.errors = [{
					instancePath: t,
					schemaPath: "#/required",
					keyword: "required",
					params: { missingProperty: i }
				}], !1;
				{
					let i = l;
					for (let n of Object.keys(e)) if (n !== "data" && n !== "meta") return ee.errors = [{
						instancePath: t,
						schemaPath: "#/additionalProperties",
						keyword: "additionalProperties",
						params: { additionalProperty: n }
					}], !1;
					if (i === l) {
						if (e.data !== void 0 && n.call(e, "data")) {
							let i = e.data, a = l;
							if (l === a) {
								if (i && typeof i == "object" && !Array.isArray(i)) {
									let a;
									if ((i.state === void 0 || !n.call(i, "state")) && (a = "state")) return ee.errors = [{
										instancePath: t + "/data",
										schemaPath: "#/properties/data/required",
										keyword: "required",
										params: { missingProperty: a }
									}], !1;
									if (i.state !== void 0 && n.call(i, "state")) {
										let e = l;
										if (typeof i.state != "string") return ee.errors = [{
											instancePath: t + "/data/state",
											schemaPath: "#/properties/data/properties/state/type",
											keyword: "type",
											params: { type: "string" }
										}], !1;
										var d = e === l;
									} else var d = !0;
									if (d) {
										let n = i.state;
										if (typeof n == "string") {
											if (n === "anonymous") {
												r(i, {
													instancePath: t + "/data",
													parentData: e,
													parentDataProperty: "data",
													rootData: o,
													dynamicAnchors: s
												}) || (c = c === null ? r.errors : c.concat(r.errors), l = c.length);
												var f = !0;
											} else if (n === "recognized") v(i, {
												instancePath: t + "/data",
												parentData: e,
												parentDataProperty: "data",
												rootData: o,
												dynamicAnchors: s
											}) || (c = c === null ? v.errors : c.concat(v.errors), l = c.length), f !== !0 && (f = !0);
											else return ee.errors = [{
												instancePath: t + "/data",
												schemaPath: "#/properties/data/discriminator",
												keyword: "discriminator",
												params: {
													error: "mapping",
													tag: "state",
													tagValue: n
												}
											}], !1;
										} else return ee.errors = [{
											instancePath: t + "/data",
											schemaPath: "#/properties/data/discriminator",
											keyword: "discriminator",
											params: {
												error: "tag",
												tag: "state",
												tagValue: n
											}
										}], !1;
									}
								} else return ee.errors = [{
									instancePath: t + "/data",
									schemaPath: "#/properties/data/type",
									keyword: "type",
									params: { type: "object" }
								}], !1;
							}
							var p = a === l;
						} else var p = !0;
						if (p) {
							if (e.meta !== void 0 && n.call(e, "meta")) {
								let n = l;
								y(e.meta, {
									instancePath: t + "/meta",
									parentData: e,
									parentDataProperty: "meta",
									rootData: o,
									dynamicAnchors: s
								}) || (c = c === null ? y.errors : c.concat(y.errors), l = c.length);
								var p = n === l;
							} else var p = !0;
						}
					}
				}
			} else return ee.errors = [{
				instancePath: t,
				schemaPath: "#/type",
				keyword: "type",
				params: { type: "object" }
			}], !1;
		}
		return ee.errors = c, l === 0;
	}
	ee.evaluated = {
		props: !0,
		dynamicProps: !1,
		dynamicItems: !1
	}, e.v32 = Te;
	var te = {
		additionalProperties: !1,
		properties: {
			body_type: {
				discriminator: { propertyName: "status" },
				oneOf: [
					{ $ref: "urn:car-shopping-assistant:contract:1#/$defs/KnownFact_Annotated_str__StringConstraints__" },
					{ $ref: "urn:car-shopping-assistant:contract:1#/$defs/UnknownFact" },
					{ $ref: "urn:car-shopping-assistant:contract:1#/$defs/ConflictingFact_Annotated_str__StringConstraints__" }
				],
				title: "Body Type",
				type: "object",
				required: ["status"],
				properties: { status: { type: "string" } }
			},
			description: {
				maxLength: 32e3,
				title: "Description",
				type: "string"
			},
			eligibility: {
				enum: [
					"simulated_eligible",
					"unavailable",
					"configuration_missing"
				],
				title: "Eligibility",
				type: "string"
			},
			eligibility_reason: {
				maxLength: 200,
				minLength: 1,
				title: "Eligibility Reason",
				type: "string"
			},
			fuel_type: {
				discriminator: { propertyName: "status" },
				oneOf: [
					{ $ref: "urn:car-shopping-assistant:contract:1#/$defs/KnownFact_Annotated_str__StringConstraints__" },
					{ $ref: "urn:car-shopping-assistant:contract:1#/$defs/UnknownFact" },
					{ $ref: "urn:car-shopping-assistant:contract:1#/$defs/ConflictingFact_Annotated_str__StringConstraints__" }
				],
				title: "Fuel Type",
				type: "object",
				required: ["status"],
				properties: { status: { type: "string" } }
			},
			listing: { $ref: "urn:car-shopping-assistant:contract:1#/$defs/ListingSummary" },
			location: {
				discriminator: { propertyName: "status" },
				oneOf: [
					{ $ref: "urn:car-shopping-assistant:contract:1#/$defs/KnownFact_Annotated_str__StringConstraints__" },
					{ $ref: "urn:car-shopping-assistant:contract:1#/$defs/UnknownFact" },
					{ $ref: "urn:car-shopping-assistant:contract:1#/$defs/ConflictingFact_Annotated_str__StringConstraints__" }
				],
				title: "Location",
				type: "object",
				required: ["status"],
				properties: { status: { type: "string" } }
			},
			service_history: {
				discriminator: { propertyName: "status" },
				oneOf: [
					{ $ref: "urn:car-shopping-assistant:contract:1#/$defs/KnownFact_Annotated_str__StringConstraints__" },
					{ $ref: "urn:car-shopping-assistant:contract:1#/$defs/UnknownFact" },
					{ $ref: "urn:car-shopping-assistant:contract:1#/$defs/ConflictingFact_Annotated_str__StringConstraints__" }
				],
				title: "Service History",
				type: "object",
				required: ["status"],
				properties: { status: { type: "string" } }
			},
			state: {
				enum: ["current", "historical"],
				title: "State",
				type: "string"
			},
			transmission: {
				discriminator: { propertyName: "status" },
				oneOf: [
					{ $ref: "urn:car-shopping-assistant:contract:1#/$defs/KnownFact_Annotated_str__StringConstraints__" },
					{ $ref: "urn:car-shopping-assistant:contract:1#/$defs/UnknownFact" },
					{ $ref: "urn:car-shopping-assistant:contract:1#/$defs/ConflictingFact_Annotated_str__StringConstraints__" }
				],
				title: "Transmission",
				type: "object",
				required: ["status"],
				properties: { status: { type: "string" } }
			},
			warranty: {
				discriminator: { propertyName: "status" },
				oneOf: [
					{ $ref: "urn:car-shopping-assistant:contract:1#/$defs/KnownFact_Annotated_str__StringConstraints__" },
					{ $ref: "urn:car-shopping-assistant:contract:1#/$defs/UnknownFact" },
					{ $ref: "urn:car-shopping-assistant:contract:1#/$defs/ConflictingFact_Annotated_str__StringConstraints__" }
				],
				title: "Warranty",
				type: "object",
				required: ["status"],
				properties: { status: { type: "string" } }
			}
		},
		required: [
			"state",
			"listing",
			"description",
			"fuel_type",
			"body_type",
			"transmission",
			"location",
			"warranty",
			"service_history",
			"eligibility",
			"eligibility_reason"
		],
		title: "ListingDetail",
		type: "object"
	}, ne = {
		additionalProperties: !1,
		properties: {
			evidence: {
				items: { $ref: "urn:car-shopping-assistant:contract:1#/$defs/SourceLocator" },
				maxItems: 20,
				minItems: 1,
				title: "Evidence",
				type: "array"
			},
			qualifier: {
				default: "exact",
				enum: [
					"exact",
					"approximate",
					"at_least",
					"at_most"
				],
				title: "Qualifier",
				type: "string"
			},
			status: {
				const: "known",
				title: "Status",
				type: "string"
			},
			value: {
				maxLength: 200,
				minLength: 1,
				title: "Value",
				type: "string"
			}
		},
		required: [
			"status",
			"value",
			"evidence"
		],
		title: "KnownFact[Annotated[str, StringConstraints]]",
		type: "object"
	}, re = {
		additionalProperties: !1,
		properties: {
			category: {
				enum: [
					"structured_source",
					"seller_description",
					"reviewed_correction"
				],
				title: "Category",
				type: "string"
			},
			cell: {
				maxLength: 32,
				title: "Cell",
				type: "string"
			},
			evidence_id: {
				pattern: "^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$",
				title: "Evidence Id",
				type: "string"
			},
			extraction_version: {
				maxLength: 200,
				minLength: 1,
				title: "Extraction Version",
				type: "string"
			},
			original_unit: {
				anyOf: [{
					maxLength: 200,
					minLength: 1,
					type: "string"
				}, { type: "null" }],
				title: "Original Unit"
			},
			raw_text: {
				maxLength: 16e3,
				title: "Raw Text",
				type: "string"
			},
			review_status: {
				enum: [
					"not_reviewed",
					"reviewed_extraction",
					"reviewed_correction"
				],
				title: "Review Status",
				type: "string"
			},
			semantic_role: {
				anyOf: [{
					enum: [
						"vehicle_mileage",
						"warranty_limit",
						"service_interval",
						"cash_price",
						"finance_instalment",
						"salary",
						"fee",
						"service_cost",
						"other"
					],
					type: "string"
				}, { type: "null" }],
				title: "Semantic Role"
			},
			sheet: {
				maxLength: 200,
				minLength: 1,
				title: "Sheet",
				type: "string"
			},
			span_end: {
				minimum: 0,
				title: "Span End",
				type: "integer"
			},
			span_start: {
				minimum: 0,
				title: "Span Start",
				type: "integer"
			},
			verification: {
				const: "source_claim",
				default: "source_claim",
				title: "Verification",
				type: "string"
			},
			workbook_sha256: {
				pattern: "^[0-9a-f]{64}$",
				title: "Workbook Sha256",
				type: "string"
			}
		},
		required: [
			"evidence_id",
			"workbook_sha256",
			"sheet",
			"cell",
			"raw_text",
			"span_start",
			"span_end",
			"extraction_version",
			"category",
			"review_status"
		],
		title: "SourceLocator",
		type: "object"
	};
	function b(e, { instancePath: t = "", parentData: r, parentDataProperty: i, rootData: a = e, dynamicAnchors: o = {} } = {}) {
		let c = null, l = 0, d = b.evaluated;
		if (d.dynamicProps && (d.props = void 0), d.dynamicItems && (d.items = void 0), l === 0) {
			if (e && typeof e == "object" && !Array.isArray(e)) {
				let r;
				if ((e.evidence_id === void 0 || !n.call(e, "evidence_id")) && (r = "evidence_id") || (e.workbook_sha256 === void 0 || !n.call(e, "workbook_sha256")) && (r = "workbook_sha256") || (e.sheet === void 0 || !n.call(e, "sheet")) && (r = "sheet") || (e.cell === void 0 || !n.call(e, "cell")) && (r = "cell") || (e.raw_text === void 0 || !n.call(e, "raw_text")) && (r = "raw_text") || (e.span_start === void 0 || !n.call(e, "span_start")) && (r = "span_start") || (e.span_end === void 0 || !n.call(e, "span_end")) && (r = "span_end") || (e.extraction_version === void 0 || !n.call(e, "extraction_version")) && (r = "extraction_version") || (e.category === void 0 || !n.call(e, "category")) && (r = "category") || (e.review_status === void 0 || !n.call(e, "review_status")) && (r = "review_status")) return b.errors = [{
					instancePath: t,
					schemaPath: "#/required",
					keyword: "required",
					params: { missingProperty: r }
				}], !1;
				{
					let r = l;
					for (let r of Object.keys(e)) if (!n.call(re.properties, r)) return b.errors = [{
						instancePath: t,
						schemaPath: "#/additionalProperties",
						keyword: "additionalProperties",
						params: { additionalProperty: r }
					}], !1;
					if (r === l) {
						if (e.category !== void 0 && n.call(e, "category")) {
							let n = e.category, r = l;
							if (typeof n != "string") return b.errors = [{
								instancePath: t + "/category",
								schemaPath: "#/properties/category/type",
								keyword: "type",
								params: { type: "string" }
							}], !1;
							if (n !== "structured_source" && n !== "seller_description" && n !== "reviewed_correction") return b.errors = [{
								instancePath: t + "/category",
								schemaPath: "#/properties/category/enum",
								keyword: "enum",
								params: { allowedValues: re.properties.category.enum }
							}], !1;
							var f = r === l;
						} else var f = !0;
						if (f) {
							if (e.cell !== void 0 && n.call(e, "cell")) {
								let n = e.cell, r = l;
								if (l === r) {
									if (typeof n == "string") {
										if (h(n) > 32) return b.errors = [{
											instancePath: t + "/cell",
											schemaPath: "#/properties/cell/maxLength",
											keyword: "maxLength",
											params: { limit: 32 }
										}], !1;
									} else return b.errors = [{
										instancePath: t + "/cell",
										schemaPath: "#/properties/cell/type",
										keyword: "type",
										params: { type: "string" }
									}], !1;
								}
								var f = r === l;
							} else var f = !0;
							if (f) {
								if (e.evidence_id !== void 0 && n.call(e, "evidence_id")) {
									let n = e.evidence_id, r = l;
									if (l === r) {
										if (typeof n == "string") {
											if (!u.test(n)) return b.errors = [{
												instancePath: t + "/evidence_id",
												schemaPath: "#/properties/evidence_id/pattern",
												keyword: "pattern",
												params: { pattern: "^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$" }
											}], !1;
										} else return b.errors = [{
											instancePath: t + "/evidence_id",
											schemaPath: "#/properties/evidence_id/type",
											keyword: "type",
											params: { type: "string" }
										}], !1;
									}
									var f = r === l;
								} else var f = !0;
								if (f) {
									if (e.extraction_version !== void 0 && n.call(e, "extraction_version")) {
										let n = e.extraction_version, r = l;
										if (l === r) {
											if (typeof n == "string") {
												if (h(n) > 200) return b.errors = [{
													instancePath: t + "/extraction_version",
													schemaPath: "#/properties/extraction_version/maxLength",
													keyword: "maxLength",
													params: { limit: 200 }
												}], !1;
												if (h(n) < 1) return b.errors = [{
													instancePath: t + "/extraction_version",
													schemaPath: "#/properties/extraction_version/minLength",
													keyword: "minLength",
													params: { limit: 1 }
												}], !1;
											} else return b.errors = [{
												instancePath: t + "/extraction_version",
												schemaPath: "#/properties/extraction_version/type",
												keyword: "type",
												params: { type: "string" }
											}], !1;
										}
										var f = r === l;
									} else var f = !0;
									if (f) {
										if (e.original_unit !== void 0 && n.call(e, "original_unit")) {
											let n = e.original_unit, r = l, i = l, a = !1, o = l;
											if (l === o) {
												if (typeof n == "string") {
													if (h(n) > 200) {
														let e = {
															instancePath: t + "/original_unit",
															schemaPath: "#/properties/original_unit/anyOf/0/maxLength",
															keyword: "maxLength",
															params: { limit: 200 }
														};
														c === null ? c = [e] : c.push(e), l++;
													} else if (h(n) < 1) {
														let e = {
															instancePath: t + "/original_unit",
															schemaPath: "#/properties/original_unit/anyOf/0/minLength",
															keyword: "minLength",
															params: { limit: 1 }
														};
														c === null ? c = [e] : c.push(e), l++;
													}
												} else {
													let e = {
														instancePath: t + "/original_unit",
														schemaPath: "#/properties/original_unit/anyOf/0/type",
														keyword: "type",
														params: { type: "string" }
													};
													c === null ? c = [e] : c.push(e), l++;
												}
											}
											var p = o === l;
											a ||= p;
											let s = l;
											if (n !== null) {
												let e = {
													instancePath: t + "/original_unit",
													schemaPath: "#/properties/original_unit/anyOf/1/type",
													keyword: "type",
													params: { type: "null" }
												};
												c === null ? c = [e] : c.push(e), l++;
											}
											var p = s === l;
											if (a ||= p, a) l = i, c !== null && (i ? c.length = i : c = null);
											else {
												let e = {
													instancePath: t + "/original_unit",
													schemaPath: "#/properties/original_unit/anyOf",
													keyword: "anyOf",
													params: {}
												};
												return c === null ? c = [e] : c.push(e), l++, b.errors = c, !1;
											}
											var f = r === l;
										} else var f = !0;
										if (f) {
											if (e.raw_text !== void 0 && n.call(e, "raw_text")) {
												let n = e.raw_text, r = l;
												if (l === r) {
													if (typeof n == "string") {
														if (h(n) > 16e3) return b.errors = [{
															instancePath: t + "/raw_text",
															schemaPath: "#/properties/raw_text/maxLength",
															keyword: "maxLength",
															params: { limit: 16e3 }
														}], !1;
													} else return b.errors = [{
														instancePath: t + "/raw_text",
														schemaPath: "#/properties/raw_text/type",
														keyword: "type",
														params: { type: "string" }
													}], !1;
												}
												var f = r === l;
											} else var f = !0;
											if (f) {
												if (e.review_status !== void 0 && n.call(e, "review_status")) {
													let n = e.review_status, r = l;
													if (typeof n != "string") return b.errors = [{
														instancePath: t + "/review_status",
														schemaPath: "#/properties/review_status/type",
														keyword: "type",
														params: { type: "string" }
													}], !1;
													if (n !== "not_reviewed" && n !== "reviewed_extraction" && n !== "reviewed_correction") return b.errors = [{
														instancePath: t + "/review_status",
														schemaPath: "#/properties/review_status/enum",
														keyword: "enum",
														params: { allowedValues: re.properties.review_status.enum }
													}], !1;
													var f = r === l;
												} else var f = !0;
												if (f) {
													if (e.semantic_role !== void 0 && n.call(e, "semantic_role")) {
														let n = e.semantic_role, r = l, i = l, a = !1, o = l;
														if (typeof n != "string") {
															let e = {
																instancePath: t + "/semantic_role",
																schemaPath: "#/properties/semantic_role/anyOf/0/type",
																keyword: "type",
																params: { type: "string" }
															};
															c === null ? c = [e] : c.push(e), l++;
														}
														if (n !== "vehicle_mileage" && n !== "warranty_limit" && n !== "service_interval" && n !== "cash_price" && n !== "finance_instalment" && n !== "salary" && n !== "fee" && n !== "service_cost" && n !== "other") {
															let e = {
																instancePath: t + "/semantic_role",
																schemaPath: "#/properties/semantic_role/anyOf/0/enum",
																keyword: "enum",
																params: { allowedValues: re.properties.semantic_role.anyOf[0].enum }
															};
															c === null ? c = [e] : c.push(e), l++;
														}
														var m = o === l;
														a ||= m;
														let s = l;
														if (n !== null) {
															let e = {
																instancePath: t + "/semantic_role",
																schemaPath: "#/properties/semantic_role/anyOf/1/type",
																keyword: "type",
																params: { type: "null" }
															};
															c === null ? c = [e] : c.push(e), l++;
														}
														var m = s === l;
														if (a ||= m, a) l = i, c !== null && (i ? c.length = i : c = null);
														else {
															let e = {
																instancePath: t + "/semantic_role",
																schemaPath: "#/properties/semantic_role/anyOf",
																keyword: "anyOf",
																params: {}
															};
															return c === null ? c = [e] : c.push(e), l++, b.errors = c, !1;
														}
														var f = r === l;
													} else var f = !0;
													if (f) {
														if (e.sheet !== void 0 && n.call(e, "sheet")) {
															let n = e.sheet, r = l;
															if (l === r) {
																if (typeof n == "string") {
																	if (h(n) > 200) return b.errors = [{
																		instancePath: t + "/sheet",
																		schemaPath: "#/properties/sheet/maxLength",
																		keyword: "maxLength",
																		params: { limit: 200 }
																	}], !1;
																	if (h(n) < 1) return b.errors = [{
																		instancePath: t + "/sheet",
																		schemaPath: "#/properties/sheet/minLength",
																		keyword: "minLength",
																		params: { limit: 1 }
																	}], !1;
																} else return b.errors = [{
																	instancePath: t + "/sheet",
																	schemaPath: "#/properties/sheet/type",
																	keyword: "type",
																	params: { type: "string" }
																}], !1;
															}
															var f = r === l;
														} else var f = !0;
														if (f) {
															if (e.span_end !== void 0 && n.call(e, "span_end")) {
																let n = e.span_end, r = l;
																if (typeof n != "number" || n % 1 || isNaN(n) || !isFinite(n)) return b.errors = [{
																	instancePath: t + "/span_end",
																	schemaPath: "#/properties/span_end/type",
																	keyword: "type",
																	params: { type: "integer" }
																}], !1;
																if (l === r && typeof n == "number" && isFinite(n) && (n < 0 || isNaN(n))) return b.errors = [{
																	instancePath: t + "/span_end",
																	schemaPath: "#/properties/span_end/minimum",
																	keyword: "minimum",
																	params: {
																		comparison: ">=",
																		limit: 0
																	}
																}], !1;
																var f = r === l;
															} else var f = !0;
															if (f) {
																if (e.span_start !== void 0 && n.call(e, "span_start")) {
																	let n = e.span_start, r = l;
																	if (typeof n != "number" || n % 1 || isNaN(n) || !isFinite(n)) return b.errors = [{
																		instancePath: t + "/span_start",
																		schemaPath: "#/properties/span_start/type",
																		keyword: "type",
																		params: { type: "integer" }
																	}], !1;
																	if (l === r && typeof n == "number" && isFinite(n) && (n < 0 || isNaN(n))) return b.errors = [{
																		instancePath: t + "/span_start",
																		schemaPath: "#/properties/span_start/minimum",
																		keyword: "minimum",
																		params: {
																			comparison: ">=",
																			limit: 0
																		}
																	}], !1;
																	var f = r === l;
																} else var f = !0;
																if (f) {
																	if (e.verification !== void 0 && n.call(e, "verification")) {
																		let n = e.verification, r = l;
																		if (typeof n != "string") return b.errors = [{
																			instancePath: t + "/verification",
																			schemaPath: "#/properties/verification/type",
																			keyword: "type",
																			params: { type: "string" }
																		}], !1;
																		if (n !== "source_claim") return b.errors = [{
																			instancePath: t + "/verification",
																			schemaPath: "#/properties/verification/const",
																			keyword: "const",
																			params: { allowedValue: "source_claim" }
																		}], !1;
																		var f = r === l;
																	} else var f = !0;
																	if (f) {
																		if (e.workbook_sha256 !== void 0 && n.call(e, "workbook_sha256")) {
																			let n = e.workbook_sha256, r = l;
																			if (l === r) {
																				if (typeof n == "string") {
																					if (!s.test(n)) return b.errors = [{
																						instancePath: t + "/workbook_sha256",
																						schemaPath: "#/properties/workbook_sha256/pattern",
																						keyword: "pattern",
																						params: { pattern: "^[0-9a-f]{64}$" }
																					}], !1;
																				} else return b.errors = [{
																					instancePath: t + "/workbook_sha256",
																					schemaPath: "#/properties/workbook_sha256/type",
																					keyword: "type",
																					params: { type: "string" }
																				}], !1;
																			}
																			var f = r === l;
																		} else var f = !0;
																	}
																}
															}
														}
													}
												}
											}
										}
									}
								}
							}
						}
					}
				}
			} else return b.errors = [{
				instancePath: t,
				schemaPath: "#/type",
				keyword: "type",
				params: { type: "object" }
			}], !1;
		}
		return b.errors = c, l === 0;
	}
	b.evaluated = {
		props: !0,
		dynamicProps: !1,
		dynamicItems: !1
	};
	function x(e, { instancePath: t = "", parentData: r, parentDataProperty: i, rootData: a = e, dynamicAnchors: o = {} } = {}) {
		let s = null, c = 0, l = x.evaluated;
		if (l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0) {
			if (e && typeof e == "object" && !Array.isArray(e)) {
				let r;
				if ((e.status === void 0 || !n.call(e, "status")) && (r = "status") || (e.value === void 0 || !n.call(e, "value")) && (r = "value") || (e.evidence === void 0 || !n.call(e, "evidence")) && (r = "evidence")) return x.errors = [{
					instancePath: t,
					schemaPath: "#/required",
					keyword: "required",
					params: { missingProperty: r }
				}], !1;
				{
					let r = c;
					for (let n of Object.keys(e)) if (n !== "evidence" && n !== "qualifier" && n !== "status" && n !== "value") return x.errors = [{
						instancePath: t,
						schemaPath: "#/additionalProperties",
						keyword: "additionalProperties",
						params: { additionalProperty: n }
					}], !1;
					if (r === c) {
						if (e.evidence !== void 0 && n.call(e, "evidence")) {
							let n = e.evidence, r = c;
							if (c === r) {
								if (Array.isArray(n)) {
									if (n.length > 20) return x.errors = [{
										instancePath: t + "/evidence",
										schemaPath: "#/properties/evidence/maxItems",
										keyword: "maxItems",
										params: { limit: 20 }
									}], !1;
									if (n.length < 1) return x.errors = [{
										instancePath: t + "/evidence",
										schemaPath: "#/properties/evidence/minItems",
										keyword: "minItems",
										params: { limit: 1 }
									}], !1;
									{
										let e = n.length;
										for (let r = 0; r < e; r++) {
											let e = c;
											if (b(n[r], {
												instancePath: t + "/evidence/" + r,
												parentData: n,
												parentDataProperty: r,
												rootData: a,
												dynamicAnchors: o
											}) || (s = s === null ? b.errors : s.concat(b.errors), c = s.length), e !== c) break;
										}
									}
								} else return x.errors = [{
									instancePath: t + "/evidence",
									schemaPath: "#/properties/evidence/type",
									keyword: "type",
									params: { type: "array" }
								}], !1;
							}
							var u = r === c;
						} else var u = !0;
						if (u) {
							if (e.qualifier !== void 0 && n.call(e, "qualifier")) {
								let n = e.qualifier, r = c;
								if (typeof n != "string") return x.errors = [{
									instancePath: t + "/qualifier",
									schemaPath: "#/properties/qualifier/type",
									keyword: "type",
									params: { type: "string" }
								}], !1;
								if (n !== "exact" && n !== "approximate" && n !== "at_least" && n !== "at_most") return x.errors = [{
									instancePath: t + "/qualifier",
									schemaPath: "#/properties/qualifier/enum",
									keyword: "enum",
									params: { allowedValues: ne.properties.qualifier.enum }
								}], !1;
								var u = r === c;
							} else var u = !0;
							if (u) {
								if (e.status !== void 0 && n.call(e, "status")) {
									let n = e.status, r = c;
									if (typeof n != "string") return x.errors = [{
										instancePath: t + "/status",
										schemaPath: "#/properties/status/type",
										keyword: "type",
										params: { type: "string" }
									}], !1;
									if (n !== "known") return x.errors = [{
										instancePath: t + "/status",
										schemaPath: "#/properties/status/const",
										keyword: "const",
										params: { allowedValue: "known" }
									}], !1;
									var u = r === c;
								} else var u = !0;
								if (u) {
									if (e.value !== void 0 && n.call(e, "value")) {
										let n = e.value, r = c;
										if (c === r) {
											if (typeof n == "string") {
												if (h(n) > 200) return x.errors = [{
													instancePath: t + "/value",
													schemaPath: "#/properties/value/maxLength",
													keyword: "maxLength",
													params: { limit: 200 }
												}], !1;
												if (h(n) < 1) return x.errors = [{
													instancePath: t + "/value",
													schemaPath: "#/properties/value/minLength",
													keyword: "minLength",
													params: { limit: 1 }
												}], !1;
											} else return x.errors = [{
												instancePath: t + "/value",
												schemaPath: "#/properties/value/type",
												keyword: "type",
												params: { type: "string" }
											}], !1;
										}
										var u = r === c;
									} else var u = !0;
								}
							}
						}
					}
				}
			} else return x.errors = [{
				instancePath: t,
				schemaPath: "#/type",
				keyword: "type",
				params: { type: "object" }
			}], !1;
		}
		return x.errors = s, c === 0;
	}
	x.evaluated = {
		props: !0,
		dynamicProps: !1,
		dynamicItems: !1
	};
	var ie = {
		additionalProperties: !1,
		properties: {
			reason: {
				enum: [
					"not_stated",
					"unparseable",
					"unsupported",
					"not_applicable"
				],
				title: "Reason",
				type: "string"
			},
			status: {
				const: "unknown",
				title: "Status",
				type: "string"
			}
		},
		required: ["status", "reason"],
		title: "UnknownFact",
		type: "object"
	};
	function S(e, { instancePath: t = "", parentData: r, parentDataProperty: i, rootData: a = e, dynamicAnchors: o = {} } = {}) {
		let s = S.evaluated;
		if (s.dynamicProps && (s.props = void 0), s.dynamicItems && (s.items = void 0), e && typeof e == "object" && !Array.isArray(e)) {
			let r;
			if ((e.status === void 0 || !n.call(e, "status")) && (r = "status") || (e.reason === void 0 || !n.call(e, "reason")) && (r = "reason")) return S.errors = [{
				instancePath: t,
				schemaPath: "#/required",
				keyword: "required",
				params: { missingProperty: r }
			}], !1;
			for (let n of Object.keys(e)) if (n !== "reason" && n !== "status") return S.errors = [{
				instancePath: t,
				schemaPath: "#/additionalProperties",
				keyword: "additionalProperties",
				params: { additionalProperty: n }
			}], !1;
			if (e.reason !== void 0 && n.call(e, "reason")) {
				let n = e.reason;
				if (typeof n != "string") return S.errors = [{
					instancePath: t + "/reason",
					schemaPath: "#/properties/reason/type",
					keyword: "type",
					params: { type: "string" }
				}], !1;
				if (n !== "not_stated" && n !== "unparseable" && n !== "unsupported" && n !== "not_applicable") return S.errors = [{
					instancePath: t + "/reason",
					schemaPath: "#/properties/reason/enum",
					keyword: "enum",
					params: { allowedValues: ie.properties.reason.enum }
				}], !1;
				var c = !0;
			} else var c = !0;
			if (c) {
				if (e.status !== void 0 && n.call(e, "status")) {
					let n = e.status;
					if (typeof n != "string") return S.errors = [{
						instancePath: t + "/status",
						schemaPath: "#/properties/status/type",
						keyword: "type",
						params: { type: "string" }
					}], !1;
					if (n !== "unknown") return S.errors = [{
						instancePath: t + "/status",
						schemaPath: "#/properties/status/const",
						keyword: "const",
						params: { allowedValue: "unknown" }
					}], !1;
					var c = !0;
				} else var c = !0;
			}
		} else return S.errors = [{
			instancePath: t,
			schemaPath: "#/type",
			keyword: "type",
			params: { type: "object" }
		}], !1;
		return S.errors = null, !0;
	}
	S.evaluated = {
		props: !0,
		dynamicProps: !1,
		dynamicItems: !1
	};
	var ae = {
		additionalProperties: !1,
		properties: {
			evidence: {
				items: { $ref: "urn:car-shopping-assistant:contract:1#/$defs/SourceLocator" },
				maxItems: 20,
				minItems: 1,
				title: "Evidence",
				type: "array"
			},
			qualifier: {
				default: "exact",
				enum: [
					"exact",
					"approximate",
					"at_least",
					"at_most"
				],
				title: "Qualifier",
				type: "string"
			},
			value: {
				maxLength: 200,
				minLength: 1,
				title: "Value",
				type: "string"
			}
		},
		required: ["value", "evidence"],
		title: "FactClaim[Annotated[str, StringConstraints]]",
		type: "object"
	};
	function oe(e, { instancePath: t = "", parentData: r, parentDataProperty: i, rootData: a = e, dynamicAnchors: o = {} } = {}) {
		let s = null, c = 0, l = oe.evaluated;
		if (l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0) {
			if (e && typeof e == "object" && !Array.isArray(e)) {
				let r;
				if ((e.value === void 0 || !n.call(e, "value")) && (r = "value") || (e.evidence === void 0 || !n.call(e, "evidence")) && (r = "evidence")) return oe.errors = [{
					instancePath: t,
					schemaPath: "#/required",
					keyword: "required",
					params: { missingProperty: r }
				}], !1;
				{
					let r = c;
					for (let n of Object.keys(e)) if (n !== "evidence" && n !== "qualifier" && n !== "value") return oe.errors = [{
						instancePath: t,
						schemaPath: "#/additionalProperties",
						keyword: "additionalProperties",
						params: { additionalProperty: n }
					}], !1;
					if (r === c) {
						if (e.evidence !== void 0 && n.call(e, "evidence")) {
							let n = e.evidence, r = c;
							if (c === r) {
								if (Array.isArray(n)) {
									if (n.length > 20) return oe.errors = [{
										instancePath: t + "/evidence",
										schemaPath: "#/properties/evidence/maxItems",
										keyword: "maxItems",
										params: { limit: 20 }
									}], !1;
									if (n.length < 1) return oe.errors = [{
										instancePath: t + "/evidence",
										schemaPath: "#/properties/evidence/minItems",
										keyword: "minItems",
										params: { limit: 1 }
									}], !1;
									{
										let e = n.length;
										for (let r = 0; r < e; r++) {
											let e = c;
											if (b(n[r], {
												instancePath: t + "/evidence/" + r,
												parentData: n,
												parentDataProperty: r,
												rootData: a,
												dynamicAnchors: o
											}) || (s = s === null ? b.errors : s.concat(b.errors), c = s.length), e !== c) break;
										}
									}
								} else return oe.errors = [{
									instancePath: t + "/evidence",
									schemaPath: "#/properties/evidence/type",
									keyword: "type",
									params: { type: "array" }
								}], !1;
							}
							var u = r === c;
						} else var u = !0;
						if (u) {
							if (e.qualifier !== void 0 && n.call(e, "qualifier")) {
								let n = e.qualifier, r = c;
								if (typeof n != "string") return oe.errors = [{
									instancePath: t + "/qualifier",
									schemaPath: "#/properties/qualifier/type",
									keyword: "type",
									params: { type: "string" }
								}], !1;
								if (n !== "exact" && n !== "approximate" && n !== "at_least" && n !== "at_most") return oe.errors = [{
									instancePath: t + "/qualifier",
									schemaPath: "#/properties/qualifier/enum",
									keyword: "enum",
									params: { allowedValues: ae.properties.qualifier.enum }
								}], !1;
								var u = r === c;
							} else var u = !0;
							if (u) {
								if (e.value !== void 0 && n.call(e, "value")) {
									let n = e.value, r = c;
									if (c === r) {
										if (typeof n == "string") {
											if (h(n) > 200) return oe.errors = [{
												instancePath: t + "/value",
												schemaPath: "#/properties/value/maxLength",
												keyword: "maxLength",
												params: { limit: 200 }
											}], !1;
											if (h(n) < 1) return oe.errors = [{
												instancePath: t + "/value",
												schemaPath: "#/properties/value/minLength",
												keyword: "minLength",
												params: { limit: 1 }
											}], !1;
										} else return oe.errors = [{
											instancePath: t + "/value",
											schemaPath: "#/properties/value/type",
											keyword: "type",
											params: { type: "string" }
										}], !1;
									}
									var u = r === c;
								} else var u = !0;
							}
						}
					}
				}
			} else return oe.errors = [{
				instancePath: t,
				schemaPath: "#/type",
				keyword: "type",
				params: { type: "object" }
			}], !1;
		}
		return oe.errors = s, c === 0;
	}
	oe.evaluated = {
		props: !0,
		dynamicProps: !1,
		dynamicItems: !1
	};
	function C(e, { instancePath: t = "", parentData: r, parentDataProperty: i, rootData: a = e, dynamicAnchors: o = {} } = {}) {
		let s = null, c = 0, l = C.evaluated;
		if (l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0) {
			if (e && typeof e == "object" && !Array.isArray(e)) {
				let r;
				if ((e.status === void 0 || !n.call(e, "status")) && (r = "status") || (e.claims === void 0 || !n.call(e, "claims")) && (r = "claims")) return C.errors = [{
					instancePath: t,
					schemaPath: "#/required",
					keyword: "required",
					params: { missingProperty: r }
				}], !1;
				{
					let r = c;
					for (let n of Object.keys(e)) if (n !== "claims" && n !== "status") return C.errors = [{
						instancePath: t,
						schemaPath: "#/additionalProperties",
						keyword: "additionalProperties",
						params: { additionalProperty: n }
					}], !1;
					if (r === c) {
						if (e.claims !== void 0 && n.call(e, "claims")) {
							let n = e.claims, r = c;
							if (c === r) {
								if (Array.isArray(n)) {
									if (n.length > 20) return C.errors = [{
										instancePath: t + "/claims",
										schemaPath: "#/properties/claims/maxItems",
										keyword: "maxItems",
										params: { limit: 20 }
									}], !1;
									if (n.length < 2) return C.errors = [{
										instancePath: t + "/claims",
										schemaPath: "#/properties/claims/minItems",
										keyword: "minItems",
										params: { limit: 2 }
									}], !1;
									{
										let e = n.length;
										for (let r = 0; r < e; r++) {
											let e = c;
											if (oe(n[r], {
												instancePath: t + "/claims/" + r,
												parentData: n,
												parentDataProperty: r,
												rootData: a,
												dynamicAnchors: o
											}) || (s = s === null ? oe.errors : s.concat(oe.errors), c = s.length), e !== c) break;
										}
									}
								} else return C.errors = [{
									instancePath: t + "/claims",
									schemaPath: "#/properties/claims/type",
									keyword: "type",
									params: { type: "array" }
								}], !1;
							}
							var u = r === c;
						} else var u = !0;
						if (u) {
							if (e.status !== void 0 && n.call(e, "status")) {
								let n = e.status, r = c;
								if (typeof n != "string") return C.errors = [{
									instancePath: t + "/status",
									schemaPath: "#/properties/status/type",
									keyword: "type",
									params: { type: "string" }
								}], !1;
								if (n !== "conflicting") return C.errors = [{
									instancePath: t + "/status",
									schemaPath: "#/properties/status/const",
									keyword: "const",
									params: { allowedValue: "conflicting" }
								}], !1;
								var u = r === c;
							} else var u = !0;
						}
					}
				}
			} else return C.errors = [{
				instancePath: t,
				schemaPath: "#/type",
				keyword: "type",
				params: { type: "object" }
			}], !1;
		}
		return C.errors = s, c === 0;
	}
	C.evaluated = {
		props: !0,
		dynamicProps: !1,
		dynamicItems: !1
	};
	var se = {
		additionalProperties: !1,
		properties: {
			cash_price: {
				discriminator: { propertyName: "status" },
				oneOf: [
					{ $ref: "urn:car-shopping-assistant:contract:1#/$defs/KnownFact_CashMoney_" },
					{ $ref: "urn:car-shopping-assistant:contract:1#/$defs/UnknownFact" },
					{ $ref: "urn:car-shopping-assistant:contract:1#/$defs/ConflictingFact_CashMoney_" }
				],
				title: "Cash Price",
				type: "object",
				required: ["status"],
				properties: { status: { type: "string" } }
			},
			evidence_warnings: {
				default: [],
				items: {
					maxLength: 200,
					minLength: 1,
					type: "string"
				},
				maxItems: 24,
				title: "Evidence Warnings",
				type: "array"
			},
			make: {
				discriminator: { propertyName: "status" },
				oneOf: [
					{ $ref: "urn:car-shopping-assistant:contract:1#/$defs/KnownFact_Annotated_str__StringConstraints__" },
					{ $ref: "urn:car-shopping-assistant:contract:1#/$defs/UnknownFact" },
					{ $ref: "urn:car-shopping-assistant:contract:1#/$defs/ConflictingFact_Annotated_str__StringConstraints__" }
				],
				title: "Make",
				type: "object",
				required: ["status"],
				properties: { status: { type: "string" } }
			},
			mileage_km: {
				discriminator: { propertyName: "status" },
				oneOf: [
					{ $ref: "urn:car-shopping-assistant:contract:1#/$defs/KnownFact_Annotated_int__Strict_strict_True___" },
					{ $ref: "urn:car-shopping-assistant:contract:1#/$defs/UnknownFact" },
					{ $ref: "urn:car-shopping-assistant:contract:1#/$defs/ConflictingFact_Annotated_int__Strict_strict_True___" }
				],
				title: "Mileage Km",
				type: "object",
				required: ["status"],
				properties: { status: { type: "string" } }
			},
			model: {
				discriminator: { propertyName: "status" },
				oneOf: [
					{ $ref: "urn:car-shopping-assistant:contract:1#/$defs/KnownFact_Annotated_str__StringConstraints__" },
					{ $ref: "urn:car-shopping-assistant:contract:1#/$defs/UnknownFact" },
					{ $ref: "urn:car-shopping-assistant:contract:1#/$defs/ConflictingFact_Annotated_str__StringConstraints__" }
				],
				title: "Model",
				type: "object",
				required: ["status"],
				properties: { status: { type: "string" } }
			},
			photo: { $ref: "urn:car-shopping-assistant:contract:1#/$defs/ListingPhoto" },
			ref: { $ref: "urn:car-shopping-assistant:contract:1#/$defs/InventoryRef" },
			title: {
				maxLength: 1e3,
				minLength: 1,
				title: "Title",
				type: "string"
			},
			trim: {
				discriminator: { propertyName: "status" },
				oneOf: [
					{ $ref: "urn:car-shopping-assistant:contract:1#/$defs/KnownFact_Annotated_str__StringConstraints__" },
					{ $ref: "urn:car-shopping-assistant:contract:1#/$defs/UnknownFact" },
					{ $ref: "urn:car-shopping-assistant:contract:1#/$defs/ConflictingFact_Annotated_str__StringConstraints__" }
				],
				title: "Trim",
				type: "object",
				required: ["status"],
				properties: { status: { type: "string" } }
			},
			year: {
				discriminator: { propertyName: "status" },
				oneOf: [
					{ $ref: "urn:car-shopping-assistant:contract:1#/$defs/KnownFact_Annotated_int__Strict_strict_True___" },
					{ $ref: "urn:car-shopping-assistant:contract:1#/$defs/UnknownFact" },
					{ $ref: "urn:car-shopping-assistant:contract:1#/$defs/ConflictingFact_Annotated_int__Strict_strict_True___" }
				],
				title: "Year",
				type: "object",
				required: ["status"],
				properties: { status: { type: "string" } }
			}
		},
		required: [
			"ref",
			"title",
			"make",
			"model",
			"trim",
			"year",
			"cash_price",
			"mileage_km",
			"photo"
		],
		title: "ListingSummary",
		type: "object"
	}, ce = {
		additionalProperties: !1,
		properties: {
			evidence: {
				items: { $ref: "urn:car-shopping-assistant:contract:1#/$defs/SourceLocator" },
				maxItems: 20,
				minItems: 1,
				title: "Evidence",
				type: "array"
			},
			qualifier: {
				default: "exact",
				enum: [
					"exact",
					"approximate",
					"at_least",
					"at_most"
				],
				title: "Qualifier",
				type: "string"
			},
			status: {
				const: "known",
				title: "Status",
				type: "string"
			},
			value: { $ref: "urn:car-shopping-assistant:contract:1#/$defs/CashMoney" }
		},
		required: [
			"status",
			"value",
			"evidence"
		],
		title: "KnownFact[CashMoney]",
		type: "object"
	}, le = /* @__PURE__ */ RegExp("^[A-Z]{3}$", "u");
	function ue(e, { instancePath: t = "", parentData: r, parentDataProperty: i, rootData: a = e, dynamicAnchors: o = {} } = {}) {
		let s = ue.evaluated;
		if (s.dynamicProps && (s.props = void 0), s.dynamicItems && (s.items = void 0), e && typeof e == "object" && !Array.isArray(e)) {
			let r;
			if ((e.minor_units === void 0 || !n.call(e, "minor_units")) && (r = "minor_units") || (e.currency === void 0 || !n.call(e, "currency")) && (r = "currency")) return ue.errors = [{
				instancePath: t,
				schemaPath: "#/required",
				keyword: "required",
				params: { missingProperty: r }
			}], !1;
			for (let n of Object.keys(e)) if (n !== "basis" && n !== "currency" && n !== "minor_units") return ue.errors = [{
				instancePath: t,
				schemaPath: "#/additionalProperties",
				keyword: "additionalProperties",
				params: { additionalProperty: n }
			}], !1;
			if (e.basis !== void 0 && n.call(e, "basis")) {
				let n = e.basis;
				if (typeof n != "string") return ue.errors = [{
					instancePath: t + "/basis",
					schemaPath: "#/properties/basis/type",
					keyword: "type",
					params: { type: "string" }
				}], !1;
				if (n !== "cash") return ue.errors = [{
					instancePath: t + "/basis",
					schemaPath: "#/properties/basis/const",
					keyword: "const",
					params: { allowedValue: "cash" }
				}], !1;
				var c = !0;
			} else var c = !0;
			if (c) {
				if (e.currency !== void 0 && n.call(e, "currency")) {
					let n = e.currency;
					if (typeof n == "string") {
						if (!le.test(n)) return ue.errors = [{
							instancePath: t + "/currency",
							schemaPath: "#/properties/currency/pattern",
							keyword: "pattern",
							params: { pattern: "^[A-Z]{3}$" }
						}], !1;
					} else return ue.errors = [{
						instancePath: t + "/currency",
						schemaPath: "#/properties/currency/type",
						keyword: "type",
						params: { type: "string" }
					}], !1;
					var c = !0;
				} else var c = !0;
				if (c) {
					if (e.minor_units !== void 0 && n.call(e, "minor_units")) {
						let n = e.minor_units;
						if (typeof n != "number" || n % 1 || isNaN(n) || !isFinite(n)) return ue.errors = [{
							instancePath: t + "/minor_units",
							schemaPath: "#/properties/minor_units/type",
							keyword: "type",
							params: { type: "integer" }
						}], !1;
						if (typeof n == "number" && isFinite(n)) {
							if (n > 0xe8d4a51000 || isNaN(n)) return ue.errors = [{
								instancePath: t + "/minor_units",
								schemaPath: "#/properties/minor_units/maximum",
								keyword: "maximum",
								params: {
									comparison: "<=",
									limit: 0xe8d4a51000
								}
							}], !1;
							if (n < 0 || isNaN(n)) return ue.errors = [{
								instancePath: t + "/minor_units",
								schemaPath: "#/properties/minor_units/minimum",
								keyword: "minimum",
								params: {
									comparison: ">=",
									limit: 0
								}
							}], !1;
						}
						var c = !0;
					} else var c = !0;
				}
			}
		} else return ue.errors = [{
			instancePath: t,
			schemaPath: "#/type",
			keyword: "type",
			params: { type: "object" }
		}], !1;
		return ue.errors = null, !0;
	}
	ue.evaluated = {
		props: !0,
		dynamicProps: !1,
		dynamicItems: !1
	};
	function de(e, { instancePath: t = "", parentData: r, parentDataProperty: i, rootData: a = e, dynamicAnchors: o = {} } = {}) {
		let s = null, c = 0, l = de.evaluated;
		if (l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0) {
			if (e && typeof e == "object" && !Array.isArray(e)) {
				let r;
				if ((e.status === void 0 || !n.call(e, "status")) && (r = "status") || (e.value === void 0 || !n.call(e, "value")) && (r = "value") || (e.evidence === void 0 || !n.call(e, "evidence")) && (r = "evidence")) return de.errors = [{
					instancePath: t,
					schemaPath: "#/required",
					keyword: "required",
					params: { missingProperty: r }
				}], !1;
				{
					let r = c;
					for (let n of Object.keys(e)) if (n !== "evidence" && n !== "qualifier" && n !== "status" && n !== "value") return de.errors = [{
						instancePath: t,
						schemaPath: "#/additionalProperties",
						keyword: "additionalProperties",
						params: { additionalProperty: n }
					}], !1;
					if (r === c) {
						if (e.evidence !== void 0 && n.call(e, "evidence")) {
							let n = e.evidence, r = c;
							if (c === r) {
								if (Array.isArray(n)) {
									if (n.length > 20) return de.errors = [{
										instancePath: t + "/evidence",
										schemaPath: "#/properties/evidence/maxItems",
										keyword: "maxItems",
										params: { limit: 20 }
									}], !1;
									if (n.length < 1) return de.errors = [{
										instancePath: t + "/evidence",
										schemaPath: "#/properties/evidence/minItems",
										keyword: "minItems",
										params: { limit: 1 }
									}], !1;
									{
										let e = n.length;
										for (let r = 0; r < e; r++) {
											let e = c;
											if (b(n[r], {
												instancePath: t + "/evidence/" + r,
												parentData: n,
												parentDataProperty: r,
												rootData: a,
												dynamicAnchors: o
											}) || (s = s === null ? b.errors : s.concat(b.errors), c = s.length), e !== c) break;
										}
									}
								} else return de.errors = [{
									instancePath: t + "/evidence",
									schemaPath: "#/properties/evidence/type",
									keyword: "type",
									params: { type: "array" }
								}], !1;
							}
							var u = r === c;
						} else var u = !0;
						if (u) {
							if (e.qualifier !== void 0 && n.call(e, "qualifier")) {
								let n = e.qualifier, r = c;
								if (typeof n != "string") return de.errors = [{
									instancePath: t + "/qualifier",
									schemaPath: "#/properties/qualifier/type",
									keyword: "type",
									params: { type: "string" }
								}], !1;
								if (n !== "exact" && n !== "approximate" && n !== "at_least" && n !== "at_most") return de.errors = [{
									instancePath: t + "/qualifier",
									schemaPath: "#/properties/qualifier/enum",
									keyword: "enum",
									params: { allowedValues: ce.properties.qualifier.enum }
								}], !1;
								var u = r === c;
							} else var u = !0;
							if (u) {
								if (e.status !== void 0 && n.call(e, "status")) {
									let n = e.status, r = c;
									if (typeof n != "string") return de.errors = [{
										instancePath: t + "/status",
										schemaPath: "#/properties/status/type",
										keyword: "type",
										params: { type: "string" }
									}], !1;
									if (n !== "known") return de.errors = [{
										instancePath: t + "/status",
										schemaPath: "#/properties/status/const",
										keyword: "const",
										params: { allowedValue: "known" }
									}], !1;
									var u = r === c;
								} else var u = !0;
								if (u) {
									if (e.value !== void 0 && n.call(e, "value")) {
										let n = c;
										ue(e.value, {
											instancePath: t + "/value",
											parentData: e,
											parentDataProperty: "value",
											rootData: a,
											dynamicAnchors: o
										}) || (s = s === null ? ue.errors : s.concat(ue.errors), c = s.length);
										var u = n === c;
									} else var u = !0;
								}
							}
						}
					}
				}
			} else return de.errors = [{
				instancePath: t,
				schemaPath: "#/type",
				keyword: "type",
				params: { type: "object" }
			}], !1;
		}
		return de.errors = s, c === 0;
	}
	de.evaluated = {
		props: !0,
		dynamicProps: !1,
		dynamicItems: !1
	};
	var fe = {
		additionalProperties: !1,
		properties: {
			evidence: {
				items: { $ref: "urn:car-shopping-assistant:contract:1#/$defs/SourceLocator" },
				maxItems: 20,
				minItems: 1,
				title: "Evidence",
				type: "array"
			},
			qualifier: {
				default: "exact",
				enum: [
					"exact",
					"approximate",
					"at_least",
					"at_most"
				],
				title: "Qualifier",
				type: "string"
			},
			value: { $ref: "urn:car-shopping-assistant:contract:1#/$defs/CashMoney" }
		},
		required: ["value", "evidence"],
		title: "FactClaim[CashMoney]",
		type: "object"
	};
	function pe(e, { instancePath: t = "", parentData: r, parentDataProperty: i, rootData: a = e, dynamicAnchors: o = {} } = {}) {
		let s = null, c = 0, l = pe.evaluated;
		if (l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0) {
			if (e && typeof e == "object" && !Array.isArray(e)) {
				let r;
				if ((e.value === void 0 || !n.call(e, "value")) && (r = "value") || (e.evidence === void 0 || !n.call(e, "evidence")) && (r = "evidence")) return pe.errors = [{
					instancePath: t,
					schemaPath: "#/required",
					keyword: "required",
					params: { missingProperty: r }
				}], !1;
				{
					let r = c;
					for (let n of Object.keys(e)) if (n !== "evidence" && n !== "qualifier" && n !== "value") return pe.errors = [{
						instancePath: t,
						schemaPath: "#/additionalProperties",
						keyword: "additionalProperties",
						params: { additionalProperty: n }
					}], !1;
					if (r === c) {
						if (e.evidence !== void 0 && n.call(e, "evidence")) {
							let n = e.evidence, r = c;
							if (c === r) {
								if (Array.isArray(n)) {
									if (n.length > 20) return pe.errors = [{
										instancePath: t + "/evidence",
										schemaPath: "#/properties/evidence/maxItems",
										keyword: "maxItems",
										params: { limit: 20 }
									}], !1;
									if (n.length < 1) return pe.errors = [{
										instancePath: t + "/evidence",
										schemaPath: "#/properties/evidence/minItems",
										keyword: "minItems",
										params: { limit: 1 }
									}], !1;
									{
										let e = n.length;
										for (let r = 0; r < e; r++) {
											let e = c;
											if (b(n[r], {
												instancePath: t + "/evidence/" + r,
												parentData: n,
												parentDataProperty: r,
												rootData: a,
												dynamicAnchors: o
											}) || (s = s === null ? b.errors : s.concat(b.errors), c = s.length), e !== c) break;
										}
									}
								} else return pe.errors = [{
									instancePath: t + "/evidence",
									schemaPath: "#/properties/evidence/type",
									keyword: "type",
									params: { type: "array" }
								}], !1;
							}
							var u = r === c;
						} else var u = !0;
						if (u) {
							if (e.qualifier !== void 0 && n.call(e, "qualifier")) {
								let n = e.qualifier, r = c;
								if (typeof n != "string") return pe.errors = [{
									instancePath: t + "/qualifier",
									schemaPath: "#/properties/qualifier/type",
									keyword: "type",
									params: { type: "string" }
								}], !1;
								if (n !== "exact" && n !== "approximate" && n !== "at_least" && n !== "at_most") return pe.errors = [{
									instancePath: t + "/qualifier",
									schemaPath: "#/properties/qualifier/enum",
									keyword: "enum",
									params: { allowedValues: fe.properties.qualifier.enum }
								}], !1;
								var u = r === c;
							} else var u = !0;
							if (u) {
								if (e.value !== void 0 && n.call(e, "value")) {
									let n = c;
									ue(e.value, {
										instancePath: t + "/value",
										parentData: e,
										parentDataProperty: "value",
										rootData: a,
										dynamicAnchors: o
									}) || (s = s === null ? ue.errors : s.concat(ue.errors), c = s.length);
									var u = n === c;
								} else var u = !0;
							}
						}
					}
				}
			} else return pe.errors = [{
				instancePath: t,
				schemaPath: "#/type",
				keyword: "type",
				params: { type: "object" }
			}], !1;
		}
		return pe.errors = s, c === 0;
	}
	pe.evaluated = {
		props: !0,
		dynamicProps: !1,
		dynamicItems: !1
	};
	function me(e, { instancePath: t = "", parentData: r, parentDataProperty: i, rootData: a = e, dynamicAnchors: o = {} } = {}) {
		let s = null, c = 0, l = me.evaluated;
		if (l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0) {
			if (e && typeof e == "object" && !Array.isArray(e)) {
				let r;
				if ((e.status === void 0 || !n.call(e, "status")) && (r = "status") || (e.claims === void 0 || !n.call(e, "claims")) && (r = "claims")) return me.errors = [{
					instancePath: t,
					schemaPath: "#/required",
					keyword: "required",
					params: { missingProperty: r }
				}], !1;
				{
					let r = c;
					for (let n of Object.keys(e)) if (n !== "claims" && n !== "status") return me.errors = [{
						instancePath: t,
						schemaPath: "#/additionalProperties",
						keyword: "additionalProperties",
						params: { additionalProperty: n }
					}], !1;
					if (r === c) {
						if (e.claims !== void 0 && n.call(e, "claims")) {
							let n = e.claims, r = c;
							if (c === r) {
								if (Array.isArray(n)) {
									if (n.length > 20) return me.errors = [{
										instancePath: t + "/claims",
										schemaPath: "#/properties/claims/maxItems",
										keyword: "maxItems",
										params: { limit: 20 }
									}], !1;
									if (n.length < 2) return me.errors = [{
										instancePath: t + "/claims",
										schemaPath: "#/properties/claims/minItems",
										keyword: "minItems",
										params: { limit: 2 }
									}], !1;
									{
										let e = n.length;
										for (let r = 0; r < e; r++) {
											let e = c;
											if (pe(n[r], {
												instancePath: t + "/claims/" + r,
												parentData: n,
												parentDataProperty: r,
												rootData: a,
												dynamicAnchors: o
											}) || (s = s === null ? pe.errors : s.concat(pe.errors), c = s.length), e !== c) break;
										}
									}
								} else return me.errors = [{
									instancePath: t + "/claims",
									schemaPath: "#/properties/claims/type",
									keyword: "type",
									params: { type: "array" }
								}], !1;
							}
							var u = r === c;
						} else var u = !0;
						if (u) {
							if (e.status !== void 0 && n.call(e, "status")) {
								let n = e.status, r = c;
								if (typeof n != "string") return me.errors = [{
									instancePath: t + "/status",
									schemaPath: "#/properties/status/type",
									keyword: "type",
									params: { type: "string" }
								}], !1;
								if (n !== "conflicting") return me.errors = [{
									instancePath: t + "/status",
									schemaPath: "#/properties/status/const",
									keyword: "const",
									params: { allowedValue: "conflicting" }
								}], !1;
								var u = r === c;
							} else var u = !0;
						}
					}
				}
			} else return me.errors = [{
				instancePath: t,
				schemaPath: "#/type",
				keyword: "type",
				params: { type: "object" }
			}], !1;
		}
		return me.errors = s, c === 0;
	}
	me.evaluated = {
		props: !0,
		dynamicProps: !1,
		dynamicItems: !1
	};
	var he = {
		additionalProperties: !1,
		properties: {
			evidence: {
				items: { $ref: "urn:car-shopping-assistant:contract:1#/$defs/SourceLocator" },
				maxItems: 20,
				minItems: 1,
				title: "Evidence",
				type: "array"
			},
			qualifier: {
				default: "exact",
				enum: [
					"exact",
					"approximate",
					"at_least",
					"at_most"
				],
				title: "Qualifier",
				type: "string"
			},
			status: {
				const: "known",
				title: "Status",
				type: "string"
			},
			value: {
				title: "Value",
				type: "integer"
			}
		},
		required: [
			"status",
			"value",
			"evidence"
		],
		title: "KnownFact[Annotated[int, Strict(strict=True)]]",
		type: "object"
	};
	function ge(e, { instancePath: t = "", parentData: r, parentDataProperty: i, rootData: a = e, dynamicAnchors: o = {} } = {}) {
		let s = null, c = 0, l = ge.evaluated;
		if (l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0) {
			if (e && typeof e == "object" && !Array.isArray(e)) {
				let r;
				if ((e.status === void 0 || !n.call(e, "status")) && (r = "status") || (e.value === void 0 || !n.call(e, "value")) && (r = "value") || (e.evidence === void 0 || !n.call(e, "evidence")) && (r = "evidence")) return ge.errors = [{
					instancePath: t,
					schemaPath: "#/required",
					keyword: "required",
					params: { missingProperty: r }
				}], !1;
				{
					let r = c;
					for (let n of Object.keys(e)) if (n !== "evidence" && n !== "qualifier" && n !== "status" && n !== "value") return ge.errors = [{
						instancePath: t,
						schemaPath: "#/additionalProperties",
						keyword: "additionalProperties",
						params: { additionalProperty: n }
					}], !1;
					if (r === c) {
						if (e.evidence !== void 0 && n.call(e, "evidence")) {
							let n = e.evidence, r = c;
							if (c === r) {
								if (Array.isArray(n)) {
									if (n.length > 20) return ge.errors = [{
										instancePath: t + "/evidence",
										schemaPath: "#/properties/evidence/maxItems",
										keyword: "maxItems",
										params: { limit: 20 }
									}], !1;
									if (n.length < 1) return ge.errors = [{
										instancePath: t + "/evidence",
										schemaPath: "#/properties/evidence/minItems",
										keyword: "minItems",
										params: { limit: 1 }
									}], !1;
									{
										let e = n.length;
										for (let r = 0; r < e; r++) {
											let e = c;
											if (b(n[r], {
												instancePath: t + "/evidence/" + r,
												parentData: n,
												parentDataProperty: r,
												rootData: a,
												dynamicAnchors: o
											}) || (s = s === null ? b.errors : s.concat(b.errors), c = s.length), e !== c) break;
										}
									}
								} else return ge.errors = [{
									instancePath: t + "/evidence",
									schemaPath: "#/properties/evidence/type",
									keyword: "type",
									params: { type: "array" }
								}], !1;
							}
							var u = r === c;
						} else var u = !0;
						if (u) {
							if (e.qualifier !== void 0 && n.call(e, "qualifier")) {
								let n = e.qualifier, r = c;
								if (typeof n != "string") return ge.errors = [{
									instancePath: t + "/qualifier",
									schemaPath: "#/properties/qualifier/type",
									keyword: "type",
									params: { type: "string" }
								}], !1;
								if (n !== "exact" && n !== "approximate" && n !== "at_least" && n !== "at_most") return ge.errors = [{
									instancePath: t + "/qualifier",
									schemaPath: "#/properties/qualifier/enum",
									keyword: "enum",
									params: { allowedValues: he.properties.qualifier.enum }
								}], !1;
								var u = r === c;
							} else var u = !0;
							if (u) {
								if (e.status !== void 0 && n.call(e, "status")) {
									let n = e.status, r = c;
									if (typeof n != "string") return ge.errors = [{
										instancePath: t + "/status",
										schemaPath: "#/properties/status/type",
										keyword: "type",
										params: { type: "string" }
									}], !1;
									if (n !== "known") return ge.errors = [{
										instancePath: t + "/status",
										schemaPath: "#/properties/status/const",
										keyword: "const",
										params: { allowedValue: "known" }
									}], !1;
									var u = r === c;
								} else var u = !0;
								if (u) {
									if (e.value !== void 0 && n.call(e, "value")) {
										let n = e.value, r = c;
										if (typeof n != "number" || n % 1 || isNaN(n) || !isFinite(n)) return ge.errors = [{
											instancePath: t + "/value",
											schemaPath: "#/properties/value/type",
											keyword: "type",
											params: { type: "integer" }
										}], !1;
										var u = r === c;
									} else var u = !0;
								}
							}
						}
					}
				}
			} else return ge.errors = [{
				instancePath: t,
				schemaPath: "#/type",
				keyword: "type",
				params: { type: "object" }
			}], !1;
		}
		return ge.errors = s, c === 0;
	}
	ge.evaluated = {
		props: !0,
		dynamicProps: !1,
		dynamicItems: !1
	};
	var _e = {
		additionalProperties: !1,
		properties: {
			evidence: {
				items: { $ref: "urn:car-shopping-assistant:contract:1#/$defs/SourceLocator" },
				maxItems: 20,
				minItems: 1,
				title: "Evidence",
				type: "array"
			},
			qualifier: {
				default: "exact",
				enum: [
					"exact",
					"approximate",
					"at_least",
					"at_most"
				],
				title: "Qualifier",
				type: "string"
			},
			value: {
				title: "Value",
				type: "integer"
			}
		},
		required: ["value", "evidence"],
		title: "FactClaim[Annotated[int, Strict(strict=True)]]",
		type: "object"
	};
	function ve(e, { instancePath: t = "", parentData: r, parentDataProperty: i, rootData: a = e, dynamicAnchors: o = {} } = {}) {
		let s = null, c = 0, l = ve.evaluated;
		if (l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0) {
			if (e && typeof e == "object" && !Array.isArray(e)) {
				let r;
				if ((e.value === void 0 || !n.call(e, "value")) && (r = "value") || (e.evidence === void 0 || !n.call(e, "evidence")) && (r = "evidence")) return ve.errors = [{
					instancePath: t,
					schemaPath: "#/required",
					keyword: "required",
					params: { missingProperty: r }
				}], !1;
				{
					let r = c;
					for (let n of Object.keys(e)) if (n !== "evidence" && n !== "qualifier" && n !== "value") return ve.errors = [{
						instancePath: t,
						schemaPath: "#/additionalProperties",
						keyword: "additionalProperties",
						params: { additionalProperty: n }
					}], !1;
					if (r === c) {
						if (e.evidence !== void 0 && n.call(e, "evidence")) {
							let n = e.evidence, r = c;
							if (c === r) {
								if (Array.isArray(n)) {
									if (n.length > 20) return ve.errors = [{
										instancePath: t + "/evidence",
										schemaPath: "#/properties/evidence/maxItems",
										keyword: "maxItems",
										params: { limit: 20 }
									}], !1;
									if (n.length < 1) return ve.errors = [{
										instancePath: t + "/evidence",
										schemaPath: "#/properties/evidence/minItems",
										keyword: "minItems",
										params: { limit: 1 }
									}], !1;
									{
										let e = n.length;
										for (let r = 0; r < e; r++) {
											let e = c;
											if (b(n[r], {
												instancePath: t + "/evidence/" + r,
												parentData: n,
												parentDataProperty: r,
												rootData: a,
												dynamicAnchors: o
											}) || (s = s === null ? b.errors : s.concat(b.errors), c = s.length), e !== c) break;
										}
									}
								} else return ve.errors = [{
									instancePath: t + "/evidence",
									schemaPath: "#/properties/evidence/type",
									keyword: "type",
									params: { type: "array" }
								}], !1;
							}
							var u = r === c;
						} else var u = !0;
						if (u) {
							if (e.qualifier !== void 0 && n.call(e, "qualifier")) {
								let n = e.qualifier, r = c;
								if (typeof n != "string") return ve.errors = [{
									instancePath: t + "/qualifier",
									schemaPath: "#/properties/qualifier/type",
									keyword: "type",
									params: { type: "string" }
								}], !1;
								if (n !== "exact" && n !== "approximate" && n !== "at_least" && n !== "at_most") return ve.errors = [{
									instancePath: t + "/qualifier",
									schemaPath: "#/properties/qualifier/enum",
									keyword: "enum",
									params: { allowedValues: _e.properties.qualifier.enum }
								}], !1;
								var u = r === c;
							} else var u = !0;
							if (u) {
								if (e.value !== void 0 && n.call(e, "value")) {
									let n = e.value, r = c;
									if (typeof n != "number" || n % 1 || isNaN(n) || !isFinite(n)) return ve.errors = [{
										instancePath: t + "/value",
										schemaPath: "#/properties/value/type",
										keyword: "type",
										params: { type: "integer" }
									}], !1;
									var u = r === c;
								} else var u = !0;
							}
						}
					}
				}
			} else return ve.errors = [{
				instancePath: t,
				schemaPath: "#/type",
				keyword: "type",
				params: { type: "object" }
			}], !1;
		}
		return ve.errors = s, c === 0;
	}
	ve.evaluated = {
		props: !0,
		dynamicProps: !1,
		dynamicItems: !1
	};
	function ye(e, { instancePath: t = "", parentData: r, parentDataProperty: i, rootData: a = e, dynamicAnchors: o = {} } = {}) {
		let s = null, c = 0, l = ye.evaluated;
		if (l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0) {
			if (e && typeof e == "object" && !Array.isArray(e)) {
				let r;
				if ((e.status === void 0 || !n.call(e, "status")) && (r = "status") || (e.claims === void 0 || !n.call(e, "claims")) && (r = "claims")) return ye.errors = [{
					instancePath: t,
					schemaPath: "#/required",
					keyword: "required",
					params: { missingProperty: r }
				}], !1;
				{
					let r = c;
					for (let n of Object.keys(e)) if (n !== "claims" && n !== "status") return ye.errors = [{
						instancePath: t,
						schemaPath: "#/additionalProperties",
						keyword: "additionalProperties",
						params: { additionalProperty: n }
					}], !1;
					if (r === c) {
						if (e.claims !== void 0 && n.call(e, "claims")) {
							let n = e.claims, r = c;
							if (c === r) {
								if (Array.isArray(n)) {
									if (n.length > 20) return ye.errors = [{
										instancePath: t + "/claims",
										schemaPath: "#/properties/claims/maxItems",
										keyword: "maxItems",
										params: { limit: 20 }
									}], !1;
									if (n.length < 2) return ye.errors = [{
										instancePath: t + "/claims",
										schemaPath: "#/properties/claims/minItems",
										keyword: "minItems",
										params: { limit: 2 }
									}], !1;
									{
										let e = n.length;
										for (let r = 0; r < e; r++) {
											let e = c;
											if (ve(n[r], {
												instancePath: t + "/claims/" + r,
												parentData: n,
												parentDataProperty: r,
												rootData: a,
												dynamicAnchors: o
											}) || (s = s === null ? ve.errors : s.concat(ve.errors), c = s.length), e !== c) break;
										}
									}
								} else return ye.errors = [{
									instancePath: t + "/claims",
									schemaPath: "#/properties/claims/type",
									keyword: "type",
									params: { type: "array" }
								}], !1;
							}
							var u = r === c;
						} else var u = !0;
						if (u) {
							if (e.status !== void 0 && n.call(e, "status")) {
								let n = e.status, r = c;
								if (typeof n != "string") return ye.errors = [{
									instancePath: t + "/status",
									schemaPath: "#/properties/status/type",
									keyword: "type",
									params: { type: "string" }
								}], !1;
								if (n !== "conflicting") return ye.errors = [{
									instancePath: t + "/status",
									schemaPath: "#/properties/status/const",
									keyword: "const",
									params: { allowedValue: "conflicting" }
								}], !1;
								var u = r === c;
							} else var u = !0;
						}
					}
				}
			} else return ye.errors = [{
				instancePath: t,
				schemaPath: "#/type",
				keyword: "type",
				params: { type: "object" }
			}], !1;
		}
		return ye.errors = s, c === 0;
	}
	ye.evaluated = {
		props: !0,
		dynamicProps: !1,
		dynamicItems: !1
	};
	var be = {
		additionalProperties: !1,
		properties: {
			alt: {
				maxLength: 300,
				title: "Alt",
				type: "string"
			},
			source: {
				const: "supplied_listing",
				default: "supplied_listing",
				title: "Source",
				type: "string"
			},
			state: {
				enum: [
					"source_present",
					"missing",
					"blocked",
					"unverified"
				],
				title: "State",
				type: "string"
			},
			url: {
				anyOf: [{
					maxLength: 2048,
					type: "string"
				}, { type: "null" }],
				title: "Url"
			}
		},
		required: [
			"state",
			"url",
			"alt"
		],
		title: "ListingPhoto",
		type: "object"
	};
	function xe(e, { instancePath: t = "", parentData: r, parentDataProperty: i, rootData: a = e, dynamicAnchors: o = {} } = {}) {
		let s = null, c = 0, l = xe.evaluated;
		if (l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0) {
			if (e && typeof e == "object" && !Array.isArray(e)) {
				let r;
				if ((e.state === void 0 || !n.call(e, "state")) && (r = "state") || (e.url === void 0 || !n.call(e, "url")) && (r = "url") || (e.alt === void 0 || !n.call(e, "alt")) && (r = "alt")) return xe.errors = [{
					instancePath: t,
					schemaPath: "#/required",
					keyword: "required",
					params: { missingProperty: r }
				}], !1;
				{
					let r = c;
					for (let n of Object.keys(e)) if (n !== "alt" && n !== "source" && n !== "state" && n !== "url") return xe.errors = [{
						instancePath: t,
						schemaPath: "#/additionalProperties",
						keyword: "additionalProperties",
						params: { additionalProperty: n }
					}], !1;
					if (r === c) {
						if (e.alt !== void 0 && n.call(e, "alt")) {
							let n = e.alt, r = c;
							if (c === r) {
								if (typeof n == "string") {
									if (h(n) > 300) return xe.errors = [{
										instancePath: t + "/alt",
										schemaPath: "#/properties/alt/maxLength",
										keyword: "maxLength",
										params: { limit: 300 }
									}], !1;
								} else return xe.errors = [{
									instancePath: t + "/alt",
									schemaPath: "#/properties/alt/type",
									keyword: "type",
									params: { type: "string" }
								}], !1;
							}
							var u = r === c;
						} else var u = !0;
						if (u) {
							if (e.source !== void 0 && n.call(e, "source")) {
								let n = e.source, r = c;
								if (typeof n != "string") return xe.errors = [{
									instancePath: t + "/source",
									schemaPath: "#/properties/source/type",
									keyword: "type",
									params: { type: "string" }
								}], !1;
								if (n !== "supplied_listing") return xe.errors = [{
									instancePath: t + "/source",
									schemaPath: "#/properties/source/const",
									keyword: "const",
									params: { allowedValue: "supplied_listing" }
								}], !1;
								var u = r === c;
							} else var u = !0;
							if (u) {
								if (e.state !== void 0 && n.call(e, "state")) {
									let n = e.state, r = c;
									if (typeof n != "string") return xe.errors = [{
										instancePath: t + "/state",
										schemaPath: "#/properties/state/type",
										keyword: "type",
										params: { type: "string" }
									}], !1;
									if (n !== "source_present" && n !== "missing" && n !== "blocked" && n !== "unverified") return xe.errors = [{
										instancePath: t + "/state",
										schemaPath: "#/properties/state/enum",
										keyword: "enum",
										params: { allowedValues: be.properties.state.enum }
									}], !1;
									var u = r === c;
								} else var u = !0;
								if (u) {
									if (e.url !== void 0 && n.call(e, "url")) {
										let n = e.url, r = c, i = c, a = !1, o = c;
										if (c === o) {
											if (typeof n == "string") {
												if (h(n) > 2048) {
													let e = {
														instancePath: t + "/url",
														schemaPath: "#/properties/url/anyOf/0/maxLength",
														keyword: "maxLength",
														params: { limit: 2048 }
													};
													s === null ? s = [e] : s.push(e), c++;
												}
											} else {
												let e = {
													instancePath: t + "/url",
													schemaPath: "#/properties/url/anyOf/0/type",
													keyword: "type",
													params: { type: "string" }
												};
												s === null ? s = [e] : s.push(e), c++;
											}
										}
										var d = o === c;
										a ||= d;
										let l = c;
										if (n !== null) {
											let e = {
												instancePath: t + "/url",
												schemaPath: "#/properties/url/anyOf/1/type",
												keyword: "type",
												params: { type: "null" }
											};
											s === null ? s = [e] : s.push(e), c++;
										}
										var d = l === c;
										if (a ||= d, a) c = i, s !== null && (i ? s.length = i : s = null);
										else {
											let e = {
												instancePath: t + "/url",
												schemaPath: "#/properties/url/anyOf",
												keyword: "anyOf",
												params: {}
											};
											return s === null ? s = [e] : s.push(e), c++, xe.errors = s, !1;
										}
										var u = r === c;
									} else var u = !0;
								}
							}
						}
					}
				}
			} else return xe.errors = [{
				instancePath: t,
				schemaPath: "#/type",
				keyword: "type",
				params: { type: "object" }
			}], !1;
		}
		return xe.errors = s, c === 0;
	}
	xe.evaluated = {
		props: !0,
		dynamicProps: !1,
		dynamicItems: !1
	};
	function w(e, { instancePath: t = "", parentData: r, parentDataProperty: i, rootData: a = e, dynamicAnchors: o = {} } = {}) {
		let s = null, c = 0, u = w.evaluated;
		if (u.dynamicProps && (u.props = void 0), u.dynamicItems && (u.items = void 0), c === 0) {
			if (e && typeof e == "object" && !Array.isArray(e)) {
				let r;
				if ((e.ref === void 0 || !n.call(e, "ref")) && (r = "ref") || (e.title === void 0 || !n.call(e, "title")) && (r = "title") || (e.make === void 0 || !n.call(e, "make")) && (r = "make") || (e.model === void 0 || !n.call(e, "model")) && (r = "model") || (e.trim === void 0 || !n.call(e, "trim")) && (r = "trim") || (e.year === void 0 || !n.call(e, "year")) && (r = "year") || (e.cash_price === void 0 || !n.call(e, "cash_price")) && (r = "cash_price") || (e.mileage_km === void 0 || !n.call(e, "mileage_km")) && (r = "mileage_km") || (e.photo === void 0 || !n.call(e, "photo")) && (r = "photo")) return w.errors = [{
					instancePath: t,
					schemaPath: "#/required",
					keyword: "required",
					params: { missingProperty: r }
				}], !1;
				{
					let r = c;
					for (let r of Object.keys(e)) if (!n.call(se.properties, r)) return w.errors = [{
						instancePath: t,
						schemaPath: "#/additionalProperties",
						keyword: "additionalProperties",
						params: { additionalProperty: r }
					}], !1;
					if (r === c) {
						if (e.cash_price !== void 0 && n.call(e, "cash_price")) {
							let r = e.cash_price, i = c;
							if (c === i) {
								if (r && typeof r == "object" && !Array.isArray(r)) {
									let i;
									if ((r.status === void 0 || !n.call(r, "status")) && (i = "status")) return w.errors = [{
										instancePath: t + "/cash_price",
										schemaPath: "#/properties/cash_price/required",
										keyword: "required",
										params: { missingProperty: i }
									}], !1;
									if (r.status !== void 0 && n.call(r, "status")) {
										let e = c;
										if (typeof r.status != "string") return w.errors = [{
											instancePath: t + "/cash_price/status",
											schemaPath: "#/properties/cash_price/properties/status/type",
											keyword: "type",
											params: { type: "string" }
										}], !1;
										var d = e === c;
									} else var d = !0;
									if (d) {
										let n = r.status;
										if (typeof n == "string") {
											if (n === "known") {
												de(r, {
													instancePath: t + "/cash_price",
													parentData: e,
													parentDataProperty: "cash_price",
													rootData: a,
													dynamicAnchors: o
												}) || (s = s === null ? de.errors : s.concat(de.errors), c = s.length);
												var f = !0;
											} else if (n === "unknown") S(r, {
												instancePath: t + "/cash_price",
												parentData: e,
												parentDataProperty: "cash_price",
												rootData: a,
												dynamicAnchors: o
											}) || (s = s === null ? S.errors : s.concat(S.errors), c = s.length), f !== !0 && (f = !0);
											else if (n === "conflicting") me(r, {
												instancePath: t + "/cash_price",
												parentData: e,
												parentDataProperty: "cash_price",
												rootData: a,
												dynamicAnchors: o
											}) || (s = s === null ? me.errors : s.concat(me.errors), c = s.length), f !== !0 && (f = !0);
											else return w.errors = [{
												instancePath: t + "/cash_price",
												schemaPath: "#/properties/cash_price/discriminator",
												keyword: "discriminator",
												params: {
													error: "mapping",
													tag: "status",
													tagValue: n
												}
											}], !1;
										} else return w.errors = [{
											instancePath: t + "/cash_price",
											schemaPath: "#/properties/cash_price/discriminator",
											keyword: "discriminator",
											params: {
												error: "tag",
												tag: "status",
												tagValue: n
											}
										}], !1;
									}
								} else return w.errors = [{
									instancePath: t + "/cash_price",
									schemaPath: "#/properties/cash_price/type",
									keyword: "type",
									params: { type: "object" }
								}], !1;
							}
							var p = i === c;
						} else var p = !0;
						if (p) {
							if (e.evidence_warnings !== void 0 && n.call(e, "evidence_warnings")) {
								let n = e.evidence_warnings, r = c;
								if (c === r) {
									if (Array.isArray(n)) {
										if (n.length > 24) return w.errors = [{
											instancePath: t + "/evidence_warnings",
											schemaPath: "#/properties/evidence_warnings/maxItems",
											keyword: "maxItems",
											params: { limit: 24 }
										}], !1;
										{
											let e = n.length;
											for (let r = 0; r < e; r++) {
												let e = n[r], i = c;
												if (c === i) {
													if (typeof e == "string") {
														if (h(e) > 200) return w.errors = [{
															instancePath: t + "/evidence_warnings/" + r,
															schemaPath: "#/properties/evidence_warnings/items/maxLength",
															keyword: "maxLength",
															params: { limit: 200 }
														}], !1;
														if (h(e) < 1) return w.errors = [{
															instancePath: t + "/evidence_warnings/" + r,
															schemaPath: "#/properties/evidence_warnings/items/minLength",
															keyword: "minLength",
															params: { limit: 1 }
														}], !1;
													} else return w.errors = [{
														instancePath: t + "/evidence_warnings/" + r,
														schemaPath: "#/properties/evidence_warnings/items/type",
														keyword: "type",
														params: { type: "string" }
													}], !1;
												}
												if (i !== c) break;
											}
										}
									} else return w.errors = [{
										instancePath: t + "/evidence_warnings",
										schemaPath: "#/properties/evidence_warnings/type",
										keyword: "type",
										params: { type: "array" }
									}], !1;
								}
								var p = r === c;
							} else var p = !0;
							if (p) {
								if (e.make !== void 0 && n.call(e, "make")) {
									let r = e.make, i = c;
									if (c === i) {
										if (r && typeof r == "object" && !Array.isArray(r)) {
											let i;
											if ((r.status === void 0 || !n.call(r, "status")) && (i = "status")) return w.errors = [{
												instancePath: t + "/make",
												schemaPath: "#/properties/make/required",
												keyword: "required",
												params: { missingProperty: i }
											}], !1;
											if (r.status !== void 0 && n.call(r, "status")) {
												let e = c;
												if (typeof r.status != "string") return w.errors = [{
													instancePath: t + "/make/status",
													schemaPath: "#/properties/make/properties/status/type",
													keyword: "type",
													params: { type: "string" }
												}], !1;
												var m = e === c;
											} else var m = !0;
											if (m) {
												let n = r.status;
												if (typeof n == "string") {
													if (n === "known") {
														x(r, {
															instancePath: t + "/make",
															parentData: e,
															parentDataProperty: "make",
															rootData: a,
															dynamicAnchors: o
														}) || (s = s === null ? x.errors : s.concat(x.errors), c = s.length);
														var g = !0;
													} else if (n === "unknown") S(r, {
														instancePath: t + "/make",
														parentData: e,
														parentDataProperty: "make",
														rootData: a,
														dynamicAnchors: o
													}) || (s = s === null ? S.errors : s.concat(S.errors), c = s.length), g !== !0 && (g = !0);
													else if (n === "conflicting") C(r, {
														instancePath: t + "/make",
														parentData: e,
														parentDataProperty: "make",
														rootData: a,
														dynamicAnchors: o
													}) || (s = s === null ? C.errors : s.concat(C.errors), c = s.length), g !== !0 && (g = !0);
													else return w.errors = [{
														instancePath: t + "/make",
														schemaPath: "#/properties/make/discriminator",
														keyword: "discriminator",
														params: {
															error: "mapping",
															tag: "status",
															tagValue: n
														}
													}], !1;
												} else return w.errors = [{
													instancePath: t + "/make",
													schemaPath: "#/properties/make/discriminator",
													keyword: "discriminator",
													params: {
														error: "tag",
														tag: "status",
														tagValue: n
													}
												}], !1;
											}
										} else return w.errors = [{
											instancePath: t + "/make",
											schemaPath: "#/properties/make/type",
											keyword: "type",
											params: { type: "object" }
										}], !1;
									}
									var p = i === c;
								} else var p = !0;
								if (p) {
									if (e.mileage_km !== void 0 && n.call(e, "mileage_km")) {
										let r = e.mileage_km, i = c;
										if (c === i) {
											if (r && typeof r == "object" && !Array.isArray(r)) {
												let i;
												if ((r.status === void 0 || !n.call(r, "status")) && (i = "status")) return w.errors = [{
													instancePath: t + "/mileage_km",
													schemaPath: "#/properties/mileage_km/required",
													keyword: "required",
													params: { missingProperty: i }
												}], !1;
												if (r.status !== void 0 && n.call(r, "status")) {
													let e = c;
													if (typeof r.status != "string") return w.errors = [{
														instancePath: t + "/mileage_km/status",
														schemaPath: "#/properties/mileage_km/properties/status/type",
														keyword: "type",
														params: { type: "string" }
													}], !1;
													var _ = e === c;
												} else var _ = !0;
												if (_) {
													let n = r.status;
													if (typeof n == "string") {
														if (n === "known") {
															ge(r, {
																instancePath: t + "/mileage_km",
																parentData: e,
																parentDataProperty: "mileage_km",
																rootData: a,
																dynamicAnchors: o
															}) || (s = s === null ? ge.errors : s.concat(ge.errors), c = s.length);
															var v = !0;
														} else if (n === "unknown") S(r, {
															instancePath: t + "/mileage_km",
															parentData: e,
															parentDataProperty: "mileage_km",
															rootData: a,
															dynamicAnchors: o
														}) || (s = s === null ? S.errors : s.concat(S.errors), c = s.length), v !== !0 && (v = !0);
														else if (n === "conflicting") ye(r, {
															instancePath: t + "/mileage_km",
															parentData: e,
															parentDataProperty: "mileage_km",
															rootData: a,
															dynamicAnchors: o
														}) || (s = s === null ? ye.errors : s.concat(ye.errors), c = s.length), v !== !0 && (v = !0);
														else return w.errors = [{
															instancePath: t + "/mileage_km",
															schemaPath: "#/properties/mileage_km/discriminator",
															keyword: "discriminator",
															params: {
																error: "mapping",
																tag: "status",
																tagValue: n
															}
														}], !1;
													} else return w.errors = [{
														instancePath: t + "/mileage_km",
														schemaPath: "#/properties/mileage_km/discriminator",
														keyword: "discriminator",
														params: {
															error: "tag",
															tag: "status",
															tagValue: n
														}
													}], !1;
												}
											} else return w.errors = [{
												instancePath: t + "/mileage_km",
												schemaPath: "#/properties/mileage_km/type",
												keyword: "type",
												params: { type: "object" }
											}], !1;
										}
										var p = i === c;
									} else var p = !0;
									if (p) {
										if (e.model !== void 0 && n.call(e, "model")) {
											let r = e.model, i = c;
											if (c === i) {
												if (r && typeof r == "object" && !Array.isArray(r)) {
													let i;
													if ((r.status === void 0 || !n.call(r, "status")) && (i = "status")) return w.errors = [{
														instancePath: t + "/model",
														schemaPath: "#/properties/model/required",
														keyword: "required",
														params: { missingProperty: i }
													}], !1;
													if (r.status !== void 0 && n.call(r, "status")) {
														let e = c;
														if (typeof r.status != "string") return w.errors = [{
															instancePath: t + "/model/status",
															schemaPath: "#/properties/model/properties/status/type",
															keyword: "type",
															params: { type: "string" }
														}], !1;
														var y = e === c;
													} else var y = !0;
													if (y) {
														let n = r.status;
														if (typeof n == "string") {
															if (n === "known") {
																x(r, {
																	instancePath: t + "/model",
																	parentData: e,
																	parentDataProperty: "model",
																	rootData: a,
																	dynamicAnchors: o
																}) || (s = s === null ? x.errors : s.concat(x.errors), c = s.length);
																var ee = !0;
															} else if (n === "unknown") S(r, {
																instancePath: t + "/model",
																parentData: e,
																parentDataProperty: "model",
																rootData: a,
																dynamicAnchors: o
															}) || (s = s === null ? S.errors : s.concat(S.errors), c = s.length), ee !== !0 && (ee = !0);
															else if (n === "conflicting") C(r, {
																instancePath: t + "/model",
																parentData: e,
																parentDataProperty: "model",
																rootData: a,
																dynamicAnchors: o
															}) || (s = s === null ? C.errors : s.concat(C.errors), c = s.length), ee !== !0 && (ee = !0);
															else return w.errors = [{
																instancePath: t + "/model",
																schemaPath: "#/properties/model/discriminator",
																keyword: "discriminator",
																params: {
																	error: "mapping",
																	tag: "status",
																	tagValue: n
																}
															}], !1;
														} else return w.errors = [{
															instancePath: t + "/model",
															schemaPath: "#/properties/model/discriminator",
															keyword: "discriminator",
															params: {
																error: "tag",
																tag: "status",
																tagValue: n
															}
														}], !1;
													}
												} else return w.errors = [{
													instancePath: t + "/model",
													schemaPath: "#/properties/model/type",
													keyword: "type",
													params: { type: "object" }
												}], !1;
											}
											var p = i === c;
										} else var p = !0;
										if (p) {
											if (e.photo !== void 0 && n.call(e, "photo")) {
												let n = c;
												xe(e.photo, {
													instancePath: t + "/photo",
													parentData: e,
													parentDataProperty: "photo",
													rootData: a,
													dynamicAnchors: o
												}) || (s = s === null ? xe.errors : s.concat(xe.errors), c = s.length);
												var p = n === c;
											} else var p = !0;
											if (p) {
												if (e.ref !== void 0 && n.call(e, "ref")) {
													let n = c;
													l(e.ref, {
														instancePath: t + "/ref",
														parentData: e,
														parentDataProperty: "ref",
														rootData: a,
														dynamicAnchors: o
													}) || (s = s === null ? l.errors : s.concat(l.errors), c = s.length);
													var p = n === c;
												} else var p = !0;
												if (p) {
													if (e.title !== void 0 && n.call(e, "title")) {
														let n = e.title, r = c;
														if (c === r) {
															if (typeof n == "string") {
																if (h(n) > 1e3) return w.errors = [{
																	instancePath: t + "/title",
																	schemaPath: "#/properties/title/maxLength",
																	keyword: "maxLength",
																	params: { limit: 1e3 }
																}], !1;
																if (h(n) < 1) return w.errors = [{
																	instancePath: t + "/title",
																	schemaPath: "#/properties/title/minLength",
																	keyword: "minLength",
																	params: { limit: 1 }
																}], !1;
															} else return w.errors = [{
																instancePath: t + "/title",
																schemaPath: "#/properties/title/type",
																keyword: "type",
																params: { type: "string" }
															}], !1;
														}
														var p = r === c;
													} else var p = !0;
													if (p) {
														if (e.trim !== void 0 && n.call(e, "trim")) {
															let r = e.trim, i = c;
															if (c === i) {
																if (r && typeof r == "object" && !Array.isArray(r)) {
																	let i;
																	if ((r.status === void 0 || !n.call(r, "status")) && (i = "status")) return w.errors = [{
																		instancePath: t + "/trim",
																		schemaPath: "#/properties/trim/required",
																		keyword: "required",
																		params: { missingProperty: i }
																	}], !1;
																	if (r.status !== void 0 && n.call(r, "status")) {
																		let e = c;
																		if (typeof r.status != "string") return w.errors = [{
																			instancePath: t + "/trim/status",
																			schemaPath: "#/properties/trim/properties/status/type",
																			keyword: "type",
																			params: { type: "string" }
																		}], !1;
																		var te = e === c;
																	} else var te = !0;
																	if (te) {
																		let n = r.status;
																		if (typeof n == "string") {
																			if (n === "known") {
																				x(r, {
																					instancePath: t + "/trim",
																					parentData: e,
																					parentDataProperty: "trim",
																					rootData: a,
																					dynamicAnchors: o
																				}) || (s = s === null ? x.errors : s.concat(x.errors), c = s.length);
																				var ne = !0;
																			} else if (n === "unknown") S(r, {
																				instancePath: t + "/trim",
																				parentData: e,
																				parentDataProperty: "trim",
																				rootData: a,
																				dynamicAnchors: o
																			}) || (s = s === null ? S.errors : s.concat(S.errors), c = s.length), ne !== !0 && (ne = !0);
																			else if (n === "conflicting") C(r, {
																				instancePath: t + "/trim",
																				parentData: e,
																				parentDataProperty: "trim",
																				rootData: a,
																				dynamicAnchors: o
																			}) || (s = s === null ? C.errors : s.concat(C.errors), c = s.length), ne !== !0 && (ne = !0);
																			else return w.errors = [{
																				instancePath: t + "/trim",
																				schemaPath: "#/properties/trim/discriminator",
																				keyword: "discriminator",
																				params: {
																					error: "mapping",
																					tag: "status",
																					tagValue: n
																				}
																			}], !1;
																		} else return w.errors = [{
																			instancePath: t + "/trim",
																			schemaPath: "#/properties/trim/discriminator",
																			keyword: "discriminator",
																			params: {
																				error: "tag",
																				tag: "status",
																				tagValue: n
																			}
																		}], !1;
																	}
																} else return w.errors = [{
																	instancePath: t + "/trim",
																	schemaPath: "#/properties/trim/type",
																	keyword: "type",
																	params: { type: "object" }
																}], !1;
															}
															var p = i === c;
														} else var p = !0;
														if (p) {
															if (e.year !== void 0 && n.call(e, "year")) {
																let r = e.year, i = c;
																if (c === i) {
																	if (r && typeof r == "object" && !Array.isArray(r)) {
																		let i;
																		if ((r.status === void 0 || !n.call(r, "status")) && (i = "status")) return w.errors = [{
																			instancePath: t + "/year",
																			schemaPath: "#/properties/year/required",
																			keyword: "required",
																			params: { missingProperty: i }
																		}], !1;
																		if (r.status !== void 0 && n.call(r, "status")) {
																			let e = c;
																			if (typeof r.status != "string") return w.errors = [{
																				instancePath: t + "/year/status",
																				schemaPath: "#/properties/year/properties/status/type",
																				keyword: "type",
																				params: { type: "string" }
																			}], !1;
																			var re = e === c;
																		} else var re = !0;
																		if (re) {
																			let n = r.status;
																			if (typeof n == "string") {
																				if (n === "known") {
																					ge(r, {
																						instancePath: t + "/year",
																						parentData: e,
																						parentDataProperty: "year",
																						rootData: a,
																						dynamicAnchors: o
																					}) || (s = s === null ? ge.errors : s.concat(ge.errors), c = s.length);
																					var b = !0;
																				} else if (n === "unknown") S(r, {
																					instancePath: t + "/year",
																					parentData: e,
																					parentDataProperty: "year",
																					rootData: a,
																					dynamicAnchors: o
																				}) || (s = s === null ? S.errors : s.concat(S.errors), c = s.length), b !== !0 && (b = !0);
																				else if (n === "conflicting") ye(r, {
																					instancePath: t + "/year",
																					parentData: e,
																					parentDataProperty: "year",
																					rootData: a,
																					dynamicAnchors: o
																				}) || (s = s === null ? ye.errors : s.concat(ye.errors), c = s.length), b !== !0 && (b = !0);
																				else return w.errors = [{
																					instancePath: t + "/year",
																					schemaPath: "#/properties/year/discriminator",
																					keyword: "discriminator",
																					params: {
																						error: "mapping",
																						tag: "status",
																						tagValue: n
																					}
																				}], !1;
																			} else return w.errors = [{
																				instancePath: t + "/year",
																				schemaPath: "#/properties/year/discriminator",
																				keyword: "discriminator",
																				params: {
																					error: "tag",
																					tag: "status",
																					tagValue: n
																				}
																			}], !1;
																		}
																	} else return w.errors = [{
																		instancePath: t + "/year",
																		schemaPath: "#/properties/year/type",
																		keyword: "type",
																		params: { type: "object" }
																	}], !1;
																}
																var p = i === c;
															} else var p = !0;
														}
													}
												}
											}
										}
									}
								}
							}
						}
					}
				}
			} else return w.errors = [{
				instancePath: t,
				schemaPath: "#/type",
				keyword: "type",
				params: { type: "object" }
			}], !1;
		}
		return w.errors = s, c === 0;
	}
	w.evaluated = {
		props: !0,
		dynamicProps: !1,
		dynamicItems: !1
	};
	function T(e, { instancePath: t = "", parentData: r, parentDataProperty: i, rootData: a = e, dynamicAnchors: o = {} } = {}) {
		let s = null, c = 0, l = T.evaluated;
		if (l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0) {
			if (e && typeof e == "object" && !Array.isArray(e)) {
				let r;
				if ((e.state === void 0 || !n.call(e, "state")) && (r = "state") || (e.listing === void 0 || !n.call(e, "listing")) && (r = "listing") || (e.description === void 0 || !n.call(e, "description")) && (r = "description") || (e.fuel_type === void 0 || !n.call(e, "fuel_type")) && (r = "fuel_type") || (e.body_type === void 0 || !n.call(e, "body_type")) && (r = "body_type") || (e.transmission === void 0 || !n.call(e, "transmission")) && (r = "transmission") || (e.location === void 0 || !n.call(e, "location")) && (r = "location") || (e.warranty === void 0 || !n.call(e, "warranty")) && (r = "warranty") || (e.service_history === void 0 || !n.call(e, "service_history")) && (r = "service_history") || (e.eligibility === void 0 || !n.call(e, "eligibility")) && (r = "eligibility") || (e.eligibility_reason === void 0 || !n.call(e, "eligibility_reason")) && (r = "eligibility_reason")) return T.errors = [{
					instancePath: t,
					schemaPath: "#/required",
					keyword: "required",
					params: { missingProperty: r }
				}], !1;
				{
					let r = c;
					for (let r of Object.keys(e)) if (!n.call(te.properties, r)) return T.errors = [{
						instancePath: t,
						schemaPath: "#/additionalProperties",
						keyword: "additionalProperties",
						params: { additionalProperty: r }
					}], !1;
					if (r === c) {
						if (e.body_type !== void 0 && n.call(e, "body_type")) {
							let r = e.body_type, i = c;
							if (c === i) {
								if (r && typeof r == "object" && !Array.isArray(r)) {
									let i;
									if ((r.status === void 0 || !n.call(r, "status")) && (i = "status")) return T.errors = [{
										instancePath: t + "/body_type",
										schemaPath: "#/properties/body_type/required",
										keyword: "required",
										params: { missingProperty: i }
									}], !1;
									if (r.status !== void 0 && n.call(r, "status")) {
										let e = c;
										if (typeof r.status != "string") return T.errors = [{
											instancePath: t + "/body_type/status",
											schemaPath: "#/properties/body_type/properties/status/type",
											keyword: "type",
											params: { type: "string" }
										}], !1;
										var u = e === c;
									} else var u = !0;
									if (u) {
										let n = r.status;
										if (typeof n == "string") {
											if (n === "known") {
												x(r, {
													instancePath: t + "/body_type",
													parentData: e,
													parentDataProperty: "body_type",
													rootData: a,
													dynamicAnchors: o
												}) || (s = s === null ? x.errors : s.concat(x.errors), c = s.length);
												var d = !0;
											} else if (n === "unknown") S(r, {
												instancePath: t + "/body_type",
												parentData: e,
												parentDataProperty: "body_type",
												rootData: a,
												dynamicAnchors: o
											}) || (s = s === null ? S.errors : s.concat(S.errors), c = s.length), d !== !0 && (d = !0);
											else if (n === "conflicting") C(r, {
												instancePath: t + "/body_type",
												parentData: e,
												parentDataProperty: "body_type",
												rootData: a,
												dynamicAnchors: o
											}) || (s = s === null ? C.errors : s.concat(C.errors), c = s.length), d !== !0 && (d = !0);
											else return T.errors = [{
												instancePath: t + "/body_type",
												schemaPath: "#/properties/body_type/discriminator",
												keyword: "discriminator",
												params: {
													error: "mapping",
													tag: "status",
													tagValue: n
												}
											}], !1;
										} else return T.errors = [{
											instancePath: t + "/body_type",
											schemaPath: "#/properties/body_type/discriminator",
											keyword: "discriminator",
											params: {
												error: "tag",
												tag: "status",
												tagValue: n
											}
										}], !1;
									}
								} else return T.errors = [{
									instancePath: t + "/body_type",
									schemaPath: "#/properties/body_type/type",
									keyword: "type",
									params: { type: "object" }
								}], !1;
							}
							var f = i === c;
						} else var f = !0;
						if (f) {
							if (e.description !== void 0 && n.call(e, "description")) {
								let n = e.description, r = c;
								if (c === r) {
									if (typeof n == "string") {
										if (h(n) > 32e3) return T.errors = [{
											instancePath: t + "/description",
											schemaPath: "#/properties/description/maxLength",
											keyword: "maxLength",
											params: { limit: 32e3 }
										}], !1;
									} else return T.errors = [{
										instancePath: t + "/description",
										schemaPath: "#/properties/description/type",
										keyword: "type",
										params: { type: "string" }
									}], !1;
								}
								var f = r === c;
							} else var f = !0;
							if (f) {
								if (e.eligibility !== void 0 && n.call(e, "eligibility")) {
									let n = e.eligibility, r = c;
									if (typeof n != "string") return T.errors = [{
										instancePath: t + "/eligibility",
										schemaPath: "#/properties/eligibility/type",
										keyword: "type",
										params: { type: "string" }
									}], !1;
									if (n !== "simulated_eligible" && n !== "unavailable" && n !== "configuration_missing") return T.errors = [{
										instancePath: t + "/eligibility",
										schemaPath: "#/properties/eligibility/enum",
										keyword: "enum",
										params: { allowedValues: te.properties.eligibility.enum }
									}], !1;
									var f = r === c;
								} else var f = !0;
								if (f) {
									if (e.eligibility_reason !== void 0 && n.call(e, "eligibility_reason")) {
										let n = e.eligibility_reason, r = c;
										if (c === r) {
											if (typeof n == "string") {
												if (h(n) > 200) return T.errors = [{
													instancePath: t + "/eligibility_reason",
													schemaPath: "#/properties/eligibility_reason/maxLength",
													keyword: "maxLength",
													params: { limit: 200 }
												}], !1;
												if (h(n) < 1) return T.errors = [{
													instancePath: t + "/eligibility_reason",
													schemaPath: "#/properties/eligibility_reason/minLength",
													keyword: "minLength",
													params: { limit: 1 }
												}], !1;
											} else return T.errors = [{
												instancePath: t + "/eligibility_reason",
												schemaPath: "#/properties/eligibility_reason/type",
												keyword: "type",
												params: { type: "string" }
											}], !1;
										}
										var f = r === c;
									} else var f = !0;
									if (f) {
										if (e.fuel_type !== void 0 && n.call(e, "fuel_type")) {
											let r = e.fuel_type, i = c;
											if (c === i) {
												if (r && typeof r == "object" && !Array.isArray(r)) {
													let i;
													if ((r.status === void 0 || !n.call(r, "status")) && (i = "status")) return T.errors = [{
														instancePath: t + "/fuel_type",
														schemaPath: "#/properties/fuel_type/required",
														keyword: "required",
														params: { missingProperty: i }
													}], !1;
													if (r.status !== void 0 && n.call(r, "status")) {
														let e = c;
														if (typeof r.status != "string") return T.errors = [{
															instancePath: t + "/fuel_type/status",
															schemaPath: "#/properties/fuel_type/properties/status/type",
															keyword: "type",
															params: { type: "string" }
														}], !1;
														var p = e === c;
													} else var p = !0;
													if (p) {
														let n = r.status;
														if (typeof n == "string") {
															if (n === "known") {
																x(r, {
																	instancePath: t + "/fuel_type",
																	parentData: e,
																	parentDataProperty: "fuel_type",
																	rootData: a,
																	dynamicAnchors: o
																}) || (s = s === null ? x.errors : s.concat(x.errors), c = s.length);
																var m = !0;
															} else if (n === "unknown") S(r, {
																instancePath: t + "/fuel_type",
																parentData: e,
																parentDataProperty: "fuel_type",
																rootData: a,
																dynamicAnchors: o
															}) || (s = s === null ? S.errors : s.concat(S.errors), c = s.length), m !== !0 && (m = !0);
															else if (n === "conflicting") C(r, {
																instancePath: t + "/fuel_type",
																parentData: e,
																parentDataProperty: "fuel_type",
																rootData: a,
																dynamicAnchors: o
															}) || (s = s === null ? C.errors : s.concat(C.errors), c = s.length), m !== !0 && (m = !0);
															else return T.errors = [{
																instancePath: t + "/fuel_type",
																schemaPath: "#/properties/fuel_type/discriminator",
																keyword: "discriminator",
																params: {
																	error: "mapping",
																	tag: "status",
																	tagValue: n
																}
															}], !1;
														} else return T.errors = [{
															instancePath: t + "/fuel_type",
															schemaPath: "#/properties/fuel_type/discriminator",
															keyword: "discriminator",
															params: {
																error: "tag",
																tag: "status",
																tagValue: n
															}
														}], !1;
													}
												} else return T.errors = [{
													instancePath: t + "/fuel_type",
													schemaPath: "#/properties/fuel_type/type",
													keyword: "type",
													params: { type: "object" }
												}], !1;
											}
											var f = i === c;
										} else var f = !0;
										if (f) {
											if (e.listing !== void 0 && n.call(e, "listing")) {
												let n = c;
												w(e.listing, {
													instancePath: t + "/listing",
													parentData: e,
													parentDataProperty: "listing",
													rootData: a,
													dynamicAnchors: o
												}) || (s = s === null ? w.errors : s.concat(w.errors), c = s.length);
												var f = n === c;
											} else var f = !0;
											if (f) {
												if (e.location !== void 0 && n.call(e, "location")) {
													let r = e.location, i = c;
													if (c === i) {
														if (r && typeof r == "object" && !Array.isArray(r)) {
															let i;
															if ((r.status === void 0 || !n.call(r, "status")) && (i = "status")) return T.errors = [{
																instancePath: t + "/location",
																schemaPath: "#/properties/location/required",
																keyword: "required",
																params: { missingProperty: i }
															}], !1;
															if (r.status !== void 0 && n.call(r, "status")) {
																let e = c;
																if (typeof r.status != "string") return T.errors = [{
																	instancePath: t + "/location/status",
																	schemaPath: "#/properties/location/properties/status/type",
																	keyword: "type",
																	params: { type: "string" }
																}], !1;
																var g = e === c;
															} else var g = !0;
															if (g) {
																let n = r.status;
																if (typeof n == "string") {
																	if (n === "known") {
																		x(r, {
																			instancePath: t + "/location",
																			parentData: e,
																			parentDataProperty: "location",
																			rootData: a,
																			dynamicAnchors: o
																		}) || (s = s === null ? x.errors : s.concat(x.errors), c = s.length);
																		var _ = !0;
																	} else if (n === "unknown") S(r, {
																		instancePath: t + "/location",
																		parentData: e,
																		parentDataProperty: "location",
																		rootData: a,
																		dynamicAnchors: o
																	}) || (s = s === null ? S.errors : s.concat(S.errors), c = s.length), _ !== !0 && (_ = !0);
																	else if (n === "conflicting") C(r, {
																		instancePath: t + "/location",
																		parentData: e,
																		parentDataProperty: "location",
																		rootData: a,
																		dynamicAnchors: o
																	}) || (s = s === null ? C.errors : s.concat(C.errors), c = s.length), _ !== !0 && (_ = !0);
																	else return T.errors = [{
																		instancePath: t + "/location",
																		schemaPath: "#/properties/location/discriminator",
																		keyword: "discriminator",
																		params: {
																			error: "mapping",
																			tag: "status",
																			tagValue: n
																		}
																	}], !1;
																} else return T.errors = [{
																	instancePath: t + "/location",
																	schemaPath: "#/properties/location/discriminator",
																	keyword: "discriminator",
																	params: {
																		error: "tag",
																		tag: "status",
																		tagValue: n
																	}
																}], !1;
															}
														} else return T.errors = [{
															instancePath: t + "/location",
															schemaPath: "#/properties/location/type",
															keyword: "type",
															params: { type: "object" }
														}], !1;
													}
													var f = i === c;
												} else var f = !0;
												if (f) {
													if (e.service_history !== void 0 && n.call(e, "service_history")) {
														let r = e.service_history, i = c;
														if (c === i) {
															if (r && typeof r == "object" && !Array.isArray(r)) {
																let i;
																if ((r.status === void 0 || !n.call(r, "status")) && (i = "status")) return T.errors = [{
																	instancePath: t + "/service_history",
																	schemaPath: "#/properties/service_history/required",
																	keyword: "required",
																	params: { missingProperty: i }
																}], !1;
																if (r.status !== void 0 && n.call(r, "status")) {
																	let e = c;
																	if (typeof r.status != "string") return T.errors = [{
																		instancePath: t + "/service_history/status",
																		schemaPath: "#/properties/service_history/properties/status/type",
																		keyword: "type",
																		params: { type: "string" }
																	}], !1;
																	var v = e === c;
																} else var v = !0;
																if (v) {
																	let n = r.status;
																	if (typeof n == "string") {
																		if (n === "known") {
																			x(r, {
																				instancePath: t + "/service_history",
																				parentData: e,
																				parentDataProperty: "service_history",
																				rootData: a,
																				dynamicAnchors: o
																			}) || (s = s === null ? x.errors : s.concat(x.errors), c = s.length);
																			var y = !0;
																		} else if (n === "unknown") S(r, {
																			instancePath: t + "/service_history",
																			parentData: e,
																			parentDataProperty: "service_history",
																			rootData: a,
																			dynamicAnchors: o
																		}) || (s = s === null ? S.errors : s.concat(S.errors), c = s.length), y !== !0 && (y = !0);
																		else if (n === "conflicting") C(r, {
																			instancePath: t + "/service_history",
																			parentData: e,
																			parentDataProperty: "service_history",
																			rootData: a,
																			dynamicAnchors: o
																		}) || (s = s === null ? C.errors : s.concat(C.errors), c = s.length), y !== !0 && (y = !0);
																		else return T.errors = [{
																			instancePath: t + "/service_history",
																			schemaPath: "#/properties/service_history/discriminator",
																			keyword: "discriminator",
																			params: {
																				error: "mapping",
																				tag: "status",
																				tagValue: n
																			}
																		}], !1;
																	} else return T.errors = [{
																		instancePath: t + "/service_history",
																		schemaPath: "#/properties/service_history/discriminator",
																		keyword: "discriminator",
																		params: {
																			error: "tag",
																			tag: "status",
																			tagValue: n
																		}
																	}], !1;
																}
															} else return T.errors = [{
																instancePath: t + "/service_history",
																schemaPath: "#/properties/service_history/type",
																keyword: "type",
																params: { type: "object" }
															}], !1;
														}
														var f = i === c;
													} else var f = !0;
													if (f) {
														if (e.state !== void 0 && n.call(e, "state")) {
															let n = e.state, r = c;
															if (typeof n != "string") return T.errors = [{
																instancePath: t + "/state",
																schemaPath: "#/properties/state/type",
																keyword: "type",
																params: { type: "string" }
															}], !1;
															if (n !== "current" && n !== "historical") return T.errors = [{
																instancePath: t + "/state",
																schemaPath: "#/properties/state/enum",
																keyword: "enum",
																params: { allowedValues: te.properties.state.enum }
															}], !1;
															var f = r === c;
														} else var f = !0;
														if (f) {
															if (e.transmission !== void 0 && n.call(e, "transmission")) {
																let r = e.transmission, i = c;
																if (c === i) {
																	if (r && typeof r == "object" && !Array.isArray(r)) {
																		let i;
																		if ((r.status === void 0 || !n.call(r, "status")) && (i = "status")) return T.errors = [{
																			instancePath: t + "/transmission",
																			schemaPath: "#/properties/transmission/required",
																			keyword: "required",
																			params: { missingProperty: i }
																		}], !1;
																		if (r.status !== void 0 && n.call(r, "status")) {
																			let e = c;
																			if (typeof r.status != "string") return T.errors = [{
																				instancePath: t + "/transmission/status",
																				schemaPath: "#/properties/transmission/properties/status/type",
																				keyword: "type",
																				params: { type: "string" }
																			}], !1;
																			var ee = e === c;
																		} else var ee = !0;
																		if (ee) {
																			let n = r.status;
																			if (typeof n == "string") {
																				if (n === "known") {
																					x(r, {
																						instancePath: t + "/transmission",
																						parentData: e,
																						parentDataProperty: "transmission",
																						rootData: a,
																						dynamicAnchors: o
																					}) || (s = s === null ? x.errors : s.concat(x.errors), c = s.length);
																					var ne = !0;
																				} else if (n === "unknown") S(r, {
																					instancePath: t + "/transmission",
																					parentData: e,
																					parentDataProperty: "transmission",
																					rootData: a,
																					dynamicAnchors: o
																				}) || (s = s === null ? S.errors : s.concat(S.errors), c = s.length), ne !== !0 && (ne = !0);
																				else if (n === "conflicting") C(r, {
																					instancePath: t + "/transmission",
																					parentData: e,
																					parentDataProperty: "transmission",
																					rootData: a,
																					dynamicAnchors: o
																				}) || (s = s === null ? C.errors : s.concat(C.errors), c = s.length), ne !== !0 && (ne = !0);
																				else return T.errors = [{
																					instancePath: t + "/transmission",
																					schemaPath: "#/properties/transmission/discriminator",
																					keyword: "discriminator",
																					params: {
																						error: "mapping",
																						tag: "status",
																						tagValue: n
																					}
																				}], !1;
																			} else return T.errors = [{
																				instancePath: t + "/transmission",
																				schemaPath: "#/properties/transmission/discriminator",
																				keyword: "discriminator",
																				params: {
																					error: "tag",
																					tag: "status",
																					tagValue: n
																				}
																			}], !1;
																		}
																	} else return T.errors = [{
																		instancePath: t + "/transmission",
																		schemaPath: "#/properties/transmission/type",
																		keyword: "type",
																		params: { type: "object" }
																	}], !1;
																}
																var f = i === c;
															} else var f = !0;
															if (f) {
																if (e.warranty !== void 0 && n.call(e, "warranty")) {
																	let r = e.warranty, i = c;
																	if (c === i) {
																		if (r && typeof r == "object" && !Array.isArray(r)) {
																			let i;
																			if ((r.status === void 0 || !n.call(r, "status")) && (i = "status")) return T.errors = [{
																				instancePath: t + "/warranty",
																				schemaPath: "#/properties/warranty/required",
																				keyword: "required",
																				params: { missingProperty: i }
																			}], !1;
																			if (r.status !== void 0 && n.call(r, "status")) {
																				let e = c;
																				if (typeof r.status != "string") return T.errors = [{
																					instancePath: t + "/warranty/status",
																					schemaPath: "#/properties/warranty/properties/status/type",
																					keyword: "type",
																					params: { type: "string" }
																				}], !1;
																				var re = e === c;
																			} else var re = !0;
																			if (re) {
																				let n = r.status;
																				if (typeof n == "string") {
																					if (n === "known") {
																						x(r, {
																							instancePath: t + "/warranty",
																							parentData: e,
																							parentDataProperty: "warranty",
																							rootData: a,
																							dynamicAnchors: o
																						}) || (s = s === null ? x.errors : s.concat(x.errors), c = s.length);
																						var b = !0;
																					} else if (n === "unknown") S(r, {
																						instancePath: t + "/warranty",
																						parentData: e,
																						parentDataProperty: "warranty",
																						rootData: a,
																						dynamicAnchors: o
																					}) || (s = s === null ? S.errors : s.concat(S.errors), c = s.length), b !== !0 && (b = !0);
																					else if (n === "conflicting") C(r, {
																						instancePath: t + "/warranty",
																						parentData: e,
																						parentDataProperty: "warranty",
																						rootData: a,
																						dynamicAnchors: o
																					}) || (s = s === null ? C.errors : s.concat(C.errors), c = s.length), b !== !0 && (b = !0);
																					else return T.errors = [{
																						instancePath: t + "/warranty",
																						schemaPath: "#/properties/warranty/discriminator",
																						keyword: "discriminator",
																						params: {
																							error: "mapping",
																							tag: "status",
																							tagValue: n
																						}
																					}], !1;
																				} else return T.errors = [{
																					instancePath: t + "/warranty",
																					schemaPath: "#/properties/warranty/discriminator",
																					keyword: "discriminator",
																					params: {
																						error: "tag",
																						tag: "status",
																						tagValue: n
																					}
																				}], !1;
																			}
																		} else return T.errors = [{
																			instancePath: t + "/warranty",
																			schemaPath: "#/properties/warranty/type",
																			keyword: "type",
																			params: { type: "object" }
																		}], !1;
																	}
																	var f = i === c;
																} else var f = !0;
															}
														}
													}
												}
											}
										}
									}
								}
							}
						}
					}
				}
			} else return T.errors = [{
				instancePath: t,
				schemaPath: "#/type",
				keyword: "type",
				params: { type: "object" }
			}], !1;
		}
		return T.errors = s, c === 0;
	}
	T.evaluated = {
		props: !0,
		dynamicProps: !1,
		dynamicItems: !1
	};
	function Se(e, { instancePath: t = "", parentData: r, parentDataProperty: i, rootData: a = e, dynamicAnchors: o = {} } = {}) {
		let s = null, c = 0, u = Se.evaluated;
		if (u.dynamicProps && (u.props = void 0), u.dynamicItems && (u.items = void 0), c === 0) {
			if (e && typeof e == "object" && !Array.isArray(e)) {
				let r;
				if ((e.state === void 0 || !n.call(e, "state")) && (r = "state") || (e.ref === void 0 || !n.call(e, "ref")) && (r = "ref")) return Se.errors = [{
					instancePath: t,
					schemaPath: "#/required",
					keyword: "required",
					params: { missingProperty: r }
				}], !1;
				{
					let r = c;
					for (let n of Object.keys(e)) if (n !== "ref" && n !== "state") return Se.errors = [{
						instancePath: t,
						schemaPath: "#/additionalProperties",
						keyword: "additionalProperties",
						params: { additionalProperty: n }
					}], !1;
					if (r === c) {
						if (e.ref !== void 0 && n.call(e, "ref")) {
							let n = c;
							l(e.ref, {
								instancePath: t + "/ref",
								parentData: e,
								parentDataProperty: "ref",
								rootData: a,
								dynamicAnchors: o
							}) || (s = s === null ? l.errors : s.concat(l.errors), c = s.length);
							var d = n === c;
						} else var d = !0;
						if (d) {
							if (e.state !== void 0 && n.call(e, "state")) {
								let n = e.state, r = c;
								if (typeof n != "string") return Se.errors = [{
									instancePath: t + "/state",
									schemaPath: "#/properties/state/type",
									keyword: "type",
									params: { type: "string" }
								}], !1;
								if (n !== "missing") return Se.errors = [{
									instancePath: t + "/state",
									schemaPath: "#/properties/state/const",
									keyword: "const",
									params: { allowedValue: "missing" }
								}], !1;
								var d = r === c;
							} else var d = !0;
						}
					}
				}
			} else return Se.errors = [{
				instancePath: t,
				schemaPath: "#/type",
				keyword: "type",
				params: { type: "object" }
			}], !1;
		}
		return Se.errors = s, c === 0;
	}
	Se.evaluated = {
		props: !0,
		dynamicProps: !1,
		dynamicItems: !1
	};
	var Ce = {
		additionalProperties: !1,
		properties: {
			code: {
				enum: [
					"STORE_UNAVAILABLE",
					"SNAPSHOT_STALE",
					"INTERNAL_ERROR"
				],
				title: "Code",
				type: "string"
			},
			ref: { $ref: "urn:car-shopping-assistant:contract:1#/$defs/InventoryRef" },
			retryable: {
				title: "Retryable",
				type: "boolean"
			},
			state: {
				const: "error",
				title: "State",
				type: "string"
			}
		},
		required: [
			"state",
			"ref",
			"code",
			"retryable"
		],
		title: "ListingReadError",
		type: "object"
	};
	function we(e, { instancePath: t = "", parentData: r, parentDataProperty: i, rootData: a = e, dynamicAnchors: o = {} } = {}) {
		let s = null, c = 0, u = we.evaluated;
		if (u.dynamicProps && (u.props = void 0), u.dynamicItems && (u.items = void 0), c === 0) {
			if (e && typeof e == "object" && !Array.isArray(e)) {
				let r;
				if ((e.state === void 0 || !n.call(e, "state")) && (r = "state") || (e.ref === void 0 || !n.call(e, "ref")) && (r = "ref") || (e.code === void 0 || !n.call(e, "code")) && (r = "code") || (e.retryable === void 0 || !n.call(e, "retryable")) && (r = "retryable")) return we.errors = [{
					instancePath: t,
					schemaPath: "#/required",
					keyword: "required",
					params: { missingProperty: r }
				}], !1;
				{
					let r = c;
					for (let n of Object.keys(e)) if (n !== "code" && n !== "ref" && n !== "retryable" && n !== "state") return we.errors = [{
						instancePath: t,
						schemaPath: "#/additionalProperties",
						keyword: "additionalProperties",
						params: { additionalProperty: n }
					}], !1;
					if (r === c) {
						if (e.code !== void 0 && n.call(e, "code")) {
							let n = e.code, r = c;
							if (typeof n != "string") return we.errors = [{
								instancePath: t + "/code",
								schemaPath: "#/properties/code/type",
								keyword: "type",
								params: { type: "string" }
							}], !1;
							if (n !== "STORE_UNAVAILABLE" && n !== "SNAPSHOT_STALE" && n !== "INTERNAL_ERROR") return we.errors = [{
								instancePath: t + "/code",
								schemaPath: "#/properties/code/enum",
								keyword: "enum",
								params: { allowedValues: Ce.properties.code.enum }
							}], !1;
							var d = r === c;
						} else var d = !0;
						if (d) {
							if (e.ref !== void 0 && n.call(e, "ref")) {
								let n = c;
								l(e.ref, {
									instancePath: t + "/ref",
									parentData: e,
									parentDataProperty: "ref",
									rootData: a,
									dynamicAnchors: o
								}) || (s = s === null ? l.errors : s.concat(l.errors), c = s.length);
								var d = n === c;
							} else var d = !0;
							if (d) {
								if (e.retryable !== void 0 && n.call(e, "retryable")) {
									let n = c;
									if (typeof e.retryable != "boolean") return we.errors = [{
										instancePath: t + "/retryable",
										schemaPath: "#/properties/retryable/type",
										keyword: "type",
										params: { type: "boolean" }
									}], !1;
									var d = n === c;
								} else var d = !0;
								if (d) {
									if (e.state !== void 0 && n.call(e, "state")) {
										let n = e.state, r = c;
										if (typeof n != "string") return we.errors = [{
											instancePath: t + "/state",
											schemaPath: "#/properties/state/type",
											keyword: "type",
											params: { type: "string" }
										}], !1;
										if (n !== "error") return we.errors = [{
											instancePath: t + "/state",
											schemaPath: "#/properties/state/const",
											keyword: "const",
											params: { allowedValue: "error" }
										}], !1;
										var d = r === c;
									} else var d = !0;
								}
							}
						}
					}
				}
			} else return we.errors = [{
				instancePath: t,
				schemaPath: "#/type",
				keyword: "type",
				params: { type: "object" }
			}], !1;
		}
		return we.errors = s, c === 0;
	}
	we.evaluated = {
		props: !0,
		dynamicProps: !1,
		dynamicItems: !1
	};
	function Te(e, { instancePath: t = "", parentData: r, parentDataProperty: i, rootData: a = e, dynamicAnchors: o = {} } = {}) {
		let s = null, c = 0, l = Te.evaluated;
		if (l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0) {
			if (e && typeof e == "object" && !Array.isArray(e)) {
				let r;
				if ((e.data === void 0 || !n.call(e, "data")) && (r = "data") || (e.meta === void 0 || !n.call(e, "meta")) && (r = "meta")) return Te.errors = [{
					instancePath: t,
					schemaPath: "#/required",
					keyword: "required",
					params: { missingProperty: r }
				}], !1;
				{
					let r = c;
					for (let n of Object.keys(e)) if (n !== "data" && n !== "meta") return Te.errors = [{
						instancePath: t,
						schemaPath: "#/additionalProperties",
						keyword: "additionalProperties",
						params: { additionalProperty: n }
					}], !1;
					if (r === c) {
						if (e.data !== void 0 && n.call(e, "data")) {
							let r = e.data, i = c;
							if (c === i) {
								if (r && typeof r == "object" && !Array.isArray(r)) {
									let i;
									if ((r.state === void 0 || !n.call(r, "state")) && (i = "state")) return Te.errors = [{
										instancePath: t + "/data",
										schemaPath: "#/properties/data/required",
										keyword: "required",
										params: { missingProperty: i }
									}], !1;
									if (r.state !== void 0 && n.call(r, "state")) {
										let e = c;
										if (typeof r.state != "string") return Te.errors = [{
											instancePath: t + "/data/state",
											schemaPath: "#/properties/data/properties/state/type",
											keyword: "type",
											params: { type: "string" }
										}], !1;
										var u = e === c;
									} else var u = !0;
									if (u) {
										let n = r.state;
										if (typeof n == "string") {
											if (n === "current") {
												T(r, {
													instancePath: t + "/data",
													parentData: e,
													parentDataProperty: "data",
													rootData: a,
													dynamicAnchors: o
												}) || (s = s === null ? T.errors : s.concat(T.errors), c = s.length);
												var d = !0;
											} else if (n === "historical") T(r, {
												instancePath: t + "/data",
												parentData: e,
												parentDataProperty: "data",
												rootData: a,
												dynamicAnchors: o
											}) || (s = s === null ? T.errors : s.concat(T.errors), c = s.length), d !== !0 && (d = !0);
											else if (n === "missing") Se(r, {
												instancePath: t + "/data",
												parentData: e,
												parentDataProperty: "data",
												rootData: a,
												dynamicAnchors: o
											}) || (s = s === null ? Se.errors : s.concat(Se.errors), c = s.length), d !== !0 && (d = !0);
											else if (n === "error") we(r, {
												instancePath: t + "/data",
												parentData: e,
												parentDataProperty: "data",
												rootData: a,
												dynamicAnchors: o
											}) || (s = s === null ? we.errors : s.concat(we.errors), c = s.length), d !== !0 && (d = !0);
											else return Te.errors = [{
												instancePath: t + "/data",
												schemaPath: "#/properties/data/discriminator",
												keyword: "discriminator",
												params: {
													error: "mapping",
													tag: "state",
													tagValue: n
												}
											}], !1;
										} else return Te.errors = [{
											instancePath: t + "/data",
											schemaPath: "#/properties/data/discriminator",
											keyword: "discriminator",
											params: {
												error: "tag",
												tag: "state",
												tagValue: n
											}
										}], !1;
									}
								} else return Te.errors = [{
									instancePath: t + "/data",
									schemaPath: "#/properties/data/type",
									keyword: "type",
									params: { type: "object" }
								}], !1;
							}
							var f = i === c;
						} else var f = !0;
						if (f) {
							if (e.meta !== void 0 && n.call(e, "meta")) {
								let n = c;
								y(e.meta, {
									instancePath: t + "/meta",
									parentData: e,
									parentDataProperty: "meta",
									rootData: a,
									dynamicAnchors: o
								}) || (s = s === null ? y.errors : s.concat(y.errors), c = s.length);
								var f = n === c;
							} else var f = !0;
						}
					}
				}
			} else return Te.errors = [{
				instancePath: t,
				schemaPath: "#/type",
				keyword: "type",
				params: { type: "object" }
			}], !1;
		}
		return Te.errors = s, c === 0;
	}
	Te.evaluated = {
		props: !0,
		dynamicProps: !1,
		dynamicItems: !1
	}, e.v33 = Ue;
	var Ee = {
		additionalProperties: !1,
		properties: {
			booking: { $ref: "urn:car-shopping-assistant:contract:1#/$defs/BookingCoreReceipt" },
			csv: {
				discriminator: { propertyName: "state" },
				oneOf: [{ $ref: "urn:car-shopping-assistant:contract:1#/$defs/ExportCurrent" }, { $ref: "urn:car-shopping-assistant:contract:1#/$defs/ExportPending" }],
				title: "Csv",
				type: "object",
				required: ["state"],
				properties: { state: { type: "string" } }
			},
			lead: { $ref: "urn:car-shopping-assistant:contract:1#/$defs/LeadSaved" },
			operation_key: {
				pattern: "^[A-Za-z0-9_-]{43}$",
				title: "Operation Key",
				type: "string"
			},
			original_store_generation: {
				pattern: "^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$",
				title: "Original Store Generation",
				type: "string"
			},
			replay_valid_until: {
				pattern: "^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}(?:\\.\\d{1,6})?Z$",
				title: "Replay Valid Until",
				type: "string"
			},
			review_id: {
				pattern: "^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$",
				title: "Review Id",
				type: "string"
			},
			state: {
				const: "succeeded",
				title: "State",
				type: "string"
			},
			terminal_at: {
				pattern: "^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}(?:\\.\\d{1,6})?Z$",
				title: "Terminal At",
				type: "string"
			}
		},
		required: [
			"state",
			"operation_key",
			"review_id",
			"original_store_generation",
			"terminal_at",
			"replay_valid_until",
			"booking",
			"lead",
			"csv"
		],
		title: "OperationSucceeded",
		type: "object"
	}, De = {
		additionalProperties: !1,
		properties: {
			appointment_type: {
				const: "viewing",
				default: "viewing",
				title: "Appointment Type",
				type: "string"
			},
			draft_id: {
				pattern: "^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$",
				title: "Draft Id",
				type: "string"
			},
			draft_revision: {
				maximum: 2147483647,
				minimum: 0,
				title: "Draft Revision",
				type: "integer"
			},
			eligibility_version: {
				maxLength: 200,
				minLength: 1,
				title: "Eligibility Version",
				type: "string"
			},
			ends_at_utc: {
				pattern: "^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}(?:\\.\\d{1,6})?Z$",
				title: "Ends At Utc",
				type: "string"
			},
			expires_at: {
				pattern: "^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}(?:\\.\\d{1,6})?Z$",
				title: "Expires At",
				type: "string"
			},
			issued_at: {
				pattern: "^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}(?:\\.\\d{1,6})?Z$",
				title: "Issued At",
				type: "string"
			},
			lead_change: {
				discriminator: { propertyName: "mode" },
				oneOf: [{ $ref: "urn:car-shopping-assistant:contract:1#/$defs/ReviewedLeadCreation" }, { $ref: "urn:car-shopping-assistant:contract:1#/$defs/ReviewedExistingLead" }],
				title: "Lead Change",
				type: "object",
				required: ["mode"],
				properties: { mode: { type: "string" } }
			},
			lead_effect: {
				const: "save_local_enquiry",
				default: "save_local_enquiry",
				title: "Lead Effect",
				type: "string"
			},
			local_start: {
				maxLength: 40,
				title: "Local Start",
				type: "string"
			},
			operation_key: {
				pattern: "^[A-Za-z0-9_-]{43}$",
				title: "Operation Key",
				type: "string"
			},
			ref: { $ref: "urn:car-shopping-assistant:contract:1#/$defs/InventoryRef" },
			resource_id: {
				pattern: "^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$",
				title: "Resource Id",
				type: "string"
			},
			review_id: {
				pattern: "^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$",
				title: "Review Id",
				type: "string"
			},
			rules_version: {
				maxLength: 200,
				minLength: 1,
				title: "Rules Version",
				type: "string"
			},
			session_id: {
				pattern: "^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$",
				title: "Session Id",
				type: "string"
			},
			simulation: {
				const: !0,
				default: !0,
				title: "Simulation",
				type: "boolean"
			},
			starts_at_utc: {
				pattern: "^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}(?:\\.\\d{1,6})?Z$",
				title: "Starts At Utc",
				type: "string"
			},
			state: {
				enum: [
					"valid",
					"invalidated",
					"expired",
					"submitted",
					"consumed"
				],
				title: "State",
				type: "string"
			},
			store_generation: {
				pattern: "^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$",
				title: "Store Generation",
				type: "string"
			},
			timezone: {
				const: "Asia/Dubai",
				default: "Asia/Dubai",
				title: "Timezone",
				type: "string"
			},
			venue_label: {
				const: "Simulated local viewing — no real venue or reservation.",
				title: "Venue Label",
				type: "string"
			}
		},
		required: [
			"review_id",
			"draft_id",
			"session_id",
			"draft_revision",
			"ref",
			"resource_id",
			"starts_at_utc",
			"ends_at_utc",
			"local_start",
			"venue_label",
			"rules_version",
			"eligibility_version",
			"store_generation",
			"operation_key",
			"issued_at",
			"expires_at",
			"lead_change",
			"state"
		],
		title: "BookingReview",
		type: "object"
	}, Oe = {
		additionalProperties: !1,
		properties: {
			state: {
				enum: [
					"provided",
					"missing",
					"declined"
				],
				title: "State",
				type: "string"
			},
			value: { anyOf: [{ $ref: "urn:car-shopping-assistant:contract:1#/$defs/BudgetRange" }, { type: "null" }] }
		},
		required: ["state"],
		title: "BudgetValue",
		type: "object"
	};
	function ke(e, { instancePath: t = "", parentData: r, parentDataProperty: i, rootData: a = e, dynamicAnchors: o = {} } = {}) {
		let s = null, c = 0, l = ke.evaluated;
		if (l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0) {
			if (e && typeof e == "object" && !Array.isArray(e)) {
				let r;
				if ((e.currency === void 0 || !n.call(e, "currency")) && (r = "currency")) return ke.errors = [{
					instancePath: t,
					schemaPath: "#/required",
					keyword: "required",
					params: { missingProperty: r }
				}], !1;
				{
					let r = c;
					for (let n of Object.keys(e)) if (n !== "basis" && n !== "currency" && n !== "maximum" && n !== "minimum") return ke.errors = [{
						instancePath: t,
						schemaPath: "#/additionalProperties",
						keyword: "additionalProperties",
						params: { additionalProperty: n }
					}], !1;
					if (r === c) {
						if (e.basis !== void 0 && n.call(e, "basis")) {
							let n = e.basis, r = c;
							if (typeof n != "string") return ke.errors = [{
								instancePath: t + "/basis",
								schemaPath: "#/properties/basis/type",
								keyword: "type",
								params: { type: "string" }
							}], !1;
							if (n !== "cash") return ke.errors = [{
								instancePath: t + "/basis",
								schemaPath: "#/properties/basis/const",
								keyword: "const",
								params: { allowedValue: "cash" }
							}], !1;
							var u = r === c;
						} else var u = !0;
						if (u) {
							if (e.currency !== void 0 && n.call(e, "currency")) {
								let n = e.currency, r = c;
								if (c === r) {
									if (typeof n == "string") {
										if (!le.test(n)) return ke.errors = [{
											instancePath: t + "/currency",
											schemaPath: "#/properties/currency/pattern",
											keyword: "pattern",
											params: { pattern: "^[A-Z]{3}$" }
										}], !1;
									} else return ke.errors = [{
										instancePath: t + "/currency",
										schemaPath: "#/properties/currency/type",
										keyword: "type",
										params: { type: "string" }
									}], !1;
								}
								var u = r === c;
							} else var u = !0;
							if (u) {
								if (e.maximum !== void 0 && n.call(e, "maximum")) {
									let n = e.maximum, r = c, i = c, a = !1, o = c;
									if (typeof n != "number" || n % 1 || isNaN(n) || !isFinite(n)) {
										let e = {
											instancePath: t + "/maximum",
											schemaPath: "#/properties/maximum/anyOf/0/type",
											keyword: "type",
											params: { type: "integer" }
										};
										s === null ? s = [e] : s.push(e), c++;
									}
									if (c === o && typeof n == "number" && isFinite(n)) {
										if (n > 0xe8d4a51000 || isNaN(n)) {
											let e = {
												instancePath: t + "/maximum",
												schemaPath: "#/properties/maximum/anyOf/0/maximum",
												keyword: "maximum",
												params: {
													comparison: "<=",
													limit: 0xe8d4a51000
												}
											};
											s === null ? s = [e] : s.push(e), c++;
										} else if (n < 0 || isNaN(n)) {
											let e = {
												instancePath: t + "/maximum",
												schemaPath: "#/properties/maximum/anyOf/0/minimum",
												keyword: "minimum",
												params: {
													comparison: ">=",
													limit: 0
												}
											};
											s === null ? s = [e] : s.push(e), c++;
										}
									}
									var d = o === c;
									a ||= d;
									let l = c;
									if (n !== null) {
										let e = {
											instancePath: t + "/maximum",
											schemaPath: "#/properties/maximum/anyOf/1/type",
											keyword: "type",
											params: { type: "null" }
										};
										s === null ? s = [e] : s.push(e), c++;
									}
									var d = l === c;
									if (a ||= d, a) c = i, s !== null && (i ? s.length = i : s = null);
									else {
										let e = {
											instancePath: t + "/maximum",
											schemaPath: "#/properties/maximum/anyOf",
											keyword: "anyOf",
											params: {}
										};
										return s === null ? s = [e] : s.push(e), c++, ke.errors = s, !1;
									}
									var u = r === c;
								} else var u = !0;
								if (u) {
									if (e.minimum !== void 0 && n.call(e, "minimum")) {
										let n = e.minimum, r = c, i = c, a = !1, o = c;
										if (typeof n != "number" || n % 1 || isNaN(n) || !isFinite(n)) {
											let e = {
												instancePath: t + "/minimum",
												schemaPath: "#/properties/minimum/anyOf/0/type",
												keyword: "type",
												params: { type: "integer" }
											};
											s === null ? s = [e] : s.push(e), c++;
										}
										if (c === o && typeof n == "number" && isFinite(n)) {
											if (n > 0xe8d4a51000 || isNaN(n)) {
												let e = {
													instancePath: t + "/minimum",
													schemaPath: "#/properties/minimum/anyOf/0/maximum",
													keyword: "maximum",
													params: {
														comparison: "<=",
														limit: 0xe8d4a51000
													}
												};
												s === null ? s = [e] : s.push(e), c++;
											} else if (n < 0 || isNaN(n)) {
												let e = {
													instancePath: t + "/minimum",
													schemaPath: "#/properties/minimum/anyOf/0/minimum",
													keyword: "minimum",
													params: {
														comparison: ">=",
														limit: 0
													}
												};
												s === null ? s = [e] : s.push(e), c++;
											}
										}
										var f = o === c;
										a ||= f;
										let l = c;
										if (n !== null) {
											let e = {
												instancePath: t + "/minimum",
												schemaPath: "#/properties/minimum/anyOf/1/type",
												keyword: "type",
												params: { type: "null" }
											};
											s === null ? s = [e] : s.push(e), c++;
										}
										var f = l === c;
										if (a ||= f, a) c = i, s !== null && (i ? s.length = i : s = null);
										else {
											let e = {
												instancePath: t + "/minimum",
												schemaPath: "#/properties/minimum/anyOf",
												keyword: "anyOf",
												params: {}
											};
											return s === null ? s = [e] : s.push(e), c++, ke.errors = s, !1;
										}
										var u = r === c;
									} else var u = !0;
								}
							}
						}
					}
				}
			} else return ke.errors = [{
				instancePath: t,
				schemaPath: "#/type",
				keyword: "type",
				params: { type: "object" }
			}], !1;
		}
		return ke.errors = s, c === 0;
	}
	ke.evaluated = {
		props: !0,
		dynamicProps: !1,
		dynamicItems: !1
	};
	function Ae(e, { instancePath: t = "", parentData: r, parentDataProperty: i, rootData: a = e, dynamicAnchors: o = {} } = {}) {
		let s = null, c = 0, l = Ae.evaluated;
		if (l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0) {
			if (e && typeof e == "object" && !Array.isArray(e)) {
				let r;
				if ((e.state === void 0 || !n.call(e, "state")) && (r = "state")) return Ae.errors = [{
					instancePath: t,
					schemaPath: "#/required",
					keyword: "required",
					params: { missingProperty: r }
				}], !1;
				{
					let r = c;
					for (let n of Object.keys(e)) if (n !== "state" && n !== "value") return Ae.errors = [{
						instancePath: t,
						schemaPath: "#/additionalProperties",
						keyword: "additionalProperties",
						params: { additionalProperty: n }
					}], !1;
					if (r === c) {
						if (e.state !== void 0 && n.call(e, "state")) {
							let n = e.state, r = c;
							if (typeof n != "string") return Ae.errors = [{
								instancePath: t + "/state",
								schemaPath: "#/properties/state/type",
								keyword: "type",
								params: { type: "string" }
							}], !1;
							if (n !== "provided" && n !== "missing" && n !== "declined") return Ae.errors = [{
								instancePath: t + "/state",
								schemaPath: "#/properties/state/enum",
								keyword: "enum",
								params: { allowedValues: Oe.properties.state.enum }
							}], !1;
							var u = r === c;
						} else var u = !0;
						if (u) {
							if (e.value !== void 0 && n.call(e, "value")) {
								let n = e.value, r = c, i = c, l = !1, f = c;
								ke(n, {
									instancePath: t + "/value",
									parentData: e,
									parentDataProperty: "value",
									rootData: a,
									dynamicAnchors: o
								}) || (s = s === null ? ke.errors : s.concat(ke.errors), c = s.length);
								var d = f === c;
								l ||= d;
								let p = c;
								if (n !== null) {
									let e = {
										instancePath: t + "/value",
										schemaPath: "#/properties/value/anyOf/1/type",
										keyword: "type",
										params: { type: "null" }
									};
									s === null ? s = [e] : s.push(e), c++;
								}
								var d = p === c;
								if (l ||= d, l) c = i, s !== null && (i ? s.length = i : s = null);
								else {
									let e = {
										instancePath: t + "/value",
										schemaPath: "#/properties/value/anyOf",
										keyword: "anyOf",
										params: {}
									};
									return s === null ? s = [e] : s.push(e), c++, Ae.errors = s, !1;
								}
								var u = r === c;
							} else var u = !0;
						}
					}
				}
			} else return Ae.errors = [{
				instancePath: t,
				schemaPath: "#/type",
				keyword: "type",
				params: { type: "object" }
			}], !1;
		}
		return Ae.errors = s, c === 0;
	}
	Ae.evaluated = {
		props: !0,
		dynamicProps: !1,
		dynamicItems: !1
	};
	var je = {
		additionalProperties: !1,
		properties: {
			state: {
				enum: [
					"provided",
					"missing",
					"declined"
				],
				title: "State",
				type: "string"
			},
			value: {
				anyOf: [{
					maxLength: 320,
					minLength: 1,
					type: "string"
				}, { type: "null" }],
				title: "Value"
			}
		},
		required: ["state"],
		title: "ContactValue",
		type: "object"
	};
	function Me(e, { instancePath: t = "", parentData: r, parentDataProperty: i, rootData: a = e, dynamicAnchors: o = {} } = {}) {
		let s = null, c = 0, l = Me.evaluated;
		if (l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0) {
			if (e && typeof e == "object" && !Array.isArray(e)) {
				let r;
				if ((e.state === void 0 || !n.call(e, "state")) && (r = "state")) return Me.errors = [{
					instancePath: t,
					schemaPath: "#/required",
					keyword: "required",
					params: { missingProperty: r }
				}], !1;
				{
					let r = c;
					for (let n of Object.keys(e)) if (n !== "state" && n !== "value") return Me.errors = [{
						instancePath: t,
						schemaPath: "#/additionalProperties",
						keyword: "additionalProperties",
						params: { additionalProperty: n }
					}], !1;
					if (r === c) {
						if (e.state !== void 0 && n.call(e, "state")) {
							let n = e.state, r = c;
							if (typeof n != "string") return Me.errors = [{
								instancePath: t + "/state",
								schemaPath: "#/properties/state/type",
								keyword: "type",
								params: { type: "string" }
							}], !1;
							if (n !== "provided" && n !== "missing" && n !== "declined") return Me.errors = [{
								instancePath: t + "/state",
								schemaPath: "#/properties/state/enum",
								keyword: "enum",
								params: { allowedValues: je.properties.state.enum }
							}], !1;
							var u = r === c;
						} else var u = !0;
						if (u) {
							if (e.value !== void 0 && n.call(e, "value")) {
								let n = e.value, r = c, i = c, a = !1, o = c;
								if (c === o) {
									if (typeof n == "string") {
										if (h(n) > 320) {
											let e = {
												instancePath: t + "/value",
												schemaPath: "#/properties/value/anyOf/0/maxLength",
												keyword: "maxLength",
												params: { limit: 320 }
											};
											s === null ? s = [e] : s.push(e), c++;
										} else if (h(n) < 1) {
											let e = {
												instancePath: t + "/value",
												schemaPath: "#/properties/value/anyOf/0/minLength",
												keyword: "minLength",
												params: { limit: 1 }
											};
											s === null ? s = [e] : s.push(e), c++;
										}
									} else {
										let e = {
											instancePath: t + "/value",
											schemaPath: "#/properties/value/anyOf/0/type",
											keyword: "type",
											params: { type: "string" }
										};
										s === null ? s = [e] : s.push(e), c++;
									}
								}
								var d = o === c;
								a ||= d;
								let l = c;
								if (n !== null) {
									let e = {
										instancePath: t + "/value",
										schemaPath: "#/properties/value/anyOf/1/type",
										keyword: "type",
										params: { type: "null" }
									};
									s === null ? s = [e] : s.push(e), c++;
								}
								var d = l === c;
								if (a ||= d, a) c = i, s !== null && (i ? s.length = i : s = null);
								else {
									let e = {
										instancePath: t + "/value",
										schemaPath: "#/properties/value/anyOf",
										keyword: "anyOf",
										params: {}
									};
									return s === null ? s = [e] : s.push(e), c++, Me.errors = s, !1;
								}
								var u = r === c;
							} else var u = !0;
						}
					}
				}
			} else return Me.errors = [{
				instancePath: t,
				schemaPath: "#/type",
				keyword: "type",
				params: { type: "object" }
			}], !1;
		}
		return Me.errors = s, c === 0;
	}
	Me.evaluated = {
		props: !0,
		dynamicProps: !1,
		dynamicItems: !1
	};
	function E(e, { instancePath: t = "", parentData: r, parentDataProperty: i, rootData: a = e, dynamicAnchors: o = {} } = {}) {
		let s = null, c = 0, u = E.evaluated;
		if (u.dynamicProps && (u.props = void 0), u.dynamicItems && (u.items = void 0), c === 0) {
			if (e && typeof e == "object" && !Array.isArray(e)) {
				let r;
				if ((e.budget === void 0 || !n.call(e, "budget")) && (r = "budget") || (e.requirements === void 0 || !n.call(e, "requirements")) && (r = "requirements") || (e.selected_refs === void 0 || !n.call(e, "selected_refs")) && (r = "selected_refs") || (e.email === void 0 || !n.call(e, "email")) && (r = "email") || (e.phone === void 0 || !n.call(e, "phone")) && (r = "phone")) return E.errors = [{
					instancePath: t,
					schemaPath: "#/required",
					keyword: "required",
					params: { missingProperty: r }
				}], !1;
				{
					let r = c;
					for (let n of Object.keys(e)) if (n !== "budget" && n !== "email" && n !== "phone" && n !== "requirements" && n !== "selected_refs") return E.errors = [{
						instancePath: t,
						schemaPath: "#/additionalProperties",
						keyword: "additionalProperties",
						params: { additionalProperty: n }
					}], !1;
					if (r === c) {
						if (e.budget !== void 0 && n.call(e, "budget")) {
							let n = c;
							Ae(e.budget, {
								instancePath: t + "/budget",
								parentData: e,
								parentDataProperty: "budget",
								rootData: a,
								dynamicAnchors: o
							}) || (s = s === null ? Ae.errors : s.concat(Ae.errors), c = s.length);
							var d = n === c;
						} else var d = !0;
						if (d) {
							if (e.email !== void 0 && n.call(e, "email")) {
								let n = c;
								Me(e.email, {
									instancePath: t + "/email",
									parentData: e,
									parentDataProperty: "email",
									rootData: a,
									dynamicAnchors: o
								}) || (s = s === null ? Me.errors : s.concat(Me.errors), c = s.length);
								var d = n === c;
							} else var d = !0;
							if (d) {
								if (e.phone !== void 0 && n.call(e, "phone")) {
									let n = c;
									Me(e.phone, {
										instancePath: t + "/phone",
										parentData: e,
										parentDataProperty: "phone",
										rootData: a,
										dynamicAnchors: o
									}) || (s = s === null ? Me.errors : s.concat(Me.errors), c = s.length);
									var d = n === c;
								} else var d = !0;
								if (d) {
									if (e.requirements !== void 0 && n.call(e, "requirements")) {
										let n = e.requirements, r = c;
										if (c === r) {
											if (Array.isArray(n)) {
												if (n.length > 24) return E.errors = [{
													instancePath: t + "/requirements",
													schemaPath: "#/properties/requirements/maxItems",
													keyword: "maxItems",
													params: { limit: 24 }
												}], !1;
												{
													let e = n.length;
													for (let r = 0; r < e; r++) {
														let e = n[r], i = c;
														if (c === i) {
															if (typeof e == "string") {
																if (h(e) > 200) return E.errors = [{
																	instancePath: t + "/requirements/" + r,
																	schemaPath: "#/properties/requirements/items/maxLength",
																	keyword: "maxLength",
																	params: { limit: 200 }
																}], !1;
																if (h(e) < 1) return E.errors = [{
																	instancePath: t + "/requirements/" + r,
																	schemaPath: "#/properties/requirements/items/minLength",
																	keyword: "minLength",
																	params: { limit: 1 }
																}], !1;
															} else return E.errors = [{
																instancePath: t + "/requirements/" + r,
																schemaPath: "#/properties/requirements/items/type",
																keyword: "type",
																params: { type: "string" }
															}], !1;
														}
														if (i !== c) break;
													}
												}
											} else return E.errors = [{
												instancePath: t + "/requirements",
												schemaPath: "#/properties/requirements/type",
												keyword: "type",
												params: { type: "array" }
											}], !1;
										}
										var d = r === c;
									} else var d = !0;
									if (d) {
										if (e.selected_refs !== void 0 && n.call(e, "selected_refs")) {
											let n = e.selected_refs, r = c;
											if (c === r) {
												if (Array.isArray(n)) {
													if (n.length > 10) return E.errors = [{
														instancePath: t + "/selected_refs",
														schemaPath: "#/properties/selected_refs/maxItems",
														keyword: "maxItems",
														params: { limit: 10 }
													}], !1;
													{
														let e = n.length;
														for (let r = 0; r < e; r++) {
															let e = c;
															if (l(n[r], {
																instancePath: t + "/selected_refs/" + r,
																parentData: n,
																parentDataProperty: r,
																rootData: a,
																dynamicAnchors: o
															}) || (s = s === null ? l.errors : s.concat(l.errors), c = s.length), e !== c) break;
														}
													}
												} else return E.errors = [{
													instancePath: t + "/selected_refs",
													schemaPath: "#/properties/selected_refs/type",
													keyword: "type",
													params: { type: "array" }
												}], !1;
											}
											var d = r === c;
										} else var d = !0;
									}
								}
							}
						}
					}
				}
			} else return E.errors = [{
				instancePath: t,
				schemaPath: "#/type",
				keyword: "type",
				params: { type: "object" }
			}], !1;
		}
		return E.errors = s, c === 0;
	}
	E.evaluated = {
		props: !0,
		dynamicProps: !1,
		dynamicItems: !1
	};
	function Ne(e, { instancePath: t = "", parentData: r, parentDataProperty: i, rootData: a = e, dynamicAnchors: o = {} } = {}) {
		let s = null, c = 0, l = Ne.evaluated;
		if (l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0) {
			if (e && typeof e == "object" && !Array.isArray(e)) {
				let r;
				if ((e.mode === void 0 || !n.call(e, "mode")) && (r = "mode") || (e.values === void 0 || !n.call(e, "values")) && (r = "values") || (e.source_session_revision === void 0 || !n.call(e, "source_session_revision")) && (r = "source_session_revision")) return Ne.errors = [{
					instancePath: t,
					schemaPath: "#/required",
					keyword: "required",
					params: { missingProperty: r }
				}], !1;
				{
					let r = c;
					for (let n of Object.keys(e)) if (n !== "mode" && n !== "source_session_revision" && n !== "values") return Ne.errors = [{
						instancePath: t,
						schemaPath: "#/additionalProperties",
						keyword: "additionalProperties",
						params: { additionalProperty: n }
					}], !1;
					if (r === c) {
						if (e.mode !== void 0 && n.call(e, "mode")) {
							let n = e.mode, r = c;
							if (typeof n != "string") return Ne.errors = [{
								instancePath: t + "/mode",
								schemaPath: "#/properties/mode/type",
								keyword: "type",
								params: { type: "string" }
							}], !1;
							if (n !== "create_from_review") return Ne.errors = [{
								instancePath: t + "/mode",
								schemaPath: "#/properties/mode/const",
								keyword: "const",
								params: { allowedValue: "create_from_review" }
							}], !1;
							var u = r === c;
						} else var u = !0;
						if (u) {
							if (e.source_session_revision !== void 0 && n.call(e, "source_session_revision")) {
								let n = e.source_session_revision, r = c;
								if (typeof n != "number" || n % 1 || isNaN(n) || !isFinite(n)) return Ne.errors = [{
									instancePath: t + "/source_session_revision",
									schemaPath: "#/properties/source_session_revision/type",
									keyword: "type",
									params: { type: "integer" }
								}], !1;
								if (c === r && typeof n == "number" && isFinite(n)) {
									if (n > 2147483647 || isNaN(n)) return Ne.errors = [{
										instancePath: t + "/source_session_revision",
										schemaPath: "#/properties/source_session_revision/maximum",
										keyword: "maximum",
										params: {
											comparison: "<=",
											limit: 2147483647
										}
									}], !1;
									if (n < 0 || isNaN(n)) return Ne.errors = [{
										instancePath: t + "/source_session_revision",
										schemaPath: "#/properties/source_session_revision/minimum",
										keyword: "minimum",
										params: {
											comparison: ">=",
											limit: 0
										}
									}], !1;
								}
								var u = r === c;
							} else var u = !0;
							if (u) {
								if (e.values !== void 0 && n.call(e, "values")) {
									let n = c;
									E(e.values, {
										instancePath: t + "/values",
										parentData: e,
										parentDataProperty: "values",
										rootData: a,
										dynamicAnchors: o
									}) || (s = s === null ? E.errors : s.concat(E.errors), c = s.length);
									var u = n === c;
								} else var u = !0;
							}
						}
					}
				}
			} else return Ne.errors = [{
				instancePath: t,
				schemaPath: "#/type",
				keyword: "type",
				params: { type: "object" }
			}], !1;
		}
		return Ne.errors = s, c === 0;
	}
	Ne.evaluated = {
		props: !0,
		dynamicProps: !1,
		dynamicItems: !1
	};
	function Pe(e, { instancePath: t = "", parentData: r, parentDataProperty: i, rootData: a = e, dynamicAnchors: o = {} } = {}) {
		let s = Pe.evaluated;
		if (s.dynamicProps && (s.props = void 0), s.dynamicItems && (s.items = void 0), e && typeof e == "object" && !Array.isArray(e)) {
			let r;
			if ((e.mode === void 0 || !n.call(e, "mode")) && (r = "mode") || (e.lead_id === void 0 || !n.call(e, "lead_id")) && (r = "lead_id") || (e.expected_revision === void 0 || !n.call(e, "expected_revision")) && (r = "expected_revision")) return Pe.errors = [{
				instancePath: t,
				schemaPath: "#/required",
				keyword: "required",
				params: { missingProperty: r }
			}], !1;
			for (let n of Object.keys(e)) if (n !== "expected_revision" && n !== "lead_id" && n !== "mode") return Pe.errors = [{
				instancePath: t,
				schemaPath: "#/additionalProperties",
				keyword: "additionalProperties",
				params: { additionalProperty: n }
			}], !1;
			if (e.expected_revision !== void 0 && n.call(e, "expected_revision")) {
				let n = e.expected_revision;
				if (typeof n != "number" || n % 1 || isNaN(n) || !isFinite(n)) return Pe.errors = [{
					instancePath: t + "/expected_revision",
					schemaPath: "#/properties/expected_revision/type",
					keyword: "type",
					params: { type: "integer" }
				}], !1;
				if (typeof n == "number" && isFinite(n)) {
					if (n > 2147483647 || isNaN(n)) return Pe.errors = [{
						instancePath: t + "/expected_revision",
						schemaPath: "#/properties/expected_revision/maximum",
						keyword: "maximum",
						params: {
							comparison: "<=",
							limit: 2147483647
						}
					}], !1;
					if (n < 0 || isNaN(n)) return Pe.errors = [{
						instancePath: t + "/expected_revision",
						schemaPath: "#/properties/expected_revision/minimum",
						keyword: "minimum",
						params: {
							comparison: ">=",
							limit: 0
						}
					}], !1;
				}
				var c = !0;
			} else var c = !0;
			if (c) {
				if (e.lead_id !== void 0 && n.call(e, "lead_id")) {
					let n = e.lead_id;
					if (typeof n == "string") {
						if (!u.test(n)) return Pe.errors = [{
							instancePath: t + "/lead_id",
							schemaPath: "#/properties/lead_id/pattern",
							keyword: "pattern",
							params: { pattern: "^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$" }
						}], !1;
					} else return Pe.errors = [{
						instancePath: t + "/lead_id",
						schemaPath: "#/properties/lead_id/type",
						keyword: "type",
						params: { type: "string" }
					}], !1;
					var c = !0;
				} else var c = !0;
				if (c) {
					if (e.mode !== void 0 && n.call(e, "mode")) {
						let n = e.mode;
						if (typeof n != "string") return Pe.errors = [{
							instancePath: t + "/mode",
							schemaPath: "#/properties/mode/type",
							keyword: "type",
							params: { type: "string" }
						}], !1;
						if (n !== "preserve_existing") return Pe.errors = [{
							instancePath: t + "/mode",
							schemaPath: "#/properties/mode/const",
							keyword: "const",
							params: { allowedValue: "preserve_existing" }
						}], !1;
						var c = !0;
					} else var c = !0;
				}
			}
		} else return Pe.errors = [{
			instancePath: t,
			schemaPath: "#/type",
			keyword: "type",
			params: { type: "object" }
		}], !1;
		return Pe.errors = null, !0;
	}
	Pe.evaluated = {
		props: !0,
		dynamicProps: !1,
		dynamicItems: !1
	};
	function D(e, { instancePath: t = "", parentData: r, parentDataProperty: a, rootData: o = e, dynamicAnchors: s = {} } = {}) {
		let c = null, d = 0, f = D.evaluated;
		if (f.dynamicProps && (f.props = void 0), f.dynamicItems && (f.items = void 0), d === 0) {
			if (e && typeof e == "object" && !Array.isArray(e)) {
				let r;
				if ((e.review_id === void 0 || !n.call(e, "review_id")) && (r = "review_id") || (e.draft_id === void 0 || !n.call(e, "draft_id")) && (r = "draft_id") || (e.session_id === void 0 || !n.call(e, "session_id")) && (r = "session_id") || (e.draft_revision === void 0 || !n.call(e, "draft_revision")) && (r = "draft_revision") || (e.ref === void 0 || !n.call(e, "ref")) && (r = "ref") || (e.resource_id === void 0 || !n.call(e, "resource_id")) && (r = "resource_id") || (e.starts_at_utc === void 0 || !n.call(e, "starts_at_utc")) && (r = "starts_at_utc") || (e.ends_at_utc === void 0 || !n.call(e, "ends_at_utc")) && (r = "ends_at_utc") || (e.local_start === void 0 || !n.call(e, "local_start")) && (r = "local_start") || (e.venue_label === void 0 || !n.call(e, "venue_label")) && (r = "venue_label") || (e.rules_version === void 0 || !n.call(e, "rules_version")) && (r = "rules_version") || (e.eligibility_version === void 0 || !n.call(e, "eligibility_version")) && (r = "eligibility_version") || (e.store_generation === void 0 || !n.call(e, "store_generation")) && (r = "store_generation") || (e.operation_key === void 0 || !n.call(e, "operation_key")) && (r = "operation_key") || (e.issued_at === void 0 || !n.call(e, "issued_at")) && (r = "issued_at") || (e.expires_at === void 0 || !n.call(e, "expires_at")) && (r = "expires_at") || (e.lead_change === void 0 || !n.call(e, "lead_change")) && (r = "lead_change") || (e.state === void 0 || !n.call(e, "state")) && (r = "state")) return D.errors = [{
					instancePath: t,
					schemaPath: "#/required",
					keyword: "required",
					params: { missingProperty: r }
				}], !1;
				{
					let r = d;
					for (let r of Object.keys(e)) if (!n.call(De.properties, r)) return D.errors = [{
						instancePath: t,
						schemaPath: "#/additionalProperties",
						keyword: "additionalProperties",
						params: { additionalProperty: r }
					}], !1;
					if (r === d) {
						if (e.appointment_type !== void 0 && n.call(e, "appointment_type")) {
							let n = e.appointment_type, r = d;
							if (typeof n != "string") return D.errors = [{
								instancePath: t + "/appointment_type",
								schemaPath: "#/properties/appointment_type/type",
								keyword: "type",
								params: { type: "string" }
							}], !1;
							if (n !== "viewing") return D.errors = [{
								instancePath: t + "/appointment_type",
								schemaPath: "#/properties/appointment_type/const",
								keyword: "const",
								params: { allowedValue: "viewing" }
							}], !1;
							var p = r === d;
						} else var p = !0;
						if (p) {
							if (e.draft_id !== void 0 && n.call(e, "draft_id")) {
								let n = e.draft_id, r = d;
								if (d === r) {
									if (typeof n == "string") {
										if (!u.test(n)) return D.errors = [{
											instancePath: t + "/draft_id",
											schemaPath: "#/properties/draft_id/pattern",
											keyword: "pattern",
											params: { pattern: "^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$" }
										}], !1;
									} else return D.errors = [{
										instancePath: t + "/draft_id",
										schemaPath: "#/properties/draft_id/type",
										keyword: "type",
										params: { type: "string" }
									}], !1;
								}
								var p = r === d;
							} else var p = !0;
							if (p) {
								if (e.draft_revision !== void 0 && n.call(e, "draft_revision")) {
									let n = e.draft_revision, r = d;
									if (typeof n != "number" || n % 1 || isNaN(n) || !isFinite(n)) return D.errors = [{
										instancePath: t + "/draft_revision",
										schemaPath: "#/properties/draft_revision/type",
										keyword: "type",
										params: { type: "integer" }
									}], !1;
									if (d === r && typeof n == "number" && isFinite(n)) {
										if (n > 2147483647 || isNaN(n)) return D.errors = [{
											instancePath: t + "/draft_revision",
											schemaPath: "#/properties/draft_revision/maximum",
											keyword: "maximum",
											params: {
												comparison: "<=",
												limit: 2147483647
											}
										}], !1;
										if (n < 0 || isNaN(n)) return D.errors = [{
											instancePath: t + "/draft_revision",
											schemaPath: "#/properties/draft_revision/minimum",
											keyword: "minimum",
											params: {
												comparison: ">=",
												limit: 0
											}
										}], !1;
									}
									var p = r === d;
								} else var p = !0;
								if (p) {
									if (e.eligibility_version !== void 0 && n.call(e, "eligibility_version")) {
										let n = e.eligibility_version, r = d;
										if (d === r) {
											if (typeof n == "string") {
												if (h(n) > 200) return D.errors = [{
													instancePath: t + "/eligibility_version",
													schemaPath: "#/properties/eligibility_version/maxLength",
													keyword: "maxLength",
													params: { limit: 200 }
												}], !1;
												if (h(n) < 1) return D.errors = [{
													instancePath: t + "/eligibility_version",
													schemaPath: "#/properties/eligibility_version/minLength",
													keyword: "minLength",
													params: { limit: 1 }
												}], !1;
											} else return D.errors = [{
												instancePath: t + "/eligibility_version",
												schemaPath: "#/properties/eligibility_version/type",
												keyword: "type",
												params: { type: "string" }
											}], !1;
										}
										var p = r === d;
									} else var p = !0;
									if (p) {
										if (e.ends_at_utc !== void 0 && n.call(e, "ends_at_utc")) {
											let n = e.ends_at_utc, r = d;
											if (d === r) {
												if (typeof n == "string") {
													if (!i.test(n)) return D.errors = [{
														instancePath: t + "/ends_at_utc",
														schemaPath: "#/properties/ends_at_utc/pattern",
														keyword: "pattern",
														params: { pattern: "^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}(?:\\.\\d{1,6})?Z$" }
													}], !1;
												} else return D.errors = [{
													instancePath: t + "/ends_at_utc",
													schemaPath: "#/properties/ends_at_utc/type",
													keyword: "type",
													params: { type: "string" }
												}], !1;
											}
											var p = r === d;
										} else var p = !0;
										if (p) {
											if (e.expires_at !== void 0 && n.call(e, "expires_at")) {
												let n = e.expires_at, r = d;
												if (d === r) {
													if (typeof n == "string") {
														if (!i.test(n)) return D.errors = [{
															instancePath: t + "/expires_at",
															schemaPath: "#/properties/expires_at/pattern",
															keyword: "pattern",
															params: { pattern: "^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}(?:\\.\\d{1,6})?Z$" }
														}], !1;
													} else return D.errors = [{
														instancePath: t + "/expires_at",
														schemaPath: "#/properties/expires_at/type",
														keyword: "type",
														params: { type: "string" }
													}], !1;
												}
												var p = r === d;
											} else var p = !0;
											if (p) {
												if (e.issued_at !== void 0 && n.call(e, "issued_at")) {
													let n = e.issued_at, r = d;
													if (d === r) {
														if (typeof n == "string") {
															if (!i.test(n)) return D.errors = [{
																instancePath: t + "/issued_at",
																schemaPath: "#/properties/issued_at/pattern",
																keyword: "pattern",
																params: { pattern: "^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}(?:\\.\\d{1,6})?Z$" }
															}], !1;
														} else return D.errors = [{
															instancePath: t + "/issued_at",
															schemaPath: "#/properties/issued_at/type",
															keyword: "type",
															params: { type: "string" }
														}], !1;
													}
													var p = r === d;
												} else var p = !0;
												if (p) {
													if (e.lead_change !== void 0 && n.call(e, "lead_change")) {
														let r = e.lead_change, i = d;
														if (d === i) {
															if (r && typeof r == "object" && !Array.isArray(r)) {
																let i;
																if ((r.mode === void 0 || !n.call(r, "mode")) && (i = "mode")) return D.errors = [{
																	instancePath: t + "/lead_change",
																	schemaPath: "#/properties/lead_change/required",
																	keyword: "required",
																	params: { missingProperty: i }
																}], !1;
																if (r.mode !== void 0 && n.call(r, "mode")) {
																	let e = d;
																	if (typeof r.mode != "string") return D.errors = [{
																		instancePath: t + "/lead_change/mode",
																		schemaPath: "#/properties/lead_change/properties/mode/type",
																		keyword: "type",
																		params: { type: "string" }
																	}], !1;
																	var m = e === d;
																} else var m = !0;
																if (m) {
																	let n = r.mode;
																	if (typeof n == "string") {
																		if (n === "create_from_review") {
																			Ne(r, {
																				instancePath: t + "/lead_change",
																				parentData: e,
																				parentDataProperty: "lead_change",
																				rootData: o,
																				dynamicAnchors: s
																			}) || (c = c === null ? Ne.errors : c.concat(Ne.errors), d = c.length);
																			var _ = !0;
																		} else if (n === "preserve_existing") Pe(r, {
																			instancePath: t + "/lead_change",
																			parentData: e,
																			parentDataProperty: "lead_change",
																			rootData: o,
																			dynamicAnchors: s
																		}) || (c = c === null ? Pe.errors : c.concat(Pe.errors), d = c.length), _ !== !0 && (_ = !0);
																		else return D.errors = [{
																			instancePath: t + "/lead_change",
																			schemaPath: "#/properties/lead_change/discriminator",
																			keyword: "discriminator",
																			params: {
																				error: "mapping",
																				tag: "mode",
																				tagValue: n
																			}
																		}], !1;
																	} else return D.errors = [{
																		instancePath: t + "/lead_change",
																		schemaPath: "#/properties/lead_change/discriminator",
																		keyword: "discriminator",
																		params: {
																			error: "tag",
																			tag: "mode",
																			tagValue: n
																		}
																	}], !1;
																}
															} else return D.errors = [{
																instancePath: t + "/lead_change",
																schemaPath: "#/properties/lead_change/type",
																keyword: "type",
																params: { type: "object" }
															}], !1;
														}
														var p = i === d;
													} else var p = !0;
													if (p) {
														if (e.lead_effect !== void 0 && n.call(e, "lead_effect")) {
															let n = e.lead_effect, r = d;
															if (typeof n != "string") return D.errors = [{
																instancePath: t + "/lead_effect",
																schemaPath: "#/properties/lead_effect/type",
																keyword: "type",
																params: { type: "string" }
															}], !1;
															if (n !== "save_local_enquiry") return D.errors = [{
																instancePath: t + "/lead_effect",
																schemaPath: "#/properties/lead_effect/const",
																keyword: "const",
																params: { allowedValue: "save_local_enquiry" }
															}], !1;
															var p = r === d;
														} else var p = !0;
														if (p) {
															if (e.local_start !== void 0 && n.call(e, "local_start")) {
																let n = e.local_start, r = d;
																if (d === r) {
																	if (typeof n == "string") {
																		if (h(n) > 40) return D.errors = [{
																			instancePath: t + "/local_start",
																			schemaPath: "#/properties/local_start/maxLength",
																			keyword: "maxLength",
																			params: { limit: 40 }
																		}], !1;
																	} else return D.errors = [{
																		instancePath: t + "/local_start",
																		schemaPath: "#/properties/local_start/type",
																		keyword: "type",
																		params: { type: "string" }
																	}], !1;
																}
																var p = r === d;
															} else var p = !0;
															if (p) {
																if (e.operation_key !== void 0 && n.call(e, "operation_key")) {
																	let n = e.operation_key, r = d;
																	if (d === r) {
																		if (typeof n == "string") {
																			if (!g.test(n)) return D.errors = [{
																				instancePath: t + "/operation_key",
																				schemaPath: "#/properties/operation_key/pattern",
																				keyword: "pattern",
																				params: { pattern: "^[A-Za-z0-9_-]{43}$" }
																			}], !1;
																		} else return D.errors = [{
																			instancePath: t + "/operation_key",
																			schemaPath: "#/properties/operation_key/type",
																			keyword: "type",
																			params: { type: "string" }
																		}], !1;
																	}
																	var p = r === d;
																} else var p = !0;
																if (p) {
																	if (e.ref !== void 0 && n.call(e, "ref")) {
																		let n = d;
																		l(e.ref, {
																			instancePath: t + "/ref",
																			parentData: e,
																			parentDataProperty: "ref",
																			rootData: o,
																			dynamicAnchors: s
																		}) || (c = c === null ? l.errors : c.concat(l.errors), d = c.length);
																		var p = n === d;
																	} else var p = !0;
																	if (p) {
																		if (e.resource_id !== void 0 && n.call(e, "resource_id")) {
																			let n = e.resource_id, r = d;
																			if (d === r) {
																				if (typeof n == "string") {
																					if (!u.test(n)) return D.errors = [{
																						instancePath: t + "/resource_id",
																						schemaPath: "#/properties/resource_id/pattern",
																						keyword: "pattern",
																						params: { pattern: "^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$" }
																					}], !1;
																				} else return D.errors = [{
																					instancePath: t + "/resource_id",
																					schemaPath: "#/properties/resource_id/type",
																					keyword: "type",
																					params: { type: "string" }
																				}], !1;
																			}
																			var p = r === d;
																		} else var p = !0;
																		if (p) {
																			if (e.review_id !== void 0 && n.call(e, "review_id")) {
																				let n = e.review_id, r = d;
																				if (d === r) {
																					if (typeof n == "string") {
																						if (!u.test(n)) return D.errors = [{
																							instancePath: t + "/review_id",
																							schemaPath: "#/properties/review_id/pattern",
																							keyword: "pattern",
																							params: { pattern: "^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$" }
																						}], !1;
																					} else return D.errors = [{
																						instancePath: t + "/review_id",
																						schemaPath: "#/properties/review_id/type",
																						keyword: "type",
																						params: { type: "string" }
																					}], !1;
																				}
																				var p = r === d;
																			} else var p = !0;
																			if (p) {
																				if (e.rules_version !== void 0 && n.call(e, "rules_version")) {
																					let n = e.rules_version, r = d;
																					if (d === r) {
																						if (typeof n == "string") {
																							if (h(n) > 200) return D.errors = [{
																								instancePath: t + "/rules_version",
																								schemaPath: "#/properties/rules_version/maxLength",
																								keyword: "maxLength",
																								params: { limit: 200 }
																							}], !1;
																							if (h(n) < 1) return D.errors = [{
																								instancePath: t + "/rules_version",
																								schemaPath: "#/properties/rules_version/minLength",
																								keyword: "minLength",
																								params: { limit: 1 }
																							}], !1;
																						} else return D.errors = [{
																							instancePath: t + "/rules_version",
																							schemaPath: "#/properties/rules_version/type",
																							keyword: "type",
																							params: { type: "string" }
																						}], !1;
																					}
																					var p = r === d;
																				} else var p = !0;
																				if (p) {
																					if (e.session_id !== void 0 && n.call(e, "session_id")) {
																						let n = e.session_id, r = d;
																						if (d === r) {
																							if (typeof n == "string") {
																								if (!u.test(n)) return D.errors = [{
																									instancePath: t + "/session_id",
																									schemaPath: "#/properties/session_id/pattern",
																									keyword: "pattern",
																									params: { pattern: "^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$" }
																								}], !1;
																							} else return D.errors = [{
																								instancePath: t + "/session_id",
																								schemaPath: "#/properties/session_id/type",
																								keyword: "type",
																								params: { type: "string" }
																							}], !1;
																						}
																						var p = r === d;
																					} else var p = !0;
																					if (p) {
																						if (e.simulation !== void 0 && n.call(e, "simulation")) {
																							let n = e.simulation, r = d;
																							if (typeof n != "boolean") return D.errors = [{
																								instancePath: t + "/simulation",
																								schemaPath: "#/properties/simulation/type",
																								keyword: "type",
																								params: { type: "boolean" }
																							}], !1;
																							if (!0 !== n) return D.errors = [{
																								instancePath: t + "/simulation",
																								schemaPath: "#/properties/simulation/const",
																								keyword: "const",
																								params: { allowedValue: !0 }
																							}], !1;
																							var p = r === d;
																						} else var p = !0;
																						if (p) {
																							if (e.starts_at_utc !== void 0 && n.call(e, "starts_at_utc")) {
																								let n = e.starts_at_utc, r = d;
																								if (d === r) {
																									if (typeof n == "string") {
																										if (!i.test(n)) return D.errors = [{
																											instancePath: t + "/starts_at_utc",
																											schemaPath: "#/properties/starts_at_utc/pattern",
																											keyword: "pattern",
																											params: { pattern: "^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}(?:\\.\\d{1,6})?Z$" }
																										}], !1;
																									} else return D.errors = [{
																										instancePath: t + "/starts_at_utc",
																										schemaPath: "#/properties/starts_at_utc/type",
																										keyword: "type",
																										params: { type: "string" }
																									}], !1;
																								}
																								var p = r === d;
																							} else var p = !0;
																							if (p) {
																								if (e.state !== void 0 && n.call(e, "state")) {
																									let n = e.state, r = d;
																									if (typeof n != "string") return D.errors = [{
																										instancePath: t + "/state",
																										schemaPath: "#/properties/state/type",
																										keyword: "type",
																										params: { type: "string" }
																									}], !1;
																									if (n !== "valid" && n !== "invalidated" && n !== "expired" && n !== "submitted" && n !== "consumed") return D.errors = [{
																										instancePath: t + "/state",
																										schemaPath: "#/properties/state/enum",
																										keyword: "enum",
																										params: { allowedValues: De.properties.state.enum }
																									}], !1;
																									var p = r === d;
																								} else var p = !0;
																								if (p) {
																									if (e.store_generation !== void 0 && n.call(e, "store_generation")) {
																										let n = e.store_generation, r = d;
																										if (d === r) {
																											if (typeof n == "string") {
																												if (!u.test(n)) return D.errors = [{
																													instancePath: t + "/store_generation",
																													schemaPath: "#/properties/store_generation/pattern",
																													keyword: "pattern",
																													params: { pattern: "^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$" }
																												}], !1;
																											} else return D.errors = [{
																												instancePath: t + "/store_generation",
																												schemaPath: "#/properties/store_generation/type",
																												keyword: "type",
																												params: { type: "string" }
																											}], !1;
																										}
																										var p = r === d;
																									} else var p = !0;
																									if (p) {
																										if (e.timezone !== void 0 && n.call(e, "timezone")) {
																											let n = e.timezone, r = d;
																											if (typeof n != "string") return D.errors = [{
																												instancePath: t + "/timezone",
																												schemaPath: "#/properties/timezone/type",
																												keyword: "type",
																												params: { type: "string" }
																											}], !1;
																											if (n !== "Asia/Dubai") return D.errors = [{
																												instancePath: t + "/timezone",
																												schemaPath: "#/properties/timezone/const",
																												keyword: "const",
																												params: { allowedValue: "Asia/Dubai" }
																											}], !1;
																											var p = r === d;
																										} else var p = !0;
																										if (p) {
																											if (e.venue_label !== void 0 && n.call(e, "venue_label")) {
																												let n = e.venue_label, r = d;
																												if (typeof n != "string") return D.errors = [{
																													instancePath: t + "/venue_label",
																													schemaPath: "#/properties/venue_label/type",
																													keyword: "type",
																													params: { type: "string" }
																												}], !1;
																												if (n !== "Simulated local viewing — no real venue or reservation.") return D.errors = [{
																													instancePath: t + "/venue_label",
																													schemaPath: "#/properties/venue_label/const",
																													keyword: "const",
																													params: { allowedValue: "Simulated local viewing — no real venue or reservation." }
																												}], !1;
																												var p = r === d;
																											} else var p = !0;
																										}
																									}
																								}
																							}
																						}
																					}
																				}
																			}
																		}
																	}
																}
															}
														}
													}
												}
											}
										}
									}
								}
							}
						}
					}
				}
			} else return D.errors = [{
				instancePath: t,
				schemaPath: "#/type",
				keyword: "type",
				params: { type: "object" }
			}], !1;
		}
		return D.errors = c, d === 0;
	}
	D.evaluated = {
		props: !0,
		dynamicProps: !1,
		dynamicItems: !1
	};
	function Fe(e, { instancePath: t = "", parentData: r, parentDataProperty: a, rootData: o = e, dynamicAnchors: s = {} } = {}) {
		let c = null, l = 0, d = Fe.evaluated;
		if (d.dynamicProps && (d.props = void 0), d.dynamicItems && (d.items = void 0), l === 0) {
			if (e && typeof e == "object" && !Array.isArray(e)) {
				let r;
				if ((e.state === void 0 || !n.call(e, "state")) && (r = "state") || (e.booking_id === void 0 || !n.call(e, "booking_id")) && (r = "booking_id") || (e.review === void 0 || !n.call(e, "review")) && (r = "review") || (e.confirmed_at === void 0 || !n.call(e, "confirmed_at")) && (r = "confirmed_at")) return Fe.errors = [{
					instancePath: t,
					schemaPath: "#/required",
					keyword: "required",
					params: { missingProperty: r }
				}], !1;
				{
					let r = l;
					for (let n of Object.keys(e)) if (n !== "booking_id" && n !== "confirmed_at" && n !== "review" && n !== "state") return Fe.errors = [{
						instancePath: t,
						schemaPath: "#/additionalProperties",
						keyword: "additionalProperties",
						params: { additionalProperty: n }
					}], !1;
					if (r === l) {
						if (e.booking_id !== void 0 && n.call(e, "booking_id")) {
							let n = e.booking_id, r = l;
							if (l === r) {
								if (typeof n == "string") {
									if (!u.test(n)) return Fe.errors = [{
										instancePath: t + "/booking_id",
										schemaPath: "#/properties/booking_id/pattern",
										keyword: "pattern",
										params: { pattern: "^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$" }
									}], !1;
								} else return Fe.errors = [{
									instancePath: t + "/booking_id",
									schemaPath: "#/properties/booking_id/type",
									keyword: "type",
									params: { type: "string" }
								}], !1;
							}
							var f = r === l;
						} else var f = !0;
						if (f) {
							if (e.confirmed_at !== void 0 && n.call(e, "confirmed_at")) {
								let n = e.confirmed_at, r = l;
								if (l === r) {
									if (typeof n == "string") {
										if (!i.test(n)) return Fe.errors = [{
											instancePath: t + "/confirmed_at",
											schemaPath: "#/properties/confirmed_at/pattern",
											keyword: "pattern",
											params: { pattern: "^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}(?:\\.\\d{1,6})?Z$" }
										}], !1;
									} else return Fe.errors = [{
										instancePath: t + "/confirmed_at",
										schemaPath: "#/properties/confirmed_at/type",
										keyword: "type",
										params: { type: "string" }
									}], !1;
								}
								var f = r === l;
							} else var f = !0;
							if (f) {
								if (e.review !== void 0 && n.call(e, "review")) {
									let n = l;
									D(e.review, {
										instancePath: t + "/review",
										parentData: e,
										parentDataProperty: "review",
										rootData: o,
										dynamicAnchors: s
									}) || (c = c === null ? D.errors : c.concat(D.errors), l = c.length);
									var f = n === l;
								} else var f = !0;
								if (f) {
									if (e.state !== void 0 && n.call(e, "state")) {
										let n = e.state, r = l;
										if (typeof n != "string") return Fe.errors = [{
											instancePath: t + "/state",
											schemaPath: "#/properties/state/type",
											keyword: "type",
											params: { type: "string" }
										}], !1;
										if (n !== "confirmed_simulated") return Fe.errors = [{
											instancePath: t + "/state",
											schemaPath: "#/properties/state/const",
											keyword: "const",
											params: { allowedValue: "confirmed_simulated" }
										}], !1;
										var f = r === l;
									} else var f = !0;
								}
							}
						}
					}
				}
			} else return Fe.errors = [{
				instancePath: t,
				schemaPath: "#/type",
				keyword: "type",
				params: { type: "object" }
			}], !1;
		}
		return Fe.errors = c, l === 0;
	}
	Fe.evaluated = {
		props: !0,
		dynamicProps: !1,
		dynamicItems: !1
	};
	function O(e, { instancePath: t = "", parentData: r, parentDataProperty: a, rootData: o = e, dynamicAnchors: s = {} } = {}) {
		let c = O.evaluated;
		if (c.dynamicProps && (c.props = void 0), c.dynamicItems && (c.items = void 0), e && typeof e == "object" && !Array.isArray(e)) {
			let r;
			if ((e.state === void 0 || !n.call(e, "state")) && (r = "state") || (e.store_generation === void 0 || !n.call(e, "store_generation")) && (r = "store_generation") || (e.observed_at === void 0 || !n.call(e, "observed_at")) && (r = "observed_at") || (e.canonical_version === void 0 || !n.call(e, "canonical_version")) && (r = "canonical_version") || (e.exported_version === void 0 || !n.call(e, "exported_version")) && (r = "exported_version")) return O.errors = [{
				instancePath: t,
				schemaPath: "#/required",
				keyword: "required",
				params: { missingProperty: r }
			}], !1;
			for (let n of Object.keys(e)) if (n !== "canonical_version" && n !== "exported_version" && n !== "observed_at" && n !== "state" && n !== "store_generation" && n !== "version_scope") return O.errors = [{
				instancePath: t,
				schemaPath: "#/additionalProperties",
				keyword: "additionalProperties",
				params: { additionalProperty: n }
			}], !1;
			if (e.canonical_version !== void 0 && n.call(e, "canonical_version")) {
				let n = e.canonical_version;
				if (typeof n != "number" || n % 1 || isNaN(n) || !isFinite(n)) return O.errors = [{
					instancePath: t + "/canonical_version",
					schemaPath: "#/properties/canonical_version/type",
					keyword: "type",
					params: { type: "integer" }
				}], !1;
				if (typeof n == "number" && isFinite(n)) {
					if (n > 2147483647 || isNaN(n)) return O.errors = [{
						instancePath: t + "/canonical_version",
						schemaPath: "#/properties/canonical_version/maximum",
						keyword: "maximum",
						params: {
							comparison: "<=",
							limit: 2147483647
						}
					}], !1;
					if (n < 0 || isNaN(n)) return O.errors = [{
						instancePath: t + "/canonical_version",
						schemaPath: "#/properties/canonical_version/minimum",
						keyword: "minimum",
						params: {
							comparison: ">=",
							limit: 0
						}
					}], !1;
				}
				var l = !0;
			} else var l = !0;
			if (l) {
				if (e.exported_version !== void 0 && n.call(e, "exported_version")) {
					let n = e.exported_version;
					if (typeof n != "number" || n % 1 || isNaN(n) || !isFinite(n)) return O.errors = [{
						instancePath: t + "/exported_version",
						schemaPath: "#/properties/exported_version/type",
						keyword: "type",
						params: { type: "integer" }
					}], !1;
					if (typeof n == "number" && isFinite(n)) {
						if (n > 2147483647 || isNaN(n)) return O.errors = [{
							instancePath: t + "/exported_version",
							schemaPath: "#/properties/exported_version/maximum",
							keyword: "maximum",
							params: {
								comparison: "<=",
								limit: 2147483647
							}
						}], !1;
						if (n < 0 || isNaN(n)) return O.errors = [{
							instancePath: t + "/exported_version",
							schemaPath: "#/properties/exported_version/minimum",
							keyword: "minimum",
							params: {
								comparison: ">=",
								limit: 0
							}
						}], !1;
					}
					var l = !0;
				} else var l = !0;
				if (l) {
					if (e.observed_at !== void 0 && n.call(e, "observed_at")) {
						let n = e.observed_at;
						if (typeof n == "string") {
							if (!i.test(n)) return O.errors = [{
								instancePath: t + "/observed_at",
								schemaPath: "#/properties/observed_at/pattern",
								keyword: "pattern",
								params: { pattern: "^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}(?:\\.\\d{1,6})?Z$" }
							}], !1;
						} else return O.errors = [{
							instancePath: t + "/observed_at",
							schemaPath: "#/properties/observed_at/type",
							keyword: "type",
							params: { type: "string" }
						}], !1;
						var l = !0;
					} else var l = !0;
					if (l) {
						if (e.state !== void 0 && n.call(e, "state")) {
							let n = e.state;
							if (typeof n != "string") return O.errors = [{
								instancePath: t + "/state",
								schemaPath: "#/properties/state/type",
								keyword: "type",
								params: { type: "string" }
							}], !1;
							if (n !== "current") return O.errors = [{
								instancePath: t + "/state",
								schemaPath: "#/properties/state/const",
								keyword: "const",
								params: { allowedValue: "current" }
							}], !1;
							var l = !0;
						} else var l = !0;
						if (l) {
							if (e.store_generation !== void 0 && n.call(e, "store_generation")) {
								let n = e.store_generation;
								if (typeof n == "string") {
									if (!u.test(n)) return O.errors = [{
										instancePath: t + "/store_generation",
										schemaPath: "#/properties/store_generation/pattern",
										keyword: "pattern",
										params: { pattern: "^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$" }
									}], !1;
								} else return O.errors = [{
									instancePath: t + "/store_generation",
									schemaPath: "#/properties/store_generation/type",
									keyword: "type",
									params: { type: "string" }
								}], !1;
								var l = !0;
							} else var l = !0;
							if (l) {
								if (e.version_scope !== void 0 && n.call(e, "version_scope")) {
									let n = e.version_scope;
									if (typeof n != "string") return O.errors = [{
										instancePath: t + "/version_scope",
										schemaPath: "#/properties/version_scope/type",
										keyword: "type",
										params: { type: "string" }
									}], !1;
									if (n !== "global_projection") return O.errors = [{
										instancePath: t + "/version_scope",
										schemaPath: "#/properties/version_scope/const",
										keyword: "const",
										params: { allowedValue: "global_projection" }
									}], !1;
									var l = !0;
								} else var l = !0;
							}
						}
					}
				}
			}
		} else return O.errors = [{
			instancePath: t,
			schemaPath: "#/type",
			keyword: "type",
			params: { type: "object" }
		}], !1;
		return O.errors = null, !0;
	}
	O.evaluated = {
		props: !0,
		dynamicProps: !1,
		dynamicItems: !1
	};
	var Ie = {
		additionalProperties: !1,
		properties: {
			canonical_version: {
				maximum: 2147483647,
				minimum: 0,
				title: "Canonical Version",
				type: "integer"
			},
			code: {
				anyOf: [{
					maxLength: 200,
					minLength: 1,
					type: "string"
				}, { type: "null" }],
				title: "Code"
			},
			exported_version: {
				anyOf: [{
					maximum: 2147483647,
					minimum: 0,
					type: "integer"
				}, { type: "null" }],
				title: "Exported Version"
			},
			observed_at: {
				pattern: "^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}(?:\\.\\d{1,6})?Z$",
				title: "Observed At",
				type: "string"
			},
			state: {
				enum: ["pending", "failed"],
				title: "State",
				type: "string"
			},
			store_generation: {
				pattern: "^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$",
				title: "Store Generation",
				type: "string"
			},
			version_scope: {
				const: "global_projection",
				default: "global_projection",
				title: "Version Scope",
				type: "string"
			}
		},
		required: [
			"state",
			"store_generation",
			"observed_at",
			"canonical_version",
			"exported_version",
			"code"
		],
		title: "ExportPending",
		type: "object"
	};
	function k(e, { instancePath: t = "", parentData: r, parentDataProperty: a, rootData: o = e, dynamicAnchors: s = {} } = {}) {
		let c = null, l = 0, d = k.evaluated;
		if (d.dynamicProps && (d.props = void 0), d.dynamicItems && (d.items = void 0), l === 0) {
			if (e && typeof e == "object" && !Array.isArray(e)) {
				let r;
				if ((e.state === void 0 || !n.call(e, "state")) && (r = "state") || (e.store_generation === void 0 || !n.call(e, "store_generation")) && (r = "store_generation") || (e.observed_at === void 0 || !n.call(e, "observed_at")) && (r = "observed_at") || (e.canonical_version === void 0 || !n.call(e, "canonical_version")) && (r = "canonical_version") || (e.exported_version === void 0 || !n.call(e, "exported_version")) && (r = "exported_version") || (e.code === void 0 || !n.call(e, "code")) && (r = "code")) return k.errors = [{
					instancePath: t,
					schemaPath: "#/required",
					keyword: "required",
					params: { missingProperty: r }
				}], !1;
				{
					let r = l;
					for (let n of Object.keys(e)) if (n !== "canonical_version" && n !== "code" && n !== "exported_version" && n !== "observed_at" && n !== "state" && n !== "store_generation" && n !== "version_scope") return k.errors = [{
						instancePath: t,
						schemaPath: "#/additionalProperties",
						keyword: "additionalProperties",
						params: { additionalProperty: n }
					}], !1;
					if (r === l) {
						if (e.canonical_version !== void 0 && n.call(e, "canonical_version")) {
							let n = e.canonical_version, r = l;
							if (typeof n != "number" || n % 1 || isNaN(n) || !isFinite(n)) return k.errors = [{
								instancePath: t + "/canonical_version",
								schemaPath: "#/properties/canonical_version/type",
								keyword: "type",
								params: { type: "integer" }
							}], !1;
							if (l === r && typeof n == "number" && isFinite(n)) {
								if (n > 2147483647 || isNaN(n)) return k.errors = [{
									instancePath: t + "/canonical_version",
									schemaPath: "#/properties/canonical_version/maximum",
									keyword: "maximum",
									params: {
										comparison: "<=",
										limit: 2147483647
									}
								}], !1;
								if (n < 0 || isNaN(n)) return k.errors = [{
									instancePath: t + "/canonical_version",
									schemaPath: "#/properties/canonical_version/minimum",
									keyword: "minimum",
									params: {
										comparison: ">=",
										limit: 0
									}
								}], !1;
							}
							var f = r === l;
						} else var f = !0;
						if (f) {
							if (e.code !== void 0 && n.call(e, "code")) {
								let n = e.code, r = l, i = l, a = !1, o = l;
								if (l === o) {
									if (typeof n == "string") {
										if (h(n) > 200) {
											let e = {
												instancePath: t + "/code",
												schemaPath: "#/properties/code/anyOf/0/maxLength",
												keyword: "maxLength",
												params: { limit: 200 }
											};
											c === null ? c = [e] : c.push(e), l++;
										} else if (h(n) < 1) {
											let e = {
												instancePath: t + "/code",
												schemaPath: "#/properties/code/anyOf/0/minLength",
												keyword: "minLength",
												params: { limit: 1 }
											};
											c === null ? c = [e] : c.push(e), l++;
										}
									} else {
										let e = {
											instancePath: t + "/code",
											schemaPath: "#/properties/code/anyOf/0/type",
											keyword: "type",
											params: { type: "string" }
										};
										c === null ? c = [e] : c.push(e), l++;
									}
								}
								var p = o === l;
								a ||= p;
								let s = l;
								if (n !== null) {
									let e = {
										instancePath: t + "/code",
										schemaPath: "#/properties/code/anyOf/1/type",
										keyword: "type",
										params: { type: "null" }
									};
									c === null ? c = [e] : c.push(e), l++;
								}
								var p = s === l;
								if (a ||= p, a) l = i, c !== null && (i ? c.length = i : c = null);
								else {
									let e = {
										instancePath: t + "/code",
										schemaPath: "#/properties/code/anyOf",
										keyword: "anyOf",
										params: {}
									};
									return c === null ? c = [e] : c.push(e), l++, k.errors = c, !1;
								}
								var f = r === l;
							} else var f = !0;
							if (f) {
								if (e.exported_version !== void 0 && n.call(e, "exported_version")) {
									let n = e.exported_version, r = l, i = l, a = !1, o = l;
									if (typeof n != "number" || n % 1 || isNaN(n) || !isFinite(n)) {
										let e = {
											instancePath: t + "/exported_version",
											schemaPath: "#/properties/exported_version/anyOf/0/type",
											keyword: "type",
											params: { type: "integer" }
										};
										c === null ? c = [e] : c.push(e), l++;
									}
									if (l === o && typeof n == "number" && isFinite(n)) {
										if (n > 2147483647 || isNaN(n)) {
											let e = {
												instancePath: t + "/exported_version",
												schemaPath: "#/properties/exported_version/anyOf/0/maximum",
												keyword: "maximum",
												params: {
													comparison: "<=",
													limit: 2147483647
												}
											};
											c === null ? c = [e] : c.push(e), l++;
										} else if (n < 0 || isNaN(n)) {
											let e = {
												instancePath: t + "/exported_version",
												schemaPath: "#/properties/exported_version/anyOf/0/minimum",
												keyword: "minimum",
												params: {
													comparison: ">=",
													limit: 0
												}
											};
											c === null ? c = [e] : c.push(e), l++;
										}
									}
									var m = o === l;
									a ||= m;
									let s = l;
									if (n !== null) {
										let e = {
											instancePath: t + "/exported_version",
											schemaPath: "#/properties/exported_version/anyOf/1/type",
											keyword: "type",
											params: { type: "null" }
										};
										c === null ? c = [e] : c.push(e), l++;
									}
									var m = s === l;
									if (a ||= m, a) l = i, c !== null && (i ? c.length = i : c = null);
									else {
										let e = {
											instancePath: t + "/exported_version",
											schemaPath: "#/properties/exported_version/anyOf",
											keyword: "anyOf",
											params: {}
										};
										return c === null ? c = [e] : c.push(e), l++, k.errors = c, !1;
									}
									var f = r === l;
								} else var f = !0;
								if (f) {
									if (e.observed_at !== void 0 && n.call(e, "observed_at")) {
										let n = e.observed_at, r = l;
										if (l === r) {
											if (typeof n == "string") {
												if (!i.test(n)) return k.errors = [{
													instancePath: t + "/observed_at",
													schemaPath: "#/properties/observed_at/pattern",
													keyword: "pattern",
													params: { pattern: "^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}(?:\\.\\d{1,6})?Z$" }
												}], !1;
											} else return k.errors = [{
												instancePath: t + "/observed_at",
												schemaPath: "#/properties/observed_at/type",
												keyword: "type",
												params: { type: "string" }
											}], !1;
										}
										var f = r === l;
									} else var f = !0;
									if (f) {
										if (e.state !== void 0 && n.call(e, "state")) {
											let n = e.state, r = l;
											if (typeof n != "string") return k.errors = [{
												instancePath: t + "/state",
												schemaPath: "#/properties/state/type",
												keyword: "type",
												params: { type: "string" }
											}], !1;
											if (n !== "pending" && n !== "failed") return k.errors = [{
												instancePath: t + "/state",
												schemaPath: "#/properties/state/enum",
												keyword: "enum",
												params: { allowedValues: Ie.properties.state.enum }
											}], !1;
											var f = r === l;
										} else var f = !0;
										if (f) {
											if (e.store_generation !== void 0 && n.call(e, "store_generation")) {
												let n = e.store_generation, r = l;
												if (l === r) {
													if (typeof n == "string") {
														if (!u.test(n)) return k.errors = [{
															instancePath: t + "/store_generation",
															schemaPath: "#/properties/store_generation/pattern",
															keyword: "pattern",
															params: { pattern: "^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$" }
														}], !1;
													} else return k.errors = [{
														instancePath: t + "/store_generation",
														schemaPath: "#/properties/store_generation/type",
														keyword: "type",
														params: { type: "string" }
													}], !1;
												}
												var f = r === l;
											} else var f = !0;
											if (f) {
												if (e.version_scope !== void 0 && n.call(e, "version_scope")) {
													let n = e.version_scope, r = l;
													if (typeof n != "string") return k.errors = [{
														instancePath: t + "/version_scope",
														schemaPath: "#/properties/version_scope/type",
														keyword: "type",
														params: { type: "string" }
													}], !1;
													if (n !== "global_projection") return k.errors = [{
														instancePath: t + "/version_scope",
														schemaPath: "#/properties/version_scope/const",
														keyword: "const",
														params: { allowedValue: "global_projection" }
													}], !1;
													var f = r === l;
												} else var f = !0;
											}
										}
									}
								}
							}
						}
					}
				}
			} else return k.errors = [{
				instancePath: t,
				schemaPath: "#/type",
				keyword: "type",
				params: { type: "object" }
			}], !1;
		}
		return k.errors = c, l === 0;
	}
	k.evaluated = {
		props: !0,
		dynamicProps: !1,
		dynamicItems: !1
	};
	function Le(e, { instancePath: t = "", parentData: r, parentDataProperty: i, rootData: a = e, dynamicAnchors: o = {} } = {}) {
		let s = Le.evaluated;
		if (s.dynamicProps && (s.props = void 0), s.dynamicItems && (s.items = void 0), e && typeof e == "object" && !Array.isArray(e)) {
			let r;
			if ((e.state === void 0 || !n.call(e, "state")) && (r = "state") || (e.lead_id === void 0 || !n.call(e, "lead_id")) && (r = "lead_id") || (e.revision === void 0 || !n.call(e, "revision")) && (r = "revision")) return Le.errors = [{
				instancePath: t,
				schemaPath: "#/required",
				keyword: "required",
				params: { missingProperty: r }
			}], !1;
			for (let n of Object.keys(e)) if (n !== "lead_id" && n !== "revision" && n !== "state") return Le.errors = [{
				instancePath: t,
				schemaPath: "#/additionalProperties",
				keyword: "additionalProperties",
				params: { additionalProperty: n }
			}], !1;
			if (e.lead_id !== void 0 && n.call(e, "lead_id")) {
				let n = e.lead_id;
				if (typeof n == "string") {
					if (!u.test(n)) return Le.errors = [{
						instancePath: t + "/lead_id",
						schemaPath: "#/properties/lead_id/pattern",
						keyword: "pattern",
						params: { pattern: "^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$" }
					}], !1;
				} else return Le.errors = [{
					instancePath: t + "/lead_id",
					schemaPath: "#/properties/lead_id/type",
					keyword: "type",
					params: { type: "string" }
				}], !1;
				var c = !0;
			} else var c = !0;
			if (c) {
				if (e.revision !== void 0 && n.call(e, "revision")) {
					let n = e.revision;
					if (typeof n != "number" || n % 1 || isNaN(n) || !isFinite(n)) return Le.errors = [{
						instancePath: t + "/revision",
						schemaPath: "#/properties/revision/type",
						keyword: "type",
						params: { type: "integer" }
					}], !1;
					if (typeof n == "number" && isFinite(n)) {
						if (n > 2147483647 || isNaN(n)) return Le.errors = [{
							instancePath: t + "/revision",
							schemaPath: "#/properties/revision/maximum",
							keyword: "maximum",
							params: {
								comparison: "<=",
								limit: 2147483647
							}
						}], !1;
						if (n < 0 || isNaN(n)) return Le.errors = [{
							instancePath: t + "/revision",
							schemaPath: "#/properties/revision/minimum",
							keyword: "minimum",
							params: {
								comparison: ">=",
								limit: 0
							}
						}], !1;
					}
					var c = !0;
				} else var c = !0;
				if (c) {
					if (e.state !== void 0 && n.call(e, "state")) {
						let n = e.state;
						if (typeof n != "string") return Le.errors = [{
							instancePath: t + "/state",
							schemaPath: "#/properties/state/type",
							keyword: "type",
							params: { type: "string" }
						}], !1;
						if (n !== "saved") return Le.errors = [{
							instancePath: t + "/state",
							schemaPath: "#/properties/state/const",
							keyword: "const",
							params: { allowedValue: "saved" }
						}], !1;
						var c = !0;
					} else var c = !0;
				}
			}
		} else return Le.errors = [{
			instancePath: t,
			schemaPath: "#/type",
			keyword: "type",
			params: { type: "object" }
		}], !1;
		return Le.errors = null, !0;
	}
	Le.evaluated = {
		props: !0,
		dynamicProps: !1,
		dynamicItems: !1
	};
	function A(e, { instancePath: t = "", parentData: r, parentDataProperty: a, rootData: o = e, dynamicAnchors: s = {} } = {}) {
		let c = null, l = 0, d = A.evaluated;
		if (d.dynamicProps && (d.props = void 0), d.dynamicItems && (d.items = void 0), l === 0) {
			if (e && typeof e == "object" && !Array.isArray(e)) {
				let r;
				if ((e.state === void 0 || !n.call(e, "state")) && (r = "state") || (e.operation_key === void 0 || !n.call(e, "operation_key")) && (r = "operation_key") || (e.review_id === void 0 || !n.call(e, "review_id")) && (r = "review_id") || (e.original_store_generation === void 0 || !n.call(e, "original_store_generation")) && (r = "original_store_generation") || (e.terminal_at === void 0 || !n.call(e, "terminal_at")) && (r = "terminal_at") || (e.replay_valid_until === void 0 || !n.call(e, "replay_valid_until")) && (r = "replay_valid_until") || (e.booking === void 0 || !n.call(e, "booking")) && (r = "booking") || (e.lead === void 0 || !n.call(e, "lead")) && (r = "lead") || (e.csv === void 0 || !n.call(e, "csv")) && (r = "csv")) return A.errors = [{
					instancePath: t,
					schemaPath: "#/required",
					keyword: "required",
					params: { missingProperty: r }
				}], !1;
				{
					let r = l;
					for (let r of Object.keys(e)) if (!n.call(Ee.properties, r)) return A.errors = [{
						instancePath: t,
						schemaPath: "#/additionalProperties",
						keyword: "additionalProperties",
						params: { additionalProperty: r }
					}], !1;
					if (r === l) {
						if (e.booking !== void 0 && n.call(e, "booking")) {
							let n = l;
							Fe(e.booking, {
								instancePath: t + "/booking",
								parentData: e,
								parentDataProperty: "booking",
								rootData: o,
								dynamicAnchors: s
							}) || (c = c === null ? Fe.errors : c.concat(Fe.errors), l = c.length);
							var f = n === l;
						} else var f = !0;
						if (f) {
							if (e.csv !== void 0 && n.call(e, "csv")) {
								let r = e.csv, i = l;
								if (l === i) {
									if (r && typeof r == "object" && !Array.isArray(r)) {
										let i;
										if ((r.state === void 0 || !n.call(r, "state")) && (i = "state")) return A.errors = [{
											instancePath: t + "/csv",
											schemaPath: "#/properties/csv/required",
											keyword: "required",
											params: { missingProperty: i }
										}], !1;
										if (r.state !== void 0 && n.call(r, "state")) {
											let e = l;
											if (typeof r.state != "string") return A.errors = [{
												instancePath: t + "/csv/state",
												schemaPath: "#/properties/csv/properties/state/type",
												keyword: "type",
												params: { type: "string" }
											}], !1;
											var p = e === l;
										} else var p = !0;
										if (p) {
											let n = r.state;
											if (typeof n == "string") {
												if (n === "current") {
													O(r, {
														instancePath: t + "/csv",
														parentData: e,
														parentDataProperty: "csv",
														rootData: o,
														dynamicAnchors: s
													}) || (c = c === null ? O.errors : c.concat(O.errors), l = c.length);
													var m = !0;
												} else if (n === "pending") k(r, {
													instancePath: t + "/csv",
													parentData: e,
													parentDataProperty: "csv",
													rootData: o,
													dynamicAnchors: s
												}) || (c = c === null ? k.errors : c.concat(k.errors), l = c.length), m !== !0 && (m = !0);
												else if (n === "failed") k(r, {
													instancePath: t + "/csv",
													parentData: e,
													parentDataProperty: "csv",
													rootData: o,
													dynamicAnchors: s
												}) || (c = c === null ? k.errors : c.concat(k.errors), l = c.length), m !== !0 && (m = !0);
												else return A.errors = [{
													instancePath: t + "/csv",
													schemaPath: "#/properties/csv/discriminator",
													keyword: "discriminator",
													params: {
														error: "mapping",
														tag: "state",
														tagValue: n
													}
												}], !1;
											} else return A.errors = [{
												instancePath: t + "/csv",
												schemaPath: "#/properties/csv/discriminator",
												keyword: "discriminator",
												params: {
													error: "tag",
													tag: "state",
													tagValue: n
												}
											}], !1;
										}
									} else return A.errors = [{
										instancePath: t + "/csv",
										schemaPath: "#/properties/csv/type",
										keyword: "type",
										params: { type: "object" }
									}], !1;
								}
								var f = i === l;
							} else var f = !0;
							if (f) {
								if (e.lead !== void 0 && n.call(e, "lead")) {
									let n = l;
									Le(e.lead, {
										instancePath: t + "/lead",
										parentData: e,
										parentDataProperty: "lead",
										rootData: o,
										dynamicAnchors: s
									}) || (c = c === null ? Le.errors : c.concat(Le.errors), l = c.length);
									var f = n === l;
								} else var f = !0;
								if (f) {
									if (e.operation_key !== void 0 && n.call(e, "operation_key")) {
										let n = e.operation_key, r = l;
										if (l === r) {
											if (typeof n == "string") {
												if (!g.test(n)) return A.errors = [{
													instancePath: t + "/operation_key",
													schemaPath: "#/properties/operation_key/pattern",
													keyword: "pattern",
													params: { pattern: "^[A-Za-z0-9_-]{43}$" }
												}], !1;
											} else return A.errors = [{
												instancePath: t + "/operation_key",
												schemaPath: "#/properties/operation_key/type",
												keyword: "type",
												params: { type: "string" }
											}], !1;
										}
										var f = r === l;
									} else var f = !0;
									if (f) {
										if (e.original_store_generation !== void 0 && n.call(e, "original_store_generation")) {
											let n = e.original_store_generation, r = l;
											if (l === r) {
												if (typeof n == "string") {
													if (!u.test(n)) return A.errors = [{
														instancePath: t + "/original_store_generation",
														schemaPath: "#/properties/original_store_generation/pattern",
														keyword: "pattern",
														params: { pattern: "^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$" }
													}], !1;
												} else return A.errors = [{
													instancePath: t + "/original_store_generation",
													schemaPath: "#/properties/original_store_generation/type",
													keyword: "type",
													params: { type: "string" }
												}], !1;
											}
											var f = r === l;
										} else var f = !0;
										if (f) {
											if (e.replay_valid_until !== void 0 && n.call(e, "replay_valid_until")) {
												let n = e.replay_valid_until, r = l;
												if (l === r) {
													if (typeof n == "string") {
														if (!i.test(n)) return A.errors = [{
															instancePath: t + "/replay_valid_until",
															schemaPath: "#/properties/replay_valid_until/pattern",
															keyword: "pattern",
															params: { pattern: "^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}(?:\\.\\d{1,6})?Z$" }
														}], !1;
													} else return A.errors = [{
														instancePath: t + "/replay_valid_until",
														schemaPath: "#/properties/replay_valid_until/type",
														keyword: "type",
														params: { type: "string" }
													}], !1;
												}
												var f = r === l;
											} else var f = !0;
											if (f) {
												if (e.review_id !== void 0 && n.call(e, "review_id")) {
													let n = e.review_id, r = l;
													if (l === r) {
														if (typeof n == "string") {
															if (!u.test(n)) return A.errors = [{
																instancePath: t + "/review_id",
																schemaPath: "#/properties/review_id/pattern",
																keyword: "pattern",
																params: { pattern: "^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$" }
															}], !1;
														} else return A.errors = [{
															instancePath: t + "/review_id",
															schemaPath: "#/properties/review_id/type",
															keyword: "type",
															params: { type: "string" }
														}], !1;
													}
													var f = r === l;
												} else var f = !0;
												if (f) {
													if (e.state !== void 0 && n.call(e, "state")) {
														let n = e.state, r = l;
														if (typeof n != "string") return A.errors = [{
															instancePath: t + "/state",
															schemaPath: "#/properties/state/type",
															keyword: "type",
															params: { type: "string" }
														}], !1;
														if (n !== "succeeded") return A.errors = [{
															instancePath: t + "/state",
															schemaPath: "#/properties/state/const",
															keyword: "const",
															params: { allowedValue: "succeeded" }
														}], !1;
														var f = r === l;
													} else var f = !0;
													if (f) {
														if (e.terminal_at !== void 0 && n.call(e, "terminal_at")) {
															let n = e.terminal_at, r = l;
															if (l === r) {
																if (typeof n == "string") {
																	if (!i.test(n)) return A.errors = [{
																		instancePath: t + "/terminal_at",
																		schemaPath: "#/properties/terminal_at/pattern",
																		keyword: "pattern",
																		params: { pattern: "^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}(?:\\.\\d{1,6})?Z$" }
																	}], !1;
																} else return A.errors = [{
																	instancePath: t + "/terminal_at",
																	schemaPath: "#/properties/terminal_at/type",
																	keyword: "type",
																	params: { type: "string" }
																}], !1;
															}
															var f = r === l;
														} else var f = !0;
													}
												}
											}
										}
									}
								}
							}
						}
					}
				}
			} else return A.errors = [{
				instancePath: t,
				schemaPath: "#/type",
				keyword: "type",
				params: { type: "object" }
			}], !1;
		}
		return A.errors = c, l === 0;
	}
	A.evaluated = {
		props: !0,
		dynamicProps: !1,
		dynamicItems: !1
	};
	var Re = {
		additionalProperties: !1,
		properties: {
			booking: { $ref: "urn:car-shopping-assistant:contract:1#/$defs/BookingNotCreated" },
			csv: { $ref: "urn:car-shopping-assistant:contract:1#/$defs/ExportNotRequested" },
			lead: { $ref: "urn:car-shopping-assistant:contract:1#/$defs/LeadNotRequested" },
			operation_key: {
				pattern: "^[A-Za-z0-9_-]{43}$",
				title: "Operation Key",
				type: "string"
			},
			original_store_generation: {
				pattern: "^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$",
				title: "Original Store Generation",
				type: "string"
			},
			rejection_code: {
				enum: [
					"REVIEW_STALE",
					"CAPACITY_UNAVAILABLE",
					"ELIGIBILITY_UNAVAILABLE",
					"RULES_UNAVAILABLE",
					"UNSUPPORTED_STATE",
					"SNAPSHOT_STALE",
					"LEAD_REVISION_CONFLICT"
				],
				title: "Rejection Code",
				type: "string"
			},
			replay_valid_until: {
				pattern: "^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}(?:\\.\\d{1,6})?Z$",
				title: "Replay Valid Until",
				type: "string"
			},
			review_id: {
				pattern: "^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$",
				title: "Review Id",
				type: "string"
			},
			state: {
				const: "rejected",
				title: "State",
				type: "string"
			},
			terminal_at: {
				pattern: "^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}(?:\\.\\d{1,6})?Z$",
				title: "Terminal At",
				type: "string"
			}
		},
		required: [
			"state",
			"operation_key",
			"review_id",
			"original_store_generation",
			"terminal_at",
			"replay_valid_until",
			"rejection_code",
			"booking",
			"lead",
			"csv"
		],
		title: "OperationRejected",
		type: "object"
	};
	function ze(e, { instancePath: t = "", parentData: r, parentDataProperty: i, rootData: a = e, dynamicAnchors: o = {} } = {}) {
		let s = ze.evaluated;
		if (s.dynamicProps && (s.props = void 0), s.dynamicItems && (s.items = void 0), e && typeof e == "object" && !Array.isArray(e)) {
			let r;
			if ((e.state === void 0 || !n.call(e, "state")) && (r = "state")) return ze.errors = [{
				instancePath: t,
				schemaPath: "#/required",
				keyword: "required",
				params: { missingProperty: r }
			}], !1;
			for (let n of Object.keys(e)) if (n !== "state") return ze.errors = [{
				instancePath: t,
				schemaPath: "#/additionalProperties",
				keyword: "additionalProperties",
				params: { additionalProperty: n }
			}], !1;
			if (e.state !== void 0 && n.call(e, "state")) {
				let n = e.state;
				if (typeof n != "string") return ze.errors = [{
					instancePath: t + "/state",
					schemaPath: "#/properties/state/type",
					keyword: "type",
					params: { type: "string" }
				}], !1;
				if (n !== "not_created") return ze.errors = [{
					instancePath: t + "/state",
					schemaPath: "#/properties/state/const",
					keyword: "const",
					params: { allowedValue: "not_created" }
				}], !1;
			}
		} else return ze.errors = [{
			instancePath: t,
			schemaPath: "#/type",
			keyword: "type",
			params: { type: "object" }
		}], !1;
		return ze.errors = null, !0;
	}
	ze.evaluated = {
		props: !0,
		dynamicProps: !1,
		dynamicItems: !1
	};
	function Be(e, { instancePath: t = "", parentData: r, parentDataProperty: i, rootData: a = e, dynamicAnchors: o = {} } = {}) {
		let s = Be.evaluated;
		if (s.dynamicProps && (s.props = void 0), s.dynamicItems && (s.items = void 0), e && typeof e == "object" && !Array.isArray(e)) {
			let r;
			if ((e.state === void 0 || !n.call(e, "state")) && (r = "state")) return Be.errors = [{
				instancePath: t,
				schemaPath: "#/required",
				keyword: "required",
				params: { missingProperty: r }
			}], !1;
			for (let n of Object.keys(e)) if (n !== "state") return Be.errors = [{
				instancePath: t,
				schemaPath: "#/additionalProperties",
				keyword: "additionalProperties",
				params: { additionalProperty: n }
			}], !1;
			if (e.state !== void 0 && n.call(e, "state")) {
				let n = e.state;
				if (typeof n != "string") return Be.errors = [{
					instancePath: t + "/state",
					schemaPath: "#/properties/state/type",
					keyword: "type",
					params: { type: "string" }
				}], !1;
				if (n !== "not_requested") return Be.errors = [{
					instancePath: t + "/state",
					schemaPath: "#/properties/state/const",
					keyword: "const",
					params: { allowedValue: "not_requested" }
				}], !1;
			}
		} else return Be.errors = [{
			instancePath: t,
			schemaPath: "#/type",
			keyword: "type",
			params: { type: "object" }
		}], !1;
		return Be.errors = null, !0;
	}
	Be.evaluated = {
		props: !0,
		dynamicProps: !1,
		dynamicItems: !1
	};
	function Ve(e, { instancePath: t = "", parentData: r, parentDataProperty: i, rootData: a = e, dynamicAnchors: o = {} } = {}) {
		let s = Ve.evaluated;
		if (s.dynamicProps && (s.props = void 0), s.dynamicItems && (s.items = void 0), e && typeof e == "object" && !Array.isArray(e)) {
			let r;
			if ((e.state === void 0 || !n.call(e, "state")) && (r = "state")) return Ve.errors = [{
				instancePath: t,
				schemaPath: "#/required",
				keyword: "required",
				params: { missingProperty: r }
			}], !1;
			for (let n of Object.keys(e)) if (n !== "state") return Ve.errors = [{
				instancePath: t,
				schemaPath: "#/additionalProperties",
				keyword: "additionalProperties",
				params: { additionalProperty: n }
			}], !1;
			if (e.state !== void 0 && n.call(e, "state")) {
				let n = e.state;
				if (typeof n != "string") return Ve.errors = [{
					instancePath: t + "/state",
					schemaPath: "#/properties/state/type",
					keyword: "type",
					params: { type: "string" }
				}], !1;
				if (n !== "not_requested") return Ve.errors = [{
					instancePath: t + "/state",
					schemaPath: "#/properties/state/const",
					keyword: "const",
					params: { allowedValue: "not_requested" }
				}], !1;
			}
		} else return Ve.errors = [{
			instancePath: t,
			schemaPath: "#/type",
			keyword: "type",
			params: { type: "object" }
		}], !1;
		return Ve.errors = null, !0;
	}
	Ve.evaluated = {
		props: !0,
		dynamicProps: !1,
		dynamicItems: !1
	};
	function j(e, { instancePath: t = "", parentData: r, parentDataProperty: a, rootData: o = e, dynamicAnchors: s = {} } = {}) {
		let c = null, l = 0, d = j.evaluated;
		if (d.dynamicProps && (d.props = void 0), d.dynamicItems && (d.items = void 0), l === 0) {
			if (e && typeof e == "object" && !Array.isArray(e)) {
				let r;
				if ((e.state === void 0 || !n.call(e, "state")) && (r = "state") || (e.operation_key === void 0 || !n.call(e, "operation_key")) && (r = "operation_key") || (e.review_id === void 0 || !n.call(e, "review_id")) && (r = "review_id") || (e.original_store_generation === void 0 || !n.call(e, "original_store_generation")) && (r = "original_store_generation") || (e.terminal_at === void 0 || !n.call(e, "terminal_at")) && (r = "terminal_at") || (e.replay_valid_until === void 0 || !n.call(e, "replay_valid_until")) && (r = "replay_valid_until") || (e.rejection_code === void 0 || !n.call(e, "rejection_code")) && (r = "rejection_code") || (e.booking === void 0 || !n.call(e, "booking")) && (r = "booking") || (e.lead === void 0 || !n.call(e, "lead")) && (r = "lead") || (e.csv === void 0 || !n.call(e, "csv")) && (r = "csv")) return j.errors = [{
					instancePath: t,
					schemaPath: "#/required",
					keyword: "required",
					params: { missingProperty: r }
				}], !1;
				{
					let r = l;
					for (let r of Object.keys(e)) if (!n.call(Re.properties, r)) return j.errors = [{
						instancePath: t,
						schemaPath: "#/additionalProperties",
						keyword: "additionalProperties",
						params: { additionalProperty: r }
					}], !1;
					if (r === l) {
						if (e.booking !== void 0 && n.call(e, "booking")) {
							let n = l;
							ze(e.booking, {
								instancePath: t + "/booking",
								parentData: e,
								parentDataProperty: "booking",
								rootData: o,
								dynamicAnchors: s
							}) || (c = c === null ? ze.errors : c.concat(ze.errors), l = c.length);
							var f = n === l;
						} else var f = !0;
						if (f) {
							if (e.csv !== void 0 && n.call(e, "csv")) {
								let n = l;
								Be(e.csv, {
									instancePath: t + "/csv",
									parentData: e,
									parentDataProperty: "csv",
									rootData: o,
									dynamicAnchors: s
								}) || (c = c === null ? Be.errors : c.concat(Be.errors), l = c.length);
								var f = n === l;
							} else var f = !0;
							if (f) {
								if (e.lead !== void 0 && n.call(e, "lead")) {
									let n = l;
									Ve(e.lead, {
										instancePath: t + "/lead",
										parentData: e,
										parentDataProperty: "lead",
										rootData: o,
										dynamicAnchors: s
									}) || (c = c === null ? Ve.errors : c.concat(Ve.errors), l = c.length);
									var f = n === l;
								} else var f = !0;
								if (f) {
									if (e.operation_key !== void 0 && n.call(e, "operation_key")) {
										let n = e.operation_key, r = l;
										if (l === r) {
											if (typeof n == "string") {
												if (!g.test(n)) return j.errors = [{
													instancePath: t + "/operation_key",
													schemaPath: "#/properties/operation_key/pattern",
													keyword: "pattern",
													params: { pattern: "^[A-Za-z0-9_-]{43}$" }
												}], !1;
											} else return j.errors = [{
												instancePath: t + "/operation_key",
												schemaPath: "#/properties/operation_key/type",
												keyword: "type",
												params: { type: "string" }
											}], !1;
										}
										var f = r === l;
									} else var f = !0;
									if (f) {
										if (e.original_store_generation !== void 0 && n.call(e, "original_store_generation")) {
											let n = e.original_store_generation, r = l;
											if (l === r) {
												if (typeof n == "string") {
													if (!u.test(n)) return j.errors = [{
														instancePath: t + "/original_store_generation",
														schemaPath: "#/properties/original_store_generation/pattern",
														keyword: "pattern",
														params: { pattern: "^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$" }
													}], !1;
												} else return j.errors = [{
													instancePath: t + "/original_store_generation",
													schemaPath: "#/properties/original_store_generation/type",
													keyword: "type",
													params: { type: "string" }
												}], !1;
											}
											var f = r === l;
										} else var f = !0;
										if (f) {
											if (e.rejection_code !== void 0 && n.call(e, "rejection_code")) {
												let n = e.rejection_code, r = l;
												if (typeof n != "string") return j.errors = [{
													instancePath: t + "/rejection_code",
													schemaPath: "#/properties/rejection_code/type",
													keyword: "type",
													params: { type: "string" }
												}], !1;
												if (n !== "REVIEW_STALE" && n !== "CAPACITY_UNAVAILABLE" && n !== "ELIGIBILITY_UNAVAILABLE" && n !== "RULES_UNAVAILABLE" && n !== "UNSUPPORTED_STATE" && n !== "SNAPSHOT_STALE" && n !== "LEAD_REVISION_CONFLICT") return j.errors = [{
													instancePath: t + "/rejection_code",
													schemaPath: "#/properties/rejection_code/enum",
													keyword: "enum",
													params: { allowedValues: Re.properties.rejection_code.enum }
												}], !1;
												var f = r === l;
											} else var f = !0;
											if (f) {
												if (e.replay_valid_until !== void 0 && n.call(e, "replay_valid_until")) {
													let n = e.replay_valid_until, r = l;
													if (l === r) {
														if (typeof n == "string") {
															if (!i.test(n)) return j.errors = [{
																instancePath: t + "/replay_valid_until",
																schemaPath: "#/properties/replay_valid_until/pattern",
																keyword: "pattern",
																params: { pattern: "^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}(?:\\.\\d{1,6})?Z$" }
															}], !1;
														} else return j.errors = [{
															instancePath: t + "/replay_valid_until",
															schemaPath: "#/properties/replay_valid_until/type",
															keyword: "type",
															params: { type: "string" }
														}], !1;
													}
													var f = r === l;
												} else var f = !0;
												if (f) {
													if (e.review_id !== void 0 && n.call(e, "review_id")) {
														let n = e.review_id, r = l;
														if (l === r) {
															if (typeof n == "string") {
																if (!u.test(n)) return j.errors = [{
																	instancePath: t + "/review_id",
																	schemaPath: "#/properties/review_id/pattern",
																	keyword: "pattern",
																	params: { pattern: "^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$" }
																}], !1;
															} else return j.errors = [{
																instancePath: t + "/review_id",
																schemaPath: "#/properties/review_id/type",
																keyword: "type",
																params: { type: "string" }
															}], !1;
														}
														var f = r === l;
													} else var f = !0;
													if (f) {
														if (e.state !== void 0 && n.call(e, "state")) {
															let n = e.state, r = l;
															if (typeof n != "string") return j.errors = [{
																instancePath: t + "/state",
																schemaPath: "#/properties/state/type",
																keyword: "type",
																params: { type: "string" }
															}], !1;
															if (n !== "rejected") return j.errors = [{
																instancePath: t + "/state",
																schemaPath: "#/properties/state/const",
																keyword: "const",
																params: { allowedValue: "rejected" }
															}], !1;
															var f = r === l;
														} else var f = !0;
														if (f) {
															if (e.terminal_at !== void 0 && n.call(e, "terminal_at")) {
																let n = e.terminal_at, r = l;
																if (l === r) {
																	if (typeof n == "string") {
																		if (!i.test(n)) return j.errors = [{
																			instancePath: t + "/terminal_at",
																			schemaPath: "#/properties/terminal_at/pattern",
																			keyword: "pattern",
																			params: { pattern: "^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}(?:\\.\\d{1,6})?Z$" }
																		}], !1;
																	} else return j.errors = [{
																		instancePath: t + "/terminal_at",
																		schemaPath: "#/properties/terminal_at/type",
																		keyword: "type",
																		params: { type: "string" }
																	}], !1;
																}
																var f = r === l;
															} else var f = !0;
														}
													}
												}
											}
										}
									}
								}
							}
						}
					}
				}
			} else return j.errors = [{
				instancePath: t,
				schemaPath: "#/type",
				keyword: "type",
				params: { type: "object" }
			}], !1;
		}
		return j.errors = c, l === 0;
	}
	j.evaluated = {
		props: !0,
		dynamicProps: !1,
		dynamicItems: !1
	};
	var He = {
		additionalProperties: !1,
		properties: {
			definitive_noncommit: {
				const: !1,
				default: !1,
				title: "Definitive Noncommit",
				type: "boolean"
			},
			observed_store_generation: {
				pattern: "^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$",
				title: "Observed Store Generation",
				type: "string"
			},
			operation_key: {
				pattern: "^[A-Za-z0-9_-]{43}$",
				title: "Operation Key",
				type: "string"
			},
			recovery: {
				enum: ["read_original_operation", "retry_original_operation"],
				title: "Recovery",
				type: "string"
			},
			state: {
				const: "not_observed",
				title: "State",
				type: "string"
			}
		},
		required: [
			"state",
			"operation_key",
			"observed_store_generation",
			"recovery"
		],
		title: "OperationNotObserved",
		type: "object"
	};
	function M(e, { instancePath: t = "", parentData: r, parentDataProperty: i, rootData: a = e, dynamicAnchors: o = {} } = {}) {
		let s = M.evaluated;
		if (s.dynamicProps && (s.props = void 0), s.dynamicItems && (s.items = void 0), e && typeof e == "object" && !Array.isArray(e)) {
			let r;
			if ((e.state === void 0 || !n.call(e, "state")) && (r = "state") || (e.operation_key === void 0 || !n.call(e, "operation_key")) && (r = "operation_key") || (e.observed_store_generation === void 0 || !n.call(e, "observed_store_generation")) && (r = "observed_store_generation") || (e.recovery === void 0 || !n.call(e, "recovery")) && (r = "recovery")) return M.errors = [{
				instancePath: t,
				schemaPath: "#/required",
				keyword: "required",
				params: { missingProperty: r }
			}], !1;
			for (let n of Object.keys(e)) if (n !== "definitive_noncommit" && n !== "observed_store_generation" && n !== "operation_key" && n !== "recovery" && n !== "state") return M.errors = [{
				instancePath: t,
				schemaPath: "#/additionalProperties",
				keyword: "additionalProperties",
				params: { additionalProperty: n }
			}], !1;
			if (e.definitive_noncommit !== void 0 && n.call(e, "definitive_noncommit")) {
				let n = e.definitive_noncommit;
				if (typeof n != "boolean") return M.errors = [{
					instancePath: t + "/definitive_noncommit",
					schemaPath: "#/properties/definitive_noncommit/type",
					keyword: "type",
					params: { type: "boolean" }
				}], !1;
				if (!1 !== n) return M.errors = [{
					instancePath: t + "/definitive_noncommit",
					schemaPath: "#/properties/definitive_noncommit/const",
					keyword: "const",
					params: { allowedValue: !1 }
				}], !1;
				var c = !0;
			} else var c = !0;
			if (c) {
				if (e.observed_store_generation !== void 0 && n.call(e, "observed_store_generation")) {
					let n = e.observed_store_generation;
					if (typeof n == "string") {
						if (!u.test(n)) return M.errors = [{
							instancePath: t + "/observed_store_generation",
							schemaPath: "#/properties/observed_store_generation/pattern",
							keyword: "pattern",
							params: { pattern: "^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$" }
						}], !1;
					} else return M.errors = [{
						instancePath: t + "/observed_store_generation",
						schemaPath: "#/properties/observed_store_generation/type",
						keyword: "type",
						params: { type: "string" }
					}], !1;
					var c = !0;
				} else var c = !0;
				if (c) {
					if (e.operation_key !== void 0 && n.call(e, "operation_key")) {
						let n = e.operation_key;
						if (typeof n == "string") {
							if (!g.test(n)) return M.errors = [{
								instancePath: t + "/operation_key",
								schemaPath: "#/properties/operation_key/pattern",
								keyword: "pattern",
								params: { pattern: "^[A-Za-z0-9_-]{43}$" }
							}], !1;
						} else return M.errors = [{
							instancePath: t + "/operation_key",
							schemaPath: "#/properties/operation_key/type",
							keyword: "type",
							params: { type: "string" }
						}], !1;
						var c = !0;
					} else var c = !0;
					if (c) {
						if (e.recovery !== void 0 && n.call(e, "recovery")) {
							let n = e.recovery;
							if (typeof n != "string") return M.errors = [{
								instancePath: t + "/recovery",
								schemaPath: "#/properties/recovery/type",
								keyword: "type",
								params: { type: "string" }
							}], !1;
							if (n !== "read_original_operation" && n !== "retry_original_operation") return M.errors = [{
								instancePath: t + "/recovery",
								schemaPath: "#/properties/recovery/enum",
								keyword: "enum",
								params: { allowedValues: He.properties.recovery.enum }
							}], !1;
							var c = !0;
						} else var c = !0;
						if (c) {
							if (e.state !== void 0 && n.call(e, "state")) {
								let n = e.state;
								if (typeof n != "string") return M.errors = [{
									instancePath: t + "/state",
									schemaPath: "#/properties/state/type",
									keyword: "type",
									params: { type: "string" }
								}], !1;
								if (n !== "not_observed") return M.errors = [{
									instancePath: t + "/state",
									schemaPath: "#/properties/state/const",
									keyword: "const",
									params: { allowedValue: "not_observed" }
								}], !1;
								var c = !0;
							} else var c = !0;
						}
					}
				}
			}
		} else return M.errors = [{
			instancePath: t,
			schemaPath: "#/type",
			keyword: "type",
			params: { type: "object" }
		}], !1;
		return M.errors = null, !0;
	}
	M.evaluated = {
		props: !0,
		dynamicProps: !1,
		dynamicItems: !1
	};
	function N(e, { instancePath: t = "", parentData: r, parentDataProperty: i, rootData: a = e, dynamicAnchors: o = {} } = {}) {
		let s = N.evaluated;
		if (s.dynamicProps && (s.props = void 0), s.dynamicItems && (s.items = void 0), e && typeof e == "object" && !Array.isArray(e)) {
			let r;
			if ((e.state === void 0 || !n.call(e, "state")) && (r = "state") || (e.operation_key === void 0 || !n.call(e, "operation_key")) && (r = "operation_key") || (e.observed_store_generation === void 0 || !n.call(e, "observed_store_generation")) && (r = "observed_store_generation") || (e.submitted_store_generation === void 0 || !n.call(e, "submitted_store_generation")) && (r = "submitted_store_generation")) return N.errors = [{
				instancePath: t,
				schemaPath: "#/required",
				keyword: "required",
				params: { missingProperty: r }
			}], !1;
			for (let n of Object.keys(e)) if (n !== "definitive_noncommit" && n !== "observed_store_generation" && n !== "operation_key" && n !== "recovery" && n !== "state" && n !== "submitted_store_generation") return N.errors = [{
				instancePath: t,
				schemaPath: "#/additionalProperties",
				keyword: "additionalProperties",
				params: { additionalProperty: n }
			}], !1;
			if (e.definitive_noncommit !== void 0 && n.call(e, "definitive_noncommit")) {
				let n = e.definitive_noncommit;
				if (typeof n != "boolean") return N.errors = [{
					instancePath: t + "/definitive_noncommit",
					schemaPath: "#/properties/definitive_noncommit/type",
					keyword: "type",
					params: { type: "boolean" }
				}], !1;
				if (!1 !== n) return N.errors = [{
					instancePath: t + "/definitive_noncommit",
					schemaPath: "#/properties/definitive_noncommit/const",
					keyword: "const",
					params: { allowedValue: !1 }
				}], !1;
				var c = !0;
			} else var c = !0;
			if (c) {
				if (e.observed_store_generation !== void 0 && n.call(e, "observed_store_generation")) {
					let n = e.observed_store_generation;
					if (typeof n == "string") {
						if (!u.test(n)) return N.errors = [{
							instancePath: t + "/observed_store_generation",
							schemaPath: "#/properties/observed_store_generation/pattern",
							keyword: "pattern",
							params: { pattern: "^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$" }
						}], !1;
					} else return N.errors = [{
						instancePath: t + "/observed_store_generation",
						schemaPath: "#/properties/observed_store_generation/type",
						keyword: "type",
						params: { type: "string" }
					}], !1;
					var c = !0;
				} else var c = !0;
				if (c) {
					if (e.operation_key !== void 0 && n.call(e, "operation_key")) {
						let n = e.operation_key;
						if (typeof n == "string") {
							if (!g.test(n)) return N.errors = [{
								instancePath: t + "/operation_key",
								schemaPath: "#/properties/operation_key/pattern",
								keyword: "pattern",
								params: { pattern: "^[A-Za-z0-9_-]{43}$" }
							}], !1;
						} else return N.errors = [{
							instancePath: t + "/operation_key",
							schemaPath: "#/properties/operation_key/type",
							keyword: "type",
							params: { type: "string" }
						}], !1;
						var c = !0;
					} else var c = !0;
					if (c) {
						if (e.recovery !== void 0 && n.call(e, "recovery")) {
							let n = e.recovery;
							if (typeof n != "string") return N.errors = [{
								instancePath: t + "/recovery",
								schemaPath: "#/properties/recovery/type",
								keyword: "type",
								params: { type: "string" }
							}], !1;
							if (n !== "operator_reconciliation") return N.errors = [{
								instancePath: t + "/recovery",
								schemaPath: "#/properties/recovery/const",
								keyword: "const",
								params: { allowedValue: "operator_reconciliation" }
							}], !1;
							var c = !0;
						} else var c = !0;
						if (c) {
							if (e.state !== void 0 && n.call(e, "state")) {
								let n = e.state;
								if (typeof n != "string") return N.errors = [{
									instancePath: t + "/state",
									schemaPath: "#/properties/state/type",
									keyword: "type",
									params: { type: "string" }
								}], !1;
								if (n !== "unresolved_generation") return N.errors = [{
									instancePath: t + "/state",
									schemaPath: "#/properties/state/const",
									keyword: "const",
									params: { allowedValue: "unresolved_generation" }
								}], !1;
								var c = !0;
							} else var c = !0;
							if (c) {
								if (e.submitted_store_generation !== void 0 && n.call(e, "submitted_store_generation")) {
									let n = e.submitted_store_generation;
									if (typeof n == "string") {
										if (!u.test(n)) return N.errors = [{
											instancePath: t + "/submitted_store_generation",
											schemaPath: "#/properties/submitted_store_generation/pattern",
											keyword: "pattern",
											params: { pattern: "^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$" }
										}], !1;
									} else return N.errors = [{
										instancePath: t + "/submitted_store_generation",
										schemaPath: "#/properties/submitted_store_generation/type",
										keyword: "type",
										params: { type: "string" }
									}], !1;
									var c = !0;
								} else var c = !0;
							}
						}
					}
				}
			}
		} else return N.errors = [{
			instancePath: t,
			schemaPath: "#/type",
			keyword: "type",
			params: { type: "object" }
		}], !1;
		return N.errors = null, !0;
	}
	N.evaluated = {
		props: !0,
		dynamicProps: !1,
		dynamicItems: !1
	};
	function Ue(e, { instancePath: t = "", parentData: r, parentDataProperty: i, rootData: a = e, dynamicAnchors: o = {} } = {}) {
		let s = null, c = 0, l = Ue.evaluated;
		if (l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0) {
			if (e && typeof e == "object" && !Array.isArray(e)) {
				let r;
				if ((e.data === void 0 || !n.call(e, "data")) && (r = "data") || (e.meta === void 0 || !n.call(e, "meta")) && (r = "meta")) return Ue.errors = [{
					instancePath: t,
					schemaPath: "#/required",
					keyword: "required",
					params: { missingProperty: r }
				}], !1;
				{
					let r = c;
					for (let n of Object.keys(e)) if (n !== "data" && n !== "meta") return Ue.errors = [{
						instancePath: t,
						schemaPath: "#/additionalProperties",
						keyword: "additionalProperties",
						params: { additionalProperty: n }
					}], !1;
					if (r === c) {
						if (e.data !== void 0 && n.call(e, "data")) {
							let r = e.data, i = c;
							if (c === i) {
								if (r && typeof r == "object" && !Array.isArray(r)) {
									let i;
									if ((r.state === void 0 || !n.call(r, "state")) && (i = "state")) return Ue.errors = [{
										instancePath: t + "/data",
										schemaPath: "#/properties/data/required",
										keyword: "required",
										params: { missingProperty: i }
									}], !1;
									if (r.state !== void 0 && n.call(r, "state")) {
										let e = c;
										if (typeof r.state != "string") return Ue.errors = [{
											instancePath: t + "/data/state",
											schemaPath: "#/properties/data/properties/state/type",
											keyword: "type",
											params: { type: "string" }
										}], !1;
										var u = e === c;
									} else var u = !0;
									if (u) {
										let n = r.state;
										if (typeof n == "string") {
											if (n === "succeeded") {
												A(r, {
													instancePath: t + "/data",
													parentData: e,
													parentDataProperty: "data",
													rootData: a,
													dynamicAnchors: o
												}) || (s = s === null ? A.errors : s.concat(A.errors), c = s.length);
												var d = !0;
											} else if (n === "rejected") j(r, {
												instancePath: t + "/data",
												parentData: e,
												parentDataProperty: "data",
												rootData: a,
												dynamicAnchors: o
											}) || (s = s === null ? j.errors : s.concat(j.errors), c = s.length), d !== !0 && (d = !0);
											else if (n === "not_observed") M(r, {
												instancePath: t + "/data",
												parentData: e,
												parentDataProperty: "data",
												rootData: a,
												dynamicAnchors: o
											}) || (s = s === null ? M.errors : s.concat(M.errors), c = s.length), d !== !0 && (d = !0);
											else if (n === "unresolved_generation") N(r, {
												instancePath: t + "/data",
												parentData: e,
												parentDataProperty: "data",
												rootData: a,
												dynamicAnchors: o
											}) || (s = s === null ? N.errors : s.concat(N.errors), c = s.length), d !== !0 && (d = !0);
											else return Ue.errors = [{
												instancePath: t + "/data",
												schemaPath: "#/properties/data/discriminator",
												keyword: "discriminator",
												params: {
													error: "mapping",
													tag: "state",
													tagValue: n
												}
											}], !1;
										} else return Ue.errors = [{
											instancePath: t + "/data",
											schemaPath: "#/properties/data/discriminator",
											keyword: "discriminator",
											params: {
												error: "tag",
												tag: "state",
												tagValue: n
											}
										}], !1;
									}
								} else return Ue.errors = [{
									instancePath: t + "/data",
									schemaPath: "#/properties/data/type",
									keyword: "type",
									params: { type: "object" }
								}], !1;
							}
							var f = i === c;
						} else var f = !0;
						if (f) {
							if (e.meta !== void 0 && n.call(e, "meta")) {
								let n = c;
								y(e.meta, {
									instancePath: t + "/meta",
									parentData: e,
									parentDataProperty: "meta",
									rootData: a,
									dynamicAnchors: o
								}) || (s = s === null ? y.errors : s.concat(y.errors), c = s.length);
								var f = n === c;
							} else var f = !0;
						}
					}
				}
			} else return Ue.errors = [{
				instancePath: t,
				schemaPath: "#/type",
				keyword: "type",
				params: { type: "object" }
			}], !1;
		}
		return Ue.errors = s, c === 0;
	}
	Ue.evaluated = {
		props: !0,
		dynamicProps: !1,
		dynamicItems: !1
	}, e.v34 = Ge;
	var We = {
		additionalProperties: !1,
		properties: {
			appointment: { anyOf: [{ $ref: "urn:car-shopping-assistant:contract:1#/$defs/AppointmentSelection" }, { type: "null" }] },
			draft_id: {
				pattern: "^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$",
				title: "Draft Id",
				type: "string"
			},
			expires_at: {
				pattern: "^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}(?:\\.\\d{1,6})?Z$",
				title: "Expires At",
				type: "string"
			},
			ref: { $ref: "urn:car-shopping-assistant:contract:1#/$defs/InventoryRef" },
			required_fields: {
				items: {
					maxLength: 200,
					minLength: 1,
					type: "string"
				},
				maxItems: 12,
				title: "Required Fields",
				type: "array"
			},
			review: { anyOf: [{ $ref: "urn:car-shopping-assistant:contract:1#/$defs/BookingReview" }, { type: "null" }] },
			revision: {
				maximum: 2147483647,
				minimum: 0,
				title: "Revision",
				type: "integer"
			},
			session_id: {
				pattern: "^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$",
				title: "Session Id",
				type: "string"
			},
			state: {
				enum: [
					"needs_details",
					"reviewable",
					"suspended",
					"discarded",
					"resolved",
					"unresolved"
				],
				title: "State",
				type: "string"
			}
		},
		required: [
			"draft_id",
			"session_id",
			"revision",
			"ref",
			"appointment",
			"state",
			"expires_at",
			"required_fields",
			"review"
		],
		title: "BookingDraft",
		type: "object"
	};
	function P(e, { instancePath: t = "", parentData: r, parentDataProperty: o, rootData: s = e, dynamicAnchors: c = {} } = {}) {
		let d = null, f = 0, p = P.evaluated;
		if (p.dynamicProps && (p.props = void 0), p.dynamicItems && (p.items = void 0), f === 0) {
			if (e && typeof e == "object" && !Array.isArray(e)) {
				let r;
				if ((e.draft_id === void 0 || !n.call(e, "draft_id")) && (r = "draft_id") || (e.session_id === void 0 || !n.call(e, "session_id")) && (r = "session_id") || (e.revision === void 0 || !n.call(e, "revision")) && (r = "revision") || (e.ref === void 0 || !n.call(e, "ref")) && (r = "ref") || (e.appointment === void 0 || !n.call(e, "appointment")) && (r = "appointment") || (e.state === void 0 || !n.call(e, "state")) && (r = "state") || (e.expires_at === void 0 || !n.call(e, "expires_at")) && (r = "expires_at") || (e.required_fields === void 0 || !n.call(e, "required_fields")) && (r = "required_fields") || (e.review === void 0 || !n.call(e, "review")) && (r = "review")) return P.errors = [{
					instancePath: t,
					schemaPath: "#/required",
					keyword: "required",
					params: { missingProperty: r }
				}], !1;
				{
					let r = f;
					for (let r of Object.keys(e)) if (!n.call(We.properties, r)) return P.errors = [{
						instancePath: t,
						schemaPath: "#/additionalProperties",
						keyword: "additionalProperties",
						params: { additionalProperty: r }
					}], !1;
					if (r === f) {
						if (e.appointment !== void 0 && n.call(e, "appointment")) {
							let n = e.appointment, r = f, i = f, o = !1, l = f;
							a(n, {
								instancePath: t + "/appointment",
								parentData: e,
								parentDataProperty: "appointment",
								rootData: s,
								dynamicAnchors: c
							}) || (d = d === null ? a.errors : d.concat(a.errors), f = d.length);
							var m = l === f;
							o ||= m;
							let u = f;
							if (n !== null) {
								let e = {
									instancePath: t + "/appointment",
									schemaPath: "#/properties/appointment/anyOf/1/type",
									keyword: "type",
									params: { type: "null" }
								};
								d === null ? d = [e] : d.push(e), f++;
							}
							var m = u === f;
							if (o ||= m, o) f = i, d !== null && (i ? d.length = i : d = null);
							else {
								let e = {
									instancePath: t + "/appointment",
									schemaPath: "#/properties/appointment/anyOf",
									keyword: "anyOf",
									params: {}
								};
								return d === null ? d = [e] : d.push(e), f++, P.errors = d, !1;
							}
							var g = r === f;
						} else var g = !0;
						if (g) {
							if (e.draft_id !== void 0 && n.call(e, "draft_id")) {
								let n = e.draft_id, r = f;
								if (f === r) {
									if (typeof n == "string") {
										if (!u.test(n)) return P.errors = [{
											instancePath: t + "/draft_id",
											schemaPath: "#/properties/draft_id/pattern",
											keyword: "pattern",
											params: { pattern: "^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$" }
										}], !1;
									} else return P.errors = [{
										instancePath: t + "/draft_id",
										schemaPath: "#/properties/draft_id/type",
										keyword: "type",
										params: { type: "string" }
									}], !1;
								}
								var g = r === f;
							} else var g = !0;
							if (g) {
								if (e.expires_at !== void 0 && n.call(e, "expires_at")) {
									let n = e.expires_at, r = f;
									if (f === r) {
										if (typeof n == "string") {
											if (!i.test(n)) return P.errors = [{
												instancePath: t + "/expires_at",
												schemaPath: "#/properties/expires_at/pattern",
												keyword: "pattern",
												params: { pattern: "^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}(?:\\.\\d{1,6})?Z$" }
											}], !1;
										} else return P.errors = [{
											instancePath: t + "/expires_at",
											schemaPath: "#/properties/expires_at/type",
											keyword: "type",
											params: { type: "string" }
										}], !1;
									}
									var g = r === f;
								} else var g = !0;
								if (g) {
									if (e.ref !== void 0 && n.call(e, "ref")) {
										let n = f;
										l(e.ref, {
											instancePath: t + "/ref",
											parentData: e,
											parentDataProperty: "ref",
											rootData: s,
											dynamicAnchors: c
										}) || (d = d === null ? l.errors : d.concat(l.errors), f = d.length);
										var g = n === f;
									} else var g = !0;
									if (g) {
										if (e.required_fields !== void 0 && n.call(e, "required_fields")) {
											let n = e.required_fields, r = f;
											if (f === r) {
												if (Array.isArray(n)) {
													if (n.length > 12) return P.errors = [{
														instancePath: t + "/required_fields",
														schemaPath: "#/properties/required_fields/maxItems",
														keyword: "maxItems",
														params: { limit: 12 }
													}], !1;
													{
														let e = n.length;
														for (let r = 0; r < e; r++) {
															let e = n[r], i = f;
															if (f === i) {
																if (typeof e == "string") {
																	if (h(e) > 200) return P.errors = [{
																		instancePath: t + "/required_fields/" + r,
																		schemaPath: "#/properties/required_fields/items/maxLength",
																		keyword: "maxLength",
																		params: { limit: 200 }
																	}], !1;
																	if (h(e) < 1) return P.errors = [{
																		instancePath: t + "/required_fields/" + r,
																		schemaPath: "#/properties/required_fields/items/minLength",
																		keyword: "minLength",
																		params: { limit: 1 }
																	}], !1;
																} else return P.errors = [{
																	instancePath: t + "/required_fields/" + r,
																	schemaPath: "#/properties/required_fields/items/type",
																	keyword: "type",
																	params: { type: "string" }
																}], !1;
															}
															if (i !== f) break;
														}
													}
												} else return P.errors = [{
													instancePath: t + "/required_fields",
													schemaPath: "#/properties/required_fields/type",
													keyword: "type",
													params: { type: "array" }
												}], !1;
											}
											var g = r === f;
										} else var g = !0;
										if (g) {
											if (e.review !== void 0 && n.call(e, "review")) {
												let n = e.review, r = f, i = f, a = !1, o = f;
												D(n, {
													instancePath: t + "/review",
													parentData: e,
													parentDataProperty: "review",
													rootData: s,
													dynamicAnchors: c
												}) || (d = d === null ? D.errors : d.concat(D.errors), f = d.length);
												var _ = o === f;
												a ||= _;
												let l = f;
												if (n !== null) {
													let e = {
														instancePath: t + "/review",
														schemaPath: "#/properties/review/anyOf/1/type",
														keyword: "type",
														params: { type: "null" }
													};
													d === null ? d = [e] : d.push(e), f++;
												}
												var _ = l === f;
												if (a ||= _, a) f = i, d !== null && (i ? d.length = i : d = null);
												else {
													let e = {
														instancePath: t + "/review",
														schemaPath: "#/properties/review/anyOf",
														keyword: "anyOf",
														params: {}
													};
													return d === null ? d = [e] : d.push(e), f++, P.errors = d, !1;
												}
												var g = r === f;
											} else var g = !0;
											if (g) {
												if (e.revision !== void 0 && n.call(e, "revision")) {
													let n = e.revision, r = f;
													if (typeof n != "number" || n % 1 || isNaN(n) || !isFinite(n)) return P.errors = [{
														instancePath: t + "/revision",
														schemaPath: "#/properties/revision/type",
														keyword: "type",
														params: { type: "integer" }
													}], !1;
													if (f === r && typeof n == "number" && isFinite(n)) {
														if (n > 2147483647 || isNaN(n)) return P.errors = [{
															instancePath: t + "/revision",
															schemaPath: "#/properties/revision/maximum",
															keyword: "maximum",
															params: {
																comparison: "<=",
																limit: 2147483647
															}
														}], !1;
														if (n < 0 || isNaN(n)) return P.errors = [{
															instancePath: t + "/revision",
															schemaPath: "#/properties/revision/minimum",
															keyword: "minimum",
															params: {
																comparison: ">=",
																limit: 0
															}
														}], !1;
													}
													var g = r === f;
												} else var g = !0;
												if (g) {
													if (e.session_id !== void 0 && n.call(e, "session_id")) {
														let n = e.session_id, r = f;
														if (f === r) {
															if (typeof n == "string") {
																if (!u.test(n)) return P.errors = [{
																	instancePath: t + "/session_id",
																	schemaPath: "#/properties/session_id/pattern",
																	keyword: "pattern",
																	params: { pattern: "^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$" }
																}], !1;
															} else return P.errors = [{
																instancePath: t + "/session_id",
																schemaPath: "#/properties/session_id/type",
																keyword: "type",
																params: { type: "string" }
															}], !1;
														}
														var g = r === f;
													} else var g = !0;
													if (g) {
														if (e.state !== void 0 && n.call(e, "state")) {
															let n = e.state, r = f;
															if (typeof n != "string") return P.errors = [{
																instancePath: t + "/state",
																schemaPath: "#/properties/state/type",
																keyword: "type",
																params: { type: "string" }
															}], !1;
															if (n !== "needs_details" && n !== "reviewable" && n !== "suspended" && n !== "discarded" && n !== "resolved" && n !== "unresolved") return P.errors = [{
																instancePath: t + "/state",
																schemaPath: "#/properties/state/enum",
																keyword: "enum",
																params: { allowedValues: We.properties.state.enum }
															}], !1;
															var g = r === f;
														} else var g = !0;
													}
												}
											}
										}
									}
								}
							}
						}
					}
				}
			} else return P.errors = [{
				instancePath: t,
				schemaPath: "#/type",
				keyword: "type",
				params: { type: "object" }
			}], !1;
		}
		return P.errors = d, f === 0;
	}
	P.evaluated = {
		props: !0,
		dynamicProps: !1,
		dynamicItems: !1
	};
	function Ge(e, { instancePath: t = "", parentData: r, parentDataProperty: i, rootData: a = e, dynamicAnchors: o = {} } = {}) {
		let s = null, c = 0, l = Ge.evaluated;
		if (l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0) {
			if (e && typeof e == "object" && !Array.isArray(e)) {
				let r;
				if ((e.data === void 0 || !n.call(e, "data")) && (r = "data") || (e.meta === void 0 || !n.call(e, "meta")) && (r = "meta")) return Ge.errors = [{
					instancePath: t,
					schemaPath: "#/required",
					keyword: "required",
					params: { missingProperty: r }
				}], !1;
				{
					let r = c;
					for (let n of Object.keys(e)) if (n !== "data" && n !== "meta") return Ge.errors = [{
						instancePath: t,
						schemaPath: "#/additionalProperties",
						keyword: "additionalProperties",
						params: { additionalProperty: n }
					}], !1;
					if (r === c) {
						if (e.data !== void 0 && n.call(e, "data")) {
							let n = c;
							P(e.data, {
								instancePath: t + "/data",
								parentData: e,
								parentDataProperty: "data",
								rootData: a,
								dynamicAnchors: o
							}) || (s = s === null ? P.errors : s.concat(P.errors), c = s.length);
							var u = n === c;
						} else var u = !0;
						if (u) {
							if (e.meta !== void 0 && n.call(e, "meta")) {
								let n = c;
								y(e.meta, {
									instancePath: t + "/meta",
									parentData: e,
									parentDataProperty: "meta",
									rootData: a,
									dynamicAnchors: o
								}) || (s = s === null ? y.errors : s.concat(y.errors), c = s.length);
								var u = n === c;
							} else var u = !0;
						}
					}
				}
			} else return Ge.errors = [{
				instancePath: t,
				schemaPath: "#/type",
				keyword: "type",
				params: { type: "object" }
			}], !1;
		}
		return Ge.errors = s, c === 0;
	}
	Ge.evaluated = {
		props: !0,
		dynamicProps: !1,
		dynamicItems: !1
	}, e.v35 = qe;
	function Ke(e, { instancePath: t = "", parentData: r, parentDataProperty: a, rootData: o = e, dynamicAnchors: s = {} } = {}) {
		let c = null, l = 0, d = Ke.evaluated;
		if (d.dynamicProps && (d.props = void 0), d.dynamicItems && (d.items = void 0), l === 0) {
			if (e && typeof e == "object" && !Array.isArray(e)) {
				let r;
				if ((e.state === void 0 || !n.call(e, "state")) && (r = "state") || (e.booking_id === void 0 || !n.call(e, "booking_id")) && (r = "booking_id") || (e.review === void 0 || !n.call(e, "review")) && (r = "review") || (e.confirmed_at === void 0 || !n.call(e, "confirmed_at")) && (r = "confirmed_at") || (e.lead === void 0 || !n.call(e, "lead")) && (r = "lead") || (e.csv === void 0 || !n.call(e, "csv")) && (r = "csv")) return Ke.errors = [{
					instancePath: t,
					schemaPath: "#/required",
					keyword: "required",
					params: { missingProperty: r }
				}], !1;
				{
					let r = l;
					for (let n of Object.keys(e)) if (n !== "booking_id" && n !== "confirmed_at" && n !== "csv" && n !== "lead" && n !== "review" && n !== "state") return Ke.errors = [{
						instancePath: t,
						schemaPath: "#/additionalProperties",
						keyword: "additionalProperties",
						params: { additionalProperty: n }
					}], !1;
					if (r === l) {
						if (e.booking_id !== void 0 && n.call(e, "booking_id")) {
							let n = e.booking_id, r = l;
							if (l === r) {
								if (typeof n == "string") {
									if (!u.test(n)) return Ke.errors = [{
										instancePath: t + "/booking_id",
										schemaPath: "#/properties/booking_id/pattern",
										keyword: "pattern",
										params: { pattern: "^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$" }
									}], !1;
								} else return Ke.errors = [{
									instancePath: t + "/booking_id",
									schemaPath: "#/properties/booking_id/type",
									keyword: "type",
									params: { type: "string" }
								}], !1;
							}
							var f = r === l;
						} else var f = !0;
						if (f) {
							if (e.confirmed_at !== void 0 && n.call(e, "confirmed_at")) {
								let n = e.confirmed_at, r = l;
								if (l === r) {
									if (typeof n == "string") {
										if (!i.test(n)) return Ke.errors = [{
											instancePath: t + "/confirmed_at",
											schemaPath: "#/properties/confirmed_at/pattern",
											keyword: "pattern",
											params: { pattern: "^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}(?:\\.\\d{1,6})?Z$" }
										}], !1;
									} else return Ke.errors = [{
										instancePath: t + "/confirmed_at",
										schemaPath: "#/properties/confirmed_at/type",
										keyword: "type",
										params: { type: "string" }
									}], !1;
								}
								var f = r === l;
							} else var f = !0;
							if (f) {
								if (e.csv !== void 0 && n.call(e, "csv")) {
									let r = e.csv, i = l;
									if (l === i) {
										if (r && typeof r == "object" && !Array.isArray(r)) {
											let i;
											if ((r.state === void 0 || !n.call(r, "state")) && (i = "state")) return Ke.errors = [{
												instancePath: t + "/csv",
												schemaPath: "#/properties/csv/required",
												keyword: "required",
												params: { missingProperty: i }
											}], !1;
											if (r.state !== void 0 && n.call(r, "state")) {
												let e = l;
												if (typeof r.state != "string") return Ke.errors = [{
													instancePath: t + "/csv/state",
													schemaPath: "#/properties/csv/properties/state/type",
													keyword: "type",
													params: { type: "string" }
												}], !1;
												var p = e === l;
											} else var p = !0;
											if (p) {
												let n = r.state;
												if (typeof n == "string") {
													if (n === "current") {
														O(r, {
															instancePath: t + "/csv",
															parentData: e,
															parentDataProperty: "csv",
															rootData: o,
															dynamicAnchors: s
														}) || (c = c === null ? O.errors : c.concat(O.errors), l = c.length);
														var m = !0;
													} else if (n === "pending") k(r, {
														instancePath: t + "/csv",
														parentData: e,
														parentDataProperty: "csv",
														rootData: o,
														dynamicAnchors: s
													}) || (c = c === null ? k.errors : c.concat(k.errors), l = c.length), m !== !0 && (m = !0);
													else if (n === "failed") k(r, {
														instancePath: t + "/csv",
														parentData: e,
														parentDataProperty: "csv",
														rootData: o,
														dynamicAnchors: s
													}) || (c = c === null ? k.errors : c.concat(k.errors), l = c.length), m !== !0 && (m = !0);
													else return Ke.errors = [{
														instancePath: t + "/csv",
														schemaPath: "#/properties/csv/discriminator",
														keyword: "discriminator",
														params: {
															error: "mapping",
															tag: "state",
															tagValue: n
														}
													}], !1;
												} else return Ke.errors = [{
													instancePath: t + "/csv",
													schemaPath: "#/properties/csv/discriminator",
													keyword: "discriminator",
													params: {
														error: "tag",
														tag: "state",
														tagValue: n
													}
												}], !1;
											}
										} else return Ke.errors = [{
											instancePath: t + "/csv",
											schemaPath: "#/properties/csv/type",
											keyword: "type",
											params: { type: "object" }
										}], !1;
									}
									var f = i === l;
								} else var f = !0;
								if (f) {
									if (e.lead !== void 0 && n.call(e, "lead")) {
										let n = l;
										Le(e.lead, {
											instancePath: t + "/lead",
											parentData: e,
											parentDataProperty: "lead",
											rootData: o,
											dynamicAnchors: s
										}) || (c = c === null ? Le.errors : c.concat(Le.errors), l = c.length);
										var f = n === l;
									} else var f = !0;
									if (f) {
										if (e.review !== void 0 && n.call(e, "review")) {
											let n = l;
											D(e.review, {
												instancePath: t + "/review",
												parentData: e,
												parentDataProperty: "review",
												rootData: o,
												dynamicAnchors: s
											}) || (c = c === null ? D.errors : c.concat(D.errors), l = c.length);
											var f = n === l;
										} else var f = !0;
										if (f) {
											if (e.state !== void 0 && n.call(e, "state")) {
												let n = e.state, r = l;
												if (typeof n != "string") return Ke.errors = [{
													instancePath: t + "/state",
													schemaPath: "#/properties/state/type",
													keyword: "type",
													params: { type: "string" }
												}], !1;
												if (n !== "confirmed_simulated") return Ke.errors = [{
													instancePath: t + "/state",
													schemaPath: "#/properties/state/const",
													keyword: "const",
													params: { allowedValue: "confirmed_simulated" }
												}], !1;
												var f = r === l;
											} else var f = !0;
										}
									}
								}
							}
						}
					}
				}
			} else return Ke.errors = [{
				instancePath: t,
				schemaPath: "#/type",
				keyword: "type",
				params: { type: "object" }
			}], !1;
		}
		return Ke.errors = c, l === 0;
	}
	Ke.evaluated = {
		props: !0,
		dynamicProps: !1,
		dynamicItems: !1
	};
	function qe(e, { instancePath: t = "", parentData: r, parentDataProperty: i, rootData: a = e, dynamicAnchors: o = {} } = {}) {
		let s = null, c = 0, l = qe.evaluated;
		if (l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0) {
			if (e && typeof e == "object" && !Array.isArray(e)) {
				let r;
				if ((e.data === void 0 || !n.call(e, "data")) && (r = "data") || (e.meta === void 0 || !n.call(e, "meta")) && (r = "meta")) return qe.errors = [{
					instancePath: t,
					schemaPath: "#/required",
					keyword: "required",
					params: { missingProperty: r }
				}], !1;
				{
					let r = c;
					for (let n of Object.keys(e)) if (n !== "data" && n !== "meta") return qe.errors = [{
						instancePath: t,
						schemaPath: "#/additionalProperties",
						keyword: "additionalProperties",
						params: { additionalProperty: n }
					}], !1;
					if (r === c) {
						if (e.data !== void 0 && n.call(e, "data")) {
							let n = c;
							Ke(e.data, {
								instancePath: t + "/data",
								parentData: e,
								parentDataProperty: "data",
								rootData: a,
								dynamicAnchors: o
							}) || (s = s === null ? Ke.errors : s.concat(Ke.errors), c = s.length);
							var u = n === c;
						} else var u = !0;
						if (u) {
							if (e.meta !== void 0 && n.call(e, "meta")) {
								let n = c;
								y(e.meta, {
									instancePath: t + "/meta",
									parentData: e,
									parentDataProperty: "meta",
									rootData: a,
									dynamicAnchors: o
								}) || (s = s === null ? y.errors : s.concat(y.errors), c = s.length);
								var u = n === c;
							} else var u = !0;
						}
					}
				}
			} else return qe.errors = [{
				instancePath: t,
				schemaPath: "#/type",
				keyword: "type",
				params: { type: "object" }
			}], !1;
		}
		return qe.errors = s, c === 0;
	}
	qe.evaluated = {
		props: !0,
		dynamicProps: !1,
		dynamicItems: !1
	}, e.v36 = Ye;
	function Je(e, { instancePath: t = "", parentData: r, parentDataProperty: i, rootData: a = e, dynamicAnchors: o = {} } = {}) {
		let s = null, c = 0, l = Je.evaluated;
		if (l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0) {
			if (e && typeof e == "object" && !Array.isArray(e)) {
				let r;
				if ((e.items === void 0 || !n.call(e, "items")) && (r = "items")) return Je.errors = [{
					instancePath: t,
					schemaPath: "#/required",
					keyword: "required",
					params: { missingProperty: r }
				}], !1;
				{
					let r = c;
					for (let n of Object.keys(e)) if (n !== "items") return Je.errors = [{
						instancePath: t,
						schemaPath: "#/additionalProperties",
						keyword: "additionalProperties",
						params: { additionalProperty: n }
					}], !1;
					if (r === c && e.items !== void 0 && n.call(e, "items")) {
						let r = e.items;
						if (c === c) {
							if (Array.isArray(r)) {
								if (r.length > 3) return Je.errors = [{
									instancePath: t + "/items",
									schemaPath: "#/properties/items/maxItems",
									keyword: "maxItems",
									params: { limit: 3 }
								}], !1;
								if (r.length < 2) return Je.errors = [{
									instancePath: t + "/items",
									schemaPath: "#/properties/items/minItems",
									keyword: "minItems",
									params: { limit: 2 }
								}], !1;
								{
									let e = r.length;
									for (let i = 0; i < e; i++) {
										let e = r[i], l = c;
										if (c === l) {
											if (e && typeof e == "object" && !Array.isArray(e)) {
												let l;
												if ((e.state === void 0 || !n.call(e, "state")) && (l = "state")) return Je.errors = [{
													instancePath: t + "/items/" + i,
													schemaPath: "#/properties/items/items/required",
													keyword: "required",
													params: { missingProperty: l }
												}], !1;
												if (e.state !== void 0 && n.call(e, "state")) {
													let n = c;
													if (typeof e.state != "string") return Je.errors = [{
														instancePath: t + "/items/" + i + "/state",
														schemaPath: "#/properties/items/items/properties/state/type",
														keyword: "type",
														params: { type: "string" }
													}], !1;
													var u = n === c;
												} else var u = !0;
												if (u) {
													let n = e.state;
													if (typeof n == "string") {
														if (n === "current") {
															T(e, {
																instancePath: t + "/items/" + i,
																parentData: r,
																parentDataProperty: i,
																rootData: a,
																dynamicAnchors: o
															}) || (s = s === null ? T.errors : s.concat(T.errors), c = s.length);
															var d = !0;
														} else if (n === "historical") T(e, {
															instancePath: t + "/items/" + i,
															parentData: r,
															parentDataProperty: i,
															rootData: a,
															dynamicAnchors: o
														}) || (s = s === null ? T.errors : s.concat(T.errors), c = s.length), d !== !0 && (d = !0);
														else if (n === "missing") Se(e, {
															instancePath: t + "/items/" + i,
															parentData: r,
															parentDataProperty: i,
															rootData: a,
															dynamicAnchors: o
														}) || (s = s === null ? Se.errors : s.concat(Se.errors), c = s.length), d !== !0 && (d = !0);
														else if (n === "error") we(e, {
															instancePath: t + "/items/" + i,
															parentData: r,
															parentDataProperty: i,
															rootData: a,
															dynamicAnchors: o
														}) || (s = s === null ? we.errors : s.concat(we.errors), c = s.length), d !== !0 && (d = !0);
														else return Je.errors = [{
															instancePath: t + "/items/" + i,
															schemaPath: "#/properties/items/items/discriminator",
															keyword: "discriminator",
															params: {
																error: "mapping",
																tag: "state",
																tagValue: n
															}
														}], !1;
													} else return Je.errors = [{
														instancePath: t + "/items/" + i,
														schemaPath: "#/properties/items/items/discriminator",
														keyword: "discriminator",
														params: {
															error: "tag",
															tag: "state",
															tagValue: n
														}
													}], !1;
												}
											} else return Je.errors = [{
												instancePath: t + "/items/" + i,
												schemaPath: "#/properties/items/items/type",
												keyword: "type",
												params: { type: "object" }
											}], !1;
										}
										if (l !== c) break;
									}
								}
							} else return Je.errors = [{
								instancePath: t + "/items",
								schemaPath: "#/properties/items/type",
								keyword: "type",
								params: { type: "array" }
							}], !1;
						}
					}
				}
			} else return Je.errors = [{
				instancePath: t,
				schemaPath: "#/type",
				keyword: "type",
				params: { type: "object" }
			}], !1;
		}
		return Je.errors = s, c === 0;
	}
	Je.evaluated = {
		props: !0,
		dynamicProps: !1,
		dynamicItems: !1
	};
	function Ye(e, { instancePath: t = "", parentData: r, parentDataProperty: i, rootData: a = e, dynamicAnchors: o = {} } = {}) {
		let s = null, c = 0, l = Ye.evaluated;
		if (l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0) {
			if (e && typeof e == "object" && !Array.isArray(e)) {
				let r;
				if ((e.data === void 0 || !n.call(e, "data")) && (r = "data") || (e.meta === void 0 || !n.call(e, "meta")) && (r = "meta")) return Ye.errors = [{
					instancePath: t,
					schemaPath: "#/required",
					keyword: "required",
					params: { missingProperty: r }
				}], !1;
				{
					let r = c;
					for (let n of Object.keys(e)) if (n !== "data" && n !== "meta") return Ye.errors = [{
						instancePath: t,
						schemaPath: "#/additionalProperties",
						keyword: "additionalProperties",
						params: { additionalProperty: n }
					}], !1;
					if (r === c) {
						if (e.data !== void 0 && n.call(e, "data")) {
							let n = c;
							Je(e.data, {
								instancePath: t + "/data",
								parentData: e,
								parentDataProperty: "data",
								rootData: a,
								dynamicAnchors: o
							}) || (s = s === null ? Je.errors : s.concat(Je.errors), c = s.length);
							var u = n === c;
						} else var u = !0;
						if (u) {
							if (e.meta !== void 0 && n.call(e, "meta")) {
								let n = c;
								y(e.meta, {
									instancePath: t + "/meta",
									parentData: e,
									parentDataProperty: "meta",
									rootData: a,
									dynamicAnchors: o
								}) || (s = s === null ? y.errors : s.concat(y.errors), c = s.length);
								var u = n === c;
							} else var u = !0;
						}
					}
				}
			} else return Ye.errors = [{
				instancePath: t,
				schemaPath: "#/type",
				keyword: "type",
				params: { type: "object" }
			}], !1;
		}
		return Ye.errors = s, c === 0;
	}
	Ye.evaluated = {
		props: !0,
		dynamicProps: !1,
		dynamicItems: !1
	}, e.v37 = Ze;
	function Xe(e, { instancePath: t = "", parentData: r, parentDataProperty: i, rootData: a = e, dynamicAnchors: o = {} } = {}) {
		let s = Xe.evaluated;
		if (s.dynamicProps && (s.props = void 0), s.dynamicItems && (s.items = void 0), e && typeof e == "object" && !Array.isArray(e)) {
			let r;
			if ((e.state === void 0 || !n.call(e, "state")) && (r = "state")) return Xe.errors = [{
				instancePath: t,
				schemaPath: "#/required",
				keyword: "required",
				params: { missingProperty: r }
			}], !1;
			for (let n of Object.keys(e)) if (n !== "state") return Xe.errors = [{
				instancePath: t,
				schemaPath: "#/additionalProperties",
				keyword: "additionalProperties",
				params: { additionalProperty: n }
			}], !1;
			if (e.state !== void 0 && n.call(e, "state")) {
				let n = e.state;
				if (typeof n != "string") return Xe.errors = [{
					instancePath: t + "/state",
					schemaPath: "#/properties/state/type",
					keyword: "type",
					params: { type: "string" }
				}], !1;
				if (n !== "ended") return Xe.errors = [{
					instancePath: t + "/state",
					schemaPath: "#/properties/state/const",
					keyword: "const",
					params: { allowedValue: "ended" }
				}], !1;
			}
		} else return Xe.errors = [{
			instancePath: t,
			schemaPath: "#/type",
			keyword: "type",
			params: { type: "object" }
		}], !1;
		return Xe.errors = null, !0;
	}
	Xe.evaluated = {
		props: !0,
		dynamicProps: !1,
		dynamicItems: !1
	};
	function Ze(e, { instancePath: t = "", parentData: r, parentDataProperty: i, rootData: a = e, dynamicAnchors: o = {} } = {}) {
		let s = null, c = 0, l = Ze.evaluated;
		if (l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0) {
			if (e && typeof e == "object" && !Array.isArray(e)) {
				let r;
				if ((e.data === void 0 || !n.call(e, "data")) && (r = "data") || (e.meta === void 0 || !n.call(e, "meta")) && (r = "meta")) return Ze.errors = [{
					instancePath: t,
					schemaPath: "#/required",
					keyword: "required",
					params: { missingProperty: r }
				}], !1;
				{
					let r = c;
					for (let n of Object.keys(e)) if (n !== "data" && n !== "meta") return Ze.errors = [{
						instancePath: t,
						schemaPath: "#/additionalProperties",
						keyword: "additionalProperties",
						params: { additionalProperty: n }
					}], !1;
					if (r === c) {
						if (e.data !== void 0 && n.call(e, "data")) {
							let n = c;
							Xe(e.data, {
								instancePath: t + "/data",
								parentData: e,
								parentDataProperty: "data",
								rootData: a,
								dynamicAnchors: o
							}) || (s = s === null ? Xe.errors : s.concat(Xe.errors), c = s.length);
							var u = n === c;
						} else var u = !0;
						if (u) {
							if (e.meta !== void 0 && n.call(e, "meta")) {
								let n = c;
								y(e.meta, {
									instancePath: t + "/meta",
									parentData: e,
									parentDataProperty: "meta",
									rootData: a,
									dynamicAnchors: o
								}) || (s = s === null ? y.errors : s.concat(y.errors), c = s.length);
								var u = n === c;
							} else var u = !0;
						}
					}
				}
			} else return Ze.errors = [{
				instancePath: t,
				schemaPath: "#/type",
				keyword: "type",
				params: { type: "object" }
			}], !1;
		}
		return Ze.errors = s, c === 0;
	}
	Ze.evaluated = {
		props: !0,
		dynamicProps: !1,
		dynamicItems: !1
	}, e.v38 = et;
	var Qe = {
		additionalProperties: !1,
		properties: {
			reason: {
				anyOf: [{
					maxLength: 200,
					minLength: 1,
					type: "string"
				}, { type: "null" }],
				title: "Reason"
			},
			state: {
				enum: [
					"ready",
					"unavailable",
					"unconfigured",
					"degraded"
				],
				title: "State",
				type: "string"
			}
		},
		required: ["state", "reason"],
		title: "Capability",
		type: "object"
	};
	function F(e, { instancePath: t = "", parentData: r, parentDataProperty: i, rootData: a = e, dynamicAnchors: o = {} } = {}) {
		let s = null, c = 0, l = F.evaluated;
		if (l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0) {
			if (e && typeof e == "object" && !Array.isArray(e)) {
				let r;
				if ((e.state === void 0 || !n.call(e, "state")) && (r = "state") || (e.reason === void 0 || !n.call(e, "reason")) && (r = "reason")) return F.errors = [{
					instancePath: t,
					schemaPath: "#/required",
					keyword: "required",
					params: { missingProperty: r }
				}], !1;
				{
					let r = c;
					for (let n of Object.keys(e)) if (n !== "reason" && n !== "state") return F.errors = [{
						instancePath: t,
						schemaPath: "#/additionalProperties",
						keyword: "additionalProperties",
						params: { additionalProperty: n }
					}], !1;
					if (r === c) {
						if (e.reason !== void 0 && n.call(e, "reason")) {
							let n = e.reason, r = c, i = c, a = !1, o = c;
							if (c === o) {
								if (typeof n == "string") {
									if (h(n) > 200) {
										let e = {
											instancePath: t + "/reason",
											schemaPath: "#/properties/reason/anyOf/0/maxLength",
											keyword: "maxLength",
											params: { limit: 200 }
										};
										s === null ? s = [e] : s.push(e), c++;
									} else if (h(n) < 1) {
										let e = {
											instancePath: t + "/reason",
											schemaPath: "#/properties/reason/anyOf/0/minLength",
											keyword: "minLength",
											params: { limit: 1 }
										};
										s === null ? s = [e] : s.push(e), c++;
									}
								} else {
									let e = {
										instancePath: t + "/reason",
										schemaPath: "#/properties/reason/anyOf/0/type",
										keyword: "type",
										params: { type: "string" }
									};
									s === null ? s = [e] : s.push(e), c++;
								}
							}
							var u = o === c;
							a ||= u;
							let l = c;
							if (n !== null) {
								let e = {
									instancePath: t + "/reason",
									schemaPath: "#/properties/reason/anyOf/1/type",
									keyword: "type",
									params: { type: "null" }
								};
								s === null ? s = [e] : s.push(e), c++;
							}
							var u = l === c;
							if (a ||= u, a) c = i, s !== null && (i ? s.length = i : s = null);
							else {
								let e = {
									instancePath: t + "/reason",
									schemaPath: "#/properties/reason/anyOf",
									keyword: "anyOf",
									params: {}
								};
								return s === null ? s = [e] : s.push(e), c++, F.errors = s, !1;
							}
							var d = r === c;
						} else var d = !0;
						if (d) {
							if (e.state !== void 0 && n.call(e, "state")) {
								let n = e.state, r = c;
								if (typeof n != "string") return F.errors = [{
									instancePath: t + "/state",
									schemaPath: "#/properties/state/type",
									keyword: "type",
									params: { type: "string" }
								}], !1;
								if (n !== "ready" && n !== "unavailable" && n !== "unconfigured" && n !== "degraded") return F.errors = [{
									instancePath: t + "/state",
									schemaPath: "#/properties/state/enum",
									keyword: "enum",
									params: { allowedValues: Qe.properties.state.enum }
								}], !1;
								var d = r === c;
							} else var d = !0;
						}
					}
				}
			} else return F.errors = [{
				instancePath: t,
				schemaPath: "#/type",
				keyword: "type",
				params: { type: "object" }
			}], !1;
		}
		return F.errors = s, c === 0;
	}
	F.evaluated = {
		props: !0,
		dynamicProps: !1,
		dynamicItems: !1
	};
	function $e(e, { instancePath: t = "", parentData: r, parentDataProperty: i, rootData: a = e, dynamicAnchors: o = {} } = {}) {
		let c = null, l = 0, u = $e.evaluated;
		if (u.dynamicProps && (u.props = void 0), u.dynamicItems && (u.items = void 0), l === 0) {
			if (e && typeof e == "object" && !Array.isArray(e)) {
				let r;
				if ((e.inventory === void 0 || !n.call(e, "inventory")) && (r = "inventory") || (e.store === void 0 || !n.call(e, "store")) && (r = "store") || (e.viewing === void 0 || !n.call(e, "viewing")) && (r = "viewing") || (e.export === void 0 || !n.call(e, "export")) && (r = "export") || (e.assistant === void 0 || !n.call(e, "assistant")) && (r = "assistant") || (e.active_snapshot_id === void 0 || !n.call(e, "active_snapshot_id")) && (r = "active_snapshot_id")) return $e.errors = [{
					instancePath: t,
					schemaPath: "#/required",
					keyword: "required",
					params: { missingProperty: r }
				}], !1;
				{
					let r = l;
					for (let n of Object.keys(e)) if (n !== "active_snapshot_id" && n !== "assistant" && n !== "export" && n !== "inventory" && n !== "service" && n !== "store" && n !== "viewing") return $e.errors = [{
						instancePath: t,
						schemaPath: "#/additionalProperties",
						keyword: "additionalProperties",
						params: { additionalProperty: n }
					}], !1;
					if (r === l) {
						if (e.active_snapshot_id !== void 0 && n.call(e, "active_snapshot_id")) {
							let n = e.active_snapshot_id, r = l, i = l, a = !1, o = l;
							if (l === o) {
								if (typeof n == "string") {
									if (!s.test(n)) {
										let e = {
											instancePath: t + "/active_snapshot_id",
											schemaPath: "#/properties/active_snapshot_id/anyOf/0/pattern",
											keyword: "pattern",
											params: { pattern: "^[0-9a-f]{64}$" }
										};
										c === null ? c = [e] : c.push(e), l++;
									}
								} else {
									let e = {
										instancePath: t + "/active_snapshot_id",
										schemaPath: "#/properties/active_snapshot_id/anyOf/0/type",
										keyword: "type",
										params: { type: "string" }
									};
									c === null ? c = [e] : c.push(e), l++;
								}
							}
							var d = o === l;
							a ||= d;
							let u = l;
							if (n !== null) {
								let e = {
									instancePath: t + "/active_snapshot_id",
									schemaPath: "#/properties/active_snapshot_id/anyOf/1/type",
									keyword: "type",
									params: { type: "null" }
								};
								c === null ? c = [e] : c.push(e), l++;
							}
							var d = u === l;
							if (a ||= d, a) l = i, c !== null && (i ? c.length = i : c = null);
							else {
								let e = {
									instancePath: t + "/active_snapshot_id",
									schemaPath: "#/properties/active_snapshot_id/anyOf",
									keyword: "anyOf",
									params: {}
								};
								return c === null ? c = [e] : c.push(e), l++, $e.errors = c, !1;
							}
							var f = r === l;
						} else var f = !0;
						if (f) {
							if (e.assistant !== void 0 && n.call(e, "assistant")) {
								let n = l;
								F(e.assistant, {
									instancePath: t + "/assistant",
									parentData: e,
									parentDataProperty: "assistant",
									rootData: a,
									dynamicAnchors: o
								}) || (c = c === null ? F.errors : c.concat(F.errors), l = c.length);
								var f = n === l;
							} else var f = !0;
							if (f) {
								if (e.export !== void 0 && n.call(e, "export")) {
									let n = l;
									F(e.export, {
										instancePath: t + "/export",
										parentData: e,
										parentDataProperty: "export",
										rootData: a,
										dynamicAnchors: o
									}) || (c = c === null ? F.errors : c.concat(F.errors), l = c.length);
									var f = n === l;
								} else var f = !0;
								if (f) {
									if (e.inventory !== void 0 && n.call(e, "inventory")) {
										let n = l;
										F(e.inventory, {
											instancePath: t + "/inventory",
											parentData: e,
											parentDataProperty: "inventory",
											rootData: a,
											dynamicAnchors: o
										}) || (c = c === null ? F.errors : c.concat(F.errors), l = c.length);
										var f = n === l;
									} else var f = !0;
									if (f) {
										if (e.service !== void 0 && n.call(e, "service")) {
											let n = e.service, r = l;
											if (typeof n != "string") return $e.errors = [{
												instancePath: t + "/service",
												schemaPath: "#/properties/service/type",
												keyword: "type",
												params: { type: "string" }
											}], !1;
											if (n !== "car-shopping-assistant") return $e.errors = [{
												instancePath: t + "/service",
												schemaPath: "#/properties/service/const",
												keyword: "const",
												params: { allowedValue: "car-shopping-assistant" }
											}], !1;
											var f = r === l;
										} else var f = !0;
										if (f) {
											if (e.store !== void 0 && n.call(e, "store")) {
												let n = l;
												F(e.store, {
													instancePath: t + "/store",
													parentData: e,
													parentDataProperty: "store",
													rootData: a,
													dynamicAnchors: o
												}) || (c = c === null ? F.errors : c.concat(F.errors), l = c.length);
												var f = n === l;
											} else var f = !0;
											if (f) {
												if (e.viewing !== void 0 && n.call(e, "viewing")) {
													let n = l;
													F(e.viewing, {
														instancePath: t + "/viewing",
														parentData: e,
														parentDataProperty: "viewing",
														rootData: a,
														dynamicAnchors: o
													}) || (c = c === null ? F.errors : c.concat(F.errors), l = c.length);
													var f = n === l;
												} else var f = !0;
											}
										}
									}
								}
							}
						}
					}
				}
			} else return $e.errors = [{
				instancePath: t,
				schemaPath: "#/type",
				keyword: "type",
				params: { type: "object" }
			}], !1;
		}
		return $e.errors = c, l === 0;
	}
	$e.evaluated = {
		props: !0,
		dynamicProps: !1,
		dynamicItems: !1
	};
	function et(e, { instancePath: t = "", parentData: r, parentDataProperty: i, rootData: a = e, dynamicAnchors: o = {} } = {}) {
		let s = null, c = 0, l = et.evaluated;
		if (l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0) {
			if (e && typeof e == "object" && !Array.isArray(e)) {
				let r;
				if ((e.data === void 0 || !n.call(e, "data")) && (r = "data") || (e.meta === void 0 || !n.call(e, "meta")) && (r = "meta")) return et.errors = [{
					instancePath: t,
					schemaPath: "#/required",
					keyword: "required",
					params: { missingProperty: r }
				}], !1;
				{
					let r = c;
					for (let n of Object.keys(e)) if (n !== "data" && n !== "meta") return et.errors = [{
						instancePath: t,
						schemaPath: "#/additionalProperties",
						keyword: "additionalProperties",
						params: { additionalProperty: n }
					}], !1;
					if (r === c) {
						if (e.data !== void 0 && n.call(e, "data")) {
							let n = c;
							$e(e.data, {
								instancePath: t + "/data",
								parentData: e,
								parentDataProperty: "data",
								rootData: a,
								dynamicAnchors: o
							}) || (s = s === null ? $e.errors : s.concat($e.errors), c = s.length);
							var u = n === c;
						} else var u = !0;
						if (u) {
							if (e.meta !== void 0 && n.call(e, "meta")) {
								let n = c;
								y(e.meta, {
									instancePath: t + "/meta",
									parentData: e,
									parentDataProperty: "meta",
									rootData: a,
									dynamicAnchors: o
								}) || (s = s === null ? y.errors : s.concat(y.errors), c = s.length);
								var u = n === c;
							} else var u = !0;
						}
					}
				}
			} else return et.errors = [{
				instancePath: t,
				schemaPath: "#/type",
				keyword: "type",
				params: { type: "object" }
			}], !1;
		}
		return et.errors = s, c === 0;
	}
	et.evaluated = {
		props: !0,
		dynamicProps: !1,
		dynamicItems: !1
	}, e.v39 = nt;
	var tt = {
		additionalProperties: !1,
		properties: {
			booking_ids: {
				items: {
					pattern: "^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$",
					type: "string"
				},
				maxItems: 100,
				title: "Booking Ids",
				type: "array"
			},
			csv: {
				discriminator: { propertyName: "state" },
				oneOf: [{ $ref: "urn:car-shopping-assistant:contract:1#/$defs/ExportCurrent" }, { $ref: "urn:car-shopping-assistant:contract:1#/$defs/ExportPending" }],
				title: "Csv",
				type: "object",
				required: ["state"],
				properties: { state: { type: "string" } }
			},
			delivery: {
				const: "local_only",
				default: "local_only",
				title: "Delivery",
				type: "string"
			},
			expires_at: {
				pattern: "^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}(?:\\.\\d{1,6})?Z$",
				title: "Expires At",
				type: "string"
			},
			journey_id: {
				pattern: "^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$",
				title: "Journey Id",
				type: "string"
			},
			lead_id: {
				pattern: "^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$",
				title: "Lead Id",
				type: "string"
			},
			revision: {
				maximum: 2147483647,
				minimum: 0,
				title: "Revision",
				type: "integer"
			},
			stage: {
				enum: ["interested", "viewing_confirmed"],
				title: "Stage",
				type: "string"
			},
			updated_at: {
				pattern: "^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}(?:\\.\\d{1,6})?Z$",
				title: "Updated At",
				type: "string"
			},
			values: { $ref: "urn:car-shopping-assistant:contract:1#/$defs/LeadValues" }
		},
		required: [
			"lead_id",
			"journey_id",
			"revision",
			"stage",
			"values",
			"booking_ids",
			"updated_at",
			"expires_at",
			"csv"
		],
		title: "LeadRecord",
		type: "object"
	};
	function I(e, { instancePath: t = "", parentData: r, parentDataProperty: a, rootData: o = e, dynamicAnchors: s = {} } = {}) {
		let c = null, l = 0, d = I.evaluated;
		if (d.dynamicProps && (d.props = void 0), d.dynamicItems && (d.items = void 0), l === 0) {
			if (e && typeof e == "object" && !Array.isArray(e)) {
				let r;
				if ((e.lead_id === void 0 || !n.call(e, "lead_id")) && (r = "lead_id") || (e.journey_id === void 0 || !n.call(e, "journey_id")) && (r = "journey_id") || (e.revision === void 0 || !n.call(e, "revision")) && (r = "revision") || (e.stage === void 0 || !n.call(e, "stage")) && (r = "stage") || (e.values === void 0 || !n.call(e, "values")) && (r = "values") || (e.booking_ids === void 0 || !n.call(e, "booking_ids")) && (r = "booking_ids") || (e.updated_at === void 0 || !n.call(e, "updated_at")) && (r = "updated_at") || (e.expires_at === void 0 || !n.call(e, "expires_at")) && (r = "expires_at") || (e.csv === void 0 || !n.call(e, "csv")) && (r = "csv")) return I.errors = [{
					instancePath: t,
					schemaPath: "#/required",
					keyword: "required",
					params: { missingProperty: r }
				}], !1;
				{
					let r = l;
					for (let r of Object.keys(e)) if (!n.call(tt.properties, r)) return I.errors = [{
						instancePath: t,
						schemaPath: "#/additionalProperties",
						keyword: "additionalProperties",
						params: { additionalProperty: r }
					}], !1;
					if (r === l) {
						if (e.booking_ids !== void 0 && n.call(e, "booking_ids")) {
							let n = e.booking_ids, r = l;
							if (l === r) {
								if (Array.isArray(n)) {
									if (n.length > 100) return I.errors = [{
										instancePath: t + "/booking_ids",
										schemaPath: "#/properties/booking_ids/maxItems",
										keyword: "maxItems",
										params: { limit: 100 }
									}], !1;
									{
										let e = n.length;
										for (let r = 0; r < e; r++) {
											let e = n[r], i = l;
											if (l === i) {
												if (typeof e == "string") {
													if (!u.test(e)) return I.errors = [{
														instancePath: t + "/booking_ids/" + r,
														schemaPath: "#/properties/booking_ids/items/pattern",
														keyword: "pattern",
														params: { pattern: "^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$" }
													}], !1;
												} else return I.errors = [{
													instancePath: t + "/booking_ids/" + r,
													schemaPath: "#/properties/booking_ids/items/type",
													keyword: "type",
													params: { type: "string" }
												}], !1;
											}
											if (i !== l) break;
										}
									}
								} else return I.errors = [{
									instancePath: t + "/booking_ids",
									schemaPath: "#/properties/booking_ids/type",
									keyword: "type",
									params: { type: "array" }
								}], !1;
							}
							var f = r === l;
						} else var f = !0;
						if (f) {
							if (e.csv !== void 0 && n.call(e, "csv")) {
								let r = e.csv, i = l;
								if (l === i) {
									if (r && typeof r == "object" && !Array.isArray(r)) {
										let i;
										if ((r.state === void 0 || !n.call(r, "state")) && (i = "state")) return I.errors = [{
											instancePath: t + "/csv",
											schemaPath: "#/properties/csv/required",
											keyword: "required",
											params: { missingProperty: i }
										}], !1;
										if (r.state !== void 0 && n.call(r, "state")) {
											let e = l;
											if (typeof r.state != "string") return I.errors = [{
												instancePath: t + "/csv/state",
												schemaPath: "#/properties/csv/properties/state/type",
												keyword: "type",
												params: { type: "string" }
											}], !1;
											var p = e === l;
										} else var p = !0;
										if (p) {
											let n = r.state;
											if (typeof n == "string") {
												if (n === "current") {
													O(r, {
														instancePath: t + "/csv",
														parentData: e,
														parentDataProperty: "csv",
														rootData: o,
														dynamicAnchors: s
													}) || (c = c === null ? O.errors : c.concat(O.errors), l = c.length);
													var m = !0;
												} else if (n === "pending") k(r, {
													instancePath: t + "/csv",
													parentData: e,
													parentDataProperty: "csv",
													rootData: o,
													dynamicAnchors: s
												}) || (c = c === null ? k.errors : c.concat(k.errors), l = c.length), m !== !0 && (m = !0);
												else if (n === "failed") k(r, {
													instancePath: t + "/csv",
													parentData: e,
													parentDataProperty: "csv",
													rootData: o,
													dynamicAnchors: s
												}) || (c = c === null ? k.errors : c.concat(k.errors), l = c.length), m !== !0 && (m = !0);
												else return I.errors = [{
													instancePath: t + "/csv",
													schemaPath: "#/properties/csv/discriminator",
													keyword: "discriminator",
													params: {
														error: "mapping",
														tag: "state",
														tagValue: n
													}
												}], !1;
											} else return I.errors = [{
												instancePath: t + "/csv",
												schemaPath: "#/properties/csv/discriminator",
												keyword: "discriminator",
												params: {
													error: "tag",
													tag: "state",
													tagValue: n
												}
											}], !1;
										}
									} else return I.errors = [{
										instancePath: t + "/csv",
										schemaPath: "#/properties/csv/type",
										keyword: "type",
										params: { type: "object" }
									}], !1;
								}
								var f = i === l;
							} else var f = !0;
							if (f) {
								if (e.delivery !== void 0 && n.call(e, "delivery")) {
									let n = e.delivery, r = l;
									if (typeof n != "string") return I.errors = [{
										instancePath: t + "/delivery",
										schemaPath: "#/properties/delivery/type",
										keyword: "type",
										params: { type: "string" }
									}], !1;
									if (n !== "local_only") return I.errors = [{
										instancePath: t + "/delivery",
										schemaPath: "#/properties/delivery/const",
										keyword: "const",
										params: { allowedValue: "local_only" }
									}], !1;
									var f = r === l;
								} else var f = !0;
								if (f) {
									if (e.expires_at !== void 0 && n.call(e, "expires_at")) {
										let n = e.expires_at, r = l;
										if (l === r) {
											if (typeof n == "string") {
												if (!i.test(n)) return I.errors = [{
													instancePath: t + "/expires_at",
													schemaPath: "#/properties/expires_at/pattern",
													keyword: "pattern",
													params: { pattern: "^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}(?:\\.\\d{1,6})?Z$" }
												}], !1;
											} else return I.errors = [{
												instancePath: t + "/expires_at",
												schemaPath: "#/properties/expires_at/type",
												keyword: "type",
												params: { type: "string" }
											}], !1;
										}
										var f = r === l;
									} else var f = !0;
									if (f) {
										if (e.journey_id !== void 0 && n.call(e, "journey_id")) {
											let n = e.journey_id, r = l;
											if (l === r) {
												if (typeof n == "string") {
													if (!u.test(n)) return I.errors = [{
														instancePath: t + "/journey_id",
														schemaPath: "#/properties/journey_id/pattern",
														keyword: "pattern",
														params: { pattern: "^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$" }
													}], !1;
												} else return I.errors = [{
													instancePath: t + "/journey_id",
													schemaPath: "#/properties/journey_id/type",
													keyword: "type",
													params: { type: "string" }
												}], !1;
											}
											var f = r === l;
										} else var f = !0;
										if (f) {
											if (e.lead_id !== void 0 && n.call(e, "lead_id")) {
												let n = e.lead_id, r = l;
												if (l === r) {
													if (typeof n == "string") {
														if (!u.test(n)) return I.errors = [{
															instancePath: t + "/lead_id",
															schemaPath: "#/properties/lead_id/pattern",
															keyword: "pattern",
															params: { pattern: "^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$" }
														}], !1;
													} else return I.errors = [{
														instancePath: t + "/lead_id",
														schemaPath: "#/properties/lead_id/type",
														keyword: "type",
														params: { type: "string" }
													}], !1;
												}
												var f = r === l;
											} else var f = !0;
											if (f) {
												if (e.revision !== void 0 && n.call(e, "revision")) {
													let n = e.revision, r = l;
													if (typeof n != "number" || n % 1 || isNaN(n) || !isFinite(n)) return I.errors = [{
														instancePath: t + "/revision",
														schemaPath: "#/properties/revision/type",
														keyword: "type",
														params: { type: "integer" }
													}], !1;
													if (l === r && typeof n == "number" && isFinite(n)) {
														if (n > 2147483647 || isNaN(n)) return I.errors = [{
															instancePath: t + "/revision",
															schemaPath: "#/properties/revision/maximum",
															keyword: "maximum",
															params: {
																comparison: "<=",
																limit: 2147483647
															}
														}], !1;
														if (n < 0 || isNaN(n)) return I.errors = [{
															instancePath: t + "/revision",
															schemaPath: "#/properties/revision/minimum",
															keyword: "minimum",
															params: {
																comparison: ">=",
																limit: 0
															}
														}], !1;
													}
													var f = r === l;
												} else var f = !0;
												if (f) {
													if (e.stage !== void 0 && n.call(e, "stage")) {
														let n = e.stage, r = l;
														if (typeof n != "string") return I.errors = [{
															instancePath: t + "/stage",
															schemaPath: "#/properties/stage/type",
															keyword: "type",
															params: { type: "string" }
														}], !1;
														if (n !== "interested" && n !== "viewing_confirmed") return I.errors = [{
															instancePath: t + "/stage",
															schemaPath: "#/properties/stage/enum",
															keyword: "enum",
															params: { allowedValues: tt.properties.stage.enum }
														}], !1;
														var f = r === l;
													} else var f = !0;
													if (f) {
														if (e.updated_at !== void 0 && n.call(e, "updated_at")) {
															let n = e.updated_at, r = l;
															if (l === r) {
																if (typeof n == "string") {
																	if (!i.test(n)) return I.errors = [{
																		instancePath: t + "/updated_at",
																		schemaPath: "#/properties/updated_at/pattern",
																		keyword: "pattern",
																		params: { pattern: "^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}(?:\\.\\d{1,6})?Z$" }
																	}], !1;
																} else return I.errors = [{
																	instancePath: t + "/updated_at",
																	schemaPath: "#/properties/updated_at/type",
																	keyword: "type",
																	params: { type: "string" }
																}], !1;
															}
															var f = r === l;
														} else var f = !0;
														if (f) {
															if (e.values !== void 0 && n.call(e, "values")) {
																let n = l;
																E(e.values, {
																	instancePath: t + "/values",
																	parentData: e,
																	parentDataProperty: "values",
																	rootData: o,
																	dynamicAnchors: s
																}) || (c = c === null ? E.errors : c.concat(E.errors), l = c.length);
																var f = n === l;
															} else var f = !0;
														}
													}
												}
											}
										}
									}
								}
							}
						}
					}
				}
			} else return I.errors = [{
				instancePath: t,
				schemaPath: "#/type",
				keyword: "type",
				params: { type: "object" }
			}], !1;
		}
		return I.errors = c, l === 0;
	}
	I.evaluated = {
		props: !0,
		dynamicProps: !1,
		dynamicItems: !1
	};
	function nt(e, { instancePath: t = "", parentData: r, parentDataProperty: i, rootData: a = e, dynamicAnchors: o = {} } = {}) {
		let s = null, c = 0, l = nt.evaluated;
		if (l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0) {
			if (e && typeof e == "object" && !Array.isArray(e)) {
				let r;
				if ((e.data === void 0 || !n.call(e, "data")) && (r = "data") || (e.meta === void 0 || !n.call(e, "meta")) && (r = "meta")) return nt.errors = [{
					instancePath: t,
					schemaPath: "#/required",
					keyword: "required",
					params: { missingProperty: r }
				}], !1;
				{
					let r = c;
					for (let n of Object.keys(e)) if (n !== "data" && n !== "meta") return nt.errors = [{
						instancePath: t,
						schemaPath: "#/additionalProperties",
						keyword: "additionalProperties",
						params: { additionalProperty: n }
					}], !1;
					if (r === c) {
						if (e.data !== void 0 && n.call(e, "data")) {
							let n = c;
							I(e.data, {
								instancePath: t + "/data",
								parentData: e,
								parentDataProperty: "data",
								rootData: a,
								dynamicAnchors: o
							}) || (s = s === null ? I.errors : s.concat(I.errors), c = s.length);
							var u = n === c;
						} else var u = !0;
						if (u) {
							if (e.meta !== void 0 && n.call(e, "meta")) {
								let n = c;
								y(e.meta, {
									instancePath: t + "/meta",
									parentData: e,
									parentDataProperty: "meta",
									rootData: a,
									dynamicAnchors: o
								}) || (s = s === null ? y.errors : s.concat(y.errors), c = s.length);
								var u = n === c;
							} else var u = !0;
						}
					}
				}
			} else return nt.errors = [{
				instancePath: t,
				schemaPath: "#/type",
				keyword: "type",
				params: { type: "object" }
			}], !1;
		}
		return nt.errors = s, c === 0;
	}
	nt.evaluated = {
		props: !0,
		dynamicProps: !1,
		dynamicItems: !1
	}, e.v40 = it;
	function rt(e, { instancePath: t = "", parentData: r, parentDataProperty: i, rootData: a = e, dynamicAnchors: o = {} } = {}) {
		let s = null, c = 0, l = rt.evaluated;
		if (l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0) {
			if (e && typeof e == "object" && !Array.isArray(e)) {
				let r;
				if ((e.lead === void 0 || !n.call(e, "lead")) && (r = "lead") || (e.replayed === void 0 || !n.call(e, "replayed")) && (r = "replayed")) return rt.errors = [{
					instancePath: t,
					schemaPath: "#/required",
					keyword: "required",
					params: { missingProperty: r }
				}], !1;
				{
					let r = c;
					for (let n of Object.keys(e)) if (n !== "lead" && n !== "replayed") return rt.errors = [{
						instancePath: t,
						schemaPath: "#/additionalProperties",
						keyword: "additionalProperties",
						params: { additionalProperty: n }
					}], !1;
					if (r === c) {
						if (e.lead !== void 0 && n.call(e, "lead")) {
							let n = c;
							I(e.lead, {
								instancePath: t + "/lead",
								parentData: e,
								parentDataProperty: "lead",
								rootData: a,
								dynamicAnchors: o
							}) || (s = s === null ? I.errors : s.concat(I.errors), c = s.length);
							var u = n === c;
						} else var u = !0;
						if (u) {
							if (e.replayed !== void 0 && n.call(e, "replayed")) {
								let n = c;
								if (typeof e.replayed != "boolean") return rt.errors = [{
									instancePath: t + "/replayed",
									schemaPath: "#/properties/replayed/type",
									keyword: "type",
									params: { type: "boolean" }
								}], !1;
								var u = n === c;
							} else var u = !0;
						}
					}
				}
			} else return rt.errors = [{
				instancePath: t,
				schemaPath: "#/type",
				keyword: "type",
				params: { type: "object" }
			}], !1;
		}
		return rt.errors = s, c === 0;
	}
	rt.evaluated = {
		props: !0,
		dynamicProps: !1,
		dynamicItems: !1
	};
	function it(e, { instancePath: t = "", parentData: r, parentDataProperty: i, rootData: a = e, dynamicAnchors: o = {} } = {}) {
		let s = null, c = 0, l = it.evaluated;
		if (l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0) {
			if (e && typeof e == "object" && !Array.isArray(e)) {
				let r;
				if ((e.data === void 0 || !n.call(e, "data")) && (r = "data") || (e.meta === void 0 || !n.call(e, "meta")) && (r = "meta")) return it.errors = [{
					instancePath: t,
					schemaPath: "#/required",
					keyword: "required",
					params: { missingProperty: r }
				}], !1;
				{
					let r = c;
					for (let n of Object.keys(e)) if (n !== "data" && n !== "meta") return it.errors = [{
						instancePath: t,
						schemaPath: "#/additionalProperties",
						keyword: "additionalProperties",
						params: { additionalProperty: n }
					}], !1;
					if (r === c) {
						if (e.data !== void 0 && n.call(e, "data")) {
							let n = c;
							rt(e.data, {
								instancePath: t + "/data",
								parentData: e,
								parentDataProperty: "data",
								rootData: a,
								dynamicAnchors: o
							}) || (s = s === null ? rt.errors : s.concat(rt.errors), c = s.length);
							var u = n === c;
						} else var u = !0;
						if (u) {
							if (e.meta !== void 0 && n.call(e, "meta")) {
								let n = c;
								y(e.meta, {
									instancePath: t + "/meta",
									parentData: e,
									parentDataProperty: "meta",
									rootData: a,
									dynamicAnchors: o
								}) || (s = s === null ? y.errors : s.concat(y.errors), c = s.length);
								var u = n === c;
							} else var u = !0;
						}
					}
				}
			} else return it.errors = [{
				instancePath: t,
				schemaPath: "#/type",
				keyword: "type",
				params: { type: "object" }
			}], !1;
		}
		return it.errors = s, c === 0;
	}
	it.evaluated = {
		props: !0,
		dynamicProps: !1,
		dynamicItems: !1
	}, e.v41 = ot;
	var at = {
		additionalProperties: !1,
		properties: {
			applied_revision: {
				maximum: 2147483647,
				minimum: 0,
				title: "Applied Revision",
				type: "integer"
			},
			changed_at_apply: {
				title: "Changed At Apply",
				type: "boolean"
			},
			client_action_id: {
				pattern: "^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$",
				title: "Client Action Id",
				type: "string"
			},
			current_revision: {
				maximum: 2147483647,
				minimum: 0,
				title: "Current Revision",
				type: "integer"
			},
			ref: { $ref: "urn:car-shopping-assistant:contract:1#/$defs/InventoryRef" },
			reference_state: {
				enum: [
					"current",
					"historical",
					"missing"
				],
				title: "Reference State",
				type: "string"
			},
			replayed: {
				title: "Replayed",
				type: "boolean"
			},
			saved: {
				title: "Saved",
				type: "boolean"
			}
		},
		required: [
			"ref",
			"client_action_id",
			"saved",
			"changed_at_apply",
			"replayed",
			"applied_revision",
			"current_revision",
			"reference_state"
		],
		title: "MembershipResult",
		type: "object"
	};
	function L(e, { instancePath: t = "", parentData: r, parentDataProperty: i, rootData: a = e, dynamicAnchors: o = {} } = {}) {
		let s = null, c = 0, d = L.evaluated;
		if (d.dynamicProps && (d.props = void 0), d.dynamicItems && (d.items = void 0), c === 0) {
			if (e && typeof e == "object" && !Array.isArray(e)) {
				let r;
				if ((e.ref === void 0 || !n.call(e, "ref")) && (r = "ref") || (e.client_action_id === void 0 || !n.call(e, "client_action_id")) && (r = "client_action_id") || (e.saved === void 0 || !n.call(e, "saved")) && (r = "saved") || (e.changed_at_apply === void 0 || !n.call(e, "changed_at_apply")) && (r = "changed_at_apply") || (e.replayed === void 0 || !n.call(e, "replayed")) && (r = "replayed") || (e.applied_revision === void 0 || !n.call(e, "applied_revision")) && (r = "applied_revision") || (e.current_revision === void 0 || !n.call(e, "current_revision")) && (r = "current_revision") || (e.reference_state === void 0 || !n.call(e, "reference_state")) && (r = "reference_state")) return L.errors = [{
					instancePath: t,
					schemaPath: "#/required",
					keyword: "required",
					params: { missingProperty: r }
				}], !1;
				{
					let r = c;
					for (let n of Object.keys(e)) if (n !== "applied_revision" && n !== "changed_at_apply" && n !== "client_action_id" && n !== "current_revision" && n !== "ref" && n !== "reference_state" && n !== "replayed" && n !== "saved") return L.errors = [{
						instancePath: t,
						schemaPath: "#/additionalProperties",
						keyword: "additionalProperties",
						params: { additionalProperty: n }
					}], !1;
					if (r === c) {
						if (e.applied_revision !== void 0 && n.call(e, "applied_revision")) {
							let n = e.applied_revision, r = c;
							if (typeof n != "number" || n % 1 || isNaN(n) || !isFinite(n)) return L.errors = [{
								instancePath: t + "/applied_revision",
								schemaPath: "#/properties/applied_revision/type",
								keyword: "type",
								params: { type: "integer" }
							}], !1;
							if (c === r && typeof n == "number" && isFinite(n)) {
								if (n > 2147483647 || isNaN(n)) return L.errors = [{
									instancePath: t + "/applied_revision",
									schemaPath: "#/properties/applied_revision/maximum",
									keyword: "maximum",
									params: {
										comparison: "<=",
										limit: 2147483647
									}
								}], !1;
								if (n < 0 || isNaN(n)) return L.errors = [{
									instancePath: t + "/applied_revision",
									schemaPath: "#/properties/applied_revision/minimum",
									keyword: "minimum",
									params: {
										comparison: ">=",
										limit: 0
									}
								}], !1;
							}
							var f = r === c;
						} else var f = !0;
						if (f) {
							if (e.changed_at_apply !== void 0 && n.call(e, "changed_at_apply")) {
								let n = c;
								if (typeof e.changed_at_apply != "boolean") return L.errors = [{
									instancePath: t + "/changed_at_apply",
									schemaPath: "#/properties/changed_at_apply/type",
									keyword: "type",
									params: { type: "boolean" }
								}], !1;
								var f = n === c;
							} else var f = !0;
							if (f) {
								if (e.client_action_id !== void 0 && n.call(e, "client_action_id")) {
									let n = e.client_action_id, r = c;
									if (c === r) {
										if (typeof n == "string") {
											if (!u.test(n)) return L.errors = [{
												instancePath: t + "/client_action_id",
												schemaPath: "#/properties/client_action_id/pattern",
												keyword: "pattern",
												params: { pattern: "^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$" }
											}], !1;
										} else return L.errors = [{
											instancePath: t + "/client_action_id",
											schemaPath: "#/properties/client_action_id/type",
											keyword: "type",
											params: { type: "string" }
										}], !1;
									}
									var f = r === c;
								} else var f = !0;
								if (f) {
									if (e.current_revision !== void 0 && n.call(e, "current_revision")) {
										let n = e.current_revision, r = c;
										if (typeof n != "number" || n % 1 || isNaN(n) || !isFinite(n)) return L.errors = [{
											instancePath: t + "/current_revision",
											schemaPath: "#/properties/current_revision/type",
											keyword: "type",
											params: { type: "integer" }
										}], !1;
										if (c === r && typeof n == "number" && isFinite(n)) {
											if (n > 2147483647 || isNaN(n)) return L.errors = [{
												instancePath: t + "/current_revision",
												schemaPath: "#/properties/current_revision/maximum",
												keyword: "maximum",
												params: {
													comparison: "<=",
													limit: 2147483647
												}
											}], !1;
											if (n < 0 || isNaN(n)) return L.errors = [{
												instancePath: t + "/current_revision",
												schemaPath: "#/properties/current_revision/minimum",
												keyword: "minimum",
												params: {
													comparison: ">=",
													limit: 0
												}
											}], !1;
										}
										var f = r === c;
									} else var f = !0;
									if (f) {
										if (e.ref !== void 0 && n.call(e, "ref")) {
											let n = c;
											l(e.ref, {
												instancePath: t + "/ref",
												parentData: e,
												parentDataProperty: "ref",
												rootData: a,
												dynamicAnchors: o
											}) || (s = s === null ? l.errors : s.concat(l.errors), c = s.length);
											var f = n === c;
										} else var f = !0;
										if (f) {
											if (e.reference_state !== void 0 && n.call(e, "reference_state")) {
												let n = e.reference_state, r = c;
												if (typeof n != "string") return L.errors = [{
													instancePath: t + "/reference_state",
													schemaPath: "#/properties/reference_state/type",
													keyword: "type",
													params: { type: "string" }
												}], !1;
												if (n !== "current" && n !== "historical" && n !== "missing") return L.errors = [{
													instancePath: t + "/reference_state",
													schemaPath: "#/properties/reference_state/enum",
													keyword: "enum",
													params: { allowedValues: at.properties.reference_state.enum }
												}], !1;
												var f = r === c;
											} else var f = !0;
											if (f) {
												if (e.replayed !== void 0 && n.call(e, "replayed")) {
													let n = c;
													if (typeof e.replayed != "boolean") return L.errors = [{
														instancePath: t + "/replayed",
														schemaPath: "#/properties/replayed/type",
														keyword: "type",
														params: { type: "boolean" }
													}], !1;
													var f = n === c;
												} else var f = !0;
												if (f) {
													if (e.saved !== void 0 && n.call(e, "saved")) {
														let n = c;
														if (typeof e.saved != "boolean") return L.errors = [{
															instancePath: t + "/saved",
															schemaPath: "#/properties/saved/type",
															keyword: "type",
															params: { type: "boolean" }
														}], !1;
														var f = n === c;
													} else var f = !0;
												}
											}
										}
									}
								}
							}
						}
					}
				}
			} else return L.errors = [{
				instancePath: t,
				schemaPath: "#/type",
				keyword: "type",
				params: { type: "object" }
			}], !1;
		}
		return L.errors = s, c === 0;
	}
	L.evaluated = {
		props: !0,
		dynamicProps: !1,
		dynamicItems: !1
	};
	function ot(e, { instancePath: t = "", parentData: r, parentDataProperty: i, rootData: a = e, dynamicAnchors: o = {} } = {}) {
		let s = null, c = 0, l = ot.evaluated;
		if (l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0) {
			if (e && typeof e == "object" && !Array.isArray(e)) {
				let r;
				if ((e.data === void 0 || !n.call(e, "data")) && (r = "data") || (e.meta === void 0 || !n.call(e, "meta")) && (r = "meta")) return ot.errors = [{
					instancePath: t,
					schemaPath: "#/required",
					keyword: "required",
					params: { missingProperty: r }
				}], !1;
				{
					let r = c;
					for (let n of Object.keys(e)) if (n !== "data" && n !== "meta") return ot.errors = [{
						instancePath: t,
						schemaPath: "#/additionalProperties",
						keyword: "additionalProperties",
						params: { additionalProperty: n }
					}], !1;
					if (r === c) {
						if (e.data !== void 0 && n.call(e, "data")) {
							let n = c;
							L(e.data, {
								instancePath: t + "/data",
								parentData: e,
								parentDataProperty: "data",
								rootData: a,
								dynamicAnchors: o
							}) || (s = s === null ? L.errors : s.concat(L.errors), c = s.length);
							var u = n === c;
						} else var u = !0;
						if (u) {
							if (e.meta !== void 0 && n.call(e, "meta")) {
								let n = c;
								y(e.meta, {
									instancePath: t + "/meta",
									parentData: e,
									parentDataProperty: "meta",
									rootData: a,
									dynamicAnchors: o
								}) || (s = s === null ? y.errors : s.concat(y.errors), c = s.length);
								var u = n === c;
							} else var u = !0;
						}
					}
				}
			} else return ot.errors = [{
				instancePath: t,
				schemaPath: "#/type",
				keyword: "type",
				params: { type: "object" }
			}], !1;
		}
		return ot.errors = s, c === 0;
	}
	ot.evaluated = {
		props: !0,
		dynamicProps: !1,
		dynamicItems: !1
	}, e.v42 = Ft;
	var st = {
		additionalProperties: !1,
		properties: {
			actions: { $ref: "urn:car-shopping-assistant:contract:1#/$defs/MessageActionResults" },
			client_message_id: {
				pattern: "^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$",
				title: "Client Message Id",
				type: "string"
			},
			comparison: { anyOf: [{ $ref: "urn:car-shopping-assistant:contract:1#/$defs/ComparisonResult" }, { type: "null" }] },
			current_revision: {
				maximum: 2147483647,
				minimum: 0,
				title: "Current Revision",
				type: "integer"
			},
			evidence: {
				default: [],
				items: { $ref: "urn:car-shopping-assistant:contract:1#/$defs/AnswerEvidence" },
				maxItems: 10,
				title: "Evidence",
				type: "array"
			},
			handoff_summary: { anyOf: [{ $ref: "urn:car-shopping-assistant:contract:1#/$defs/HandoffSummary" }, { type: "null" }] },
			operation: {
				anyOf: [{
					discriminator: { propertyName: "state" },
					oneOf: [
						{ $ref: "urn:car-shopping-assistant:contract:1#/$defs/OperationSucceeded" },
						{ $ref: "urn:car-shopping-assistant:contract:1#/$defs/OperationRejected" },
						{ $ref: "urn:car-shopping-assistant:contract:1#/$defs/OperationNotObserved" },
						{ $ref: "urn:car-shopping-assistant:contract:1#/$defs/OperationGenerationUnresolved" }
					],
					type: "object",
					required: ["state"],
					properties: { state: { type: "string" } }
				}, { type: "null" }],
				title: "Operation"
			},
			pending_intent: {
				discriminator: { propertyName: "kind" },
				oneOf: [
					{ $ref: "urn:car-shopping-assistant:contract:1#/$defs/NoPendingIntent" },
					{ $ref: "urn:car-shopping-assistant:contract:1#/$defs/ClarificationIntent" },
					{ $ref: "urn:car-shopping-assistant:contract:1#/$defs/ViewingReviewIntent" },
					{ $ref: "urn:car-shopping-assistant:contract:1#/$defs/UnresolvedOperationIntent" }
				],
				title: "Pending Intent",
				type: "object",
				required: ["kind"],
				properties: { kind: { type: "string" } }
			},
			persistence: {
				enum: ["saved", "not_saved"],
				title: "Persistence",
				type: "string"
			},
			provider_state: {
				enum: [
					"not_used",
					"available",
					"unavailable"
				],
				title: "Provider State",
				type: "string"
			},
			search: { anyOf: [{ $ref: "urn:car-shopping-assistant:contract:1#/$defs/SearchResult" }, { type: "null" }] },
			session_id: {
				pattern: "^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$",
				title: "Session Id",
				type: "string"
			},
			state: {
				enum: [
					"answered",
					"clarification",
					"provider_unavailable",
					"superseded"
				],
				title: "State",
				type: "string"
			},
			text: {
				maxLength: 12e3,
				title: "Text",
				type: "string"
			},
			turn_revision: {
				maximum: 2147483647,
				minimum: 0,
				title: "Turn Revision",
				type: "integer"
			}
		},
		required: [
			"client_message_id",
			"session_id",
			"turn_revision",
			"current_revision",
			"state",
			"text",
			"pending_intent",
			"persistence",
			"provider_state"
		],
		title: "MessageResult",
		type: "object"
	};
	function ct(e, { instancePath: t = "", parentData: r, parentDataProperty: i, rootData: a = e, dynamicAnchors: o = {} } = {}) {
		let s = ct.evaluated;
		if (s.dynamicProps && (s.props = void 0), s.dynamicItems && (s.items = void 0), e && typeof e == "object" && !Array.isArray(e)) {
			for (let n of Object.keys(e)) if (n !== "state") return ct.errors = [{
				instancePath: t,
				schemaPath: "#/additionalProperties",
				keyword: "additionalProperties",
				params: { additionalProperty: n }
			}], !1;
			if (e.state !== void 0 && n.call(e, "state")) {
				let n = e.state;
				if (typeof n != "string") return ct.errors = [{
					instancePath: t + "/state",
					schemaPath: "#/properties/state/type",
					keyword: "type",
					params: { type: "string" }
				}], !1;
				if (n !== "not_requested") return ct.errors = [{
					instancePath: t + "/state",
					schemaPath: "#/properties/state/const",
					keyword: "const",
					params: { allowedValue: "not_requested" }
				}], !1;
			}
		} else return ct.errors = [{
			instancePath: t,
			schemaPath: "#/type",
			keyword: "type",
			params: { type: "object" }
		}], !1;
		return ct.errors = null, !0;
	}
	ct.evaluated = {
		props: !0,
		dynamicProps: !1,
		dynamicItems: !1
	};
	function lt(e, { instancePath: t = "", parentData: r, parentDataProperty: i, rootData: a = e, dynamicAnchors: o = {} } = {}) {
		let s = null, c = 0, l = lt.evaluated;
		if (l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0) {
			if (e && typeof e == "object" && !Array.isArray(e)) {
				let r;
				if ((e.state === void 0 || !n.call(e, "state")) && (r = "state") || (e.client_action_id === void 0 || !n.call(e, "client_action_id")) && (r = "client_action_id") || (e.result === void 0 || !n.call(e, "result")) && (r = "result")) return lt.errors = [{
					instancePath: t,
					schemaPath: "#/required",
					keyword: "required",
					params: { missingProperty: r }
				}], !1;
				{
					let r = c;
					for (let n of Object.keys(e)) if (n !== "client_action_id" && n !== "result" && n !== "state") return lt.errors = [{
						instancePath: t,
						schemaPath: "#/additionalProperties",
						keyword: "additionalProperties",
						params: { additionalProperty: n }
					}], !1;
					if (r === c) {
						if (e.client_action_id !== void 0 && n.call(e, "client_action_id")) {
							let n = e.client_action_id, r = c;
							if (c === r) {
								if (typeof n == "string") {
									if (!u.test(n)) return lt.errors = [{
										instancePath: t + "/client_action_id",
										schemaPath: "#/properties/client_action_id/pattern",
										keyword: "pattern",
										params: { pattern: "^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$" }
									}], !1;
								} else return lt.errors = [{
									instancePath: t + "/client_action_id",
									schemaPath: "#/properties/client_action_id/type",
									keyword: "type",
									params: { type: "string" }
								}], !1;
							}
							var d = r === c;
						} else var d = !0;
						if (d) {
							if (e.result !== void 0 && n.call(e, "result")) {
								let n = c;
								rt(e.result, {
									instancePath: t + "/result",
									parentData: e,
									parentDataProperty: "result",
									rootData: a,
									dynamicAnchors: o
								}) || (s = s === null ? rt.errors : s.concat(rt.errors), c = s.length);
								var d = n === c;
							} else var d = !0;
							if (d) {
								if (e.state !== void 0 && n.call(e, "state")) {
									let n = e.state, r = c;
									if (typeof n != "string") return lt.errors = [{
										instancePath: t + "/state",
										schemaPath: "#/properties/state/type",
										keyword: "type",
										params: { type: "string" }
									}], !1;
									if (n !== "succeeded") return lt.errors = [{
										instancePath: t + "/state",
										schemaPath: "#/properties/state/const",
										keyword: "const",
										params: { allowedValue: "succeeded" }
									}], !1;
									var d = r === c;
								} else var d = !0;
							}
						}
					}
				}
			} else return lt.errors = [{
				instancePath: t,
				schemaPath: "#/type",
				keyword: "type",
				params: { type: "object" }
			}], !1;
		}
		return lt.errors = s, c === 0;
	}
	lt.evaluated = {
		props: !0,
		dynamicProps: !1,
		dynamicItems: !1
	};
	var ut = {
		additionalProperties: !1,
		properties: {
			client_action_id: {
				pattern: "^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$",
				title: "Client Action Id",
				type: "string"
			},
			code: {
				enum: [
					"VALIDATION_ERROR",
					"REVISION_CONFLICT",
					"UNSUPPORTED_STATE",
					"LEAD_EXISTS"
				],
				title: "Code",
				type: "string"
			},
			state: {
				const: "rejected",
				title: "State",
				type: "string"
			}
		},
		required: [
			"state",
			"client_action_id",
			"code"
		],
		title: "ActionRejected",
		type: "object"
	};
	function dt(e, { instancePath: t = "", parentData: r, parentDataProperty: i, rootData: a = e, dynamicAnchors: o = {} } = {}) {
		let s = dt.evaluated;
		if (s.dynamicProps && (s.props = void 0), s.dynamicItems && (s.items = void 0), e && typeof e == "object" && !Array.isArray(e)) {
			let r;
			if ((e.state === void 0 || !n.call(e, "state")) && (r = "state") || (e.client_action_id === void 0 || !n.call(e, "client_action_id")) && (r = "client_action_id") || (e.code === void 0 || !n.call(e, "code")) && (r = "code")) return dt.errors = [{
				instancePath: t,
				schemaPath: "#/required",
				keyword: "required",
				params: { missingProperty: r }
			}], !1;
			for (let n of Object.keys(e)) if (n !== "client_action_id" && n !== "code" && n !== "state") return dt.errors = [{
				instancePath: t,
				schemaPath: "#/additionalProperties",
				keyword: "additionalProperties",
				params: { additionalProperty: n }
			}], !1;
			if (e.client_action_id !== void 0 && n.call(e, "client_action_id")) {
				let n = e.client_action_id;
				if (typeof n == "string") {
					if (!u.test(n)) return dt.errors = [{
						instancePath: t + "/client_action_id",
						schemaPath: "#/properties/client_action_id/pattern",
						keyword: "pattern",
						params: { pattern: "^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$" }
					}], !1;
				} else return dt.errors = [{
					instancePath: t + "/client_action_id",
					schemaPath: "#/properties/client_action_id/type",
					keyword: "type",
					params: { type: "string" }
				}], !1;
				var c = !0;
			} else var c = !0;
			if (c) {
				if (e.code !== void 0 && n.call(e, "code")) {
					let n = e.code;
					if (typeof n != "string") return dt.errors = [{
						instancePath: t + "/code",
						schemaPath: "#/properties/code/type",
						keyword: "type",
						params: { type: "string" }
					}], !1;
					if (n !== "VALIDATION_ERROR" && n !== "REVISION_CONFLICT" && n !== "UNSUPPORTED_STATE" && n !== "LEAD_EXISTS") return dt.errors = [{
						instancePath: t + "/code",
						schemaPath: "#/properties/code/enum",
						keyword: "enum",
						params: { allowedValues: ut.properties.code.enum }
					}], !1;
					var c = !0;
				} else var c = !0;
				if (c) {
					if (e.state !== void 0 && n.call(e, "state")) {
						let n = e.state;
						if (typeof n != "string") return dt.errors = [{
							instancePath: t + "/state",
							schemaPath: "#/properties/state/type",
							keyword: "type",
							params: { type: "string" }
						}], !1;
						if (n !== "rejected") return dt.errors = [{
							instancePath: t + "/state",
							schemaPath: "#/properties/state/const",
							keyword: "const",
							params: { allowedValue: "rejected" }
						}], !1;
						var c = !0;
					} else var c = !0;
				}
			}
		} else return dt.errors = [{
			instancePath: t,
			schemaPath: "#/type",
			keyword: "type",
			params: { type: "object" }
		}], !1;
		return dt.errors = null, !0;
	}
	dt.evaluated = {
		props: !0,
		dynamicProps: !1,
		dynamicItems: !1
	};
	var ft = {
		additionalProperties: !1,
		properties: {
			client_action_id: {
				pattern: "^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$",
				title: "Client Action Id",
				type: "string"
			},
			recovery: {
				enum: [
					"read_current_state",
					"retry_same_action",
					"operator_reconciliation"
				],
				title: "Recovery",
				type: "string"
			},
			state: {
				const: "unresolved",
				title: "State",
				type: "string"
			},
			submitted_store_generation: {
				pattern: "^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$",
				title: "Submitted Store Generation",
				type: "string"
			}
		},
		required: [
			"state",
			"client_action_id",
			"submitted_store_generation",
			"recovery"
		],
		title: "ActionUnresolved",
		type: "object"
	};
	function R(e, { instancePath: t = "", parentData: r, parentDataProperty: i, rootData: a = e, dynamicAnchors: o = {} } = {}) {
		let s = R.evaluated;
		if (s.dynamicProps && (s.props = void 0), s.dynamicItems && (s.items = void 0), e && typeof e == "object" && !Array.isArray(e)) {
			let r;
			if ((e.state === void 0 || !n.call(e, "state")) && (r = "state") || (e.client_action_id === void 0 || !n.call(e, "client_action_id")) && (r = "client_action_id") || (e.submitted_store_generation === void 0 || !n.call(e, "submitted_store_generation")) && (r = "submitted_store_generation") || (e.recovery === void 0 || !n.call(e, "recovery")) && (r = "recovery")) return R.errors = [{
				instancePath: t,
				schemaPath: "#/required",
				keyword: "required",
				params: { missingProperty: r }
			}], !1;
			for (let n of Object.keys(e)) if (n !== "client_action_id" && n !== "recovery" && n !== "state" && n !== "submitted_store_generation") return R.errors = [{
				instancePath: t,
				schemaPath: "#/additionalProperties",
				keyword: "additionalProperties",
				params: { additionalProperty: n }
			}], !1;
			if (e.client_action_id !== void 0 && n.call(e, "client_action_id")) {
				let n = e.client_action_id;
				if (typeof n == "string") {
					if (!u.test(n)) return R.errors = [{
						instancePath: t + "/client_action_id",
						schemaPath: "#/properties/client_action_id/pattern",
						keyword: "pattern",
						params: { pattern: "^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$" }
					}], !1;
				} else return R.errors = [{
					instancePath: t + "/client_action_id",
					schemaPath: "#/properties/client_action_id/type",
					keyword: "type",
					params: { type: "string" }
				}], !1;
				var c = !0;
			} else var c = !0;
			if (c) {
				if (e.recovery !== void 0 && n.call(e, "recovery")) {
					let n = e.recovery;
					if (typeof n != "string") return R.errors = [{
						instancePath: t + "/recovery",
						schemaPath: "#/properties/recovery/type",
						keyword: "type",
						params: { type: "string" }
					}], !1;
					if (n !== "read_current_state" && n !== "retry_same_action" && n !== "operator_reconciliation") return R.errors = [{
						instancePath: t + "/recovery",
						schemaPath: "#/properties/recovery/enum",
						keyword: "enum",
						params: { allowedValues: ft.properties.recovery.enum }
					}], !1;
					var c = !0;
				} else var c = !0;
				if (c) {
					if (e.state !== void 0 && n.call(e, "state")) {
						let n = e.state;
						if (typeof n != "string") return R.errors = [{
							instancePath: t + "/state",
							schemaPath: "#/properties/state/type",
							keyword: "type",
							params: { type: "string" }
						}], !1;
						if (n !== "unresolved") return R.errors = [{
							instancePath: t + "/state",
							schemaPath: "#/properties/state/const",
							keyword: "const",
							params: { allowedValue: "unresolved" }
						}], !1;
						var c = !0;
					} else var c = !0;
					if (c) {
						if (e.submitted_store_generation !== void 0 && n.call(e, "submitted_store_generation")) {
							let n = e.submitted_store_generation;
							if (typeof n == "string") {
								if (!u.test(n)) return R.errors = [{
									instancePath: t + "/submitted_store_generation",
									schemaPath: "#/properties/submitted_store_generation/pattern",
									keyword: "pattern",
									params: { pattern: "^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$" }
								}], !1;
							} else return R.errors = [{
								instancePath: t + "/submitted_store_generation",
								schemaPath: "#/properties/submitted_store_generation/type",
								keyword: "type",
								params: { type: "string" }
							}], !1;
							var c = !0;
						} else var c = !0;
					}
				}
			}
		} else return R.errors = [{
			instancePath: t,
			schemaPath: "#/type",
			keyword: "type",
			params: { type: "object" }
		}], !1;
		return R.errors = null, !0;
	}
	R.evaluated = {
		props: !0,
		dynamicProps: !1,
		dynamicItems: !1
	};
	var pt = {
		additionalProperties: !1,
		properties: {
			collection_mode: {
				enum: ["explicit_save", "disabled"],
				title: "Collection Mode",
				type: "string"
			},
			entries: {
				items: { $ref: "urn:car-shopping-assistant:contract:1#/$defs/PreferenceEntry" },
				maxItems: 4,
				title: "Entries",
				type: "array"
			},
			revision: {
				maximum: 2147483647,
				minimum: 0,
				title: "Revision",
				type: "integer"
			}
		},
		required: [
			"entries",
			"revision",
			"collection_mode"
		],
		title: "PreferenceRecord",
		type: "object"
	}, mt = {
		additionalProperties: !1,
		properties: {
			applicability: {
				enum: ["confirmed", "requires_reconfirmation"],
				title: "Applicability",
				type: "string"
			},
			confirmed_at: {
				pattern: "^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}(?:\\.\\d{1,6})?Z$",
				title: "Confirmed At",
				type: "string"
			},
			expires_at: {
				pattern: "^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}(?:\\.\\d{1,6})?Z$",
				title: "Expires At",
				type: "string"
			},
			preference: {
				discriminator: { propertyName: "key" },
				oneOf: [{ $ref: "urn:car-shopping-assistant:contract:1#/$defs/BudgetPreference" }, { $ref: "urn:car-shopping-assistant:contract:1#/$defs/CategoryPreference" }],
				title: "Preference",
				type: "object",
				required: ["key"],
				properties: { key: { type: "string" } }
			},
			source_action_id: {
				pattern: "^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$",
				title: "Source Action Id",
				type: "string"
			},
			source_message_id: {
				anyOf: [{
					pattern: "^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$",
					type: "string"
				}, { type: "null" }],
				title: "Source Message Id"
			},
			source_session_id: {
				pattern: "^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$",
				title: "Source Session Id",
				type: "string"
			}
		},
		required: [
			"preference",
			"source_session_id",
			"source_action_id",
			"confirmed_at",
			"expires_at",
			"applicability"
		],
		title: "PreferenceEntry",
		type: "object"
	}, ht = {
		additionalProperties: !1,
		properties: {
			key: {
				const: "budget",
				title: "Key",
				type: "string"
			},
			strength: {
				enum: ["hard", "soft"],
				title: "Strength",
				type: "string"
			},
			value: { anyOf: [{ $ref: "urn:car-shopping-assistant:contract:1#/$defs/BudgetRange" }, { type: "null" }] }
		},
		required: [
			"key",
			"value",
			"strength"
		],
		title: "BudgetPreference",
		type: "object"
	};
	function gt(e, { instancePath: t = "", parentData: r, parentDataProperty: i, rootData: a = e, dynamicAnchors: o = {} } = {}) {
		let s = null, c = 0, l = gt.evaluated;
		if (l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0) {
			if (e && typeof e == "object" && !Array.isArray(e)) {
				let r;
				if ((e.key === void 0 || !n.call(e, "key")) && (r = "key") || (e.value === void 0 || !n.call(e, "value")) && (r = "value") || (e.strength === void 0 || !n.call(e, "strength")) && (r = "strength")) return gt.errors = [{
					instancePath: t,
					schemaPath: "#/required",
					keyword: "required",
					params: { missingProperty: r }
				}], !1;
				{
					let r = c;
					for (let n of Object.keys(e)) if (n !== "key" && n !== "strength" && n !== "value") return gt.errors = [{
						instancePath: t,
						schemaPath: "#/additionalProperties",
						keyword: "additionalProperties",
						params: { additionalProperty: n }
					}], !1;
					if (r === c) {
						if (e.key !== void 0 && n.call(e, "key")) {
							let n = e.key, r = c;
							if (typeof n != "string") return gt.errors = [{
								instancePath: t + "/key",
								schemaPath: "#/properties/key/type",
								keyword: "type",
								params: { type: "string" }
							}], !1;
							if (n !== "budget") return gt.errors = [{
								instancePath: t + "/key",
								schemaPath: "#/properties/key/const",
								keyword: "const",
								params: { allowedValue: "budget" }
							}], !1;
							var u = r === c;
						} else var u = !0;
						if (u) {
							if (e.strength !== void 0 && n.call(e, "strength")) {
								let n = e.strength, r = c;
								if (typeof n != "string") return gt.errors = [{
									instancePath: t + "/strength",
									schemaPath: "#/properties/strength/type",
									keyword: "type",
									params: { type: "string" }
								}], !1;
								if (n !== "hard" && n !== "soft") return gt.errors = [{
									instancePath: t + "/strength",
									schemaPath: "#/properties/strength/enum",
									keyword: "enum",
									params: { allowedValues: ht.properties.strength.enum }
								}], !1;
								var u = r === c;
							} else var u = !0;
							if (u) {
								if (e.value !== void 0 && n.call(e, "value")) {
									let n = e.value, r = c, i = c, l = !1, f = c;
									ke(n, {
										instancePath: t + "/value",
										parentData: e,
										parentDataProperty: "value",
										rootData: a,
										dynamicAnchors: o
									}) || (s = s === null ? ke.errors : s.concat(ke.errors), c = s.length);
									var d = f === c;
									l ||= d;
									let p = c;
									if (n !== null) {
										let e = {
											instancePath: t + "/value",
											schemaPath: "#/properties/value/anyOf/1/type",
											keyword: "type",
											params: { type: "null" }
										};
										s === null ? s = [e] : s.push(e), c++;
									}
									var d = p === c;
									if (l ||= d, l) c = i, s !== null && (i ? s.length = i : s = null);
									else {
										let e = {
											instancePath: t + "/value",
											schemaPath: "#/properties/value/anyOf",
											keyword: "anyOf",
											params: {}
										};
										return s === null ? s = [e] : s.push(e), c++, gt.errors = s, !1;
									}
									var u = r === c;
								} else var u = !0;
							}
						}
					}
				}
			} else return gt.errors = [{
				instancePath: t,
				schemaPath: "#/type",
				keyword: "type",
				params: { type: "object" }
			}], !1;
		}
		return gt.errors = s, c === 0;
	}
	gt.evaluated = {
		props: !0,
		dynamicProps: !1,
		dynamicItems: !1
	};
	var _t = {
		additionalProperties: !1,
		properties: {
			key: {
				enum: [
					"makes",
					"use_cases",
					"requirements"
				],
				title: "Key",
				type: "string"
			},
			strength: {
				enum: ["hard", "soft"],
				title: "Strength",
				type: "string"
			},
			value: {
				items: {
					maxLength: 200,
					minLength: 1,
					type: "string"
				},
				maxItems: 24,
				title: "Value",
				type: "array"
			}
		},
		required: [
			"key",
			"value",
			"strength"
		],
		title: "CategoryPreference",
		type: "object"
	};
	function z(e, { instancePath: t = "", parentData: r, parentDataProperty: i, rootData: a = e, dynamicAnchors: o = {} } = {}) {
		let s = z.evaluated;
		if (s.dynamicProps && (s.props = void 0), s.dynamicItems && (s.items = void 0), e && typeof e == "object" && !Array.isArray(e)) {
			let r;
			if ((e.key === void 0 || !n.call(e, "key")) && (r = "key") || (e.value === void 0 || !n.call(e, "value")) && (r = "value") || (e.strength === void 0 || !n.call(e, "strength")) && (r = "strength")) return z.errors = [{
				instancePath: t,
				schemaPath: "#/required",
				keyword: "required",
				params: { missingProperty: r }
			}], !1;
			for (let n of Object.keys(e)) if (n !== "key" && n !== "strength" && n !== "value") return z.errors = [{
				instancePath: t,
				schemaPath: "#/additionalProperties",
				keyword: "additionalProperties",
				params: { additionalProperty: n }
			}], !1;
			if (e.key !== void 0 && n.call(e, "key")) {
				let n = e.key;
				if (typeof n != "string") return z.errors = [{
					instancePath: t + "/key",
					schemaPath: "#/properties/key/type",
					keyword: "type",
					params: { type: "string" }
				}], !1;
				if (n !== "makes" && n !== "use_cases" && n !== "requirements") return z.errors = [{
					instancePath: t + "/key",
					schemaPath: "#/properties/key/enum",
					keyword: "enum",
					params: { allowedValues: _t.properties.key.enum }
				}], !1;
				var c = !0;
			} else var c = !0;
			if (c) {
				if (e.strength !== void 0 && n.call(e, "strength")) {
					let n = e.strength;
					if (typeof n != "string") return z.errors = [{
						instancePath: t + "/strength",
						schemaPath: "#/properties/strength/type",
						keyword: "type",
						params: { type: "string" }
					}], !1;
					if (n !== "hard" && n !== "soft") return z.errors = [{
						instancePath: t + "/strength",
						schemaPath: "#/properties/strength/enum",
						keyword: "enum",
						params: { allowedValues: _t.properties.strength.enum }
					}], !1;
					var c = !0;
				} else var c = !0;
				if (c) {
					if (e.value !== void 0 && n.call(e, "value")) {
						let n = e.value;
						if (Array.isArray(n)) {
							if (n.length > 24) return z.errors = [{
								instancePath: t + "/value",
								schemaPath: "#/properties/value/maxItems",
								keyword: "maxItems",
								params: { limit: 24 }
							}], !1;
							{
								let e = n.length;
								for (let r = 0; r < e; r++) {
									let e = n[r];
									if (typeof e == "string") {
										if (h(e) > 200) return z.errors = [{
											instancePath: t + "/value/" + r,
											schemaPath: "#/properties/value/items/maxLength",
											keyword: "maxLength",
											params: { limit: 200 }
										}], !1;
										if (h(e) < 1) return z.errors = [{
											instancePath: t + "/value/" + r,
											schemaPath: "#/properties/value/items/minLength",
											keyword: "minLength",
											params: { limit: 1 }
										}], !1;
									} else return z.errors = [{
										instancePath: t + "/value/" + r,
										schemaPath: "#/properties/value/items/type",
										keyword: "type",
										params: { type: "string" }
									}], !1;
								}
							}
						} else return z.errors = [{
							instancePath: t + "/value",
							schemaPath: "#/properties/value/type",
							keyword: "type",
							params: { type: "array" }
						}], !1;
						var c = !0;
					} else var c = !0;
				}
			}
		} else return z.errors = [{
			instancePath: t,
			schemaPath: "#/type",
			keyword: "type",
			params: { type: "object" }
		}], !1;
		return z.errors = null, !0;
	}
	z.evaluated = {
		props: !0,
		dynamicProps: !1,
		dynamicItems: !1
	};
	function B(e, { instancePath: t = "", parentData: r, parentDataProperty: a, rootData: o = e, dynamicAnchors: s = {} } = {}) {
		let c = null, l = 0, d = B.evaluated;
		if (d.dynamicProps && (d.props = void 0), d.dynamicItems && (d.items = void 0), l === 0) {
			if (e && typeof e == "object" && !Array.isArray(e)) {
				let r;
				if ((e.preference === void 0 || !n.call(e, "preference")) && (r = "preference") || (e.source_session_id === void 0 || !n.call(e, "source_session_id")) && (r = "source_session_id") || (e.source_action_id === void 0 || !n.call(e, "source_action_id")) && (r = "source_action_id") || (e.confirmed_at === void 0 || !n.call(e, "confirmed_at")) && (r = "confirmed_at") || (e.expires_at === void 0 || !n.call(e, "expires_at")) && (r = "expires_at") || (e.applicability === void 0 || !n.call(e, "applicability")) && (r = "applicability")) return B.errors = [{
					instancePath: t,
					schemaPath: "#/required",
					keyword: "required",
					params: { missingProperty: r }
				}], !1;
				{
					let r = l;
					for (let n of Object.keys(e)) if (n !== "applicability" && n !== "confirmed_at" && n !== "expires_at" && n !== "preference" && n !== "source_action_id" && n !== "source_message_id" && n !== "source_session_id") return B.errors = [{
						instancePath: t,
						schemaPath: "#/additionalProperties",
						keyword: "additionalProperties",
						params: { additionalProperty: n }
					}], !1;
					if (r === l) {
						if (e.applicability !== void 0 && n.call(e, "applicability")) {
							let n = e.applicability, r = l;
							if (typeof n != "string") return B.errors = [{
								instancePath: t + "/applicability",
								schemaPath: "#/properties/applicability/type",
								keyword: "type",
								params: { type: "string" }
							}], !1;
							if (n !== "confirmed" && n !== "requires_reconfirmation") return B.errors = [{
								instancePath: t + "/applicability",
								schemaPath: "#/properties/applicability/enum",
								keyword: "enum",
								params: { allowedValues: mt.properties.applicability.enum }
							}], !1;
							var f = r === l;
						} else var f = !0;
						if (f) {
							if (e.confirmed_at !== void 0 && n.call(e, "confirmed_at")) {
								let n = e.confirmed_at, r = l;
								if (l === r) {
									if (typeof n == "string") {
										if (!i.test(n)) return B.errors = [{
											instancePath: t + "/confirmed_at",
											schemaPath: "#/properties/confirmed_at/pattern",
											keyword: "pattern",
											params: { pattern: "^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}(?:\\.\\d{1,6})?Z$" }
										}], !1;
									} else return B.errors = [{
										instancePath: t + "/confirmed_at",
										schemaPath: "#/properties/confirmed_at/type",
										keyword: "type",
										params: { type: "string" }
									}], !1;
								}
								var f = r === l;
							} else var f = !0;
							if (f) {
								if (e.expires_at !== void 0 && n.call(e, "expires_at")) {
									let n = e.expires_at, r = l;
									if (l === r) {
										if (typeof n == "string") {
											if (!i.test(n)) return B.errors = [{
												instancePath: t + "/expires_at",
												schemaPath: "#/properties/expires_at/pattern",
												keyword: "pattern",
												params: { pattern: "^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}(?:\\.\\d{1,6})?Z$" }
											}], !1;
										} else return B.errors = [{
											instancePath: t + "/expires_at",
											schemaPath: "#/properties/expires_at/type",
											keyword: "type",
											params: { type: "string" }
										}], !1;
									}
									var f = r === l;
								} else var f = !0;
								if (f) {
									if (e.preference !== void 0 && n.call(e, "preference")) {
										let r = e.preference, i = l;
										if (l === i) {
											if (r && typeof r == "object" && !Array.isArray(r)) {
												let i;
												if ((r.key === void 0 || !n.call(r, "key")) && (i = "key")) return B.errors = [{
													instancePath: t + "/preference",
													schemaPath: "#/properties/preference/required",
													keyword: "required",
													params: { missingProperty: i }
												}], !1;
												if (r.key !== void 0 && n.call(r, "key")) {
													let e = l;
													if (typeof r.key != "string") return B.errors = [{
														instancePath: t + "/preference/key",
														schemaPath: "#/properties/preference/properties/key/type",
														keyword: "type",
														params: { type: "string" }
													}], !1;
													var p = e === l;
												} else var p = !0;
												if (p) {
													let n = r.key;
													if (typeof n == "string") {
														if (n === "budget") {
															gt(r, {
																instancePath: t + "/preference",
																parentData: e,
																parentDataProperty: "preference",
																rootData: o,
																dynamicAnchors: s
															}) || (c = c === null ? gt.errors : c.concat(gt.errors), l = c.length);
															var m = !0;
														} else if (n === "makes") z(r, {
															instancePath: t + "/preference",
															parentData: e,
															parentDataProperty: "preference",
															rootData: o,
															dynamicAnchors: s
														}) || (c = c === null ? z.errors : c.concat(z.errors), l = c.length), m !== !0 && (m = !0);
														else if (n === "use_cases") z(r, {
															instancePath: t + "/preference",
															parentData: e,
															parentDataProperty: "preference",
															rootData: o,
															dynamicAnchors: s
														}) || (c = c === null ? z.errors : c.concat(z.errors), l = c.length), m !== !0 && (m = !0);
														else if (n === "requirements") z(r, {
															instancePath: t + "/preference",
															parentData: e,
															parentDataProperty: "preference",
															rootData: o,
															dynamicAnchors: s
														}) || (c = c === null ? z.errors : c.concat(z.errors), l = c.length), m !== !0 && (m = !0);
														else return B.errors = [{
															instancePath: t + "/preference",
															schemaPath: "#/properties/preference/discriminator",
															keyword: "discriminator",
															params: {
																error: "mapping",
																tag: "key",
																tagValue: n
															}
														}], !1;
													} else return B.errors = [{
														instancePath: t + "/preference",
														schemaPath: "#/properties/preference/discriminator",
														keyword: "discriminator",
														params: {
															error: "tag",
															tag: "key",
															tagValue: n
														}
													}], !1;
												}
											} else return B.errors = [{
												instancePath: t + "/preference",
												schemaPath: "#/properties/preference/type",
												keyword: "type",
												params: { type: "object" }
											}], !1;
										}
										var f = i === l;
									} else var f = !0;
									if (f) {
										if (e.source_action_id !== void 0 && n.call(e, "source_action_id")) {
											let n = e.source_action_id, r = l;
											if (l === r) {
												if (typeof n == "string") {
													if (!u.test(n)) return B.errors = [{
														instancePath: t + "/source_action_id",
														schemaPath: "#/properties/source_action_id/pattern",
														keyword: "pattern",
														params: { pattern: "^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$" }
													}], !1;
												} else return B.errors = [{
													instancePath: t + "/source_action_id",
													schemaPath: "#/properties/source_action_id/type",
													keyword: "type",
													params: { type: "string" }
												}], !1;
											}
											var f = r === l;
										} else var f = !0;
										if (f) {
											if (e.source_message_id !== void 0 && n.call(e, "source_message_id")) {
												let n = e.source_message_id, r = l, i = l, a = !1, o = l;
												if (l === o) {
													if (typeof n == "string") {
														if (!u.test(n)) {
															let e = {
																instancePath: t + "/source_message_id",
																schemaPath: "#/properties/source_message_id/anyOf/0/pattern",
																keyword: "pattern",
																params: { pattern: "^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$" }
															};
															c === null ? c = [e] : c.push(e), l++;
														}
													} else {
														let e = {
															instancePath: t + "/source_message_id",
															schemaPath: "#/properties/source_message_id/anyOf/0/type",
															keyword: "type",
															params: { type: "string" }
														};
														c === null ? c = [e] : c.push(e), l++;
													}
												}
												var h = o === l;
												a ||= h;
												let s = l;
												if (n !== null) {
													let e = {
														instancePath: t + "/source_message_id",
														schemaPath: "#/properties/source_message_id/anyOf/1/type",
														keyword: "type",
														params: { type: "null" }
													};
													c === null ? c = [e] : c.push(e), l++;
												}
												var h = s === l;
												if (a ||= h, a) l = i, c !== null && (i ? c.length = i : c = null);
												else {
													let e = {
														instancePath: t + "/source_message_id",
														schemaPath: "#/properties/source_message_id/anyOf",
														keyword: "anyOf",
														params: {}
													};
													return c === null ? c = [e] : c.push(e), l++, B.errors = c, !1;
												}
												var f = r === l;
											} else var f = !0;
											if (f) {
												if (e.source_session_id !== void 0 && n.call(e, "source_session_id")) {
													let n = e.source_session_id, r = l;
													if (l === r) {
														if (typeof n == "string") {
															if (!u.test(n)) return B.errors = [{
																instancePath: t + "/source_session_id",
																schemaPath: "#/properties/source_session_id/pattern",
																keyword: "pattern",
																params: { pattern: "^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$" }
															}], !1;
														} else return B.errors = [{
															instancePath: t + "/source_session_id",
															schemaPath: "#/properties/source_session_id/type",
															keyword: "type",
															params: { type: "string" }
														}], !1;
													}
													var f = r === l;
												} else var f = !0;
											}
										}
									}
								}
							}
						}
					}
				}
			} else return B.errors = [{
				instancePath: t,
				schemaPath: "#/type",
				keyword: "type",
				params: { type: "object" }
			}], !1;
		}
		return B.errors = c, l === 0;
	}
	B.evaluated = {
		props: !0,
		dynamicProps: !1,
		dynamicItems: !1
	};
	function V(e, { instancePath: t = "", parentData: r, parentDataProperty: i, rootData: a = e, dynamicAnchors: o = {} } = {}) {
		let s = null, c = 0, l = V.evaluated;
		if (l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0) {
			if (e && typeof e == "object" && !Array.isArray(e)) {
				let r;
				if ((e.entries === void 0 || !n.call(e, "entries")) && (r = "entries") || (e.revision === void 0 || !n.call(e, "revision")) && (r = "revision") || (e.collection_mode === void 0 || !n.call(e, "collection_mode")) && (r = "collection_mode")) return V.errors = [{
					instancePath: t,
					schemaPath: "#/required",
					keyword: "required",
					params: { missingProperty: r }
				}], !1;
				{
					let r = c;
					for (let n of Object.keys(e)) if (n !== "collection_mode" && n !== "entries" && n !== "revision") return V.errors = [{
						instancePath: t,
						schemaPath: "#/additionalProperties",
						keyword: "additionalProperties",
						params: { additionalProperty: n }
					}], !1;
					if (r === c) {
						if (e.collection_mode !== void 0 && n.call(e, "collection_mode")) {
							let n = e.collection_mode, r = c;
							if (typeof n != "string") return V.errors = [{
								instancePath: t + "/collection_mode",
								schemaPath: "#/properties/collection_mode/type",
								keyword: "type",
								params: { type: "string" }
							}], !1;
							if (n !== "explicit_save" && n !== "disabled") return V.errors = [{
								instancePath: t + "/collection_mode",
								schemaPath: "#/properties/collection_mode/enum",
								keyword: "enum",
								params: { allowedValues: pt.properties.collection_mode.enum }
							}], !1;
							var u = r === c;
						} else var u = !0;
						if (u) {
							if (e.entries !== void 0 && n.call(e, "entries")) {
								let n = e.entries, r = c;
								if (c === r) {
									if (Array.isArray(n)) {
										if (n.length > 4) return V.errors = [{
											instancePath: t + "/entries",
											schemaPath: "#/properties/entries/maxItems",
											keyword: "maxItems",
											params: { limit: 4 }
										}], !1;
										{
											let e = n.length;
											for (let r = 0; r < e; r++) {
												let e = c;
												if (B(n[r], {
													instancePath: t + "/entries/" + r,
													parentData: n,
													parentDataProperty: r,
													rootData: a,
													dynamicAnchors: o
												}) || (s = s === null ? B.errors : s.concat(B.errors), c = s.length), e !== c) break;
											}
										}
									} else return V.errors = [{
										instancePath: t + "/entries",
										schemaPath: "#/properties/entries/type",
										keyword: "type",
										params: { type: "array" }
									}], !1;
								}
								var u = r === c;
							} else var u = !0;
							if (u) {
								if (e.revision !== void 0 && n.call(e, "revision")) {
									let n = e.revision, r = c;
									if (typeof n != "number" || n % 1 || isNaN(n) || !isFinite(n)) return V.errors = [{
										instancePath: t + "/revision",
										schemaPath: "#/properties/revision/type",
										keyword: "type",
										params: { type: "integer" }
									}], !1;
									if (c === r && typeof n == "number" && isFinite(n)) {
										if (n > 2147483647 || isNaN(n)) return V.errors = [{
											instancePath: t + "/revision",
											schemaPath: "#/properties/revision/maximum",
											keyword: "maximum",
											params: {
												comparison: "<=",
												limit: 2147483647
											}
										}], !1;
										if (n < 0 || isNaN(n)) return V.errors = [{
											instancePath: t + "/revision",
											schemaPath: "#/properties/revision/minimum",
											keyword: "minimum",
											params: {
												comparison: ">=",
												limit: 0
											}
										}], !1;
									}
									var u = r === c;
								} else var u = !0;
							}
						}
					}
				}
			} else return V.errors = [{
				instancePath: t,
				schemaPath: "#/type",
				keyword: "type",
				params: { type: "object" }
			}], !1;
		}
		return V.errors = s, c === 0;
	}
	V.evaluated = {
		props: !0,
		dynamicProps: !1,
		dynamicItems: !1
	};
	function vt(e, { instancePath: t = "", parentData: r, parentDataProperty: i, rootData: a = e, dynamicAnchors: o = {} } = {}) {
		let s = null, c = 0, l = vt.evaluated;
		if (l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0) {
			if (e && typeof e == "object" && !Array.isArray(e)) {
				let r;
				if ((e.state === void 0 || !n.call(e, "state")) && (r = "state") || (e.client_action_id === void 0 || !n.call(e, "client_action_id")) && (r = "client_action_id") || (e.result === void 0 || !n.call(e, "result")) && (r = "result")) return vt.errors = [{
					instancePath: t,
					schemaPath: "#/required",
					keyword: "required",
					params: { missingProperty: r }
				}], !1;
				{
					let r = c;
					for (let n of Object.keys(e)) if (n !== "client_action_id" && n !== "result" && n !== "state") return vt.errors = [{
						instancePath: t,
						schemaPath: "#/additionalProperties",
						keyword: "additionalProperties",
						params: { additionalProperty: n }
					}], !1;
					if (r === c) {
						if (e.client_action_id !== void 0 && n.call(e, "client_action_id")) {
							let n = e.client_action_id, r = c;
							if (c === r) {
								if (typeof n == "string") {
									if (!u.test(n)) return vt.errors = [{
										instancePath: t + "/client_action_id",
										schemaPath: "#/properties/client_action_id/pattern",
										keyword: "pattern",
										params: { pattern: "^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$" }
									}], !1;
								} else return vt.errors = [{
									instancePath: t + "/client_action_id",
									schemaPath: "#/properties/client_action_id/type",
									keyword: "type",
									params: { type: "string" }
								}], !1;
							}
							var d = r === c;
						} else var d = !0;
						if (d) {
							if (e.result !== void 0 && n.call(e, "result")) {
								let n = c;
								V(e.result, {
									instancePath: t + "/result",
									parentData: e,
									parentDataProperty: "result",
									rootData: a,
									dynamicAnchors: o
								}) || (s = s === null ? V.errors : s.concat(V.errors), c = s.length);
								var d = n === c;
							} else var d = !0;
							if (d) {
								if (e.state !== void 0 && n.call(e, "state")) {
									let n = e.state, r = c;
									if (typeof n != "string") return vt.errors = [{
										instancePath: t + "/state",
										schemaPath: "#/properties/state/type",
										keyword: "type",
										params: { type: "string" }
									}], !1;
									if (n !== "succeeded") return vt.errors = [{
										instancePath: t + "/state",
										schemaPath: "#/properties/state/const",
										keyword: "const",
										params: { allowedValue: "succeeded" }
									}], !1;
									var d = r === c;
								} else var d = !0;
							}
						}
					}
				}
			} else return vt.errors = [{
				instancePath: t,
				schemaPath: "#/type",
				keyword: "type",
				params: { type: "object" }
			}], !1;
		}
		return vt.errors = s, c === 0;
	}
	vt.evaluated = {
		props: !0,
		dynamicProps: !1,
		dynamicItems: !1
	};
	function yt(e, { instancePath: t = "", parentData: r, parentDataProperty: i, rootData: a = e, dynamicAnchors: o = {} } = {}) {
		let s = null, c = 0, l = yt.evaluated;
		if (l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0) {
			if (e && typeof e == "object" && !Array.isArray(e)) {
				let r;
				if ((e.state === void 0 || !n.call(e, "state")) && (r = "state") || (e.client_action_id === void 0 || !n.call(e, "client_action_id")) && (r = "client_action_id") || (e.result === void 0 || !n.call(e, "result")) && (r = "result")) return yt.errors = [{
					instancePath: t,
					schemaPath: "#/required",
					keyword: "required",
					params: { missingProperty: r }
				}], !1;
				{
					let r = c;
					for (let n of Object.keys(e)) if (n !== "client_action_id" && n !== "result" && n !== "state") return yt.errors = [{
						instancePath: t,
						schemaPath: "#/additionalProperties",
						keyword: "additionalProperties",
						params: { additionalProperty: n }
					}], !1;
					if (r === c) {
						if (e.client_action_id !== void 0 && n.call(e, "client_action_id")) {
							let n = e.client_action_id, r = c;
							if (c === r) {
								if (typeof n == "string") {
									if (!u.test(n)) return yt.errors = [{
										instancePath: t + "/client_action_id",
										schemaPath: "#/properties/client_action_id/pattern",
										keyword: "pattern",
										params: { pattern: "^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$" }
									}], !1;
								} else return yt.errors = [{
									instancePath: t + "/client_action_id",
									schemaPath: "#/properties/client_action_id/type",
									keyword: "type",
									params: { type: "string" }
								}], !1;
							}
							var d = r === c;
						} else var d = !0;
						if (d) {
							if (e.result !== void 0 && n.call(e, "result")) {
								let n = c;
								L(e.result, {
									instancePath: t + "/result",
									parentData: e,
									parentDataProperty: "result",
									rootData: a,
									dynamicAnchors: o
								}) || (s = s === null ? L.errors : s.concat(L.errors), c = s.length);
								var d = n === c;
							} else var d = !0;
							if (d) {
								if (e.state !== void 0 && n.call(e, "state")) {
									let n = e.state, r = c;
									if (typeof n != "string") return yt.errors = [{
										instancePath: t + "/state",
										schemaPath: "#/properties/state/type",
										keyword: "type",
										params: { type: "string" }
									}], !1;
									if (n !== "succeeded") return yt.errors = [{
										instancePath: t + "/state",
										schemaPath: "#/properties/state/const",
										keyword: "const",
										params: { allowedValue: "succeeded" }
									}], !1;
									var d = r === c;
								} else var d = !0;
							}
						}
					}
				}
			} else return yt.errors = [{
				instancePath: t,
				schemaPath: "#/type",
				keyword: "type",
				params: { type: "object" }
			}], !1;
		}
		return yt.errors = s, c === 0;
	}
	yt.evaluated = {
		props: !0,
		dynamicProps: !1,
		dynamicItems: !1
	};
	function H(e, { instancePath: t = "", parentData: r, parentDataProperty: i, rootData: a = e, dynamicAnchors: o = {} } = {}) {
		let s = null, c = 0, l = H.evaluated;
		if (l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0) {
			if (e && typeof e == "object" && !Array.isArray(e)) {
				let r = c;
				for (let n of Object.keys(e)) if (n !== "lead" && n !== "preferences" && n !== "shortlist") return H.errors = [{
					instancePath: t,
					schemaPath: "#/additionalProperties",
					keyword: "additionalProperties",
					params: { additionalProperty: n }
				}], !1;
				if (r === c) {
					if (e.lead !== void 0 && n.call(e, "lead")) {
						let r = e.lead, i = c;
						if (c === i) {
							if (r && typeof r == "object" && !Array.isArray(r)) {
								let i;
								if ((r.state === void 0 || !n.call(r, "state")) && (i = "state")) return H.errors = [{
									instancePath: t + "/lead",
									schemaPath: "#/properties/lead/required",
									keyword: "required",
									params: { missingProperty: i }
								}], !1;
								if (r.state !== void 0 && n.call(r, "state")) {
									let e = c;
									if (typeof r.state != "string") return H.errors = [{
										instancePath: t + "/lead/state",
										schemaPath: "#/properties/lead/properties/state/type",
										keyword: "type",
										params: { type: "string" }
									}], !1;
									var u = e === c;
								} else var u = !0;
								if (u) {
									let n = r.state;
									if (typeof n == "string") {
										if (n === "not_requested") {
											ct(r, {
												instancePath: t + "/lead",
												parentData: e,
												parentDataProperty: "lead",
												rootData: a,
												dynamicAnchors: o
											}) || (s = s === null ? ct.errors : s.concat(ct.errors), c = s.length);
											var d = !0;
										} else if (n === "succeeded") lt(r, {
											instancePath: t + "/lead",
											parentData: e,
											parentDataProperty: "lead",
											rootData: a,
											dynamicAnchors: o
										}) || (s = s === null ? lt.errors : s.concat(lt.errors), c = s.length), d !== !0 && (d = !0);
										else if (n === "rejected") dt(r, {
											instancePath: t + "/lead",
											parentData: e,
											parentDataProperty: "lead",
											rootData: a,
											dynamicAnchors: o
										}) || (s = s === null ? dt.errors : s.concat(dt.errors), c = s.length), d !== !0 && (d = !0);
										else if (n === "unresolved") R(r, {
											instancePath: t + "/lead",
											parentData: e,
											parentDataProperty: "lead",
											rootData: a,
											dynamicAnchors: o
										}) || (s = s === null ? R.errors : s.concat(R.errors), c = s.length), d !== !0 && (d = !0);
										else return H.errors = [{
											instancePath: t + "/lead",
											schemaPath: "#/properties/lead/discriminator",
											keyword: "discriminator",
											params: {
												error: "mapping",
												tag: "state",
												tagValue: n
											}
										}], !1;
									} else return H.errors = [{
										instancePath: t + "/lead",
										schemaPath: "#/properties/lead/discriminator",
										keyword: "discriminator",
										params: {
											error: "tag",
											tag: "state",
											tagValue: n
										}
									}], !1;
								}
							} else return H.errors = [{
								instancePath: t + "/lead",
								schemaPath: "#/properties/lead/type",
								keyword: "type",
								params: { type: "object" }
							}], !1;
						}
						var f = i === c;
					} else var f = !0;
					if (f) {
						if (e.preferences !== void 0 && n.call(e, "preferences")) {
							let r = e.preferences, i = c;
							if (c === i) {
								if (r && typeof r == "object" && !Array.isArray(r)) {
									let i;
									if ((r.state === void 0 || !n.call(r, "state")) && (i = "state")) return H.errors = [{
										instancePath: t + "/preferences",
										schemaPath: "#/properties/preferences/required",
										keyword: "required",
										params: { missingProperty: i }
									}], !1;
									if (r.state !== void 0 && n.call(r, "state")) {
										let e = c;
										if (typeof r.state != "string") return H.errors = [{
											instancePath: t + "/preferences/state",
											schemaPath: "#/properties/preferences/properties/state/type",
											keyword: "type",
											params: { type: "string" }
										}], !1;
										var p = e === c;
									} else var p = !0;
									if (p) {
										let n = r.state;
										if (typeof n == "string") {
											if (n === "not_requested") {
												ct(r, {
													instancePath: t + "/preferences",
													parentData: e,
													parentDataProperty: "preferences",
													rootData: a,
													dynamicAnchors: o
												}) || (s = s === null ? ct.errors : s.concat(ct.errors), c = s.length);
												var m = !0;
											} else if (n === "succeeded") vt(r, {
												instancePath: t + "/preferences",
												parentData: e,
												parentDataProperty: "preferences",
												rootData: a,
												dynamicAnchors: o
											}) || (s = s === null ? vt.errors : s.concat(vt.errors), c = s.length), m !== !0 && (m = !0);
											else if (n === "rejected") dt(r, {
												instancePath: t + "/preferences",
												parentData: e,
												parentDataProperty: "preferences",
												rootData: a,
												dynamicAnchors: o
											}) || (s = s === null ? dt.errors : s.concat(dt.errors), c = s.length), m !== !0 && (m = !0);
											else if (n === "unresolved") R(r, {
												instancePath: t + "/preferences",
												parentData: e,
												parentDataProperty: "preferences",
												rootData: a,
												dynamicAnchors: o
											}) || (s = s === null ? R.errors : s.concat(R.errors), c = s.length), m !== !0 && (m = !0);
											else return H.errors = [{
												instancePath: t + "/preferences",
												schemaPath: "#/properties/preferences/discriminator",
												keyword: "discriminator",
												params: {
													error: "mapping",
													tag: "state",
													tagValue: n
												}
											}], !1;
										} else return H.errors = [{
											instancePath: t + "/preferences",
											schemaPath: "#/properties/preferences/discriminator",
											keyword: "discriminator",
											params: {
												error: "tag",
												tag: "state",
												tagValue: n
											}
										}], !1;
									}
								} else return H.errors = [{
									instancePath: t + "/preferences",
									schemaPath: "#/properties/preferences/type",
									keyword: "type",
									params: { type: "object" }
								}], !1;
							}
							var f = i === c;
						} else var f = !0;
						if (f) {
							if (e.shortlist !== void 0 && n.call(e, "shortlist")) {
								let r = e.shortlist, i = c;
								if (c === i) {
									if (r && typeof r == "object" && !Array.isArray(r)) {
										let i;
										if ((r.state === void 0 || !n.call(r, "state")) && (i = "state")) return H.errors = [{
											instancePath: t + "/shortlist",
											schemaPath: "#/properties/shortlist/required",
											keyword: "required",
											params: { missingProperty: i }
										}], !1;
										if (r.state !== void 0 && n.call(r, "state")) {
											let e = c;
											if (typeof r.state != "string") return H.errors = [{
												instancePath: t + "/shortlist/state",
												schemaPath: "#/properties/shortlist/properties/state/type",
												keyword: "type",
												params: { type: "string" }
											}], !1;
											var h = e === c;
										} else var h = !0;
										if (h) {
											let n = r.state;
											if (typeof n == "string") {
												if (n === "not_requested") {
													ct(r, {
														instancePath: t + "/shortlist",
														parentData: e,
														parentDataProperty: "shortlist",
														rootData: a,
														dynamicAnchors: o
													}) || (s = s === null ? ct.errors : s.concat(ct.errors), c = s.length);
													var g = !0;
												} else if (n === "succeeded") yt(r, {
													instancePath: t + "/shortlist",
													parentData: e,
													parentDataProperty: "shortlist",
													rootData: a,
													dynamicAnchors: o
												}) || (s = s === null ? yt.errors : s.concat(yt.errors), c = s.length), g !== !0 && (g = !0);
												else if (n === "rejected") dt(r, {
													instancePath: t + "/shortlist",
													parentData: e,
													parentDataProperty: "shortlist",
													rootData: a,
													dynamicAnchors: o
												}) || (s = s === null ? dt.errors : s.concat(dt.errors), c = s.length), g !== !0 && (g = !0);
												else if (n === "unresolved") R(r, {
													instancePath: t + "/shortlist",
													parentData: e,
													parentDataProperty: "shortlist",
													rootData: a,
													dynamicAnchors: o
												}) || (s = s === null ? R.errors : s.concat(R.errors), c = s.length), g !== !0 && (g = !0);
												else return H.errors = [{
													instancePath: t + "/shortlist",
													schemaPath: "#/properties/shortlist/discriminator",
													keyword: "discriminator",
													params: {
														error: "mapping",
														tag: "state",
														tagValue: n
													}
												}], !1;
											} else return H.errors = [{
												instancePath: t + "/shortlist",
												schemaPath: "#/properties/shortlist/discriminator",
												keyword: "discriminator",
												params: {
													error: "tag",
													tag: "state",
													tagValue: n
												}
											}], !1;
										}
									} else return H.errors = [{
										instancePath: t + "/shortlist",
										schemaPath: "#/properties/shortlist/type",
										keyword: "type",
										params: { type: "object" }
									}], !1;
								}
								var f = i === c;
							} else var f = !0;
						}
					}
				}
			} else return H.errors = [{
				instancePath: t,
				schemaPath: "#/type",
				keyword: "type",
				params: { type: "object" }
			}], !1;
		}
		return H.errors = s, c === 0;
	}
	H.evaluated = {
		props: !0,
		dynamicProps: !1,
		dynamicItems: !1
	};
	function bt(e, { instancePath: t = "", parentData: r, parentDataProperty: i, rootData: a = e, dynamicAnchors: o = {} } = {}) {
		let s = null, c = 0, u = bt.evaluated;
		if (u.dynamicProps && (u.props = void 0), u.dynamicItems && (u.items = void 0), c === 0) {
			if (e && typeof e == "object" && !Array.isArray(e)) {
				let r;
				if ((e.ref === void 0 || !n.call(e, "ref")) && (r = "ref") || (e.attributes === void 0 || !n.call(e, "attributes")) && (r = "attributes")) return bt.errors = [{
					instancePath: t,
					schemaPath: "#/required",
					keyword: "required",
					params: { missingProperty: r }
				}], !1;
				{
					let r = c;
					for (let n of Object.keys(e)) if (n !== "attributes" && n !== "ref") return bt.errors = [{
						instancePath: t,
						schemaPath: "#/additionalProperties",
						keyword: "additionalProperties",
						params: { additionalProperty: n }
					}], !1;
					if (r === c) {
						if (e.attributes !== void 0 && n.call(e, "attributes")) {
							let n = e.attributes, r = c;
							if (c === r) {
								if (Array.isArray(n)) {
									if (n.length > 24) return bt.errors = [{
										instancePath: t + "/attributes",
										schemaPath: "#/properties/attributes/maxItems",
										keyword: "maxItems",
										params: { limit: 24 }
									}], !1;
									{
										let e = n.length;
										for (let r = 0; r < e; r++) {
											let e = n[r], i = c;
											if (c === i) {
												if (typeof e == "string") {
													if (h(e) > 200) return bt.errors = [{
														instancePath: t + "/attributes/" + r,
														schemaPath: "#/properties/attributes/items/maxLength",
														keyword: "maxLength",
														params: { limit: 200 }
													}], !1;
													if (h(e) < 1) return bt.errors = [{
														instancePath: t + "/attributes/" + r,
														schemaPath: "#/properties/attributes/items/minLength",
														keyword: "minLength",
														params: { limit: 1 }
													}], !1;
												} else return bt.errors = [{
													instancePath: t + "/attributes/" + r,
													schemaPath: "#/properties/attributes/items/type",
													keyword: "type",
													params: { type: "string" }
												}], !1;
											}
											if (i !== c) break;
										}
									}
								} else return bt.errors = [{
									instancePath: t + "/attributes",
									schemaPath: "#/properties/attributes/type",
									keyword: "type",
									params: { type: "array" }
								}], !1;
							}
							var d = r === c;
						} else var d = !0;
						if (d) {
							if (e.ref !== void 0 && n.call(e, "ref")) {
								let n = c;
								l(e.ref, {
									instancePath: t + "/ref",
									parentData: e,
									parentDataProperty: "ref",
									rootData: a,
									dynamicAnchors: o
								}) || (s = s === null ? l.errors : s.concat(l.errors), c = s.length);
								var d = n === c;
							} else var d = !0;
						}
					}
				}
			} else return bt.errors = [{
				instancePath: t,
				schemaPath: "#/type",
				keyword: "type",
				params: { type: "object" }
			}], !1;
		}
		return bt.errors = s, c === 0;
	}
	bt.evaluated = {
		props: !0,
		dynamicProps: !1,
		dynamicItems: !1
	};
	var xt = {
		additionalProperties: !1,
		properties: {
			body_types: {
				default: [],
				items: {
					maxLength: 200,
					minLength: 1,
					type: "string"
				},
				maxItems: 8,
				title: "Body Types",
				type: "array"
			},
			budget: { anyOf: [{ $ref: "urn:car-shopping-assistant:contract:1#/$defs/BudgetRange" }, { type: "null" }] },
			fuel_types: {
				default: [],
				items: {
					maxLength: 200,
					minLength: 1,
					type: "string"
				},
				maxItems: 8,
				title: "Fuel Types",
				type: "array"
			},
			makes: {
				default: [],
				items: {
					maxLength: 200,
					minLength: 1,
					type: "string"
				},
				maxItems: 12,
				title: "Makes",
				type: "array"
			},
			mileage_km: { anyOf: [{ $ref: "urn:car-shopping-assistant:contract:1#/$defs/IntegerRange" }, { type: "null" }] },
			models: {
				default: [],
				items: {
					maxLength: 200,
					minLength: 1,
					type: "string"
				},
				maxItems: 12,
				title: "Models",
				type: "array"
			},
			transmissions: {
				default: [],
				items: {
					maxLength: 200,
					minLength: 1,
					type: "string"
				},
				maxItems: 8,
				title: "Transmissions",
				type: "array"
			},
			trims: {
				default: [],
				items: {
					maxLength: 200,
					minLength: 1,
					type: "string"
				},
				maxItems: 12,
				title: "Trims",
				type: "array"
			},
			years: { anyOf: [{ $ref: "urn:car-shopping-assistant:contract:1#/$defs/IntegerRange" }, { type: "null" }] }
		},
		title: "SearchFilters",
		type: "object"
	};
	function St(e, { instancePath: t = "", parentData: r, parentDataProperty: i, rootData: a = e, dynamicAnchors: o = {} } = {}) {
		let s = null, c = 0, l = St.evaluated;
		if (l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0) {
			if (e && typeof e == "object" && !Array.isArray(e)) {
				let r = c;
				for (let n of Object.keys(e)) if (n !== "maximum" && n !== "minimum") return St.errors = [{
					instancePath: t,
					schemaPath: "#/additionalProperties",
					keyword: "additionalProperties",
					params: { additionalProperty: n }
				}], !1;
				if (r === c) {
					if (e.maximum !== void 0 && n.call(e, "maximum")) {
						let n = e.maximum, r = c, i = c, a = !1, o = c;
						if (typeof n != "number" || n % 1 || isNaN(n) || !isFinite(n)) {
							let e = {
								instancePath: t + "/maximum",
								schemaPath: "#/properties/maximum/anyOf/0/type",
								keyword: "type",
								params: { type: "integer" }
							};
							s === null ? s = [e] : s.push(e), c++;
						}
						if (c === o && typeof n == "number" && isFinite(n)) {
							if (n > 0xe8d4a51000 || isNaN(n)) {
								let e = {
									instancePath: t + "/maximum",
									schemaPath: "#/properties/maximum/anyOf/0/maximum",
									keyword: "maximum",
									params: {
										comparison: "<=",
										limit: 0xe8d4a51000
									}
								};
								s === null ? s = [e] : s.push(e), c++;
							} else if (n < 0 || isNaN(n)) {
								let e = {
									instancePath: t + "/maximum",
									schemaPath: "#/properties/maximum/anyOf/0/minimum",
									keyword: "minimum",
									params: {
										comparison: ">=",
										limit: 0
									}
								};
								s === null ? s = [e] : s.push(e), c++;
							}
						}
						var u = o === c;
						a ||= u;
						let l = c;
						if (n !== null) {
							let e = {
								instancePath: t + "/maximum",
								schemaPath: "#/properties/maximum/anyOf/1/type",
								keyword: "type",
								params: { type: "null" }
							};
							s === null ? s = [e] : s.push(e), c++;
						}
						var u = l === c;
						if (a ||= u, a) c = i, s !== null && (i ? s.length = i : s = null);
						else {
							let e = {
								instancePath: t + "/maximum",
								schemaPath: "#/properties/maximum/anyOf",
								keyword: "anyOf",
								params: {}
							};
							return s === null ? s = [e] : s.push(e), c++, St.errors = s, !1;
						}
						var d = r === c;
					} else var d = !0;
					if (d) {
						if (e.minimum !== void 0 && n.call(e, "minimum")) {
							let n = e.minimum, r = c, i = c, a = !1, o = c;
							if (typeof n != "number" || n % 1 || isNaN(n) || !isFinite(n)) {
								let e = {
									instancePath: t + "/minimum",
									schemaPath: "#/properties/minimum/anyOf/0/type",
									keyword: "type",
									params: { type: "integer" }
								};
								s === null ? s = [e] : s.push(e), c++;
							}
							if (c === o && typeof n == "number" && isFinite(n)) {
								if (n > 0xe8d4a51000 || isNaN(n)) {
									let e = {
										instancePath: t + "/minimum",
										schemaPath: "#/properties/minimum/anyOf/0/maximum",
										keyword: "maximum",
										params: {
											comparison: "<=",
											limit: 0xe8d4a51000
										}
									};
									s === null ? s = [e] : s.push(e), c++;
								} else if (n < 0 || isNaN(n)) {
									let e = {
										instancePath: t + "/minimum",
										schemaPath: "#/properties/minimum/anyOf/0/minimum",
										keyword: "minimum",
										params: {
											comparison: ">=",
											limit: 0
										}
									};
									s === null ? s = [e] : s.push(e), c++;
								}
							}
							var f = o === c;
							a ||= f;
							let l = c;
							if (n !== null) {
								let e = {
									instancePath: t + "/minimum",
									schemaPath: "#/properties/minimum/anyOf/1/type",
									keyword: "type",
									params: { type: "null" }
								};
								s === null ? s = [e] : s.push(e), c++;
							}
							var f = l === c;
							if (a ||= f, a) c = i, s !== null && (i ? s.length = i : s = null);
							else {
								let e = {
									instancePath: t + "/minimum",
									schemaPath: "#/properties/minimum/anyOf",
									keyword: "anyOf",
									params: {}
								};
								return s === null ? s = [e] : s.push(e), c++, St.errors = s, !1;
							}
							var d = r === c;
						} else var d = !0;
					}
				}
			} else return St.errors = [{
				instancePath: t,
				schemaPath: "#/type",
				keyword: "type",
				params: { type: "object" }
			}], !1;
		}
		return St.errors = s, c === 0;
	}
	St.evaluated = {
		props: !0,
		dynamicProps: !1,
		dynamicItems: !1
	};
	function U(e, { instancePath: t = "", parentData: r, parentDataProperty: i, rootData: a = e, dynamicAnchors: o = {} } = {}) {
		let s = null, c = 0, l = U.evaluated;
		if (l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0) {
			if (e && typeof e == "object" && !Array.isArray(e)) {
				let r = c;
				for (let r of Object.keys(e)) if (!n.call(xt.properties, r)) return U.errors = [{
					instancePath: t,
					schemaPath: "#/additionalProperties",
					keyword: "additionalProperties",
					params: { additionalProperty: r }
				}], !1;
				if (r === c) {
					if (e.body_types !== void 0 && n.call(e, "body_types")) {
						let n = e.body_types, r = c;
						if (c === r) {
							if (Array.isArray(n)) {
								if (n.length > 8) return U.errors = [{
									instancePath: t + "/body_types",
									schemaPath: "#/properties/body_types/maxItems",
									keyword: "maxItems",
									params: { limit: 8 }
								}], !1;
								{
									let e = n.length;
									for (let r = 0; r < e; r++) {
										let e = n[r], i = c;
										if (c === i) {
											if (typeof e == "string") {
												if (h(e) > 200) return U.errors = [{
													instancePath: t + "/body_types/" + r,
													schemaPath: "#/properties/body_types/items/maxLength",
													keyword: "maxLength",
													params: { limit: 200 }
												}], !1;
												if (h(e) < 1) return U.errors = [{
													instancePath: t + "/body_types/" + r,
													schemaPath: "#/properties/body_types/items/minLength",
													keyword: "minLength",
													params: { limit: 1 }
												}], !1;
											} else return U.errors = [{
												instancePath: t + "/body_types/" + r,
												schemaPath: "#/properties/body_types/items/type",
												keyword: "type",
												params: { type: "string" }
											}], !1;
										}
										if (i !== c) break;
									}
								}
							} else return U.errors = [{
								instancePath: t + "/body_types",
								schemaPath: "#/properties/body_types/type",
								keyword: "type",
								params: { type: "array" }
							}], !1;
						}
						var u = r === c;
					} else var u = !0;
					if (u) {
						if (e.budget !== void 0 && n.call(e, "budget")) {
							let n = e.budget, r = c, i = c, l = !1, f = c;
							ke(n, {
								instancePath: t + "/budget",
								parentData: e,
								parentDataProperty: "budget",
								rootData: a,
								dynamicAnchors: o
							}) || (s = s === null ? ke.errors : s.concat(ke.errors), c = s.length);
							var d = f === c;
							l ||= d;
							let p = c;
							if (n !== null) {
								let e = {
									instancePath: t + "/budget",
									schemaPath: "#/properties/budget/anyOf/1/type",
									keyword: "type",
									params: { type: "null" }
								};
								s === null ? s = [e] : s.push(e), c++;
							}
							var d = p === c;
							if (l ||= d, l) c = i, s !== null && (i ? s.length = i : s = null);
							else {
								let e = {
									instancePath: t + "/budget",
									schemaPath: "#/properties/budget/anyOf",
									keyword: "anyOf",
									params: {}
								};
								return s === null ? s = [e] : s.push(e), c++, U.errors = s, !1;
							}
							var u = r === c;
						} else var u = !0;
						if (u) {
							if (e.fuel_types !== void 0 && n.call(e, "fuel_types")) {
								let n = e.fuel_types, r = c;
								if (c === r) {
									if (Array.isArray(n)) {
										if (n.length > 8) return U.errors = [{
											instancePath: t + "/fuel_types",
											schemaPath: "#/properties/fuel_types/maxItems",
											keyword: "maxItems",
											params: { limit: 8 }
										}], !1;
										{
											let e = n.length;
											for (let r = 0; r < e; r++) {
												let e = n[r], i = c;
												if (c === i) {
													if (typeof e == "string") {
														if (h(e) > 200) return U.errors = [{
															instancePath: t + "/fuel_types/" + r,
															schemaPath: "#/properties/fuel_types/items/maxLength",
															keyword: "maxLength",
															params: { limit: 200 }
														}], !1;
														if (h(e) < 1) return U.errors = [{
															instancePath: t + "/fuel_types/" + r,
															schemaPath: "#/properties/fuel_types/items/minLength",
															keyword: "minLength",
															params: { limit: 1 }
														}], !1;
													} else return U.errors = [{
														instancePath: t + "/fuel_types/" + r,
														schemaPath: "#/properties/fuel_types/items/type",
														keyword: "type",
														params: { type: "string" }
													}], !1;
												}
												if (i !== c) break;
											}
										}
									} else return U.errors = [{
										instancePath: t + "/fuel_types",
										schemaPath: "#/properties/fuel_types/type",
										keyword: "type",
										params: { type: "array" }
									}], !1;
								}
								var u = r === c;
							} else var u = !0;
							if (u) {
								if (e.makes !== void 0 && n.call(e, "makes")) {
									let n = e.makes, r = c;
									if (c === r) {
										if (Array.isArray(n)) {
											if (n.length > 12) return U.errors = [{
												instancePath: t + "/makes",
												schemaPath: "#/properties/makes/maxItems",
												keyword: "maxItems",
												params: { limit: 12 }
											}], !1;
											{
												let e = n.length;
												for (let r = 0; r < e; r++) {
													let e = n[r], i = c;
													if (c === i) {
														if (typeof e == "string") {
															if (h(e) > 200) return U.errors = [{
																instancePath: t + "/makes/" + r,
																schemaPath: "#/properties/makes/items/maxLength",
																keyword: "maxLength",
																params: { limit: 200 }
															}], !1;
															if (h(e) < 1) return U.errors = [{
																instancePath: t + "/makes/" + r,
																schemaPath: "#/properties/makes/items/minLength",
																keyword: "minLength",
																params: { limit: 1 }
															}], !1;
														} else return U.errors = [{
															instancePath: t + "/makes/" + r,
															schemaPath: "#/properties/makes/items/type",
															keyword: "type",
															params: { type: "string" }
														}], !1;
													}
													if (i !== c) break;
												}
											}
										} else return U.errors = [{
											instancePath: t + "/makes",
											schemaPath: "#/properties/makes/type",
											keyword: "type",
											params: { type: "array" }
										}], !1;
									}
									var u = r === c;
								} else var u = !0;
								if (u) {
									if (e.mileage_km !== void 0 && n.call(e, "mileage_km")) {
										let n = e.mileage_km, r = c, i = c, l = !1, d = c;
										St(n, {
											instancePath: t + "/mileage_km",
											parentData: e,
											parentDataProperty: "mileage_km",
											rootData: a,
											dynamicAnchors: o
										}) || (s = s === null ? St.errors : s.concat(St.errors), c = s.length);
										var f = d === c;
										l ||= f;
										let p = c;
										if (n !== null) {
											let e = {
												instancePath: t + "/mileage_km",
												schemaPath: "#/properties/mileage_km/anyOf/1/type",
												keyword: "type",
												params: { type: "null" }
											};
											s === null ? s = [e] : s.push(e), c++;
										}
										var f = p === c;
										if (l ||= f, l) c = i, s !== null && (i ? s.length = i : s = null);
										else {
											let e = {
												instancePath: t + "/mileage_km",
												schemaPath: "#/properties/mileage_km/anyOf",
												keyword: "anyOf",
												params: {}
											};
											return s === null ? s = [e] : s.push(e), c++, U.errors = s, !1;
										}
										var u = r === c;
									} else var u = !0;
									if (u) {
										if (e.models !== void 0 && n.call(e, "models")) {
											let n = e.models, r = c;
											if (c === r) {
												if (Array.isArray(n)) {
													if (n.length > 12) return U.errors = [{
														instancePath: t + "/models",
														schemaPath: "#/properties/models/maxItems",
														keyword: "maxItems",
														params: { limit: 12 }
													}], !1;
													{
														let e = n.length;
														for (let r = 0; r < e; r++) {
															let e = n[r], i = c;
															if (c === i) {
																if (typeof e == "string") {
																	if (h(e) > 200) return U.errors = [{
																		instancePath: t + "/models/" + r,
																		schemaPath: "#/properties/models/items/maxLength",
																		keyword: "maxLength",
																		params: { limit: 200 }
																	}], !1;
																	if (h(e) < 1) return U.errors = [{
																		instancePath: t + "/models/" + r,
																		schemaPath: "#/properties/models/items/minLength",
																		keyword: "minLength",
																		params: { limit: 1 }
																	}], !1;
																} else return U.errors = [{
																	instancePath: t + "/models/" + r,
																	schemaPath: "#/properties/models/items/type",
																	keyword: "type",
																	params: { type: "string" }
																}], !1;
															}
															if (i !== c) break;
														}
													}
												} else return U.errors = [{
													instancePath: t + "/models",
													schemaPath: "#/properties/models/type",
													keyword: "type",
													params: { type: "array" }
												}], !1;
											}
											var u = r === c;
										} else var u = !0;
										if (u) {
											if (e.transmissions !== void 0 && n.call(e, "transmissions")) {
												let n = e.transmissions, r = c;
												if (c === r) {
													if (Array.isArray(n)) {
														if (n.length > 8) return U.errors = [{
															instancePath: t + "/transmissions",
															schemaPath: "#/properties/transmissions/maxItems",
															keyword: "maxItems",
															params: { limit: 8 }
														}], !1;
														{
															let e = n.length;
															for (let r = 0; r < e; r++) {
																let e = n[r], i = c;
																if (c === i) {
																	if (typeof e == "string") {
																		if (h(e) > 200) return U.errors = [{
																			instancePath: t + "/transmissions/" + r,
																			schemaPath: "#/properties/transmissions/items/maxLength",
																			keyword: "maxLength",
																			params: { limit: 200 }
																		}], !1;
																		if (h(e) < 1) return U.errors = [{
																			instancePath: t + "/transmissions/" + r,
																			schemaPath: "#/properties/transmissions/items/minLength",
																			keyword: "minLength",
																			params: { limit: 1 }
																		}], !1;
																	} else return U.errors = [{
																		instancePath: t + "/transmissions/" + r,
																		schemaPath: "#/properties/transmissions/items/type",
																		keyword: "type",
																		params: { type: "string" }
																	}], !1;
																}
																if (i !== c) break;
															}
														}
													} else return U.errors = [{
														instancePath: t + "/transmissions",
														schemaPath: "#/properties/transmissions/type",
														keyword: "type",
														params: { type: "array" }
													}], !1;
												}
												var u = r === c;
											} else var u = !0;
											if (u) {
												if (e.trims !== void 0 && n.call(e, "trims")) {
													let n = e.trims, r = c;
													if (c === r) {
														if (Array.isArray(n)) {
															if (n.length > 12) return U.errors = [{
																instancePath: t + "/trims",
																schemaPath: "#/properties/trims/maxItems",
																keyword: "maxItems",
																params: { limit: 12 }
															}], !1;
															{
																let e = n.length;
																for (let r = 0; r < e; r++) {
																	let e = n[r], i = c;
																	if (c === i) {
																		if (typeof e == "string") {
																			if (h(e) > 200) return U.errors = [{
																				instancePath: t + "/trims/" + r,
																				schemaPath: "#/properties/trims/items/maxLength",
																				keyword: "maxLength",
																				params: { limit: 200 }
																			}], !1;
																			if (h(e) < 1) return U.errors = [{
																				instancePath: t + "/trims/" + r,
																				schemaPath: "#/properties/trims/items/minLength",
																				keyword: "minLength",
																				params: { limit: 1 }
																			}], !1;
																		} else return U.errors = [{
																			instancePath: t + "/trims/" + r,
																			schemaPath: "#/properties/trims/items/type",
																			keyword: "type",
																			params: { type: "string" }
																		}], !1;
																	}
																	if (i !== c) break;
																}
															}
														} else return U.errors = [{
															instancePath: t + "/trims",
															schemaPath: "#/properties/trims/type",
															keyword: "type",
															params: { type: "array" }
														}], !1;
													}
													var u = r === c;
												} else var u = !0;
												if (u) {
													if (e.years !== void 0 && n.call(e, "years")) {
														let n = e.years, r = c, i = c, l = !1, d = c;
														St(n, {
															instancePath: t + "/years",
															parentData: e,
															parentDataProperty: "years",
															rootData: a,
															dynamicAnchors: o
														}) || (s = s === null ? St.errors : s.concat(St.errors), c = s.length);
														var p = d === c;
														l ||= p;
														let f = c;
														if (n !== null) {
															let e = {
																instancePath: t + "/years",
																schemaPath: "#/properties/years/anyOf/1/type",
																keyword: "type",
																params: { type: "null" }
															};
															s === null ? s = [e] : s.push(e), c++;
														}
														var p = f === c;
														if (l ||= p, l) c = i, s !== null && (i ? s.length = i : s = null);
														else {
															let e = {
																instancePath: t + "/years",
																schemaPath: "#/properties/years/anyOf",
																keyword: "anyOf",
																params: {}
															};
															return s === null ? s = [e] : s.push(e), c++, U.errors = s, !1;
														}
														var u = r === c;
													} else var u = !0;
												}
											}
										}
									}
								}
							}
						}
					}
				}
			} else return U.errors = [{
				instancePath: t,
				schemaPath: "#/type",
				keyword: "type",
				params: { type: "object" }
			}], !1;
		}
		return U.errors = s, c === 0;
	}
	U.evaluated = {
		props: !0,
		dynamicProps: !1,
		dynamicItems: !1
	};
	function Ct(e, { instancePath: t = "", parentData: r, parentDataProperty: i, rootData: a = e, dynamicAnchors: o = {} } = {}) {
		let s = null, c = 0, l = Ct.evaluated;
		if (l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0) {
			if (e && typeof e == "object" && !Array.isArray(e)) {
				let r = c;
				for (let n of Object.keys(e)) if (n !== "filters" && n !== "query" && n !== "soft_preferences") return Ct.errors = [{
					instancePath: t,
					schemaPath: "#/additionalProperties",
					keyword: "additionalProperties",
					params: { additionalProperty: n }
				}], !1;
				if (r === c) {
					if (e.filters !== void 0 && n.call(e, "filters")) {
						let n = c;
						U(e.filters, {
							instancePath: t + "/filters",
							parentData: e,
							parentDataProperty: "filters",
							rootData: a,
							dynamicAnchors: o
						}) || (s = s === null ? U.errors : s.concat(U.errors), c = s.length);
						var u = n === c;
					} else var u = !0;
					if (u) {
						if (e.query !== void 0 && n.call(e, "query")) {
							let n = e.query, r = c;
							if (c === r) {
								if (typeof n == "string") {
									if (h(n) > 1e3) return Ct.errors = [{
										instancePath: t + "/query",
										schemaPath: "#/properties/query/maxLength",
										keyword: "maxLength",
										params: { limit: 1e3 }
									}], !1;
								} else return Ct.errors = [{
									instancePath: t + "/query",
									schemaPath: "#/properties/query/type",
									keyword: "type",
									params: { type: "string" }
								}], !1;
							}
							var u = r === c;
						} else var u = !0;
						if (u) {
							if (e.soft_preferences !== void 0 && n.call(e, "soft_preferences")) {
								let n = e.soft_preferences, r = c;
								if (c === r) {
									if (Array.isArray(n)) {
										if (n.length > 12) return Ct.errors = [{
											instancePath: t + "/soft_preferences",
											schemaPath: "#/properties/soft_preferences/maxItems",
											keyword: "maxItems",
											params: { limit: 12 }
										}], !1;
										{
											let e = n.length;
											for (let r = 0; r < e; r++) {
												let e = n[r], i = c;
												if (c === i) {
													if (typeof e == "string") {
														if (h(e) > 200) return Ct.errors = [{
															instancePath: t + "/soft_preferences/" + r,
															schemaPath: "#/properties/soft_preferences/items/maxLength",
															keyword: "maxLength",
															params: { limit: 200 }
														}], !1;
														if (h(e) < 1) return Ct.errors = [{
															instancePath: t + "/soft_preferences/" + r,
															schemaPath: "#/properties/soft_preferences/items/minLength",
															keyword: "minLength",
															params: { limit: 1 }
														}], !1;
													} else return Ct.errors = [{
														instancePath: t + "/soft_preferences/" + r,
														schemaPath: "#/properties/soft_preferences/items/type",
														keyword: "type",
														params: { type: "string" }
													}], !1;
												}
												if (i !== c) break;
											}
										}
									} else return Ct.errors = [{
										instancePath: t + "/soft_preferences",
										schemaPath: "#/properties/soft_preferences/type",
										keyword: "type",
										params: { type: "array" }
									}], !1;
								}
								var u = r === c;
							} else var u = !0;
						}
					}
				}
			} else return Ct.errors = [{
				instancePath: t,
				schemaPath: "#/type",
				keyword: "type",
				params: { type: "object" }
			}], !1;
		}
		return Ct.errors = s, c === 0;
	}
	Ct.evaluated = {
		props: !0,
		dynamicProps: !1,
		dynamicItems: !1
	};
	function wt(e, { instancePath: t = "", parentData: r, parentDataProperty: i, rootData: a = e, dynamicAnchors: o = {} } = {}) {
		let s = wt.evaluated;
		if (s.dynamicProps && (s.props = void 0), s.dynamicItems && (s.items = void 0), e && typeof e == "object" && !Array.isArray(e)) {
			let r;
			if ((e.criterion === void 0 || !n.call(e, "criterion")) && (r = "criterion") || (e.attribute === void 0 || !n.call(e, "attribute")) && (r = "attribute") || (e.evidence_ids === void 0 || !n.call(e, "evidence_ids")) && (r = "evidence_ids") || (e.text === void 0 || !n.call(e, "text")) && (r = "text")) return wt.errors = [{
				instancePath: t,
				schemaPath: "#/required",
				keyword: "required",
				params: { missingProperty: r }
			}], !1;
			for (let n of Object.keys(e)) if (n !== "attribute" && n !== "criterion" && n !== "evidence_ids" && n !== "text") return wt.errors = [{
				instancePath: t,
				schemaPath: "#/additionalProperties",
				keyword: "additionalProperties",
				params: { additionalProperty: n }
			}], !1;
			if (e.attribute !== void 0 && n.call(e, "attribute")) {
				let n = e.attribute;
				if (typeof n == "string") {
					if (h(n) > 200) return wt.errors = [{
						instancePath: t + "/attribute",
						schemaPath: "#/properties/attribute/maxLength",
						keyword: "maxLength",
						params: { limit: 200 }
					}], !1;
					if (h(n) < 1) return wt.errors = [{
						instancePath: t + "/attribute",
						schemaPath: "#/properties/attribute/minLength",
						keyword: "minLength",
						params: { limit: 1 }
					}], !1;
				} else return wt.errors = [{
					instancePath: t + "/attribute",
					schemaPath: "#/properties/attribute/type",
					keyword: "type",
					params: { type: "string" }
				}], !1;
				var c = !0;
			} else var c = !0;
			if (c) {
				if (e.criterion !== void 0 && n.call(e, "criterion")) {
					let n = e.criterion;
					if (typeof n == "string") {
						if (h(n) > 200) return wt.errors = [{
							instancePath: t + "/criterion",
							schemaPath: "#/properties/criterion/maxLength",
							keyword: "maxLength",
							params: { limit: 200 }
						}], !1;
						if (h(n) < 1) return wt.errors = [{
							instancePath: t + "/criterion",
							schemaPath: "#/properties/criterion/minLength",
							keyword: "minLength",
							params: { limit: 1 }
						}], !1;
					} else return wt.errors = [{
						instancePath: t + "/criterion",
						schemaPath: "#/properties/criterion/type",
						keyword: "type",
						params: { type: "string" }
					}], !1;
					var c = !0;
				} else var c = !0;
				if (c) {
					if (e.evidence_ids !== void 0 && n.call(e, "evidence_ids")) {
						let n = e.evidence_ids;
						if (Array.isArray(n)) {
							if (n.length > 12) return wt.errors = [{
								instancePath: t + "/evidence_ids",
								schemaPath: "#/properties/evidence_ids/maxItems",
								keyword: "maxItems",
								params: { limit: 12 }
							}], !1;
							if (n.length < 1) return wt.errors = [{
								instancePath: t + "/evidence_ids",
								schemaPath: "#/properties/evidence_ids/minItems",
								keyword: "minItems",
								params: { limit: 1 }
							}], !1;
							{
								let e = n.length;
								for (let r = 0; r < e; r++) {
									let e = n[r];
									if (typeof e == "string") {
										if (!u.test(e)) return wt.errors = [{
											instancePath: t + "/evidence_ids/" + r,
											schemaPath: "#/properties/evidence_ids/items/pattern",
											keyword: "pattern",
											params: { pattern: "^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$" }
										}], !1;
									} else return wt.errors = [{
										instancePath: t + "/evidence_ids/" + r,
										schemaPath: "#/properties/evidence_ids/items/type",
										keyword: "type",
										params: { type: "string" }
									}], !1;
								}
							}
						} else return wt.errors = [{
							instancePath: t + "/evidence_ids",
							schemaPath: "#/properties/evidence_ids/type",
							keyword: "type",
							params: { type: "array" }
						}], !1;
						var c = !0;
					} else var c = !0;
					if (c) {
						if (e.text !== void 0 && n.call(e, "text")) {
							let n = e.text;
							if (typeof n == "string") {
								if (h(n) > 1e3) return wt.errors = [{
									instancePath: t + "/text",
									schemaPath: "#/properties/text/maxLength",
									keyword: "maxLength",
									params: { limit: 1e3 }
								}], !1;
							} else return wt.errors = [{
								instancePath: t + "/text",
								schemaPath: "#/properties/text/type",
								keyword: "type",
								params: { type: "string" }
							}], !1;
							var c = !0;
						} else var c = !0;
					}
				}
			}
		} else return wt.errors = [{
			instancePath: t,
			schemaPath: "#/type",
			keyword: "type",
			params: { type: "object" }
		}], !1;
		return wt.errors = null, !0;
	}
	wt.evaluated = {
		props: !0,
		dynamicProps: !1,
		dynamicItems: !1
	};
	var Tt = {
		additionalProperties: !1,
		properties: {
			attribute: {
				maxLength: 200,
				minLength: 1,
				title: "Attribute",
				type: "string"
			},
			criterion: {
				maxLength: 200,
				minLength: 1,
				title: "Criterion",
				type: "string"
			},
			question: {
				maxLength: 1e3,
				title: "Question",
				type: "string"
			},
			reason: {
				enum: [
					"unknown",
					"conflicting",
					"unverified",
					"unmet"
				],
				title: "Reason",
				type: "string"
			}
		},
		required: [
			"criterion",
			"attribute",
			"reason",
			"question"
		],
		title: "UnresolvedQuestion",
		type: "object"
	};
	function Et(e, { instancePath: t = "", parentData: r, parentDataProperty: i, rootData: a = e, dynamicAnchors: o = {} } = {}) {
		let s = Et.evaluated;
		if (s.dynamicProps && (s.props = void 0), s.dynamicItems && (s.items = void 0), e && typeof e == "object" && !Array.isArray(e)) {
			let r;
			if ((e.criterion === void 0 || !n.call(e, "criterion")) && (r = "criterion") || (e.attribute === void 0 || !n.call(e, "attribute")) && (r = "attribute") || (e.reason === void 0 || !n.call(e, "reason")) && (r = "reason") || (e.question === void 0 || !n.call(e, "question")) && (r = "question")) return Et.errors = [{
				instancePath: t,
				schemaPath: "#/required",
				keyword: "required",
				params: { missingProperty: r }
			}], !1;
			for (let n of Object.keys(e)) if (n !== "attribute" && n !== "criterion" && n !== "question" && n !== "reason") return Et.errors = [{
				instancePath: t,
				schemaPath: "#/additionalProperties",
				keyword: "additionalProperties",
				params: { additionalProperty: n }
			}], !1;
			if (e.attribute !== void 0 && n.call(e, "attribute")) {
				let n = e.attribute;
				if (typeof n == "string") {
					if (h(n) > 200) return Et.errors = [{
						instancePath: t + "/attribute",
						schemaPath: "#/properties/attribute/maxLength",
						keyword: "maxLength",
						params: { limit: 200 }
					}], !1;
					if (h(n) < 1) return Et.errors = [{
						instancePath: t + "/attribute",
						schemaPath: "#/properties/attribute/minLength",
						keyword: "minLength",
						params: { limit: 1 }
					}], !1;
				} else return Et.errors = [{
					instancePath: t + "/attribute",
					schemaPath: "#/properties/attribute/type",
					keyword: "type",
					params: { type: "string" }
				}], !1;
				var c = !0;
			} else var c = !0;
			if (c) {
				if (e.criterion !== void 0 && n.call(e, "criterion")) {
					let n = e.criterion;
					if (typeof n == "string") {
						if (h(n) > 200) return Et.errors = [{
							instancePath: t + "/criterion",
							schemaPath: "#/properties/criterion/maxLength",
							keyword: "maxLength",
							params: { limit: 200 }
						}], !1;
						if (h(n) < 1) return Et.errors = [{
							instancePath: t + "/criterion",
							schemaPath: "#/properties/criterion/minLength",
							keyword: "minLength",
							params: { limit: 1 }
						}], !1;
					} else return Et.errors = [{
						instancePath: t + "/criterion",
						schemaPath: "#/properties/criterion/type",
						keyword: "type",
						params: { type: "string" }
					}], !1;
					var c = !0;
				} else var c = !0;
				if (c) {
					if (e.question !== void 0 && n.call(e, "question")) {
						let n = e.question;
						if (typeof n == "string") {
							if (h(n) > 1e3) return Et.errors = [{
								instancePath: t + "/question",
								schemaPath: "#/properties/question/maxLength",
								keyword: "maxLength",
								params: { limit: 1e3 }
							}], !1;
						} else return Et.errors = [{
							instancePath: t + "/question",
							schemaPath: "#/properties/question/type",
							keyword: "type",
							params: { type: "string" }
						}], !1;
						var c = !0;
					} else var c = !0;
					if (c) {
						if (e.reason !== void 0 && n.call(e, "reason")) {
							let n = e.reason;
							if (typeof n != "string") return Et.errors = [{
								instancePath: t + "/reason",
								schemaPath: "#/properties/reason/type",
								keyword: "type",
								params: { type: "string" }
							}], !1;
							if (n !== "unknown" && n !== "conflicting" && n !== "unverified" && n !== "unmet") return Et.errors = [{
								instancePath: t + "/reason",
								schemaPath: "#/properties/reason/enum",
								keyword: "enum",
								params: { allowedValues: Tt.properties.reason.enum }
							}], !1;
							var c = !0;
						} else var c = !0;
					}
				}
			}
		} else return Et.errors = [{
			instancePath: t,
			schemaPath: "#/type",
			keyword: "type",
			params: { type: "object" }
		}], !1;
		return Et.errors = null, !0;
	}
	Et.evaluated = {
		props: !0,
		dynamicProps: !1,
		dynamicItems: !1
	};
	function Dt(e, { instancePath: t = "", parentData: r, parentDataProperty: i, rootData: a = e, dynamicAnchors: o = {} } = {}) {
		let s = null, c = 0, u = Dt.evaluated;
		if (u.dynamicProps && (u.props = void 0), u.dynamicItems && (u.items = void 0), c === 0) {
			if (e && typeof e == "object" && !Array.isArray(e)) {
				let r;
				if ((e.selected_ref === void 0 || !n.call(e, "selected_ref")) && (r = "selected_ref") || (e.listing === void 0 || !n.call(e, "listing")) && (r = "listing") || (e.expressed_criteria === void 0 || !n.call(e, "expressed_criteria")) && (r = "expressed_criteria") || (e.fit_reasons === void 0 || !n.call(e, "fit_reasons")) && (r = "fit_reasons") || (e.unresolved_questions === void 0 || !n.call(e, "unresolved_questions")) && (r = "unresolved_questions")) return Dt.errors = [{
					instancePath: t,
					schemaPath: "#/required",
					keyword: "required",
					params: { missingProperty: r }
				}], !1;
				{
					let r = c;
					for (let n of Object.keys(e)) if (n !== "expressed_criteria" && n !== "fit_reasons" && n !== "listing" && n !== "selected_ref" && n !== "unresolved_questions") return Dt.errors = [{
						instancePath: t,
						schemaPath: "#/additionalProperties",
						keyword: "additionalProperties",
						params: { additionalProperty: n }
					}], !1;
					if (r === c) {
						if (e.expressed_criteria !== void 0 && n.call(e, "expressed_criteria")) {
							let n = c;
							Ct(e.expressed_criteria, {
								instancePath: t + "/expressed_criteria",
								parentData: e,
								parentDataProperty: "expressed_criteria",
								rootData: a,
								dynamicAnchors: o
							}) || (s = s === null ? Ct.errors : s.concat(Ct.errors), c = s.length);
							var d = n === c;
						} else var d = !0;
						if (d) {
							if (e.fit_reasons !== void 0 && n.call(e, "fit_reasons")) {
								let n = e.fit_reasons, r = c;
								if (c === r) {
									if (Array.isArray(n)) {
										if (n.length > 12) return Dt.errors = [{
											instancePath: t + "/fit_reasons",
											schemaPath: "#/properties/fit_reasons/maxItems",
											keyword: "maxItems",
											params: { limit: 12 }
										}], !1;
										{
											let e = n.length;
											for (let r = 0; r < e; r++) {
												let e = c;
												if (wt(n[r], {
													instancePath: t + "/fit_reasons/" + r,
													parentData: n,
													parentDataProperty: r,
													rootData: a,
													dynamicAnchors: o
												}) || (s = s === null ? wt.errors : s.concat(wt.errors), c = s.length), e !== c) break;
											}
										}
									} else return Dt.errors = [{
										instancePath: t + "/fit_reasons",
										schemaPath: "#/properties/fit_reasons/type",
										keyword: "type",
										params: { type: "array" }
									}], !1;
								}
								var d = r === c;
							} else var d = !0;
							if (d) {
								if (e.listing !== void 0 && n.call(e, "listing")) {
									let r = e.listing, i = c;
									if (c === i) {
										if (r && typeof r == "object" && !Array.isArray(r)) {
											let i;
											if ((r.state === void 0 || !n.call(r, "state")) && (i = "state")) return Dt.errors = [{
												instancePath: t + "/listing",
												schemaPath: "#/properties/listing/required",
												keyword: "required",
												params: { missingProperty: i }
											}], !1;
											if (r.state !== void 0 && n.call(r, "state")) {
												let e = c;
												if (typeof r.state != "string") return Dt.errors = [{
													instancePath: t + "/listing/state",
													schemaPath: "#/properties/listing/properties/state/type",
													keyword: "type",
													params: { type: "string" }
												}], !1;
												var f = e === c;
											} else var f = !0;
											if (f) {
												let n = r.state;
												if (typeof n == "string") {
													if (n === "current") {
														T(r, {
															instancePath: t + "/listing",
															parentData: e,
															parentDataProperty: "listing",
															rootData: a,
															dynamicAnchors: o
														}) || (s = s === null ? T.errors : s.concat(T.errors), c = s.length);
														var p = !0;
													} else if (n === "historical") T(r, {
														instancePath: t + "/listing",
														parentData: e,
														parentDataProperty: "listing",
														rootData: a,
														dynamicAnchors: o
													}) || (s = s === null ? T.errors : s.concat(T.errors), c = s.length), p !== !0 && (p = !0);
													else if (n === "missing") Se(r, {
														instancePath: t + "/listing",
														parentData: e,
														parentDataProperty: "listing",
														rootData: a,
														dynamicAnchors: o
													}) || (s = s === null ? Se.errors : s.concat(Se.errors), c = s.length), p !== !0 && (p = !0);
													else if (n === "error") we(r, {
														instancePath: t + "/listing",
														parentData: e,
														parentDataProperty: "listing",
														rootData: a,
														dynamicAnchors: o
													}) || (s = s === null ? we.errors : s.concat(we.errors), c = s.length), p !== !0 && (p = !0);
													else return Dt.errors = [{
														instancePath: t + "/listing",
														schemaPath: "#/properties/listing/discriminator",
														keyword: "discriminator",
														params: {
															error: "mapping",
															tag: "state",
															tagValue: n
														}
													}], !1;
												} else return Dt.errors = [{
													instancePath: t + "/listing",
													schemaPath: "#/properties/listing/discriminator",
													keyword: "discriminator",
													params: {
														error: "tag",
														tag: "state",
														tagValue: n
													}
												}], !1;
											}
										} else return Dt.errors = [{
											instancePath: t + "/listing",
											schemaPath: "#/properties/listing/type",
											keyword: "type",
											params: { type: "object" }
										}], !1;
									}
									var d = i === c;
								} else var d = !0;
								if (d) {
									if (e.selected_ref !== void 0 && n.call(e, "selected_ref")) {
										let n = c;
										l(e.selected_ref, {
											instancePath: t + "/selected_ref",
											parentData: e,
											parentDataProperty: "selected_ref",
											rootData: a,
											dynamicAnchors: o
										}) || (s = s === null ? l.errors : s.concat(l.errors), c = s.length);
										var d = n === c;
									} else var d = !0;
									if (d) {
										if (e.unresolved_questions !== void 0 && n.call(e, "unresolved_questions")) {
											let n = e.unresolved_questions, r = c;
											if (c === r) {
												if (Array.isArray(n)) {
													if (n.length > 12) return Dt.errors = [{
														instancePath: t + "/unresolved_questions",
														schemaPath: "#/properties/unresolved_questions/maxItems",
														keyword: "maxItems",
														params: { limit: 12 }
													}], !1;
													{
														let e = n.length;
														for (let r = 0; r < e; r++) {
															let e = c;
															if (Et(n[r], {
																instancePath: t + "/unresolved_questions/" + r,
																parentData: n,
																parentDataProperty: r,
																rootData: a,
																dynamicAnchors: o
															}) || (s = s === null ? Et.errors : s.concat(Et.errors), c = s.length), e !== c) break;
														}
													}
												} else return Dt.errors = [{
													instancePath: t + "/unresolved_questions",
													schemaPath: "#/properties/unresolved_questions/type",
													keyword: "type",
													params: { type: "array" }
												}], !1;
											}
											var d = r === c;
										} else var d = !0;
									}
								}
							}
						}
					}
				}
			} else return Dt.errors = [{
				instancePath: t,
				schemaPath: "#/type",
				keyword: "type",
				params: { type: "object" }
			}], !1;
		}
		return Dt.errors = s, c === 0;
	}
	Dt.evaluated = {
		props: !0,
		dynamicProps: !1,
		dynamicItems: !1
	};
	function Ot(e, { instancePath: t = "", parentData: r, parentDataProperty: i, rootData: a = e, dynamicAnchors: o = {} } = {}) {
		let s = Ot.evaluated;
		if (s.dynamicProps && (s.props = void 0), s.dynamicItems && (s.items = void 0), e && typeof e == "object" && !Array.isArray(e)) {
			let r;
			if ((e.kind === void 0 || !n.call(e, "kind")) && (r = "kind")) return Ot.errors = [{
				instancePath: t,
				schemaPath: "#/required",
				keyword: "required",
				params: { missingProperty: r }
			}], !1;
			for (let n of Object.keys(e)) if (n !== "kind") return Ot.errors = [{
				instancePath: t,
				schemaPath: "#/additionalProperties",
				keyword: "additionalProperties",
				params: { additionalProperty: n }
			}], !1;
			if (e.kind !== void 0 && n.call(e, "kind")) {
				let n = e.kind;
				if (typeof n != "string") return Ot.errors = [{
					instancePath: t + "/kind",
					schemaPath: "#/properties/kind/type",
					keyword: "type",
					params: { type: "string" }
				}], !1;
				if (n !== "none") return Ot.errors = [{
					instancePath: t + "/kind",
					schemaPath: "#/properties/kind/const",
					keyword: "const",
					params: { allowedValue: "none" }
				}], !1;
			}
		} else return Ot.errors = [{
			instancePath: t,
			schemaPath: "#/type",
			keyword: "type",
			params: { type: "object" }
		}], !1;
		return Ot.errors = null, !0;
	}
	Ot.evaluated = {
		props: !0,
		dynamicProps: !1,
		dynamicItems: !1
	};
	var kt = {
		additionalProperties: !1,
		properties: {
			created_revision: {
				maximum: 2147483647,
				minimum: 0,
				title: "Created Revision",
				type: "integer"
			},
			intent_id: {
				pattern: "^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$",
				title: "Intent Id",
				type: "string"
			},
			kind: {
				const: "clarification",
				title: "Kind",
				type: "string"
			},
			purpose: {
				enum: [
					"search_criteria",
					"listing_reference",
					"viewing_details",
					"action_intent"
				],
				title: "Purpose",
				type: "string"
			},
			question: {
				maxLength: 200,
				minLength: 1,
				title: "Question",
				type: "string"
			},
			targets: {
				items: {
					enum: [
						"query",
						"makes",
						"models",
						"trims",
						"years",
						"budget",
						"mileage_km",
						"body_types",
						"fuel_types",
						"transmissions",
						"soft_preferences",
						"selected_ref",
						"appointment",
						"confirmation",
						"preference_scope"
					],
					type: "string"
				},
				maxItems: 12,
				minItems: 1,
				title: "Targets",
				type: "array"
			}
		},
		required: [
			"kind",
			"intent_id",
			"created_revision",
			"purpose",
			"targets",
			"question"
		],
		title: "ClarificationIntent",
		type: "object"
	};
	function W(e, { instancePath: t = "", parentData: r, parentDataProperty: i, rootData: a = e, dynamicAnchors: o = {} } = {}) {
		let s = W.evaluated;
		if (s.dynamicProps && (s.props = void 0), s.dynamicItems && (s.items = void 0), e && typeof e == "object" && !Array.isArray(e)) {
			let r;
			if ((e.kind === void 0 || !n.call(e, "kind")) && (r = "kind") || (e.intent_id === void 0 || !n.call(e, "intent_id")) && (r = "intent_id") || (e.created_revision === void 0 || !n.call(e, "created_revision")) && (r = "created_revision") || (e.purpose === void 0 || !n.call(e, "purpose")) && (r = "purpose") || (e.targets === void 0 || !n.call(e, "targets")) && (r = "targets") || (e.question === void 0 || !n.call(e, "question")) && (r = "question")) return W.errors = [{
				instancePath: t,
				schemaPath: "#/required",
				keyword: "required",
				params: { missingProperty: r }
			}], !1;
			for (let n of Object.keys(e)) if (n !== "created_revision" && n !== "intent_id" && n !== "kind" && n !== "purpose" && n !== "question" && n !== "targets") return W.errors = [{
				instancePath: t,
				schemaPath: "#/additionalProperties",
				keyword: "additionalProperties",
				params: { additionalProperty: n }
			}], !1;
			if (e.created_revision !== void 0 && n.call(e, "created_revision")) {
				let n = e.created_revision;
				if (typeof n != "number" || n % 1 || isNaN(n) || !isFinite(n)) return W.errors = [{
					instancePath: t + "/created_revision",
					schemaPath: "#/properties/created_revision/type",
					keyword: "type",
					params: { type: "integer" }
				}], !1;
				if (typeof n == "number" && isFinite(n)) {
					if (n > 2147483647 || isNaN(n)) return W.errors = [{
						instancePath: t + "/created_revision",
						schemaPath: "#/properties/created_revision/maximum",
						keyword: "maximum",
						params: {
							comparison: "<=",
							limit: 2147483647
						}
					}], !1;
					if (n < 0 || isNaN(n)) return W.errors = [{
						instancePath: t + "/created_revision",
						schemaPath: "#/properties/created_revision/minimum",
						keyword: "minimum",
						params: {
							comparison: ">=",
							limit: 0
						}
					}], !1;
				}
				var c = !0;
			} else var c = !0;
			if (c) {
				if (e.intent_id !== void 0 && n.call(e, "intent_id")) {
					let n = e.intent_id;
					if (typeof n == "string") {
						if (!u.test(n)) return W.errors = [{
							instancePath: t + "/intent_id",
							schemaPath: "#/properties/intent_id/pattern",
							keyword: "pattern",
							params: { pattern: "^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$" }
						}], !1;
					} else return W.errors = [{
						instancePath: t + "/intent_id",
						schemaPath: "#/properties/intent_id/type",
						keyword: "type",
						params: { type: "string" }
					}], !1;
					var c = !0;
				} else var c = !0;
				if (c) {
					if (e.kind !== void 0 && n.call(e, "kind")) {
						let n = e.kind;
						if (typeof n != "string") return W.errors = [{
							instancePath: t + "/kind",
							schemaPath: "#/properties/kind/type",
							keyword: "type",
							params: { type: "string" }
						}], !1;
						if (n !== "clarification") return W.errors = [{
							instancePath: t + "/kind",
							schemaPath: "#/properties/kind/const",
							keyword: "const",
							params: { allowedValue: "clarification" }
						}], !1;
						var c = !0;
					} else var c = !0;
					if (c) {
						if (e.purpose !== void 0 && n.call(e, "purpose")) {
							let n = e.purpose;
							if (typeof n != "string") return W.errors = [{
								instancePath: t + "/purpose",
								schemaPath: "#/properties/purpose/type",
								keyword: "type",
								params: { type: "string" }
							}], !1;
							if (n !== "search_criteria" && n !== "listing_reference" && n !== "viewing_details" && n !== "action_intent") return W.errors = [{
								instancePath: t + "/purpose",
								schemaPath: "#/properties/purpose/enum",
								keyword: "enum",
								params: { allowedValues: kt.properties.purpose.enum }
							}], !1;
							var c = !0;
						} else var c = !0;
						if (c) {
							if (e.question !== void 0 && n.call(e, "question")) {
								let n = e.question;
								if (typeof n == "string") {
									if (h(n) > 200) return W.errors = [{
										instancePath: t + "/question",
										schemaPath: "#/properties/question/maxLength",
										keyword: "maxLength",
										params: { limit: 200 }
									}], !1;
									if (h(n) < 1) return W.errors = [{
										instancePath: t + "/question",
										schemaPath: "#/properties/question/minLength",
										keyword: "minLength",
										params: { limit: 1 }
									}], !1;
								} else return W.errors = [{
									instancePath: t + "/question",
									schemaPath: "#/properties/question/type",
									keyword: "type",
									params: { type: "string" }
								}], !1;
								var c = !0;
							} else var c = !0;
							if (c) {
								if (e.targets !== void 0 && n.call(e, "targets")) {
									let n = e.targets;
									if (Array.isArray(n)) {
										if (n.length > 12) return W.errors = [{
											instancePath: t + "/targets",
											schemaPath: "#/properties/targets/maxItems",
											keyword: "maxItems",
											params: { limit: 12 }
										}], !1;
										if (n.length < 1) return W.errors = [{
											instancePath: t + "/targets",
											schemaPath: "#/properties/targets/minItems",
											keyword: "minItems",
											params: { limit: 1 }
										}], !1;
										{
											let e = n.length;
											for (let r = 0; r < e; r++) {
												let e = n[r];
												if (typeof e != "string") return W.errors = [{
													instancePath: t + "/targets/" + r,
													schemaPath: "#/properties/targets/items/type",
													keyword: "type",
													params: { type: "string" }
												}], !1;
												if (e !== "query" && e !== "makes" && e !== "models" && e !== "trims" && e !== "years" && e !== "budget" && e !== "mileage_km" && e !== "body_types" && e !== "fuel_types" && e !== "transmissions" && e !== "soft_preferences" && e !== "selected_ref" && e !== "appointment" && e !== "confirmation" && e !== "preference_scope") return W.errors = [{
													instancePath: t + "/targets/" + r,
													schemaPath: "#/properties/targets/items/enum",
													keyword: "enum",
													params: { allowedValues: kt.properties.targets.items.enum }
												}], !1;
											}
										}
									} else return W.errors = [{
										instancePath: t + "/targets",
										schemaPath: "#/properties/targets/type",
										keyword: "type",
										params: { type: "array" }
									}], !1;
									var c = !0;
								} else var c = !0;
							}
						}
					}
				}
			}
		} else return W.errors = [{
			instancePath: t,
			schemaPath: "#/type",
			keyword: "type",
			params: { type: "object" }
		}], !1;
		return W.errors = null, !0;
	}
	W.evaluated = {
		props: !0,
		dynamicProps: !1,
		dynamicItems: !1
	};
	function At(e, { instancePath: t = "", parentData: r, parentDataProperty: i, rootData: a = e, dynamicAnchors: o = {} } = {}) {
		let s = At.evaluated;
		if (s.dynamicProps && (s.props = void 0), s.dynamicItems && (s.items = void 0), e && typeof e == "object" && !Array.isArray(e)) {
			let r;
			if ((e.kind === void 0 || !n.call(e, "kind")) && (r = "kind") || (e.draft_id === void 0 || !n.call(e, "draft_id")) && (r = "draft_id") || (e.review_id === void 0 || !n.call(e, "review_id")) && (r = "review_id") || (e.operation_key === void 0 || !n.call(e, "operation_key")) && (r = "operation_key")) return At.errors = [{
				instancePath: t,
				schemaPath: "#/required",
				keyword: "required",
				params: { missingProperty: r }
			}], !1;
			for (let n of Object.keys(e)) if (n !== "draft_id" && n !== "kind" && n !== "operation_key" && n !== "review_id") return At.errors = [{
				instancePath: t,
				schemaPath: "#/additionalProperties",
				keyword: "additionalProperties",
				params: { additionalProperty: n }
			}], !1;
			if (e.draft_id !== void 0 && n.call(e, "draft_id")) {
				let n = e.draft_id;
				if (typeof n == "string") {
					if (!u.test(n)) return At.errors = [{
						instancePath: t + "/draft_id",
						schemaPath: "#/properties/draft_id/pattern",
						keyword: "pattern",
						params: { pattern: "^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$" }
					}], !1;
				} else return At.errors = [{
					instancePath: t + "/draft_id",
					schemaPath: "#/properties/draft_id/type",
					keyword: "type",
					params: { type: "string" }
				}], !1;
				var c = !0;
			} else var c = !0;
			if (c) {
				if (e.kind !== void 0 && n.call(e, "kind")) {
					let n = e.kind;
					if (typeof n != "string") return At.errors = [{
						instancePath: t + "/kind",
						schemaPath: "#/properties/kind/type",
						keyword: "type",
						params: { type: "string" }
					}], !1;
					if (n !== "viewing_review") return At.errors = [{
						instancePath: t + "/kind",
						schemaPath: "#/properties/kind/const",
						keyword: "const",
						params: { allowedValue: "viewing_review" }
					}], !1;
					var c = !0;
				} else var c = !0;
				if (c) {
					if (e.operation_key !== void 0 && n.call(e, "operation_key")) {
						let n = e.operation_key;
						if (typeof n == "string") {
							if (!g.test(n)) return At.errors = [{
								instancePath: t + "/operation_key",
								schemaPath: "#/properties/operation_key/pattern",
								keyword: "pattern",
								params: { pattern: "^[A-Za-z0-9_-]{43}$" }
							}], !1;
						} else return At.errors = [{
							instancePath: t + "/operation_key",
							schemaPath: "#/properties/operation_key/type",
							keyword: "type",
							params: { type: "string" }
						}], !1;
						var c = !0;
					} else var c = !0;
					if (c) {
						if (e.review_id !== void 0 && n.call(e, "review_id")) {
							let n = e.review_id;
							if (typeof n == "string") {
								if (!u.test(n)) return At.errors = [{
									instancePath: t + "/review_id",
									schemaPath: "#/properties/review_id/pattern",
									keyword: "pattern",
									params: { pattern: "^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$" }
								}], !1;
							} else return At.errors = [{
								instancePath: t + "/review_id",
								schemaPath: "#/properties/review_id/type",
								keyword: "type",
								params: { type: "string" }
							}], !1;
							var c = !0;
						} else var c = !0;
					}
				}
			}
		} else return At.errors = [{
			instancePath: t,
			schemaPath: "#/type",
			keyword: "type",
			params: { type: "object" }
		}], !1;
		return At.errors = null, !0;
	}
	At.evaluated = {
		props: !0,
		dynamicProps: !1,
		dynamicItems: !1
	};
	function jt(e, { instancePath: t = "", parentData: r, parentDataProperty: i, rootData: a = e, dynamicAnchors: o = {} } = {}) {
		let s = jt.evaluated;
		if (s.dynamicProps && (s.props = void 0), s.dynamicItems && (s.items = void 0), e && typeof e == "object" && !Array.isArray(e)) {
			let r;
			if ((e.kind === void 0 || !n.call(e, "kind")) && (r = "kind") || (e.draft_id === void 0 || !n.call(e, "draft_id")) && (r = "draft_id") || (e.operation_key === void 0 || !n.call(e, "operation_key")) && (r = "operation_key") || (e.submitted_store_generation === void 0 || !n.call(e, "submitted_store_generation")) && (r = "submitted_store_generation")) return jt.errors = [{
				instancePath: t,
				schemaPath: "#/required",
				keyword: "required",
				params: { missingProperty: r }
			}], !1;
			for (let n of Object.keys(e)) if (n !== "draft_id" && n !== "kind" && n !== "operation_key" && n !== "submitted_store_generation") return jt.errors = [{
				instancePath: t,
				schemaPath: "#/additionalProperties",
				keyword: "additionalProperties",
				params: { additionalProperty: n }
			}], !1;
			if (e.draft_id !== void 0 && n.call(e, "draft_id")) {
				let n = e.draft_id;
				if (typeof n == "string") {
					if (!u.test(n)) return jt.errors = [{
						instancePath: t + "/draft_id",
						schemaPath: "#/properties/draft_id/pattern",
						keyword: "pattern",
						params: { pattern: "^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$" }
					}], !1;
				} else return jt.errors = [{
					instancePath: t + "/draft_id",
					schemaPath: "#/properties/draft_id/type",
					keyword: "type",
					params: { type: "string" }
				}], !1;
				var c = !0;
			} else var c = !0;
			if (c) {
				if (e.kind !== void 0 && n.call(e, "kind")) {
					let n = e.kind;
					if (typeof n != "string") return jt.errors = [{
						instancePath: t + "/kind",
						schemaPath: "#/properties/kind/type",
						keyword: "type",
						params: { type: "string" }
					}], !1;
					if (n !== "operation_unresolved") return jt.errors = [{
						instancePath: t + "/kind",
						schemaPath: "#/properties/kind/const",
						keyword: "const",
						params: { allowedValue: "operation_unresolved" }
					}], !1;
					var c = !0;
				} else var c = !0;
				if (c) {
					if (e.operation_key !== void 0 && n.call(e, "operation_key")) {
						let n = e.operation_key;
						if (typeof n == "string") {
							if (!g.test(n)) return jt.errors = [{
								instancePath: t + "/operation_key",
								schemaPath: "#/properties/operation_key/pattern",
								keyword: "pattern",
								params: { pattern: "^[A-Za-z0-9_-]{43}$" }
							}], !1;
						} else return jt.errors = [{
							instancePath: t + "/operation_key",
							schemaPath: "#/properties/operation_key/type",
							keyword: "type",
							params: { type: "string" }
						}], !1;
						var c = !0;
					} else var c = !0;
					if (c) {
						if (e.submitted_store_generation !== void 0 && n.call(e, "submitted_store_generation")) {
							let n = e.submitted_store_generation;
							if (typeof n == "string") {
								if (!u.test(n)) return jt.errors = [{
									instancePath: t + "/submitted_store_generation",
									schemaPath: "#/properties/submitted_store_generation/pattern",
									keyword: "pattern",
									params: { pattern: "^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$" }
								}], !1;
							} else return jt.errors = [{
								instancePath: t + "/submitted_store_generation",
								schemaPath: "#/properties/submitted_store_generation/type",
								keyword: "type",
								params: { type: "string" }
							}], !1;
							var c = !0;
						} else var c = !0;
					}
				}
			}
		} else return jt.errors = [{
			instancePath: t,
			schemaPath: "#/type",
			keyword: "type",
			params: { type: "object" }
		}], !1;
		return jt.errors = null, !0;
	}
	jt.evaluated = {
		props: !0,
		dynamicProps: !1,
		dynamicItems: !1
	};
	var Mt = {
		additionalProperties: !1,
		properties: {
			applied_criteria: { $ref: "urn:car-shopping-assistant:contract:1#/$defs/SearchCriteria" },
			client_request_id: {
				pattern: "^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$",
				title: "Client Request Id",
				type: "string"
			},
			constraints_relaxed: {
				const: !1,
				default: !1,
				title: "Constraints Relaxed",
				type: "boolean"
			},
			evidence_coverage: {
				items: { $ref: "urn:car-shopping-assistant:contract:1#/$defs/ConstraintCoverage" },
				maxItems: 24,
				title: "Evidence Coverage",
				type: "array"
			},
			items: {
				items: { $ref: "urn:car-shopping-assistant:contract:1#/$defs/ListingSummary" },
				maxItems: 50,
				title: "Items",
				type: "array"
			},
			next_cursor: {
				anyOf: [{
					maxLength: 2048,
					type: "string"
				}, { type: "null" }],
				title: "Next Cursor"
			},
			presentation: { $ref: "urn:car-shopping-assistant:contract:1#/$defs/PresentationProof" },
			state: {
				enum: ["matches", "no_supported_matches"],
				title: "State",
				type: "string"
			},
			supported_total: {
				minimum: 0,
				title: "Supported Total",
				type: "integer"
			},
			unsupported_constraints: {
				default: [],
				items: {
					maxLength: 200,
					minLength: 1,
					type: "string"
				},
				maxItems: 24,
				title: "Unsupported Constraints",
				type: "array"
			}
		},
		required: [
			"client_request_id",
			"state",
			"items",
			"supported_total",
			"next_cursor",
			"presentation",
			"applied_criteria",
			"evidence_coverage"
		],
		title: "SearchResult",
		type: "object"
	}, Nt = {
		additionalProperties: !1,
		properties: {
			attribute: {
				enum: [
					"make",
					"model",
					"trim",
					"year",
					"cash_price",
					"mileage_km",
					"body_type",
					"fuel_type",
					"transmission"
				],
				title: "Attribute",
				type: "string"
			},
			excluded_conflicting: {
				minimum: 0,
				title: "Excluded Conflicting",
				type: "integer"
			},
			excluded_unknown: {
				minimum: 0,
				title: "Excluded Unknown",
				type: "integer"
			},
			excluded_unsupported_qualifier: {
				minimum: 0,
				title: "Excluded Unsupported Qualifier",
				type: "integer"
			},
			source_total: {
				minimum: 0,
				title: "Source Total",
				type: "integer"
			},
			supported: {
				minimum: 0,
				title: "Supported",
				type: "integer"
			}
		},
		required: [
			"attribute",
			"source_total",
			"supported",
			"excluded_unknown",
			"excluded_conflicting",
			"excluded_unsupported_qualifier"
		],
		title: "ConstraintCoverage",
		type: "object"
	};
	function Pt(e, { instancePath: t = "", parentData: r, parentDataProperty: i, rootData: a = e, dynamicAnchors: o = {} } = {}) {
		let s = Pt.evaluated;
		if (s.dynamicProps && (s.props = void 0), s.dynamicItems && (s.items = void 0), e && typeof e == "object" && !Array.isArray(e)) {
			let r;
			if ((e.attribute === void 0 || !n.call(e, "attribute")) && (r = "attribute") || (e.source_total === void 0 || !n.call(e, "source_total")) && (r = "source_total") || (e.supported === void 0 || !n.call(e, "supported")) && (r = "supported") || (e.excluded_unknown === void 0 || !n.call(e, "excluded_unknown")) && (r = "excluded_unknown") || (e.excluded_conflicting === void 0 || !n.call(e, "excluded_conflicting")) && (r = "excluded_conflicting") || (e.excluded_unsupported_qualifier === void 0 || !n.call(e, "excluded_unsupported_qualifier")) && (r = "excluded_unsupported_qualifier")) return Pt.errors = [{
				instancePath: t,
				schemaPath: "#/required",
				keyword: "required",
				params: { missingProperty: r }
			}], !1;
			for (let n of Object.keys(e)) if (n !== "attribute" && n !== "excluded_conflicting" && n !== "excluded_unknown" && n !== "excluded_unsupported_qualifier" && n !== "source_total" && n !== "supported") return Pt.errors = [{
				instancePath: t,
				schemaPath: "#/additionalProperties",
				keyword: "additionalProperties",
				params: { additionalProperty: n }
			}], !1;
			if (e.attribute !== void 0 && n.call(e, "attribute")) {
				let n = e.attribute;
				if (typeof n != "string") return Pt.errors = [{
					instancePath: t + "/attribute",
					schemaPath: "#/properties/attribute/type",
					keyword: "type",
					params: { type: "string" }
				}], !1;
				if (n !== "make" && n !== "model" && n !== "trim" && n !== "year" && n !== "cash_price" && n !== "mileage_km" && n !== "body_type" && n !== "fuel_type" && n !== "transmission") return Pt.errors = [{
					instancePath: t + "/attribute",
					schemaPath: "#/properties/attribute/enum",
					keyword: "enum",
					params: { allowedValues: Nt.properties.attribute.enum }
				}], !1;
				var c = !0;
			} else var c = !0;
			if (c) {
				if (e.excluded_conflicting !== void 0 && n.call(e, "excluded_conflicting")) {
					let n = e.excluded_conflicting;
					if (typeof n != "number" || n % 1 || isNaN(n) || !isFinite(n)) return Pt.errors = [{
						instancePath: t + "/excluded_conflicting",
						schemaPath: "#/properties/excluded_conflicting/type",
						keyword: "type",
						params: { type: "integer" }
					}], !1;
					if (typeof n == "number" && isFinite(n) && (n < 0 || isNaN(n))) return Pt.errors = [{
						instancePath: t + "/excluded_conflicting",
						schemaPath: "#/properties/excluded_conflicting/minimum",
						keyword: "minimum",
						params: {
							comparison: ">=",
							limit: 0
						}
					}], !1;
					var c = !0;
				} else var c = !0;
				if (c) {
					if (e.excluded_unknown !== void 0 && n.call(e, "excluded_unknown")) {
						let n = e.excluded_unknown;
						if (typeof n != "number" || n % 1 || isNaN(n) || !isFinite(n)) return Pt.errors = [{
							instancePath: t + "/excluded_unknown",
							schemaPath: "#/properties/excluded_unknown/type",
							keyword: "type",
							params: { type: "integer" }
						}], !1;
						if (typeof n == "number" && isFinite(n) && (n < 0 || isNaN(n))) return Pt.errors = [{
							instancePath: t + "/excluded_unknown",
							schemaPath: "#/properties/excluded_unknown/minimum",
							keyword: "minimum",
							params: {
								comparison: ">=",
								limit: 0
							}
						}], !1;
						var c = !0;
					} else var c = !0;
					if (c) {
						if (e.excluded_unsupported_qualifier !== void 0 && n.call(e, "excluded_unsupported_qualifier")) {
							let n = e.excluded_unsupported_qualifier;
							if (typeof n != "number" || n % 1 || isNaN(n) || !isFinite(n)) return Pt.errors = [{
								instancePath: t + "/excluded_unsupported_qualifier",
								schemaPath: "#/properties/excluded_unsupported_qualifier/type",
								keyword: "type",
								params: { type: "integer" }
							}], !1;
							if (typeof n == "number" && isFinite(n) && (n < 0 || isNaN(n))) return Pt.errors = [{
								instancePath: t + "/excluded_unsupported_qualifier",
								schemaPath: "#/properties/excluded_unsupported_qualifier/minimum",
								keyword: "minimum",
								params: {
									comparison: ">=",
									limit: 0
								}
							}], !1;
							var c = !0;
						} else var c = !0;
						if (c) {
							if (e.source_total !== void 0 && n.call(e, "source_total")) {
								let n = e.source_total;
								if (typeof n != "number" || n % 1 || isNaN(n) || !isFinite(n)) return Pt.errors = [{
									instancePath: t + "/source_total",
									schemaPath: "#/properties/source_total/type",
									keyword: "type",
									params: { type: "integer" }
								}], !1;
								if (typeof n == "number" && isFinite(n) && (n < 0 || isNaN(n))) return Pt.errors = [{
									instancePath: t + "/source_total",
									schemaPath: "#/properties/source_total/minimum",
									keyword: "minimum",
									params: {
										comparison: ">=",
										limit: 0
									}
								}], !1;
								var c = !0;
							} else var c = !0;
							if (c) {
								if (e.supported !== void 0 && n.call(e, "supported")) {
									let n = e.supported;
									if (typeof n != "number" || n % 1 || isNaN(n) || !isFinite(n)) return Pt.errors = [{
										instancePath: t + "/supported",
										schemaPath: "#/properties/supported/type",
										keyword: "type",
										params: { type: "integer" }
									}], !1;
									if (typeof n == "number" && isFinite(n) && (n < 0 || isNaN(n))) return Pt.errors = [{
										instancePath: t + "/supported",
										schemaPath: "#/properties/supported/minimum",
										keyword: "minimum",
										params: {
											comparison: ">=",
											limit: 0
										}
									}], !1;
									var c = !0;
								} else var c = !0;
							}
						}
					}
				}
			}
		} else return Pt.errors = [{
			instancePath: t,
			schemaPath: "#/type",
			keyword: "type",
			params: { type: "object" }
		}], !1;
		return Pt.errors = null, !0;
	}
	Pt.evaluated = {
		props: !0,
		dynamicProps: !1,
		dynamicItems: !1
	};
	function G(e, { instancePath: t = "", parentData: r, parentDataProperty: a, rootData: o = e, dynamicAnchors: c = {} } = {}) {
		let d = null, f = 0, p = G.evaluated;
		if (p.dynamicProps && (p.props = void 0), p.dynamicItems && (p.items = void 0), f === 0) {
			if (e && typeof e == "object" && !Array.isArray(e)) {
				let r;
				if ((e.presentation_id === void 0 || !n.call(e, "presentation_id")) && (r = "presentation_id") || (e.snapshot_id === void 0 || !n.call(e, "snapshot_id")) && (r = "snapshot_id") || (e.ordered_refs === void 0 || !n.call(e, "ordered_refs")) && (r = "ordered_refs") || (e.criteria_hash === void 0 || !n.call(e, "criteria_hash")) && (r = "criteria_hash") || (e.issued_at === void 0 || !n.call(e, "issued_at")) && (r = "issued_at") || (e.expires_at === void 0 || !n.call(e, "expires_at")) && (r = "expires_at") || (e.signature === void 0 || !n.call(e, "signature")) && (r = "signature")) return G.errors = [{
					instancePath: t,
					schemaPath: "#/required",
					keyword: "required",
					params: { missingProperty: r }
				}], !1;
				{
					let r = f;
					for (let n of Object.keys(e)) if (n !== "criteria_hash" && n !== "expires_at" && n !== "issued_at" && n !== "ordered_refs" && n !== "presentation_id" && n !== "signature" && n !== "snapshot_id") return G.errors = [{
						instancePath: t,
						schemaPath: "#/additionalProperties",
						keyword: "additionalProperties",
						params: { additionalProperty: n }
					}], !1;
					if (r === f) {
						if (e.criteria_hash !== void 0 && n.call(e, "criteria_hash")) {
							let n = e.criteria_hash, r = f;
							if (f === r) {
								if (typeof n == "string") {
									if (!s.test(n)) return G.errors = [{
										instancePath: t + "/criteria_hash",
										schemaPath: "#/properties/criteria_hash/pattern",
										keyword: "pattern",
										params: { pattern: "^[0-9a-f]{64}$" }
									}], !1;
								} else return G.errors = [{
									instancePath: t + "/criteria_hash",
									schemaPath: "#/properties/criteria_hash/type",
									keyword: "type",
									params: { type: "string" }
								}], !1;
							}
							var m = r === f;
						} else var m = !0;
						if (m) {
							if (e.expires_at !== void 0 && n.call(e, "expires_at")) {
								let n = e.expires_at, r = f;
								if (f === r) {
									if (typeof n == "string") {
										if (!i.test(n)) return G.errors = [{
											instancePath: t + "/expires_at",
											schemaPath: "#/properties/expires_at/pattern",
											keyword: "pattern",
											params: { pattern: "^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}(?:\\.\\d{1,6})?Z$" }
										}], !1;
									} else return G.errors = [{
										instancePath: t + "/expires_at",
										schemaPath: "#/properties/expires_at/type",
										keyword: "type",
										params: { type: "string" }
									}], !1;
								}
								var m = r === f;
							} else var m = !0;
							if (m) {
								if (e.issued_at !== void 0 && n.call(e, "issued_at")) {
									let n = e.issued_at, r = f;
									if (f === r) {
										if (typeof n == "string") {
											if (!i.test(n)) return G.errors = [{
												instancePath: t + "/issued_at",
												schemaPath: "#/properties/issued_at/pattern",
												keyword: "pattern",
												params: { pattern: "^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}(?:\\.\\d{1,6})?Z$" }
											}], !1;
										} else return G.errors = [{
											instancePath: t + "/issued_at",
											schemaPath: "#/properties/issued_at/type",
											keyword: "type",
											params: { type: "string" }
										}], !1;
									}
									var m = r === f;
								} else var m = !0;
								if (m) {
									if (e.ordered_refs !== void 0 && n.call(e, "ordered_refs")) {
										let n = e.ordered_refs, r = f;
										if (f === r) {
											if (Array.isArray(n)) {
												if (n.length > 50) return G.errors = [{
													instancePath: t + "/ordered_refs",
													schemaPath: "#/properties/ordered_refs/maxItems",
													keyword: "maxItems",
													params: { limit: 50 }
												}], !1;
												{
													let e = n.length;
													for (let r = 0; r < e; r++) {
														let e = f;
														if (l(n[r], {
															instancePath: t + "/ordered_refs/" + r,
															parentData: n,
															parentDataProperty: r,
															rootData: o,
															dynamicAnchors: c
														}) || (d = d === null ? l.errors : d.concat(l.errors), f = d.length), e !== f) break;
													}
												}
											} else return G.errors = [{
												instancePath: t + "/ordered_refs",
												schemaPath: "#/properties/ordered_refs/type",
												keyword: "type",
												params: { type: "array" }
											}], !1;
										}
										var m = r === f;
									} else var m = !0;
									if (m) {
										if (e.presentation_id !== void 0 && n.call(e, "presentation_id")) {
											let n = e.presentation_id, r = f;
											if (f === r) {
												if (typeof n == "string") {
													if (!u.test(n)) return G.errors = [{
														instancePath: t + "/presentation_id",
														schemaPath: "#/properties/presentation_id/pattern",
														keyword: "pattern",
														params: { pattern: "^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$" }
													}], !1;
												} else return G.errors = [{
													instancePath: t + "/presentation_id",
													schemaPath: "#/properties/presentation_id/type",
													keyword: "type",
													params: { type: "string" }
												}], !1;
											}
											var m = r === f;
										} else var m = !0;
										if (m) {
											if (e.signature !== void 0 && n.call(e, "signature")) {
												let n = e.signature, r = f;
												if (f === r) {
													if (typeof n == "string") {
														if (!g.test(n)) return G.errors = [{
															instancePath: t + "/signature",
															schemaPath: "#/properties/signature/pattern",
															keyword: "pattern",
															params: { pattern: "^[A-Za-z0-9_-]{43}$" }
														}], !1;
													} else return G.errors = [{
														instancePath: t + "/signature",
														schemaPath: "#/properties/signature/type",
														keyword: "type",
														params: { type: "string" }
													}], !1;
												}
												var m = r === f;
											} else var m = !0;
											if (m) {
												if (e.snapshot_id !== void 0 && n.call(e, "snapshot_id")) {
													let n = e.snapshot_id, r = f;
													if (f === r) {
														if (typeof n == "string") {
															if (!s.test(n)) return G.errors = [{
																instancePath: t + "/snapshot_id",
																schemaPath: "#/properties/snapshot_id/pattern",
																keyword: "pattern",
																params: { pattern: "^[0-9a-f]{64}$" }
															}], !1;
														} else return G.errors = [{
															instancePath: t + "/snapshot_id",
															schemaPath: "#/properties/snapshot_id/type",
															keyword: "type",
															params: { type: "string" }
														}], !1;
													}
													var m = r === f;
												} else var m = !0;
											}
										}
									}
								}
							}
						}
					}
				}
			} else return G.errors = [{
				instancePath: t,
				schemaPath: "#/type",
				keyword: "type",
				params: { type: "object" }
			}], !1;
		}
		return G.errors = d, f === 0;
	}
	G.evaluated = {
		props: !0,
		dynamicProps: !1,
		dynamicItems: !1
	};
	function K(e, { instancePath: t = "", parentData: r, parentDataProperty: i, rootData: a = e, dynamicAnchors: o = {} } = {}) {
		let s = null, c = 0, l = K.evaluated;
		if (l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0) {
			if (e && typeof e == "object" && !Array.isArray(e)) {
				let r;
				if ((e.client_request_id === void 0 || !n.call(e, "client_request_id")) && (r = "client_request_id") || (e.state === void 0 || !n.call(e, "state")) && (r = "state") || (e.items === void 0 || !n.call(e, "items")) && (r = "items") || (e.supported_total === void 0 || !n.call(e, "supported_total")) && (r = "supported_total") || (e.next_cursor === void 0 || !n.call(e, "next_cursor")) && (r = "next_cursor") || (e.presentation === void 0 || !n.call(e, "presentation")) && (r = "presentation") || (e.applied_criteria === void 0 || !n.call(e, "applied_criteria")) && (r = "applied_criteria") || (e.evidence_coverage === void 0 || !n.call(e, "evidence_coverage")) && (r = "evidence_coverage")) return K.errors = [{
					instancePath: t,
					schemaPath: "#/required",
					keyword: "required",
					params: { missingProperty: r }
				}], !1;
				{
					let r = c;
					for (let r of Object.keys(e)) if (!n.call(Mt.properties, r)) return K.errors = [{
						instancePath: t,
						schemaPath: "#/additionalProperties",
						keyword: "additionalProperties",
						params: { additionalProperty: r }
					}], !1;
					if (r === c) {
						if (e.applied_criteria !== void 0 && n.call(e, "applied_criteria")) {
							let n = c;
							Ct(e.applied_criteria, {
								instancePath: t + "/applied_criteria",
								parentData: e,
								parentDataProperty: "applied_criteria",
								rootData: a,
								dynamicAnchors: o
							}) || (s = s === null ? Ct.errors : s.concat(Ct.errors), c = s.length);
							var d = n === c;
						} else var d = !0;
						if (d) {
							if (e.client_request_id !== void 0 && n.call(e, "client_request_id")) {
								let n = e.client_request_id, r = c;
								if (c === r) {
									if (typeof n == "string") {
										if (!u.test(n)) return K.errors = [{
											instancePath: t + "/client_request_id",
											schemaPath: "#/properties/client_request_id/pattern",
											keyword: "pattern",
											params: { pattern: "^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$" }
										}], !1;
									} else return K.errors = [{
										instancePath: t + "/client_request_id",
										schemaPath: "#/properties/client_request_id/type",
										keyword: "type",
										params: { type: "string" }
									}], !1;
								}
								var d = r === c;
							} else var d = !0;
							if (d) {
								if (e.constraints_relaxed !== void 0 && n.call(e, "constraints_relaxed")) {
									let n = e.constraints_relaxed, r = c;
									if (typeof n != "boolean") return K.errors = [{
										instancePath: t + "/constraints_relaxed",
										schemaPath: "#/properties/constraints_relaxed/type",
										keyword: "type",
										params: { type: "boolean" }
									}], !1;
									if (!1 !== n) return K.errors = [{
										instancePath: t + "/constraints_relaxed",
										schemaPath: "#/properties/constraints_relaxed/const",
										keyword: "const",
										params: { allowedValue: !1 }
									}], !1;
									var d = r === c;
								} else var d = !0;
								if (d) {
									if (e.evidence_coverage !== void 0 && n.call(e, "evidence_coverage")) {
										let n = e.evidence_coverage, r = c;
										if (c === r) {
											if (Array.isArray(n)) {
												if (n.length > 24) return K.errors = [{
													instancePath: t + "/evidence_coverage",
													schemaPath: "#/properties/evidence_coverage/maxItems",
													keyword: "maxItems",
													params: { limit: 24 }
												}], !1;
												{
													let e = n.length;
													for (let r = 0; r < e; r++) {
														let e = c;
														if (Pt(n[r], {
															instancePath: t + "/evidence_coverage/" + r,
															parentData: n,
															parentDataProperty: r,
															rootData: a,
															dynamicAnchors: o
														}) || (s = s === null ? Pt.errors : s.concat(Pt.errors), c = s.length), e !== c) break;
													}
												}
											} else return K.errors = [{
												instancePath: t + "/evidence_coverage",
												schemaPath: "#/properties/evidence_coverage/type",
												keyword: "type",
												params: { type: "array" }
											}], !1;
										}
										var d = r === c;
									} else var d = !0;
									if (d) {
										if (e.items !== void 0 && n.call(e, "items")) {
											let n = e.items, r = c;
											if (c === r) {
												if (Array.isArray(n)) {
													if (n.length > 50) return K.errors = [{
														instancePath: t + "/items",
														schemaPath: "#/properties/items/maxItems",
														keyword: "maxItems",
														params: { limit: 50 }
													}], !1;
													{
														let e = n.length;
														for (let r = 0; r < e; r++) {
															let e = c;
															if (w(n[r], {
																instancePath: t + "/items/" + r,
																parentData: n,
																parentDataProperty: r,
																rootData: a,
																dynamicAnchors: o
															}) || (s = s === null ? w.errors : s.concat(w.errors), c = s.length), e !== c) break;
														}
													}
												} else return K.errors = [{
													instancePath: t + "/items",
													schemaPath: "#/properties/items/type",
													keyword: "type",
													params: { type: "array" }
												}], !1;
											}
											var d = r === c;
										} else var d = !0;
										if (d) {
											if (e.next_cursor !== void 0 && n.call(e, "next_cursor")) {
												let n = e.next_cursor, r = c, i = c, a = !1, o = c;
												if (c === o) {
													if (typeof n == "string") {
														if (h(n) > 2048) {
															let e = {
																instancePath: t + "/next_cursor",
																schemaPath: "#/properties/next_cursor/anyOf/0/maxLength",
																keyword: "maxLength",
																params: { limit: 2048 }
															};
															s === null ? s = [e] : s.push(e), c++;
														}
													} else {
														let e = {
															instancePath: t + "/next_cursor",
															schemaPath: "#/properties/next_cursor/anyOf/0/type",
															keyword: "type",
															params: { type: "string" }
														};
														s === null ? s = [e] : s.push(e), c++;
													}
												}
												var f = o === c;
												a ||= f;
												let l = c;
												if (n !== null) {
													let e = {
														instancePath: t + "/next_cursor",
														schemaPath: "#/properties/next_cursor/anyOf/1/type",
														keyword: "type",
														params: { type: "null" }
													};
													s === null ? s = [e] : s.push(e), c++;
												}
												var f = l === c;
												if (a ||= f, a) c = i, s !== null && (i ? s.length = i : s = null);
												else {
													let e = {
														instancePath: t + "/next_cursor",
														schemaPath: "#/properties/next_cursor/anyOf",
														keyword: "anyOf",
														params: {}
													};
													return s === null ? s = [e] : s.push(e), c++, K.errors = s, !1;
												}
												var d = r === c;
											} else var d = !0;
											if (d) {
												if (e.presentation !== void 0 && n.call(e, "presentation")) {
													let n = c;
													G(e.presentation, {
														instancePath: t + "/presentation",
														parentData: e,
														parentDataProperty: "presentation",
														rootData: a,
														dynamicAnchors: o
													}) || (s = s === null ? G.errors : s.concat(G.errors), c = s.length);
													var d = n === c;
												} else var d = !0;
												if (d) {
													if (e.state !== void 0 && n.call(e, "state")) {
														let n = e.state, r = c;
														if (typeof n != "string") return K.errors = [{
															instancePath: t + "/state",
															schemaPath: "#/properties/state/type",
															keyword: "type",
															params: { type: "string" }
														}], !1;
														if (n !== "matches" && n !== "no_supported_matches") return K.errors = [{
															instancePath: t + "/state",
															schemaPath: "#/properties/state/enum",
															keyword: "enum",
															params: { allowedValues: Mt.properties.state.enum }
														}], !1;
														var d = r === c;
													} else var d = !0;
													if (d) {
														if (e.supported_total !== void 0 && n.call(e, "supported_total")) {
															let n = e.supported_total, r = c;
															if (typeof n != "number" || n % 1 || isNaN(n) || !isFinite(n)) return K.errors = [{
																instancePath: t + "/supported_total",
																schemaPath: "#/properties/supported_total/type",
																keyword: "type",
																params: { type: "integer" }
															}], !1;
															if (c === r && typeof n == "number" && isFinite(n) && (n < 0 || isNaN(n))) return K.errors = [{
																instancePath: t + "/supported_total",
																schemaPath: "#/properties/supported_total/minimum",
																keyword: "minimum",
																params: {
																	comparison: ">=",
																	limit: 0
																}
															}], !1;
															var d = r === c;
														} else var d = !0;
														if (d) {
															if (e.unsupported_constraints !== void 0 && n.call(e, "unsupported_constraints")) {
																let n = e.unsupported_constraints, r = c;
																if (c === r) {
																	if (Array.isArray(n)) {
																		if (n.length > 24) return K.errors = [{
																			instancePath: t + "/unsupported_constraints",
																			schemaPath: "#/properties/unsupported_constraints/maxItems",
																			keyword: "maxItems",
																			params: { limit: 24 }
																		}], !1;
																		{
																			let e = n.length;
																			for (let r = 0; r < e; r++) {
																				let e = n[r], i = c;
																				if (c === i) {
																					if (typeof e == "string") {
																						if (h(e) > 200) return K.errors = [{
																							instancePath: t + "/unsupported_constraints/" + r,
																							schemaPath: "#/properties/unsupported_constraints/items/maxLength",
																							keyword: "maxLength",
																							params: { limit: 200 }
																						}], !1;
																						if (h(e) < 1) return K.errors = [{
																							instancePath: t + "/unsupported_constraints/" + r,
																							schemaPath: "#/properties/unsupported_constraints/items/minLength",
																							keyword: "minLength",
																							params: { limit: 1 }
																						}], !1;
																					} else return K.errors = [{
																						instancePath: t + "/unsupported_constraints/" + r,
																						schemaPath: "#/properties/unsupported_constraints/items/type",
																						keyword: "type",
																						params: { type: "string" }
																					}], !1;
																				}
																				if (i !== c) break;
																			}
																		}
																	} else return K.errors = [{
																		instancePath: t + "/unsupported_constraints",
																		schemaPath: "#/properties/unsupported_constraints/type",
																		keyword: "type",
																		params: { type: "array" }
																	}], !1;
																}
																var d = r === c;
															} else var d = !0;
														}
													}
												}
											}
										}
									}
								}
							}
						}
					}
				}
			} else return K.errors = [{
				instancePath: t,
				schemaPath: "#/type",
				keyword: "type",
				params: { type: "object" }
			}], !1;
		}
		return K.errors = s, c === 0;
	}
	K.evaluated = {
		props: !0,
		dynamicProps: !1,
		dynamicItems: !1
	};
	function q(e, { instancePath: t = "", parentData: r, parentDataProperty: i, rootData: a = e, dynamicAnchors: o = {} } = {}) {
		let s = null, c = 0, l = q.evaluated;
		if (l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0) {
			if (e && typeof e == "object" && !Array.isArray(e)) {
				let r;
				if ((e.client_message_id === void 0 || !n.call(e, "client_message_id")) && (r = "client_message_id") || (e.session_id === void 0 || !n.call(e, "session_id")) && (r = "session_id") || (e.turn_revision === void 0 || !n.call(e, "turn_revision")) && (r = "turn_revision") || (e.current_revision === void 0 || !n.call(e, "current_revision")) && (r = "current_revision") || (e.state === void 0 || !n.call(e, "state")) && (r = "state") || (e.text === void 0 || !n.call(e, "text")) && (r = "text") || (e.pending_intent === void 0 || !n.call(e, "pending_intent")) && (r = "pending_intent") || (e.persistence === void 0 || !n.call(e, "persistence")) && (r = "persistence") || (e.provider_state === void 0 || !n.call(e, "provider_state")) && (r = "provider_state")) return q.errors = [{
					instancePath: t,
					schemaPath: "#/required",
					keyword: "required",
					params: { missingProperty: r }
				}], !1;
				{
					let r = c;
					for (let r of Object.keys(e)) if (!n.call(st.properties, r)) return q.errors = [{
						instancePath: t,
						schemaPath: "#/additionalProperties",
						keyword: "additionalProperties",
						params: { additionalProperty: r }
					}], !1;
					if (r === c) {
						if (e.actions !== void 0 && n.call(e, "actions")) {
							let n = c;
							H(e.actions, {
								instancePath: t + "/actions",
								parentData: e,
								parentDataProperty: "actions",
								rootData: a,
								dynamicAnchors: o
							}) || (s = s === null ? H.errors : s.concat(H.errors), c = s.length);
							var d = n === c;
						} else var d = !0;
						if (d) {
							if (e.client_message_id !== void 0 && n.call(e, "client_message_id")) {
								let n = e.client_message_id, r = c;
								if (c === r) {
									if (typeof n == "string") {
										if (!u.test(n)) return q.errors = [{
											instancePath: t + "/client_message_id",
											schemaPath: "#/properties/client_message_id/pattern",
											keyword: "pattern",
											params: { pattern: "^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$" }
										}], !1;
									} else return q.errors = [{
										instancePath: t + "/client_message_id",
										schemaPath: "#/properties/client_message_id/type",
										keyword: "type",
										params: { type: "string" }
									}], !1;
								}
								var d = r === c;
							} else var d = !0;
							if (d) {
								if (e.comparison !== void 0 && n.call(e, "comparison")) {
									let n = e.comparison, r = c, i = c, l = !1, u = c;
									Je(n, {
										instancePath: t + "/comparison",
										parentData: e,
										parentDataProperty: "comparison",
										rootData: a,
										dynamicAnchors: o
									}) || (s = s === null ? Je.errors : s.concat(Je.errors), c = s.length);
									var f = u === c;
									l ||= f;
									let p = c;
									if (n !== null) {
										let e = {
											instancePath: t + "/comparison",
											schemaPath: "#/properties/comparison/anyOf/1/type",
											keyword: "type",
											params: { type: "null" }
										};
										s === null ? s = [e] : s.push(e), c++;
									}
									var f = p === c;
									if (l ||= f, l) c = i, s !== null && (i ? s.length = i : s = null);
									else {
										let e = {
											instancePath: t + "/comparison",
											schemaPath: "#/properties/comparison/anyOf",
											keyword: "anyOf",
											params: {}
										};
										return s === null ? s = [e] : s.push(e), c++, q.errors = s, !1;
									}
									var d = r === c;
								} else var d = !0;
								if (d) {
									if (e.current_revision !== void 0 && n.call(e, "current_revision")) {
										let n = e.current_revision, r = c;
										if (typeof n != "number" || n % 1 || isNaN(n) || !isFinite(n)) return q.errors = [{
											instancePath: t + "/current_revision",
											schemaPath: "#/properties/current_revision/type",
											keyword: "type",
											params: { type: "integer" }
										}], !1;
										if (c === r && typeof n == "number" && isFinite(n)) {
											if (n > 2147483647 || isNaN(n)) return q.errors = [{
												instancePath: t + "/current_revision",
												schemaPath: "#/properties/current_revision/maximum",
												keyword: "maximum",
												params: {
													comparison: "<=",
													limit: 2147483647
												}
											}], !1;
											if (n < 0 || isNaN(n)) return q.errors = [{
												instancePath: t + "/current_revision",
												schemaPath: "#/properties/current_revision/minimum",
												keyword: "minimum",
												params: {
													comparison: ">=",
													limit: 0
												}
											}], !1;
										}
										var d = r === c;
									} else var d = !0;
									if (d) {
										if (e.evidence !== void 0 && n.call(e, "evidence")) {
											let n = e.evidence, r = c;
											if (c === r) {
												if (Array.isArray(n)) {
													if (n.length > 10) return q.errors = [{
														instancePath: t + "/evidence",
														schemaPath: "#/properties/evidence/maxItems",
														keyword: "maxItems",
														params: { limit: 10 }
													}], !1;
													{
														let e = n.length;
														for (let r = 0; r < e; r++) {
															let e = c;
															if (bt(n[r], {
																instancePath: t + "/evidence/" + r,
																parentData: n,
																parentDataProperty: r,
																rootData: a,
																dynamicAnchors: o
															}) || (s = s === null ? bt.errors : s.concat(bt.errors), c = s.length), e !== c) break;
														}
													}
												} else return q.errors = [{
													instancePath: t + "/evidence",
													schemaPath: "#/properties/evidence/type",
													keyword: "type",
													params: { type: "array" }
												}], !1;
											}
											var d = r === c;
										} else var d = !0;
										if (d) {
											if (e.handoff_summary !== void 0 && n.call(e, "handoff_summary")) {
												let n = e.handoff_summary, r = c, i = c, l = !1, u = c;
												Dt(n, {
													instancePath: t + "/handoff_summary",
													parentData: e,
													parentDataProperty: "handoff_summary",
													rootData: a,
													dynamicAnchors: o
												}) || (s = s === null ? Dt.errors : s.concat(Dt.errors), c = s.length);
												var p = u === c;
												l ||= p;
												let f = c;
												if (n !== null) {
													let e = {
														instancePath: t + "/handoff_summary",
														schemaPath: "#/properties/handoff_summary/anyOf/1/type",
														keyword: "type",
														params: { type: "null" }
													};
													s === null ? s = [e] : s.push(e), c++;
												}
												var p = f === c;
												if (l ||= p, l) c = i, s !== null && (i ? s.length = i : s = null);
												else {
													let e = {
														instancePath: t + "/handoff_summary",
														schemaPath: "#/properties/handoff_summary/anyOf",
														keyword: "anyOf",
														params: {}
													};
													return s === null ? s = [e] : s.push(e), c++, q.errors = s, !1;
												}
												var d = r === c;
											} else var d = !0;
											if (d) {
												if (e.operation !== void 0 && n.call(e, "operation")) {
													let r = e.operation, i = c, l = c, u = !1, f = c;
													if (c === f) {
														if (r && typeof r == "object" && !Array.isArray(r)) {
															let i;
															if ((r.state === void 0 || !n.call(r, "state")) && (i = "state")) {
																let e = {
																	instancePath: t + "/operation",
																	schemaPath: "#/properties/operation/anyOf/0/required",
																	keyword: "required",
																	params: { missingProperty: i }
																};
																s === null ? s = [e] : s.push(e), c++;
															} else {
																if (r.state !== void 0 && n.call(r, "state")) {
																	let e = c;
																	if (typeof r.state != "string") {
																		let e = {
																			instancePath: t + "/operation/state",
																			schemaPath: "#/properties/operation/anyOf/0/properties/state/type",
																			keyword: "type",
																			params: { type: "string" }
																		};
																		s === null ? s = [e] : s.push(e), c++;
																	}
																	var m = e === c;
																} else var m = !0;
																if (m) {
																	let n = r.state;
																	if (typeof n == "string") {
																		if (n === "succeeded") {
																			A(r, {
																				instancePath: t + "/operation",
																				parentData: e,
																				parentDataProperty: "operation",
																				rootData: a,
																				dynamicAnchors: o
																			}) || (s = s === null ? A.errors : s.concat(A.errors), c = s.length);
																			var g = !0;
																		} else if (n === "rejected") j(r, {
																			instancePath: t + "/operation",
																			parentData: e,
																			parentDataProperty: "operation",
																			rootData: a,
																			dynamicAnchors: o
																		}) || (s = s === null ? j.errors : s.concat(j.errors), c = s.length), g !== !0 && (g = !0);
																		else if (n === "not_observed") M(r, {
																			instancePath: t + "/operation",
																			parentData: e,
																			parentDataProperty: "operation",
																			rootData: a,
																			dynamicAnchors: o
																		}) || (s = s === null ? M.errors : s.concat(M.errors), c = s.length), g !== !0 && (g = !0);
																		else if (n === "unresolved_generation") N(r, {
																			instancePath: t + "/operation",
																			parentData: e,
																			parentDataProperty: "operation",
																			rootData: a,
																			dynamicAnchors: o
																		}) || (s = s === null ? N.errors : s.concat(N.errors), c = s.length), g !== !0 && (g = !0);
																		else {
																			let e = {
																				instancePath: t + "/operation",
																				schemaPath: "#/properties/operation/anyOf/0/discriminator",
																				keyword: "discriminator",
																				params: {
																					error: "mapping",
																					tag: "state",
																					tagValue: n
																				}
																			};
																			s === null ? s = [e] : s.push(e), c++;
																		}
																	} else {
																		let e = {
																			instancePath: t + "/operation",
																			schemaPath: "#/properties/operation/anyOf/0/discriminator",
																			keyword: "discriminator",
																			params: {
																				error: "tag",
																				tag: "state",
																				tagValue: n
																			}
																		};
																		s === null ? s = [e] : s.push(e), c++;
																	}
																}
															}
														} else {
															let e = {
																instancePath: t + "/operation",
																schemaPath: "#/properties/operation/anyOf/0/type",
																keyword: "type",
																params: { type: "object" }
															};
															s === null ? s = [e] : s.push(e), c++;
														}
													}
													var _ = f === c;
													u ||= _;
													let p = c;
													if (r !== null) {
														let e = {
															instancePath: t + "/operation",
															schemaPath: "#/properties/operation/anyOf/1/type",
															keyword: "type",
															params: { type: "null" }
														};
														s === null ? s = [e] : s.push(e), c++;
													}
													var _ = p === c;
													if (u ||= _, u) c = l, s !== null && (l ? s.length = l : s = null);
													else {
														let e = {
															instancePath: t + "/operation",
															schemaPath: "#/properties/operation/anyOf",
															keyword: "anyOf",
															params: {}
														};
														return s === null ? s = [e] : s.push(e), c++, q.errors = s, !1;
													}
													var d = i === c;
												} else var d = !0;
												if (d) {
													if (e.pending_intent !== void 0 && n.call(e, "pending_intent")) {
														let r = e.pending_intent, i = c;
														if (c === i) {
															if (r && typeof r == "object" && !Array.isArray(r)) {
																let i;
																if ((r.kind === void 0 || !n.call(r, "kind")) && (i = "kind")) return q.errors = [{
																	instancePath: t + "/pending_intent",
																	schemaPath: "#/properties/pending_intent/required",
																	keyword: "required",
																	params: { missingProperty: i }
																}], !1;
																if (r.kind !== void 0 && n.call(r, "kind")) {
																	let e = c;
																	if (typeof r.kind != "string") return q.errors = [{
																		instancePath: t + "/pending_intent/kind",
																		schemaPath: "#/properties/pending_intent/properties/kind/type",
																		keyword: "type",
																		params: { type: "string" }
																	}], !1;
																	var v = e === c;
																} else var v = !0;
																if (v) {
																	let n = r.kind;
																	if (typeof n == "string") {
																		if (n === "none") {
																			Ot(r, {
																				instancePath: t + "/pending_intent",
																				parentData: e,
																				parentDataProperty: "pending_intent",
																				rootData: a,
																				dynamicAnchors: o
																			}) || (s = s === null ? Ot.errors : s.concat(Ot.errors), c = s.length);
																			var y = !0;
																		} else if (n === "clarification") W(r, {
																			instancePath: t + "/pending_intent",
																			parentData: e,
																			parentDataProperty: "pending_intent",
																			rootData: a,
																			dynamicAnchors: o
																		}) || (s = s === null ? W.errors : s.concat(W.errors), c = s.length), y !== !0 && (y = !0);
																		else if (n === "viewing_review") At(r, {
																			instancePath: t + "/pending_intent",
																			parentData: e,
																			parentDataProperty: "pending_intent",
																			rootData: a,
																			dynamicAnchors: o
																		}) || (s = s === null ? At.errors : s.concat(At.errors), c = s.length), y !== !0 && (y = !0);
																		else if (n === "operation_unresolved") jt(r, {
																			instancePath: t + "/pending_intent",
																			parentData: e,
																			parentDataProperty: "pending_intent",
																			rootData: a,
																			dynamicAnchors: o
																		}) || (s = s === null ? jt.errors : s.concat(jt.errors), c = s.length), y !== !0 && (y = !0);
																		else return q.errors = [{
																			instancePath: t + "/pending_intent",
																			schemaPath: "#/properties/pending_intent/discriminator",
																			keyword: "discriminator",
																			params: {
																				error: "mapping",
																				tag: "kind",
																				tagValue: n
																			}
																		}], !1;
																	} else return q.errors = [{
																		instancePath: t + "/pending_intent",
																		schemaPath: "#/properties/pending_intent/discriminator",
																		keyword: "discriminator",
																		params: {
																			error: "tag",
																			tag: "kind",
																			tagValue: n
																		}
																	}], !1;
																}
															} else return q.errors = [{
																instancePath: t + "/pending_intent",
																schemaPath: "#/properties/pending_intent/type",
																keyword: "type",
																params: { type: "object" }
															}], !1;
														}
														var d = i === c;
													} else var d = !0;
													if (d) {
														if (e.persistence !== void 0 && n.call(e, "persistence")) {
															let n = e.persistence, r = c;
															if (typeof n != "string") return q.errors = [{
																instancePath: t + "/persistence",
																schemaPath: "#/properties/persistence/type",
																keyword: "type",
																params: { type: "string" }
															}], !1;
															if (n !== "saved" && n !== "not_saved") return q.errors = [{
																instancePath: t + "/persistence",
																schemaPath: "#/properties/persistence/enum",
																keyword: "enum",
																params: { allowedValues: st.properties.persistence.enum }
															}], !1;
															var d = r === c;
														} else var d = !0;
														if (d) {
															if (e.provider_state !== void 0 && n.call(e, "provider_state")) {
																let n = e.provider_state, r = c;
																if (typeof n != "string") return q.errors = [{
																	instancePath: t + "/provider_state",
																	schemaPath: "#/properties/provider_state/type",
																	keyword: "type",
																	params: { type: "string" }
																}], !1;
																if (n !== "not_used" && n !== "available" && n !== "unavailable") return q.errors = [{
																	instancePath: t + "/provider_state",
																	schemaPath: "#/properties/provider_state/enum",
																	keyword: "enum",
																	params: { allowedValues: st.properties.provider_state.enum }
																}], !1;
																var d = r === c;
															} else var d = !0;
															if (d) {
																if (e.search !== void 0 && n.call(e, "search")) {
																	let n = e.search, r = c, i = c, l = !1, u = c;
																	K(n, {
																		instancePath: t + "/search",
																		parentData: e,
																		parentDataProperty: "search",
																		rootData: a,
																		dynamicAnchors: o
																	}) || (s = s === null ? K.errors : s.concat(K.errors), c = s.length);
																	var ee = u === c;
																	l ||= ee;
																	let f = c;
																	if (n !== null) {
																		let e = {
																			instancePath: t + "/search",
																			schemaPath: "#/properties/search/anyOf/1/type",
																			keyword: "type",
																			params: { type: "null" }
																		};
																		s === null ? s = [e] : s.push(e), c++;
																	}
																	var ee = f === c;
																	if (l ||= ee, l) c = i, s !== null && (i ? s.length = i : s = null);
																	else {
																		let e = {
																			instancePath: t + "/search",
																			schemaPath: "#/properties/search/anyOf",
																			keyword: "anyOf",
																			params: {}
																		};
																		return s === null ? s = [e] : s.push(e), c++, q.errors = s, !1;
																	}
																	var d = r === c;
																} else var d = !0;
																if (d) {
																	if (e.session_id !== void 0 && n.call(e, "session_id")) {
																		let n = e.session_id, r = c;
																		if (c === r) {
																			if (typeof n == "string") {
																				if (!u.test(n)) return q.errors = [{
																					instancePath: t + "/session_id",
																					schemaPath: "#/properties/session_id/pattern",
																					keyword: "pattern",
																					params: { pattern: "^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$" }
																				}], !1;
																			} else return q.errors = [{
																				instancePath: t + "/session_id",
																				schemaPath: "#/properties/session_id/type",
																				keyword: "type",
																				params: { type: "string" }
																			}], !1;
																		}
																		var d = r === c;
																	} else var d = !0;
																	if (d) {
																		if (e.state !== void 0 && n.call(e, "state")) {
																			let n = e.state, r = c;
																			if (typeof n != "string") return q.errors = [{
																				instancePath: t + "/state",
																				schemaPath: "#/properties/state/type",
																				keyword: "type",
																				params: { type: "string" }
																			}], !1;
																			if (n !== "answered" && n !== "clarification" && n !== "provider_unavailable" && n !== "superseded") return q.errors = [{
																				instancePath: t + "/state",
																				schemaPath: "#/properties/state/enum",
																				keyword: "enum",
																				params: { allowedValues: st.properties.state.enum }
																			}], !1;
																			var d = r === c;
																		} else var d = !0;
																		if (d) {
																			if (e.text !== void 0 && n.call(e, "text")) {
																				let n = e.text, r = c;
																				if (c === r) {
																					if (typeof n == "string") {
																						if (h(n) > 12e3) return q.errors = [{
																							instancePath: t + "/text",
																							schemaPath: "#/properties/text/maxLength",
																							keyword: "maxLength",
																							params: { limit: 12e3 }
																						}], !1;
																					} else return q.errors = [{
																						instancePath: t + "/text",
																						schemaPath: "#/properties/text/type",
																						keyword: "type",
																						params: { type: "string" }
																					}], !1;
																				}
																				var d = r === c;
																			} else var d = !0;
																			if (d) {
																				if (e.turn_revision !== void 0 && n.call(e, "turn_revision")) {
																					let n = e.turn_revision, r = c;
																					if (typeof n != "number" || n % 1 || isNaN(n) || !isFinite(n)) return q.errors = [{
																						instancePath: t + "/turn_revision",
																						schemaPath: "#/properties/turn_revision/type",
																						keyword: "type",
																						params: { type: "integer" }
																					}], !1;
																					if (c === r && typeof n == "number" && isFinite(n)) {
																						if (n > 2147483647 || isNaN(n)) return q.errors = [{
																							instancePath: t + "/turn_revision",
																							schemaPath: "#/properties/turn_revision/maximum",
																							keyword: "maximum",
																							params: {
																								comparison: "<=",
																								limit: 2147483647
																							}
																						}], !1;
																						if (n < 0 || isNaN(n)) return q.errors = [{
																							instancePath: t + "/turn_revision",
																							schemaPath: "#/properties/turn_revision/minimum",
																							keyword: "minimum",
																							params: {
																								comparison: ">=",
																								limit: 0
																							}
																						}], !1;
																					}
																					var d = r === c;
																				} else var d = !0;
																			}
																		}
																	}
																}
															}
														}
													}
												}
											}
										}
									}
								}
							}
						}
					}
				}
			} else return q.errors = [{
				instancePath: t,
				schemaPath: "#/type",
				keyword: "type",
				params: { type: "object" }
			}], !1;
		}
		return q.errors = s, c === 0;
	}
	q.evaluated = {
		props: !0,
		dynamicProps: !1,
		dynamicItems: !1
	};
	function Ft(e, { instancePath: t = "", parentData: r, parentDataProperty: i, rootData: a = e, dynamicAnchors: o = {} } = {}) {
		let s = null, c = 0, l = Ft.evaluated;
		if (l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0) {
			if (e && typeof e == "object" && !Array.isArray(e)) {
				let r;
				if ((e.data === void 0 || !n.call(e, "data")) && (r = "data") || (e.meta === void 0 || !n.call(e, "meta")) && (r = "meta")) return Ft.errors = [{
					instancePath: t,
					schemaPath: "#/required",
					keyword: "required",
					params: { missingProperty: r }
				}], !1;
				{
					let r = c;
					for (let n of Object.keys(e)) if (n !== "data" && n !== "meta") return Ft.errors = [{
						instancePath: t,
						schemaPath: "#/additionalProperties",
						keyword: "additionalProperties",
						params: { additionalProperty: n }
					}], !1;
					if (r === c) {
						if (e.data !== void 0 && n.call(e, "data")) {
							let n = c;
							q(e.data, {
								instancePath: t + "/data",
								parentData: e,
								parentDataProperty: "data",
								rootData: a,
								dynamicAnchors: o
							}) || (s = s === null ? q.errors : s.concat(q.errors), c = s.length);
							var u = n === c;
						} else var u = !0;
						if (u) {
							if (e.meta !== void 0 && n.call(e, "meta")) {
								let n = c;
								y(e.meta, {
									instancePath: t + "/meta",
									parentData: e,
									parentDataProperty: "meta",
									rootData: a,
									dynamicAnchors: o
								}) || (s = s === null ? y.errors : s.concat(y.errors), c = s.length);
								var u = n === c;
							} else var u = !0;
						}
					}
				}
			} else return Ft.errors = [{
				instancePath: t,
				schemaPath: "#/type",
				keyword: "type",
				params: { type: "object" }
			}], !1;
		}
		return Ft.errors = s, c === 0;
	}
	Ft.evaluated = {
		props: !0,
		dynamicProps: !1,
		dynamicItems: !1
	}, e.v44 = It;
	function It(e, { instancePath: t = "", parentData: r, parentDataProperty: i, rootData: a = e, dynamicAnchors: o = {} } = {}) {
		let s = null, c = 0, l = It.evaluated;
		if (l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0) {
			if (e && typeof e == "object" && !Array.isArray(e)) {
				let r;
				if ((e.data === void 0 || !n.call(e, "data")) && (r = "data") || (e.meta === void 0 || !n.call(e, "meta")) && (r = "meta")) return It.errors = [{
					instancePath: t,
					schemaPath: "#/required",
					keyword: "required",
					params: { missingProperty: r }
				}], !1;
				{
					let r = c;
					for (let n of Object.keys(e)) if (n !== "data" && n !== "meta") return It.errors = [{
						instancePath: t,
						schemaPath: "#/additionalProperties",
						keyword: "additionalProperties",
						params: { additionalProperty: n }
					}], !1;
					if (r === c) {
						if (e.data !== void 0 && n.call(e, "data")) {
							let n = c;
							V(e.data, {
								instancePath: t + "/data",
								parentData: e,
								parentDataProperty: "data",
								rootData: a,
								dynamicAnchors: o
							}) || (s = s === null ? V.errors : s.concat(V.errors), c = s.length);
							var u = n === c;
						} else var u = !0;
						if (u) {
							if (e.meta !== void 0 && n.call(e, "meta")) {
								let n = c;
								y(e.meta, {
									instancePath: t + "/meta",
									parentData: e,
									parentDataProperty: "meta",
									rootData: a,
									dynamicAnchors: o
								}) || (s = s === null ? y.errors : s.concat(y.errors), c = s.length);
								var u = n === c;
							} else var u = !0;
						}
					}
				}
			} else return It.errors = [{
				instancePath: t,
				schemaPath: "#/type",
				keyword: "type",
				params: { type: "object" }
			}], !1;
		}
		return It.errors = s, c === 0;
	}
	It.evaluated = {
		props: !0,
		dynamicProps: !1,
		dynamicItems: !1
	}, e.v45 = zt;
	var Lt = {
		additionalProperties: !1,
		properties: {
			identity_mode: {
				const: "browser_local_explicit_save",
				default: "browser_local_explicit_save",
				title: "Identity Mode",
				type: "string"
			},
			language: {
				const: "en",
				default: "en",
				title: "Language",
				type: "string"
			},
			limits: { $ref: "urn:car-shopping-assistant:contract:1#/$defs/PublicLimits" },
			mode: {
				const: "local_simulated",
				default: "local_simulated",
				title: "Mode",
				type: "string"
			},
			notice_version: {
				const: "DEMO-POLICY-1",
				default: "DEMO-POLICY-1",
				title: "Notice Version",
				type: "string"
			},
			optional_features: {
				default: [],
				items: { type: "string" },
				maxItems: 0,
				title: "Optional Features",
				type: "array"
			},
			policy_version: {
				const: "DEMO-POLICY-1",
				default: "DEMO-POLICY-1",
				title: "Policy Version",
				type: "string"
			},
			timezone: {
				const: "Asia/Dubai",
				default: "Asia/Dubai",
				title: "Timezone",
				type: "string"
			},
			viewing_venue: {
				const: "Simulated local viewing — no real venue or reservation.",
				title: "Viewing Venue",
				type: "string"
			}
		},
		required: ["limits", "viewing_venue"],
		title: "PublicConfig",
		type: "object"
	};
	function Rt(e, { instancePath: t = "", parentData: r, parentDataProperty: i, rootData: a = e, dynamicAnchors: o = {} } = {}) {
		let s = Rt.evaluated;
		if (s.dynamicProps && (s.props = void 0), s.dynamicItems && (s.items = void 0), e && typeof e == "object" && !Array.isArray(e)) {
			for (let n of Object.keys(e)) if (n !== "body_bytes_max" && n !== "comparison_max" && n !== "filter_clauses_max" && n !== "message_codepoints" && n !== "page_size_default" && n !== "page_size_max" && n !== "search_codepoints") return Rt.errors = [{
				instancePath: t,
				schemaPath: "#/additionalProperties",
				keyword: "additionalProperties",
				params: { additionalProperty: n }
			}], !1;
			if (e.body_bytes_max !== void 0 && n.call(e, "body_bytes_max")) {
				let n = e.body_bytes_max;
				if (typeof n != "number" || n % 1 || isNaN(n) || !isFinite(n)) return Rt.errors = [{
					instancePath: t + "/body_bytes_max",
					schemaPath: "#/properties/body_bytes_max/type",
					keyword: "type",
					params: { type: "integer" }
				}], !1;
				if (n !== 65536) return Rt.errors = [{
					instancePath: t + "/body_bytes_max",
					schemaPath: "#/properties/body_bytes_max/const",
					keyword: "const",
					params: { allowedValue: 65536 }
				}], !1;
				var c = !0;
			} else var c = !0;
			if (c) {
				if (e.comparison_max !== void 0 && n.call(e, "comparison_max")) {
					let n = e.comparison_max;
					if (typeof n != "number" || n % 1 || isNaN(n) || !isFinite(n)) return Rt.errors = [{
						instancePath: t + "/comparison_max",
						schemaPath: "#/properties/comparison_max/type",
						keyword: "type",
						params: { type: "integer" }
					}], !1;
					if (n !== 3) return Rt.errors = [{
						instancePath: t + "/comparison_max",
						schemaPath: "#/properties/comparison_max/const",
						keyword: "const",
						params: { allowedValue: 3 }
					}], !1;
					var c = !0;
				} else var c = !0;
				if (c) {
					if (e.filter_clauses_max !== void 0 && n.call(e, "filter_clauses_max")) {
						let n = e.filter_clauses_max;
						if (typeof n != "number" || n % 1 || isNaN(n) || !isFinite(n)) return Rt.errors = [{
							instancePath: t + "/filter_clauses_max",
							schemaPath: "#/properties/filter_clauses_max/type",
							keyword: "type",
							params: { type: "integer" }
						}], !1;
						if (n !== 24) return Rt.errors = [{
							instancePath: t + "/filter_clauses_max",
							schemaPath: "#/properties/filter_clauses_max/const",
							keyword: "const",
							params: { allowedValue: 24 }
						}], !1;
						var c = !0;
					} else var c = !0;
					if (c) {
						if (e.message_codepoints !== void 0 && n.call(e, "message_codepoints")) {
							let n = e.message_codepoints;
							if (typeof n != "number" || n % 1 || isNaN(n) || !isFinite(n)) return Rt.errors = [{
								instancePath: t + "/message_codepoints",
								schemaPath: "#/properties/message_codepoints/type",
								keyword: "type",
								params: { type: "integer" }
							}], !1;
							if (n !== 4e3) return Rt.errors = [{
								instancePath: t + "/message_codepoints",
								schemaPath: "#/properties/message_codepoints/const",
								keyword: "const",
								params: { allowedValue: 4e3 }
							}], !1;
							var c = !0;
						} else var c = !0;
						if (c) {
							if (e.page_size_default !== void 0 && n.call(e, "page_size_default")) {
								let n = e.page_size_default;
								if (typeof n != "number" || n % 1 || isNaN(n) || !isFinite(n)) return Rt.errors = [{
									instancePath: t + "/page_size_default",
									schemaPath: "#/properties/page_size_default/type",
									keyword: "type",
									params: { type: "integer" }
								}], !1;
								if (n !== 20) return Rt.errors = [{
									instancePath: t + "/page_size_default",
									schemaPath: "#/properties/page_size_default/const",
									keyword: "const",
									params: { allowedValue: 20 }
								}], !1;
								var c = !0;
							} else var c = !0;
							if (c) {
								if (e.page_size_max !== void 0 && n.call(e, "page_size_max")) {
									let n = e.page_size_max;
									if (typeof n != "number" || n % 1 || isNaN(n) || !isFinite(n)) return Rt.errors = [{
										instancePath: t + "/page_size_max",
										schemaPath: "#/properties/page_size_max/type",
										keyword: "type",
										params: { type: "integer" }
									}], !1;
									if (n !== 50) return Rt.errors = [{
										instancePath: t + "/page_size_max",
										schemaPath: "#/properties/page_size_max/const",
										keyword: "const",
										params: { allowedValue: 50 }
									}], !1;
									var c = !0;
								} else var c = !0;
								if (c) {
									if (e.search_codepoints !== void 0 && n.call(e, "search_codepoints")) {
										let n = e.search_codepoints;
										if (typeof n != "number" || n % 1 || isNaN(n) || !isFinite(n)) return Rt.errors = [{
											instancePath: t + "/search_codepoints",
											schemaPath: "#/properties/search_codepoints/type",
											keyword: "type",
											params: { type: "integer" }
										}], !1;
										if (n !== 1e3) return Rt.errors = [{
											instancePath: t + "/search_codepoints",
											schemaPath: "#/properties/search_codepoints/const",
											keyword: "const",
											params: { allowedValue: 1e3 }
										}], !1;
										var c = !0;
									} else var c = !0;
								}
							}
						}
					}
				}
			}
		} else return Rt.errors = [{
			instancePath: t,
			schemaPath: "#/type",
			keyword: "type",
			params: { type: "object" }
		}], !1;
		return Rt.errors = null, !0;
	}
	Rt.evaluated = {
		props: !0,
		dynamicProps: !1,
		dynamicItems: !1
	};
	function J(e, { instancePath: t = "", parentData: r, parentDataProperty: i, rootData: a = e, dynamicAnchors: o = {} } = {}) {
		let s = null, c = 0, l = J.evaluated;
		if (l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0) {
			if (e && typeof e == "object" && !Array.isArray(e)) {
				let r;
				if ((e.limits === void 0 || !n.call(e, "limits")) && (r = "limits") || (e.viewing_venue === void 0 || !n.call(e, "viewing_venue")) && (r = "viewing_venue")) return J.errors = [{
					instancePath: t,
					schemaPath: "#/required",
					keyword: "required",
					params: { missingProperty: r }
				}], !1;
				{
					let r = c;
					for (let r of Object.keys(e)) if (!n.call(Lt.properties, r)) return J.errors = [{
						instancePath: t,
						schemaPath: "#/additionalProperties",
						keyword: "additionalProperties",
						params: { additionalProperty: r }
					}], !1;
					if (r === c) {
						if (e.identity_mode !== void 0 && n.call(e, "identity_mode")) {
							let n = e.identity_mode, r = c;
							if (typeof n != "string") return J.errors = [{
								instancePath: t + "/identity_mode",
								schemaPath: "#/properties/identity_mode/type",
								keyword: "type",
								params: { type: "string" }
							}], !1;
							if (n !== "browser_local_explicit_save") return J.errors = [{
								instancePath: t + "/identity_mode",
								schemaPath: "#/properties/identity_mode/const",
								keyword: "const",
								params: { allowedValue: "browser_local_explicit_save" }
							}], !1;
							var u = r === c;
						} else var u = !0;
						if (u) {
							if (e.language !== void 0 && n.call(e, "language")) {
								let n = e.language, r = c;
								if (typeof n != "string") return J.errors = [{
									instancePath: t + "/language",
									schemaPath: "#/properties/language/type",
									keyword: "type",
									params: { type: "string" }
								}], !1;
								if (n !== "en") return J.errors = [{
									instancePath: t + "/language",
									schemaPath: "#/properties/language/const",
									keyword: "const",
									params: { allowedValue: "en" }
								}], !1;
								var u = r === c;
							} else var u = !0;
							if (u) {
								if (e.limits !== void 0 && n.call(e, "limits")) {
									let n = c;
									Rt(e.limits, {
										instancePath: t + "/limits",
										parentData: e,
										parentDataProperty: "limits",
										rootData: a,
										dynamicAnchors: o
									}) || (s = s === null ? Rt.errors : s.concat(Rt.errors), c = s.length);
									var u = n === c;
								} else var u = !0;
								if (u) {
									if (e.mode !== void 0 && n.call(e, "mode")) {
										let n = e.mode, r = c;
										if (typeof n != "string") return J.errors = [{
											instancePath: t + "/mode",
											schemaPath: "#/properties/mode/type",
											keyword: "type",
											params: { type: "string" }
										}], !1;
										if (n !== "local_simulated") return J.errors = [{
											instancePath: t + "/mode",
											schemaPath: "#/properties/mode/const",
											keyword: "const",
											params: { allowedValue: "local_simulated" }
										}], !1;
										var u = r === c;
									} else var u = !0;
									if (u) {
										if (e.notice_version !== void 0 && n.call(e, "notice_version")) {
											let n = e.notice_version, r = c;
											if (typeof n != "string") return J.errors = [{
												instancePath: t + "/notice_version",
												schemaPath: "#/properties/notice_version/type",
												keyword: "type",
												params: { type: "string" }
											}], !1;
											if (n !== "DEMO-POLICY-1") return J.errors = [{
												instancePath: t + "/notice_version",
												schemaPath: "#/properties/notice_version/const",
												keyword: "const",
												params: { allowedValue: "DEMO-POLICY-1" }
											}], !1;
											var u = r === c;
										} else var u = !0;
										if (u) {
											if (e.optional_features !== void 0 && n.call(e, "optional_features")) {
												let n = e.optional_features, r = c;
												if (c === r) {
													if (Array.isArray(n)) {
														if (n.length > 0) return J.errors = [{
															instancePath: t + "/optional_features",
															schemaPath: "#/properties/optional_features/maxItems",
															keyword: "maxItems",
															params: { limit: 0 }
														}], !1;
														{
															let e = n.length;
															for (let r = 0; r < e; r++) {
																let e = c;
																if (typeof n[r] != "string") return J.errors = [{
																	instancePath: t + "/optional_features/" + r,
																	schemaPath: "#/properties/optional_features/items/type",
																	keyword: "type",
																	params: { type: "string" }
																}], !1;
																if (e !== c) break;
															}
														}
													} else return J.errors = [{
														instancePath: t + "/optional_features",
														schemaPath: "#/properties/optional_features/type",
														keyword: "type",
														params: { type: "array" }
													}], !1;
												}
												var u = r === c;
											} else var u = !0;
											if (u) {
												if (e.policy_version !== void 0 && n.call(e, "policy_version")) {
													let n = e.policy_version, r = c;
													if (typeof n != "string") return J.errors = [{
														instancePath: t + "/policy_version",
														schemaPath: "#/properties/policy_version/type",
														keyword: "type",
														params: { type: "string" }
													}], !1;
													if (n !== "DEMO-POLICY-1") return J.errors = [{
														instancePath: t + "/policy_version",
														schemaPath: "#/properties/policy_version/const",
														keyword: "const",
														params: { allowedValue: "DEMO-POLICY-1" }
													}], !1;
													var u = r === c;
												} else var u = !0;
												if (u) {
													if (e.timezone !== void 0 && n.call(e, "timezone")) {
														let n = e.timezone, r = c;
														if (typeof n != "string") return J.errors = [{
															instancePath: t + "/timezone",
															schemaPath: "#/properties/timezone/type",
															keyword: "type",
															params: { type: "string" }
														}], !1;
														if (n !== "Asia/Dubai") return J.errors = [{
															instancePath: t + "/timezone",
															schemaPath: "#/properties/timezone/const",
															keyword: "const",
															params: { allowedValue: "Asia/Dubai" }
														}], !1;
														var u = r === c;
													} else var u = !0;
													if (u) {
														if (e.viewing_venue !== void 0 && n.call(e, "viewing_venue")) {
															let n = e.viewing_venue, r = c;
															if (typeof n != "string") return J.errors = [{
																instancePath: t + "/viewing_venue",
																schemaPath: "#/properties/viewing_venue/type",
																keyword: "type",
																params: { type: "string" }
															}], !1;
															if (n !== "Simulated local viewing — no real venue or reservation.") return J.errors = [{
																instancePath: t + "/viewing_venue",
																schemaPath: "#/properties/viewing_venue/const",
																keyword: "const",
																params: { allowedValue: "Simulated local viewing — no real venue or reservation." }
															}], !1;
															var u = r === c;
														} else var u = !0;
													}
												}
											}
										}
									}
								}
							}
						}
					}
				}
			} else return J.errors = [{
				instancePath: t,
				schemaPath: "#/type",
				keyword: "type",
				params: { type: "object" }
			}], !1;
		}
		return J.errors = s, c === 0;
	}
	J.evaluated = {
		props: !0,
		dynamicProps: !1,
		dynamicItems: !1
	};
	function zt(e, { instancePath: t = "", parentData: r, parentDataProperty: i, rootData: a = e, dynamicAnchors: o = {} } = {}) {
		let s = null, c = 0, l = zt.evaluated;
		if (l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0) {
			if (e && typeof e == "object" && !Array.isArray(e)) {
				let r;
				if ((e.data === void 0 || !n.call(e, "data")) && (r = "data") || (e.meta === void 0 || !n.call(e, "meta")) && (r = "meta")) return zt.errors = [{
					instancePath: t,
					schemaPath: "#/required",
					keyword: "required",
					params: { missingProperty: r }
				}], !1;
				{
					let r = c;
					for (let n of Object.keys(e)) if (n !== "data" && n !== "meta") return zt.errors = [{
						instancePath: t,
						schemaPath: "#/additionalProperties",
						keyword: "additionalProperties",
						params: { additionalProperty: n }
					}], !1;
					if (r === c) {
						if (e.data !== void 0 && n.call(e, "data")) {
							let n = c;
							J(e.data, {
								instancePath: t + "/data",
								parentData: e,
								parentDataProperty: "data",
								rootData: a,
								dynamicAnchors: o
							}) || (s = s === null ? J.errors : s.concat(J.errors), c = s.length);
							var u = n === c;
						} else var u = !0;
						if (u) {
							if (e.meta !== void 0 && n.call(e, "meta")) {
								let n = c;
								y(e.meta, {
									instancePath: t + "/meta",
									parentData: e,
									parentDataProperty: "meta",
									rootData: a,
									dynamicAnchors: o
								}) || (s = s === null ? y.errors : s.concat(y.errors), c = s.length);
								var u = n === c;
							} else var u = !0;
						}
					}
				}
			} else return zt.errors = [{
				instancePath: t,
				schemaPath: "#/type",
				keyword: "type",
				params: { type: "object" }
			}], !1;
		}
		return zt.errors = s, c === 0;
	}
	zt.evaluated = {
		props: !0,
		dynamicProps: !1,
		dynamicItems: !1
	}, e.v46 = Bt;
	function Bt(e, { instancePath: t = "", parentData: r, parentDataProperty: i, rootData: a = e, dynamicAnchors: o = {} } = {}) {
		let s = null, c = 0, l = Bt.evaluated;
		if (l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0) {
			if (e && typeof e == "object" && !Array.isArray(e)) {
				let r;
				if ((e.data === void 0 || !n.call(e, "data")) && (r = "data") || (e.meta === void 0 || !n.call(e, "meta")) && (r = "meta")) return Bt.errors = [{
					instancePath: t,
					schemaPath: "#/required",
					keyword: "required",
					params: { missingProperty: r }
				}], !1;
				{
					let r = c;
					for (let n of Object.keys(e)) if (n !== "data" && n !== "meta") return Bt.errors = [{
						instancePath: t,
						schemaPath: "#/additionalProperties",
						keyword: "additionalProperties",
						params: { additionalProperty: n }
					}], !1;
					if (r === c) {
						if (e.data !== void 0 && n.call(e, "data")) {
							let n = c;
							v(e.data, {
								instancePath: t + "/data",
								parentData: e,
								parentDataProperty: "data",
								rootData: a,
								dynamicAnchors: o
							}) || (s = s === null ? v.errors : s.concat(v.errors), c = s.length);
							var u = n === c;
						} else var u = !0;
						if (u) {
							if (e.meta !== void 0 && n.call(e, "meta")) {
								let n = c;
								y(e.meta, {
									instancePath: t + "/meta",
									parentData: e,
									parentDataProperty: "meta",
									rootData: a,
									dynamicAnchors: o
								}) || (s = s === null ? y.errors : s.concat(y.errors), c = s.length);
								var u = n === c;
							} else var u = !0;
						}
					}
				}
			} else return Bt.errors = [{
				instancePath: t,
				schemaPath: "#/type",
				keyword: "type",
				params: { type: "object" }
			}], !1;
		}
		return Bt.errors = s, c === 0;
	}
	Bt.evaluated = {
		props: !0,
		dynamicProps: !1,
		dynamicItems: !1
	}, e.v47 = Vt;
	function Vt(e, { instancePath: t = "", parentData: r, parentDataProperty: i, rootData: a = e, dynamicAnchors: o = {} } = {}) {
		let s = null, c = 0, l = Vt.evaluated;
		if (l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0) {
			if (e && typeof e == "object" && !Array.isArray(e)) {
				let r;
				if ((e.data === void 0 || !n.call(e, "data")) && (r = "data") || (e.meta === void 0 || !n.call(e, "meta")) && (r = "meta")) return Vt.errors = [{
					instancePath: t,
					schemaPath: "#/required",
					keyword: "required",
					params: { missingProperty: r }
				}], !1;
				{
					let r = c;
					for (let n of Object.keys(e)) if (n !== "data" && n !== "meta") return Vt.errors = [{
						instancePath: t,
						schemaPath: "#/additionalProperties",
						keyword: "additionalProperties",
						params: { additionalProperty: n }
					}], !1;
					if (r === c) {
						if (e.data !== void 0 && n.call(e, "data")) {
							let n = c;
							K(e.data, {
								instancePath: t + "/data",
								parentData: e,
								parentDataProperty: "data",
								rootData: a,
								dynamicAnchors: o
							}) || (s = s === null ? K.errors : s.concat(K.errors), c = s.length);
							var u = n === c;
						} else var u = !0;
						if (u) {
							if (e.meta !== void 0 && n.call(e, "meta")) {
								let n = c;
								y(e.meta, {
									instancePath: t + "/meta",
									parentData: e,
									parentDataProperty: "meta",
									rootData: a,
									dynamicAnchors: o
								}) || (s = s === null ? y.errors : s.concat(y.errors), c = s.length);
								var u = n === c;
							} else var u = !0;
						}
					}
				}
			} else return Vt.errors = [{
				instancePath: t,
				schemaPath: "#/type",
				keyword: "type",
				params: { type: "object" }
			}], !1;
		}
		return Vt.errors = s, c === 0;
	}
	Vt.evaluated = {
		props: !0,
		dynamicProps: !1,
		dynamicItems: !1
	}, e.v48 = Ut;
	var Ht = {
		additionalProperties: !1,
		properties: {
			active_presentation_id: {
				anyOf: [{
					pattern: "^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$",
					type: "string"
				}, { type: "null" }],
				title: "Active Presentation Id"
			},
			criteria: { $ref: "urn:car-shopping-assistant:contract:1#/$defs/SearchCriteria" },
			current_draft_id: {
				anyOf: [{
					pattern: "^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$",
					type: "string"
				}, { type: "null" }],
				title: "Current Draft Id"
			},
			journey_id: {
				pattern: "^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$",
				title: "Journey Id",
				type: "string"
			},
			pending_intent: {
				discriminator: { propertyName: "kind" },
				oneOf: [
					{ $ref: "urn:car-shopping-assistant:contract:1#/$defs/NoPendingIntent" },
					{ $ref: "urn:car-shopping-assistant:contract:1#/$defs/ClarificationIntent" },
					{ $ref: "urn:car-shopping-assistant:contract:1#/$defs/ViewingReviewIntent" },
					{ $ref: "urn:car-shopping-assistant:contract:1#/$defs/UnresolvedOperationIntent" }
				],
				title: "Pending Intent",
				type: "object",
				required: ["kind"],
				properties: { kind: { type: "string" } }
			},
			recalled_preferences: { $ref: "urn:car-shopping-assistant:contract:1#/$defs/PreferenceRecord" },
			revision: {
				maximum: 2147483647,
				minimum: 0,
				title: "Revision",
				type: "integer"
			},
			selected_ref: { anyOf: [{ $ref: "urn:car-shopping-assistant:contract:1#/$defs/InventoryRef" }, { type: "null" }] },
			session_id: {
				pattern: "^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$",
				title: "Session Id",
				type: "string"
			}
		},
		required: [
			"session_id",
			"journey_id",
			"revision",
			"criteria",
			"selected_ref",
			"active_presentation_id",
			"current_draft_id",
			"pending_intent",
			"recalled_preferences"
		],
		title: "SessionState",
		type: "object"
	};
	function Y(e, { instancePath: t = "", parentData: r, parentDataProperty: i, rootData: a = e, dynamicAnchors: o = {} } = {}) {
		let s = null, c = 0, d = Y.evaluated;
		if (d.dynamicProps && (d.props = void 0), d.dynamicItems && (d.items = void 0), c === 0) {
			if (e && typeof e == "object" && !Array.isArray(e)) {
				let r;
				if ((e.session_id === void 0 || !n.call(e, "session_id")) && (r = "session_id") || (e.journey_id === void 0 || !n.call(e, "journey_id")) && (r = "journey_id") || (e.revision === void 0 || !n.call(e, "revision")) && (r = "revision") || (e.criteria === void 0 || !n.call(e, "criteria")) && (r = "criteria") || (e.selected_ref === void 0 || !n.call(e, "selected_ref")) && (r = "selected_ref") || (e.active_presentation_id === void 0 || !n.call(e, "active_presentation_id")) && (r = "active_presentation_id") || (e.current_draft_id === void 0 || !n.call(e, "current_draft_id")) && (r = "current_draft_id") || (e.pending_intent === void 0 || !n.call(e, "pending_intent")) && (r = "pending_intent") || (e.recalled_preferences === void 0 || !n.call(e, "recalled_preferences")) && (r = "recalled_preferences")) return Y.errors = [{
					instancePath: t,
					schemaPath: "#/required",
					keyword: "required",
					params: { missingProperty: r }
				}], !1;
				{
					let r = c;
					for (let r of Object.keys(e)) if (!n.call(Ht.properties, r)) return Y.errors = [{
						instancePath: t,
						schemaPath: "#/additionalProperties",
						keyword: "additionalProperties",
						params: { additionalProperty: r }
					}], !1;
					if (r === c) {
						if (e.active_presentation_id !== void 0 && n.call(e, "active_presentation_id")) {
							let n = e.active_presentation_id, r = c, i = c, a = !1, o = c;
							if (c === o) {
								if (typeof n == "string") {
									if (!u.test(n)) {
										let e = {
											instancePath: t + "/active_presentation_id",
											schemaPath: "#/properties/active_presentation_id/anyOf/0/pattern",
											keyword: "pattern",
											params: { pattern: "^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$" }
										};
										s === null ? s = [e] : s.push(e), c++;
									}
								} else {
									let e = {
										instancePath: t + "/active_presentation_id",
										schemaPath: "#/properties/active_presentation_id/anyOf/0/type",
										keyword: "type",
										params: { type: "string" }
									};
									s === null ? s = [e] : s.push(e), c++;
								}
							}
							var f = o === c;
							a ||= f;
							let l = c;
							if (n !== null) {
								let e = {
									instancePath: t + "/active_presentation_id",
									schemaPath: "#/properties/active_presentation_id/anyOf/1/type",
									keyword: "type",
									params: { type: "null" }
								};
								s === null ? s = [e] : s.push(e), c++;
							}
							var f = l === c;
							if (a ||= f, a) c = i, s !== null && (i ? s.length = i : s = null);
							else {
								let e = {
									instancePath: t + "/active_presentation_id",
									schemaPath: "#/properties/active_presentation_id/anyOf",
									keyword: "anyOf",
									params: {}
								};
								return s === null ? s = [e] : s.push(e), c++, Y.errors = s, !1;
							}
							var p = r === c;
						} else var p = !0;
						if (p) {
							if (e.criteria !== void 0 && n.call(e, "criteria")) {
								let n = c;
								Ct(e.criteria, {
									instancePath: t + "/criteria",
									parentData: e,
									parentDataProperty: "criteria",
									rootData: a,
									dynamicAnchors: o
								}) || (s = s === null ? Ct.errors : s.concat(Ct.errors), c = s.length);
								var p = n === c;
							} else var p = !0;
							if (p) {
								if (e.current_draft_id !== void 0 && n.call(e, "current_draft_id")) {
									let n = e.current_draft_id, r = c, i = c, a = !1, o = c;
									if (c === o) {
										if (typeof n == "string") {
											if (!u.test(n)) {
												let e = {
													instancePath: t + "/current_draft_id",
													schemaPath: "#/properties/current_draft_id/anyOf/0/pattern",
													keyword: "pattern",
													params: { pattern: "^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$" }
												};
												s === null ? s = [e] : s.push(e), c++;
											}
										} else {
											let e = {
												instancePath: t + "/current_draft_id",
												schemaPath: "#/properties/current_draft_id/anyOf/0/type",
												keyword: "type",
												params: { type: "string" }
											};
											s === null ? s = [e] : s.push(e), c++;
										}
									}
									var m = o === c;
									a ||= m;
									let l = c;
									if (n !== null) {
										let e = {
											instancePath: t + "/current_draft_id",
											schemaPath: "#/properties/current_draft_id/anyOf/1/type",
											keyword: "type",
											params: { type: "null" }
										};
										s === null ? s = [e] : s.push(e), c++;
									}
									var m = l === c;
									if (a ||= m, a) c = i, s !== null && (i ? s.length = i : s = null);
									else {
										let e = {
											instancePath: t + "/current_draft_id",
											schemaPath: "#/properties/current_draft_id/anyOf",
											keyword: "anyOf",
											params: {}
										};
										return s === null ? s = [e] : s.push(e), c++, Y.errors = s, !1;
									}
									var p = r === c;
								} else var p = !0;
								if (p) {
									if (e.journey_id !== void 0 && n.call(e, "journey_id")) {
										let n = e.journey_id, r = c;
										if (c === r) {
											if (typeof n == "string") {
												if (!u.test(n)) return Y.errors = [{
													instancePath: t + "/journey_id",
													schemaPath: "#/properties/journey_id/pattern",
													keyword: "pattern",
													params: { pattern: "^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$" }
												}], !1;
											} else return Y.errors = [{
												instancePath: t + "/journey_id",
												schemaPath: "#/properties/journey_id/type",
												keyword: "type",
												params: { type: "string" }
											}], !1;
										}
										var p = r === c;
									} else var p = !0;
									if (p) {
										if (e.pending_intent !== void 0 && n.call(e, "pending_intent")) {
											let r = e.pending_intent, i = c;
											if (c === i) {
												if (r && typeof r == "object" && !Array.isArray(r)) {
													let i;
													if ((r.kind === void 0 || !n.call(r, "kind")) && (i = "kind")) return Y.errors = [{
														instancePath: t + "/pending_intent",
														schemaPath: "#/properties/pending_intent/required",
														keyword: "required",
														params: { missingProperty: i }
													}], !1;
													if (r.kind !== void 0 && n.call(r, "kind")) {
														let e = c;
														if (typeof r.kind != "string") return Y.errors = [{
															instancePath: t + "/pending_intent/kind",
															schemaPath: "#/properties/pending_intent/properties/kind/type",
															keyword: "type",
															params: { type: "string" }
														}], !1;
														var h = e === c;
													} else var h = !0;
													if (h) {
														let n = r.kind;
														if (typeof n == "string") {
															if (n === "none") {
																Ot(r, {
																	instancePath: t + "/pending_intent",
																	parentData: e,
																	parentDataProperty: "pending_intent",
																	rootData: a,
																	dynamicAnchors: o
																}) || (s = s === null ? Ot.errors : s.concat(Ot.errors), c = s.length);
																var g = !0;
															} else if (n === "clarification") W(r, {
																instancePath: t + "/pending_intent",
																parentData: e,
																parentDataProperty: "pending_intent",
																rootData: a,
																dynamicAnchors: o
															}) || (s = s === null ? W.errors : s.concat(W.errors), c = s.length), g !== !0 && (g = !0);
															else if (n === "viewing_review") At(r, {
																instancePath: t + "/pending_intent",
																parentData: e,
																parentDataProperty: "pending_intent",
																rootData: a,
																dynamicAnchors: o
															}) || (s = s === null ? At.errors : s.concat(At.errors), c = s.length), g !== !0 && (g = !0);
															else if (n === "operation_unresolved") jt(r, {
																instancePath: t + "/pending_intent",
																parentData: e,
																parentDataProperty: "pending_intent",
																rootData: a,
																dynamicAnchors: o
															}) || (s = s === null ? jt.errors : s.concat(jt.errors), c = s.length), g !== !0 && (g = !0);
															else return Y.errors = [{
																instancePath: t + "/pending_intent",
																schemaPath: "#/properties/pending_intent/discriminator",
																keyword: "discriminator",
																params: {
																	error: "mapping",
																	tag: "kind",
																	tagValue: n
																}
															}], !1;
														} else return Y.errors = [{
															instancePath: t + "/pending_intent",
															schemaPath: "#/properties/pending_intent/discriminator",
															keyword: "discriminator",
															params: {
																error: "tag",
																tag: "kind",
																tagValue: n
															}
														}], !1;
													}
												} else return Y.errors = [{
													instancePath: t + "/pending_intent",
													schemaPath: "#/properties/pending_intent/type",
													keyword: "type",
													params: { type: "object" }
												}], !1;
											}
											var p = i === c;
										} else var p = !0;
										if (p) {
											if (e.recalled_preferences !== void 0 && n.call(e, "recalled_preferences")) {
												let n = c;
												V(e.recalled_preferences, {
													instancePath: t + "/recalled_preferences",
													parentData: e,
													parentDataProperty: "recalled_preferences",
													rootData: a,
													dynamicAnchors: o
												}) || (s = s === null ? V.errors : s.concat(V.errors), c = s.length);
												var p = n === c;
											} else var p = !0;
											if (p) {
												if (e.revision !== void 0 && n.call(e, "revision")) {
													let n = e.revision, r = c;
													if (typeof n != "number" || n % 1 || isNaN(n) || !isFinite(n)) return Y.errors = [{
														instancePath: t + "/revision",
														schemaPath: "#/properties/revision/type",
														keyword: "type",
														params: { type: "integer" }
													}], !1;
													if (c === r && typeof n == "number" && isFinite(n)) {
														if (n > 2147483647 || isNaN(n)) return Y.errors = [{
															instancePath: t + "/revision",
															schemaPath: "#/properties/revision/maximum",
															keyword: "maximum",
															params: {
																comparison: "<=",
																limit: 2147483647
															}
														}], !1;
														if (n < 0 || isNaN(n)) return Y.errors = [{
															instancePath: t + "/revision",
															schemaPath: "#/properties/revision/minimum",
															keyword: "minimum",
															params: {
																comparison: ">=",
																limit: 0
															}
														}], !1;
													}
													var p = r === c;
												} else var p = !0;
												if (p) {
													if (e.selected_ref !== void 0 && n.call(e, "selected_ref")) {
														let n = e.selected_ref, r = c, i = c, u = !1, d = c;
														l(n, {
															instancePath: t + "/selected_ref",
															parentData: e,
															parentDataProperty: "selected_ref",
															rootData: a,
															dynamicAnchors: o
														}) || (s = s === null ? l.errors : s.concat(l.errors), c = s.length);
														var _ = d === c;
														u ||= _;
														let f = c;
														if (n !== null) {
															let e = {
																instancePath: t + "/selected_ref",
																schemaPath: "#/properties/selected_ref/anyOf/1/type",
																keyword: "type",
																params: { type: "null" }
															};
															s === null ? s = [e] : s.push(e), c++;
														}
														var _ = f === c;
														if (u ||= _, u) c = i, s !== null && (i ? s.length = i : s = null);
														else {
															let e = {
																instancePath: t + "/selected_ref",
																schemaPath: "#/properties/selected_ref/anyOf",
																keyword: "anyOf",
																params: {}
															};
															return s === null ? s = [e] : s.push(e), c++, Y.errors = s, !1;
														}
														var p = r === c;
													} else var p = !0;
													if (p) {
														if (e.session_id !== void 0 && n.call(e, "session_id")) {
															let n = e.session_id, r = c;
															if (c === r) {
																if (typeof n == "string") {
																	if (!u.test(n)) return Y.errors = [{
																		instancePath: t + "/session_id",
																		schemaPath: "#/properties/session_id/pattern",
																		keyword: "pattern",
																		params: { pattern: "^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$" }
																	}], !1;
																} else return Y.errors = [{
																	instancePath: t + "/session_id",
																	schemaPath: "#/properties/session_id/type",
																	keyword: "type",
																	params: { type: "string" }
																}], !1;
															}
															var p = r === c;
														} else var p = !0;
													}
												}
											}
										}
									}
								}
							}
						}
					}
				}
			} else return Y.errors = [{
				instancePath: t,
				schemaPath: "#/type",
				keyword: "type",
				params: { type: "object" }
			}], !1;
		}
		return Y.errors = s, c === 0;
	}
	Y.evaluated = {
		props: !0,
		dynamicProps: !1,
		dynamicItems: !1
	};
	function Ut(e, { instancePath: t = "", parentData: r, parentDataProperty: i, rootData: a = e, dynamicAnchors: o = {} } = {}) {
		let s = null, c = 0, l = Ut.evaluated;
		if (l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0) {
			if (e && typeof e == "object" && !Array.isArray(e)) {
				let r;
				if ((e.data === void 0 || !n.call(e, "data")) && (r = "data") || (e.meta === void 0 || !n.call(e, "meta")) && (r = "meta")) return Ut.errors = [{
					instancePath: t,
					schemaPath: "#/required",
					keyword: "required",
					params: { missingProperty: r }
				}], !1;
				{
					let r = c;
					for (let n of Object.keys(e)) if (n !== "data" && n !== "meta") return Ut.errors = [{
						instancePath: t,
						schemaPath: "#/additionalProperties",
						keyword: "additionalProperties",
						params: { additionalProperty: n }
					}], !1;
					if (r === c) {
						if (e.data !== void 0 && n.call(e, "data")) {
							let n = c;
							Y(e.data, {
								instancePath: t + "/data",
								parentData: e,
								parentDataProperty: "data",
								rootData: a,
								dynamicAnchors: o
							}) || (s = s === null ? Y.errors : s.concat(Y.errors), c = s.length);
							var u = n === c;
						} else var u = !0;
						if (u) {
							if (e.meta !== void 0 && n.call(e, "meta")) {
								let n = c;
								y(e.meta, {
									instancePath: t + "/meta",
									parentData: e,
									parentDataProperty: "meta",
									rootData: a,
									dynamicAnchors: o
								}) || (s = s === null ? y.errors : s.concat(y.errors), c = s.length);
								var u = n === c;
							} else var u = !0;
						}
					}
				}
			} else return Ut.errors = [{
				instancePath: t,
				schemaPath: "#/type",
				keyword: "type",
				params: { type: "object" }
			}], !1;
		}
		return Ut.errors = s, c === 0;
	}
	Ut.evaluated = {
		props: !0,
		dynamicProps: !1,
		dynamicItems: !1
	}, e.v49 = qt;
	var Wt = {
		additionalProperties: !1,
		properties: {
			added_at: {
				pattern: "^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}(?:\\.\\d{1,6})?Z$",
				title: "Added At",
				type: "string"
			},
			expires_at: {
				pattern: "^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}(?:\\.\\d{1,6})?Z$",
				title: "Expires At",
				type: "string"
			},
			listing: { anyOf: [{ $ref: "urn:car-shopping-assistant:contract:1#/$defs/ListingSummary" }, { type: "null" }] },
			ref: { $ref: "urn:car-shopping-assistant:contract:1#/$defs/InventoryRef" },
			state: {
				enum: [
					"current",
					"historical",
					"missing"
				],
				title: "State",
				type: "string"
			}
		},
		required: [
			"ref",
			"state",
			"listing",
			"added_at",
			"expires_at"
		],
		title: "ShortlistItem",
		type: "object"
	};
	function Gt(e, { instancePath: t = "", parentData: r, parentDataProperty: a, rootData: o = e, dynamicAnchors: s = {} } = {}) {
		let c = null, u = 0, d = Gt.evaluated;
		if (d.dynamicProps && (d.props = void 0), d.dynamicItems && (d.items = void 0), u === 0) {
			if (e && typeof e == "object" && !Array.isArray(e)) {
				let r;
				if ((e.ref === void 0 || !n.call(e, "ref")) && (r = "ref") || (e.state === void 0 || !n.call(e, "state")) && (r = "state") || (e.listing === void 0 || !n.call(e, "listing")) && (r = "listing") || (e.added_at === void 0 || !n.call(e, "added_at")) && (r = "added_at") || (e.expires_at === void 0 || !n.call(e, "expires_at")) && (r = "expires_at")) return Gt.errors = [{
					instancePath: t,
					schemaPath: "#/required",
					keyword: "required",
					params: { missingProperty: r }
				}], !1;
				{
					let r = u;
					for (let n of Object.keys(e)) if (n !== "added_at" && n !== "expires_at" && n !== "listing" && n !== "ref" && n !== "state") return Gt.errors = [{
						instancePath: t,
						schemaPath: "#/additionalProperties",
						keyword: "additionalProperties",
						params: { additionalProperty: n }
					}], !1;
					if (r === u) {
						if (e.added_at !== void 0 && n.call(e, "added_at")) {
							let n = e.added_at, r = u;
							if (u === r) {
								if (typeof n == "string") {
									if (!i.test(n)) return Gt.errors = [{
										instancePath: t + "/added_at",
										schemaPath: "#/properties/added_at/pattern",
										keyword: "pattern",
										params: { pattern: "^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}(?:\\.\\d{1,6})?Z$" }
									}], !1;
								} else return Gt.errors = [{
									instancePath: t + "/added_at",
									schemaPath: "#/properties/added_at/type",
									keyword: "type",
									params: { type: "string" }
								}], !1;
							}
							var f = r === u;
						} else var f = !0;
						if (f) {
							if (e.expires_at !== void 0 && n.call(e, "expires_at")) {
								let n = e.expires_at, r = u;
								if (u === r) {
									if (typeof n == "string") {
										if (!i.test(n)) return Gt.errors = [{
											instancePath: t + "/expires_at",
											schemaPath: "#/properties/expires_at/pattern",
											keyword: "pattern",
											params: { pattern: "^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}(?:\\.\\d{1,6})?Z$" }
										}], !1;
									} else return Gt.errors = [{
										instancePath: t + "/expires_at",
										schemaPath: "#/properties/expires_at/type",
										keyword: "type",
										params: { type: "string" }
									}], !1;
								}
								var f = r === u;
							} else var f = !0;
							if (f) {
								if (e.listing !== void 0 && n.call(e, "listing")) {
									let n = e.listing, r = u, i = u, a = !1, l = u;
									w(n, {
										instancePath: t + "/listing",
										parentData: e,
										parentDataProperty: "listing",
										rootData: o,
										dynamicAnchors: s
									}) || (c = c === null ? w.errors : c.concat(w.errors), u = c.length);
									var p = l === u;
									a ||= p;
									let d = u;
									if (n !== null) {
										let e = {
											instancePath: t + "/listing",
											schemaPath: "#/properties/listing/anyOf/1/type",
											keyword: "type",
											params: { type: "null" }
										};
										c === null ? c = [e] : c.push(e), u++;
									}
									var p = d === u;
									if (a ||= p, a) u = i, c !== null && (i ? c.length = i : c = null);
									else {
										let e = {
											instancePath: t + "/listing",
											schemaPath: "#/properties/listing/anyOf",
											keyword: "anyOf",
											params: {}
										};
										return c === null ? c = [e] : c.push(e), u++, Gt.errors = c, !1;
									}
									var f = r === u;
								} else var f = !0;
								if (f) {
									if (e.ref !== void 0 && n.call(e, "ref")) {
										let n = u;
										l(e.ref, {
											instancePath: t + "/ref",
											parentData: e,
											parentDataProperty: "ref",
											rootData: o,
											dynamicAnchors: s
										}) || (c = c === null ? l.errors : c.concat(l.errors), u = c.length);
										var f = n === u;
									} else var f = !0;
									if (f) {
										if (e.state !== void 0 && n.call(e, "state")) {
											let n = e.state, r = u;
											if (typeof n != "string") return Gt.errors = [{
												instancePath: t + "/state",
												schemaPath: "#/properties/state/type",
												keyword: "type",
												params: { type: "string" }
											}], !1;
											if (n !== "current" && n !== "historical" && n !== "missing") return Gt.errors = [{
												instancePath: t + "/state",
												schemaPath: "#/properties/state/enum",
												keyword: "enum",
												params: { allowedValues: Wt.properties.state.enum }
											}], !1;
											var f = r === u;
										} else var f = !0;
									}
								}
							}
						}
					}
				}
			} else return Gt.errors = [{
				instancePath: t,
				schemaPath: "#/type",
				keyword: "type",
				params: { type: "object" }
			}], !1;
		}
		return Gt.errors = c, u === 0;
	}
	Gt.evaluated = {
		props: !0,
		dynamicProps: !1,
		dynamicItems: !1
	};
	function Kt(e, { instancePath: t = "", parentData: r, parentDataProperty: i, rootData: a = e, dynamicAnchors: o = {} } = {}) {
		let s = null, c = 0, l = Kt.evaluated;
		if (l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0) {
			if (e && typeof e == "object" && !Array.isArray(e)) {
				let r;
				if ((e.revision === void 0 || !n.call(e, "revision")) && (r = "revision") || (e.items === void 0 || !n.call(e, "items")) && (r = "items") || (e.total === void 0 || !n.call(e, "total")) && (r = "total") || (e.next_cursor === void 0 || !n.call(e, "next_cursor")) && (r = "next_cursor")) return Kt.errors = [{
					instancePath: t,
					schemaPath: "#/required",
					keyword: "required",
					params: { missingProperty: r }
				}], !1;
				{
					let r = c;
					for (let n of Object.keys(e)) if (n !== "items" && n !== "next_cursor" && n !== "revision" && n !== "total") return Kt.errors = [{
						instancePath: t,
						schemaPath: "#/additionalProperties",
						keyword: "additionalProperties",
						params: { additionalProperty: n }
					}], !1;
					if (r === c) {
						if (e.items !== void 0 && n.call(e, "items")) {
							let n = e.items, r = c;
							if (c === r) {
								if (Array.isArray(n)) {
									if (n.length > 50) return Kt.errors = [{
										instancePath: t + "/items",
										schemaPath: "#/properties/items/maxItems",
										keyword: "maxItems",
										params: { limit: 50 }
									}], !1;
									{
										let e = n.length;
										for (let r = 0; r < e; r++) {
											let e = c;
											if (Gt(n[r], {
												instancePath: t + "/items/" + r,
												parentData: n,
												parentDataProperty: r,
												rootData: a,
												dynamicAnchors: o
											}) || (s = s === null ? Gt.errors : s.concat(Gt.errors), c = s.length), e !== c) break;
										}
									}
								} else return Kt.errors = [{
									instancePath: t + "/items",
									schemaPath: "#/properties/items/type",
									keyword: "type",
									params: { type: "array" }
								}], !1;
							}
							var u = r === c;
						} else var u = !0;
						if (u) {
							if (e.next_cursor !== void 0 && n.call(e, "next_cursor")) {
								let n = e.next_cursor, r = c, i = c, a = !1, o = c;
								if (c === o) {
									if (typeof n == "string") {
										if (h(n) > 2048) {
											let e = {
												instancePath: t + "/next_cursor",
												schemaPath: "#/properties/next_cursor/anyOf/0/maxLength",
												keyword: "maxLength",
												params: { limit: 2048 }
											};
											s === null ? s = [e] : s.push(e), c++;
										}
									} else {
										let e = {
											instancePath: t + "/next_cursor",
											schemaPath: "#/properties/next_cursor/anyOf/0/type",
											keyword: "type",
											params: { type: "string" }
										};
										s === null ? s = [e] : s.push(e), c++;
									}
								}
								var d = o === c;
								a ||= d;
								let l = c;
								if (n !== null) {
									let e = {
										instancePath: t + "/next_cursor",
										schemaPath: "#/properties/next_cursor/anyOf/1/type",
										keyword: "type",
										params: { type: "null" }
									};
									s === null ? s = [e] : s.push(e), c++;
								}
								var d = l === c;
								if (a ||= d, a) c = i, s !== null && (i ? s.length = i : s = null);
								else {
									let e = {
										instancePath: t + "/next_cursor",
										schemaPath: "#/properties/next_cursor/anyOf",
										keyword: "anyOf",
										params: {}
									};
									return s === null ? s = [e] : s.push(e), c++, Kt.errors = s, !1;
								}
								var u = r === c;
							} else var u = !0;
							if (u) {
								if (e.revision !== void 0 && n.call(e, "revision")) {
									let n = e.revision, r = c;
									if (typeof n != "number" || n % 1 || isNaN(n) || !isFinite(n)) return Kt.errors = [{
										instancePath: t + "/revision",
										schemaPath: "#/properties/revision/type",
										keyword: "type",
										params: { type: "integer" }
									}], !1;
									if (c === r && typeof n == "number" && isFinite(n)) {
										if (n > 2147483647 || isNaN(n)) return Kt.errors = [{
											instancePath: t + "/revision",
											schemaPath: "#/properties/revision/maximum",
											keyword: "maximum",
											params: {
												comparison: "<=",
												limit: 2147483647
											}
										}], !1;
										if (n < 0 || isNaN(n)) return Kt.errors = [{
											instancePath: t + "/revision",
											schemaPath: "#/properties/revision/minimum",
											keyword: "minimum",
											params: {
												comparison: ">=",
												limit: 0
											}
										}], !1;
									}
									var u = r === c;
								} else var u = !0;
								if (u) {
									if (e.total !== void 0 && n.call(e, "total")) {
										let n = e.total, r = c;
										if (typeof n != "number" || n % 1 || isNaN(n) || !isFinite(n)) return Kt.errors = [{
											instancePath: t + "/total",
											schemaPath: "#/properties/total/type",
											keyword: "type",
											params: { type: "integer" }
										}], !1;
										if (c === r && typeof n == "number" && isFinite(n) && (n < 0 || isNaN(n))) return Kt.errors = [{
											instancePath: t + "/total",
											schemaPath: "#/properties/total/minimum",
											keyword: "minimum",
											params: {
												comparison: ">=",
												limit: 0
											}
										}], !1;
										var u = r === c;
									} else var u = !0;
								}
							}
						}
					}
				}
			} else return Kt.errors = [{
				instancePath: t,
				schemaPath: "#/type",
				keyword: "type",
				params: { type: "object" }
			}], !1;
		}
		return Kt.errors = s, c === 0;
	}
	Kt.evaluated = {
		props: !0,
		dynamicProps: !1,
		dynamicItems: !1
	};
	function qt(e, { instancePath: t = "", parentData: r, parentDataProperty: i, rootData: a = e, dynamicAnchors: o = {} } = {}) {
		let s = null, c = 0, l = qt.evaluated;
		if (l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0) {
			if (e && typeof e == "object" && !Array.isArray(e)) {
				let r;
				if ((e.data === void 0 || !n.call(e, "data")) && (r = "data") || (e.meta === void 0 || !n.call(e, "meta")) && (r = "meta")) return qt.errors = [{
					instancePath: t,
					schemaPath: "#/required",
					keyword: "required",
					params: { missingProperty: r }
				}], !1;
				{
					let r = c;
					for (let n of Object.keys(e)) if (n !== "data" && n !== "meta") return qt.errors = [{
						instancePath: t,
						schemaPath: "#/additionalProperties",
						keyword: "additionalProperties",
						params: { additionalProperty: n }
					}], !1;
					if (r === c) {
						if (e.data !== void 0 && n.call(e, "data")) {
							let n = c;
							Kt(e.data, {
								instancePath: t + "/data",
								parentData: e,
								parentDataProperty: "data",
								rootData: a,
								dynamicAnchors: o
							}) || (s = s === null ? Kt.errors : s.concat(Kt.errors), c = s.length);
							var u = n === c;
						} else var u = !0;
						if (u) {
							if (e.meta !== void 0 && n.call(e, "meta")) {
								let n = c;
								y(e.meta, {
									instancePath: t + "/meta",
									parentData: e,
									parentDataProperty: "meta",
									rootData: a,
									dynamicAnchors: o
								}) || (s = s === null ? y.errors : s.concat(y.errors), c = s.length);
								var u = n === c;
							} else var u = !0;
						}
					}
				}
			} else return qt.errors = [{
				instancePath: t,
				schemaPath: "#/type",
				keyword: "type",
				params: { type: "object" }
			}], !1;
		}
		return qt.errors = s, c === 0;
	}
	qt.evaluated = {
		props: !0,
		dynamicProps: !1,
		dynamicItems: !1
	}, e.v50 = Xt;
	var Jt = {
		additionalProperties: !1,
		properties: {
			accepted_at: {
				pattern: "^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}(?:\\.\\d{1,6})?Z$",
				title: "Accepted At",
				type: "string"
			},
			accepted_revision: {
				maximum: 2147483647,
				minimum: 0,
				title: "Accepted Revision",
				type: "integer"
			},
			assistant_result: { anyOf: [{ $ref: "urn:car-shopping-assistant:contract:1#/$defs/MessageResult" }, { type: "null" }] },
			client_message_id: {
				pattern: "^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$",
				title: "Client Message Id",
				type: "string"
			},
			historical: {
				const: !0,
				default: !0,
				title: "Historical",
				type: "boolean"
			},
			message_id: {
				pattern: "^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$",
				title: "Message Id",
				type: "string"
			},
			session_id: {
				pattern: "^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$",
				title: "Session Id",
				type: "string"
			},
			state: {
				enum: [
					"completed",
					"pending",
					"interrupted"
				],
				title: "State",
				type: "string"
			},
			user_text: {
				maxLength: 4e3,
				minLength: 1,
				title: "User Text",
				type: "string"
			}
		},
		required: [
			"message_id",
			"client_message_id",
			"session_id",
			"accepted_revision",
			"accepted_at",
			"user_text",
			"state",
			"assistant_result"
		],
		title: "TranscriptTurn",
		type: "object"
	};
	function X(e, { instancePath: t = "", parentData: r, parentDataProperty: a, rootData: o = e, dynamicAnchors: s = {} } = {}) {
		let c = null, l = 0, d = X.evaluated;
		if (d.dynamicProps && (d.props = void 0), d.dynamicItems && (d.items = void 0), l === 0) {
			if (e && typeof e == "object" && !Array.isArray(e)) {
				let r;
				if ((e.message_id === void 0 || !n.call(e, "message_id")) && (r = "message_id") || (e.client_message_id === void 0 || !n.call(e, "client_message_id")) && (r = "client_message_id") || (e.session_id === void 0 || !n.call(e, "session_id")) && (r = "session_id") || (e.accepted_revision === void 0 || !n.call(e, "accepted_revision")) && (r = "accepted_revision") || (e.accepted_at === void 0 || !n.call(e, "accepted_at")) && (r = "accepted_at") || (e.user_text === void 0 || !n.call(e, "user_text")) && (r = "user_text") || (e.state === void 0 || !n.call(e, "state")) && (r = "state") || (e.assistant_result === void 0 || !n.call(e, "assistant_result")) && (r = "assistant_result")) return X.errors = [{
					instancePath: t,
					schemaPath: "#/required",
					keyword: "required",
					params: { missingProperty: r }
				}], !1;
				{
					let r = l;
					for (let r of Object.keys(e)) if (!n.call(Jt.properties, r)) return X.errors = [{
						instancePath: t,
						schemaPath: "#/additionalProperties",
						keyword: "additionalProperties",
						params: { additionalProperty: r }
					}], !1;
					if (r === l) {
						if (e.accepted_at !== void 0 && n.call(e, "accepted_at")) {
							let n = e.accepted_at, r = l;
							if (l === r) {
								if (typeof n == "string") {
									if (!i.test(n)) return X.errors = [{
										instancePath: t + "/accepted_at",
										schemaPath: "#/properties/accepted_at/pattern",
										keyword: "pattern",
										params: { pattern: "^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}(?:\\.\\d{1,6})?Z$" }
									}], !1;
								} else return X.errors = [{
									instancePath: t + "/accepted_at",
									schemaPath: "#/properties/accepted_at/type",
									keyword: "type",
									params: { type: "string" }
								}], !1;
							}
							var f = r === l;
						} else var f = !0;
						if (f) {
							if (e.accepted_revision !== void 0 && n.call(e, "accepted_revision")) {
								let n = e.accepted_revision, r = l;
								if (typeof n != "number" || n % 1 || isNaN(n) || !isFinite(n)) return X.errors = [{
									instancePath: t + "/accepted_revision",
									schemaPath: "#/properties/accepted_revision/type",
									keyword: "type",
									params: { type: "integer" }
								}], !1;
								if (l === r && typeof n == "number" && isFinite(n)) {
									if (n > 2147483647 || isNaN(n)) return X.errors = [{
										instancePath: t + "/accepted_revision",
										schemaPath: "#/properties/accepted_revision/maximum",
										keyword: "maximum",
										params: {
											comparison: "<=",
											limit: 2147483647
										}
									}], !1;
									if (n < 0 || isNaN(n)) return X.errors = [{
										instancePath: t + "/accepted_revision",
										schemaPath: "#/properties/accepted_revision/minimum",
										keyword: "minimum",
										params: {
											comparison: ">=",
											limit: 0
										}
									}], !1;
								}
								var f = r === l;
							} else var f = !0;
							if (f) {
								if (e.assistant_result !== void 0 && n.call(e, "assistant_result")) {
									let n = e.assistant_result, r = l, i = l, a = !1, u = l;
									q(n, {
										instancePath: t + "/assistant_result",
										parentData: e,
										parentDataProperty: "assistant_result",
										rootData: o,
										dynamicAnchors: s
									}) || (c = c === null ? q.errors : c.concat(q.errors), l = c.length);
									var p = u === l;
									a ||= p;
									let d = l;
									if (n !== null) {
										let e = {
											instancePath: t + "/assistant_result",
											schemaPath: "#/properties/assistant_result/anyOf/1/type",
											keyword: "type",
											params: { type: "null" }
										};
										c === null ? c = [e] : c.push(e), l++;
									}
									var p = d === l;
									if (a ||= p, a) l = i, c !== null && (i ? c.length = i : c = null);
									else {
										let e = {
											instancePath: t + "/assistant_result",
											schemaPath: "#/properties/assistant_result/anyOf",
											keyword: "anyOf",
											params: {}
										};
										return c === null ? c = [e] : c.push(e), l++, X.errors = c, !1;
									}
									var f = r === l;
								} else var f = !0;
								if (f) {
									if (e.client_message_id !== void 0 && n.call(e, "client_message_id")) {
										let n = e.client_message_id, r = l;
										if (l === r) {
											if (typeof n == "string") {
												if (!u.test(n)) return X.errors = [{
													instancePath: t + "/client_message_id",
													schemaPath: "#/properties/client_message_id/pattern",
													keyword: "pattern",
													params: { pattern: "^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$" }
												}], !1;
											} else return X.errors = [{
												instancePath: t + "/client_message_id",
												schemaPath: "#/properties/client_message_id/type",
												keyword: "type",
												params: { type: "string" }
											}], !1;
										}
										var f = r === l;
									} else var f = !0;
									if (f) {
										if (e.historical !== void 0 && n.call(e, "historical")) {
											let n = e.historical, r = l;
											if (typeof n != "boolean") return X.errors = [{
												instancePath: t + "/historical",
												schemaPath: "#/properties/historical/type",
												keyword: "type",
												params: { type: "boolean" }
											}], !1;
											if (!0 !== n) return X.errors = [{
												instancePath: t + "/historical",
												schemaPath: "#/properties/historical/const",
												keyword: "const",
												params: { allowedValue: !0 }
											}], !1;
											var f = r === l;
										} else var f = !0;
										if (f) {
											if (e.message_id !== void 0 && n.call(e, "message_id")) {
												let n = e.message_id, r = l;
												if (l === r) {
													if (typeof n == "string") {
														if (!u.test(n)) return X.errors = [{
															instancePath: t + "/message_id",
															schemaPath: "#/properties/message_id/pattern",
															keyword: "pattern",
															params: { pattern: "^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$" }
														}], !1;
													} else return X.errors = [{
														instancePath: t + "/message_id",
														schemaPath: "#/properties/message_id/type",
														keyword: "type",
														params: { type: "string" }
													}], !1;
												}
												var f = r === l;
											} else var f = !0;
											if (f) {
												if (e.session_id !== void 0 && n.call(e, "session_id")) {
													let n = e.session_id, r = l;
													if (l === r) {
														if (typeof n == "string") {
															if (!u.test(n)) return X.errors = [{
																instancePath: t + "/session_id",
																schemaPath: "#/properties/session_id/pattern",
																keyword: "pattern",
																params: { pattern: "^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$" }
															}], !1;
														} else return X.errors = [{
															instancePath: t + "/session_id",
															schemaPath: "#/properties/session_id/type",
															keyword: "type",
															params: { type: "string" }
														}], !1;
													}
													var f = r === l;
												} else var f = !0;
												if (f) {
													if (e.state !== void 0 && n.call(e, "state")) {
														let n = e.state, r = l;
														if (typeof n != "string") return X.errors = [{
															instancePath: t + "/state",
															schemaPath: "#/properties/state/type",
															keyword: "type",
															params: { type: "string" }
														}], !1;
														if (n !== "completed" && n !== "pending" && n !== "interrupted") return X.errors = [{
															instancePath: t + "/state",
															schemaPath: "#/properties/state/enum",
															keyword: "enum",
															params: { allowedValues: Jt.properties.state.enum }
														}], !1;
														var f = r === l;
													} else var f = !0;
													if (f) {
														if (e.user_text !== void 0 && n.call(e, "user_text")) {
															let n = e.user_text, r = l;
															if (l === r) {
																if (typeof n == "string") {
																	if (h(n) > 4e3) return X.errors = [{
																		instancePath: t + "/user_text",
																		schemaPath: "#/properties/user_text/maxLength",
																		keyword: "maxLength",
																		params: { limit: 4e3 }
																	}], !1;
																	if (h(n) < 1) return X.errors = [{
																		instancePath: t + "/user_text",
																		schemaPath: "#/properties/user_text/minLength",
																		keyword: "minLength",
																		params: { limit: 1 }
																	}], !1;
																} else return X.errors = [{
																	instancePath: t + "/user_text",
																	schemaPath: "#/properties/user_text/type",
																	keyword: "type",
																	params: { type: "string" }
																}], !1;
															}
															var f = r === l;
														} else var f = !0;
													}
												}
											}
										}
									}
								}
							}
						}
					}
				}
			} else return X.errors = [{
				instancePath: t,
				schemaPath: "#/type",
				keyword: "type",
				params: { type: "object" }
			}], !1;
		}
		return X.errors = c, l === 0;
	}
	X.evaluated = {
		props: !0,
		dynamicProps: !1,
		dynamicItems: !1
	};
	function Yt(e, { instancePath: t = "", parentData: r, parentDataProperty: i, rootData: a = e, dynamicAnchors: o = {} } = {}) {
		let s = null, c = 0, l = Yt.evaluated;
		if (l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0) {
			if (e && typeof e == "object" && !Array.isArray(e)) {
				let r;
				if ((e.session_id === void 0 || !n.call(e, "session_id")) && (r = "session_id") || (e.observed_revision === void 0 || !n.call(e, "observed_revision")) && (r = "observed_revision") || (e.items === void 0 || !n.call(e, "items")) && (r = "items") || (e.next_cursor === void 0 || !n.call(e, "next_cursor")) && (r = "next_cursor")) return Yt.errors = [{
					instancePath: t,
					schemaPath: "#/required",
					keyword: "required",
					params: { missingProperty: r }
				}], !1;
				{
					let r = c;
					for (let n of Object.keys(e)) if (n !== "items" && n !== "next_cursor" && n !== "observed_revision" && n !== "session_id") return Yt.errors = [{
						instancePath: t,
						schemaPath: "#/additionalProperties",
						keyword: "additionalProperties",
						params: { additionalProperty: n }
					}], !1;
					if (r === c) {
						if (e.items !== void 0 && n.call(e, "items")) {
							let n = e.items, r = c;
							if (c === r) {
								if (Array.isArray(n)) {
									if (n.length > 50) return Yt.errors = [{
										instancePath: t + "/items",
										schemaPath: "#/properties/items/maxItems",
										keyword: "maxItems",
										params: { limit: 50 }
									}], !1;
									{
										let e = n.length;
										for (let r = 0; r < e; r++) {
											let e = c;
											if (X(n[r], {
												instancePath: t + "/items/" + r,
												parentData: n,
												parentDataProperty: r,
												rootData: a,
												dynamicAnchors: o
											}) || (s = s === null ? X.errors : s.concat(X.errors), c = s.length), e !== c) break;
										}
									}
								} else return Yt.errors = [{
									instancePath: t + "/items",
									schemaPath: "#/properties/items/type",
									keyword: "type",
									params: { type: "array" }
								}], !1;
							}
							var d = r === c;
						} else var d = !0;
						if (d) {
							if (e.next_cursor !== void 0 && n.call(e, "next_cursor")) {
								let n = e.next_cursor, r = c, i = c, a = !1, o = c;
								if (c === o) {
									if (typeof n == "string") {
										if (h(n) > 2048) {
											let e = {
												instancePath: t + "/next_cursor",
												schemaPath: "#/properties/next_cursor/anyOf/0/maxLength",
												keyword: "maxLength",
												params: { limit: 2048 }
											};
											s === null ? s = [e] : s.push(e), c++;
										}
									} else {
										let e = {
											instancePath: t + "/next_cursor",
											schemaPath: "#/properties/next_cursor/anyOf/0/type",
											keyword: "type",
											params: { type: "string" }
										};
										s === null ? s = [e] : s.push(e), c++;
									}
								}
								var f = o === c;
								a ||= f;
								let l = c;
								if (n !== null) {
									let e = {
										instancePath: t + "/next_cursor",
										schemaPath: "#/properties/next_cursor/anyOf/1/type",
										keyword: "type",
										params: { type: "null" }
									};
									s === null ? s = [e] : s.push(e), c++;
								}
								var f = l === c;
								if (a ||= f, a) c = i, s !== null && (i ? s.length = i : s = null);
								else {
									let e = {
										instancePath: t + "/next_cursor",
										schemaPath: "#/properties/next_cursor/anyOf",
										keyword: "anyOf",
										params: {}
									};
									return s === null ? s = [e] : s.push(e), c++, Yt.errors = s, !1;
								}
								var d = r === c;
							} else var d = !0;
							if (d) {
								if (e.observed_revision !== void 0 && n.call(e, "observed_revision")) {
									let n = e.observed_revision, r = c;
									if (typeof n != "number" || n % 1 || isNaN(n) || !isFinite(n)) return Yt.errors = [{
										instancePath: t + "/observed_revision",
										schemaPath: "#/properties/observed_revision/type",
										keyword: "type",
										params: { type: "integer" }
									}], !1;
									if (c === r && typeof n == "number" && isFinite(n)) {
										if (n > 2147483647 || isNaN(n)) return Yt.errors = [{
											instancePath: t + "/observed_revision",
											schemaPath: "#/properties/observed_revision/maximum",
											keyword: "maximum",
											params: {
												comparison: "<=",
												limit: 2147483647
											}
										}], !1;
										if (n < 0 || isNaN(n)) return Yt.errors = [{
											instancePath: t + "/observed_revision",
											schemaPath: "#/properties/observed_revision/minimum",
											keyword: "minimum",
											params: {
												comparison: ">=",
												limit: 0
											}
										}], !1;
									}
									var d = r === c;
								} else var d = !0;
								if (d) {
									if (e.session_id !== void 0 && n.call(e, "session_id")) {
										let n = e.session_id, r = c;
										if (c === r) {
											if (typeof n == "string") {
												if (!u.test(n)) return Yt.errors = [{
													instancePath: t + "/session_id",
													schemaPath: "#/properties/session_id/pattern",
													keyword: "pattern",
													params: { pattern: "^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$" }
												}], !1;
											} else return Yt.errors = [{
												instancePath: t + "/session_id",
												schemaPath: "#/properties/session_id/type",
												keyword: "type",
												params: { type: "string" }
											}], !1;
										}
										var d = r === c;
									} else var d = !0;
								}
							}
						}
					}
				}
			} else return Yt.errors = [{
				instancePath: t,
				schemaPath: "#/type",
				keyword: "type",
				params: { type: "object" }
			}], !1;
		}
		return Yt.errors = s, c === 0;
	}
	Yt.evaluated = {
		props: !0,
		dynamicProps: !1,
		dynamicItems: !1
	};
	function Xt(e, { instancePath: t = "", parentData: r, parentDataProperty: i, rootData: a = e, dynamicAnchors: o = {} } = {}) {
		let s = null, c = 0, l = Xt.evaluated;
		if (l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0) {
			if (e && typeof e == "object" && !Array.isArray(e)) {
				let r;
				if ((e.data === void 0 || !n.call(e, "data")) && (r = "data") || (e.meta === void 0 || !n.call(e, "meta")) && (r = "meta")) return Xt.errors = [{
					instancePath: t,
					schemaPath: "#/required",
					keyword: "required",
					params: { missingProperty: r }
				}], !1;
				{
					let r = c;
					for (let n of Object.keys(e)) if (n !== "data" && n !== "meta") return Xt.errors = [{
						instancePath: t,
						schemaPath: "#/additionalProperties",
						keyword: "additionalProperties",
						params: { additionalProperty: n }
					}], !1;
					if (r === c) {
						if (e.data !== void 0 && n.call(e, "data")) {
							let n = c;
							Yt(e.data, {
								instancePath: t + "/data",
								parentData: e,
								parentDataProperty: "data",
								rootData: a,
								dynamicAnchors: o
							}) || (s = s === null ? Yt.errors : s.concat(Yt.errors), c = s.length);
							var u = n === c;
						} else var u = !0;
						if (u) {
							if (e.meta !== void 0 && n.call(e, "meta")) {
								let n = c;
								y(e.meta, {
									instancePath: t + "/meta",
									parentData: e,
									parentDataProperty: "meta",
									rootData: a,
									dynamicAnchors: o
								}) || (s = s === null ? y.errors : s.concat(y.errors), c = s.length);
								var u = n === c;
							} else var u = !0;
						}
					}
				}
			} else return Xt.errors = [{
				instancePath: t,
				schemaPath: "#/type",
				keyword: "type",
				params: { type: "object" }
			}], !1;
		}
		return Xt.errors = s, c === 0;
	}
	Xt.evaluated = {
		props: !0,
		dynamicProps: !1,
		dynamicItems: !1
	}, e.v51 = Qt;
	function Zt(e, { instancePath: t = "", parentData: r, parentDataProperty: i, rootData: a = e, dynamicAnchors: o = {} } = {}) {
		let s = Zt.evaluated;
		if (s.dynamicProps && (s.props = void 0), s.dynamicItems && (s.items = void 0), e && typeof e == "object" && !Array.isArray(e)) {
			let r;
			if ((e.state === void 0 || !n.call(e, "state")) && (r = "state")) return Zt.errors = [{
				instancePath: t,
				schemaPath: "#/required",
				keyword: "required",
				params: { missingProperty: r }
			}], !1;
			for (let n of Object.keys(e)) if (n !== "state") return Zt.errors = [{
				instancePath: t,
				schemaPath: "#/additionalProperties",
				keyword: "additionalProperties",
				params: { additionalProperty: n }
			}], !1;
			if (e.state !== void 0 && n.call(e, "state")) {
				let n = e.state;
				if (typeof n != "string") return Zt.errors = [{
					instancePath: t + "/state",
					schemaPath: "#/properties/state/type",
					keyword: "type",
					params: { type: "string" }
				}], !1;
				if (n !== "not_created") return Zt.errors = [{
					instancePath: t + "/state",
					schemaPath: "#/properties/state/const",
					keyword: "const",
					params: { allowedValue: "not_created" }
				}], !1;
			}
		} else return Zt.errors = [{
			instancePath: t,
			schemaPath: "#/type",
			keyword: "type",
			params: { type: "object" }
		}], !1;
		return Zt.errors = null, !0;
	}
	Zt.evaluated = {
		props: !0,
		dynamicProps: !1,
		dynamicItems: !1
	};
	function Qt(e, { instancePath: t = "", parentData: r, parentDataProperty: i, rootData: a = e, dynamicAnchors: o = {} } = {}) {
		let s = null, c = 0, l = Qt.evaluated;
		if (l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0) {
			if (e && typeof e == "object" && !Array.isArray(e)) {
				let r;
				if ((e.data === void 0 || !n.call(e, "data")) && (r = "data") || (e.meta === void 0 || !n.call(e, "meta")) && (r = "meta")) return Qt.errors = [{
					instancePath: t,
					schemaPath: "#/required",
					keyword: "required",
					params: { missingProperty: r }
				}], !1;
				{
					let r = c;
					for (let n of Object.keys(e)) if (n !== "data" && n !== "meta") return Qt.errors = [{
						instancePath: t,
						schemaPath: "#/additionalProperties",
						keyword: "additionalProperties",
						params: { additionalProperty: n }
					}], !1;
					if (r === c) {
						if (e.data !== void 0 && n.call(e, "data")) {
							let n = e.data, r = c, i = c, l = !1, p = c;
							I(n, {
								instancePath: t + "/data",
								parentData: e,
								parentDataProperty: "data",
								rootData: a,
								dynamicAnchors: o
							}) || (s = s === null ? I.errors : s.concat(I.errors), c = s.length);
							var u = p === c;
							if (l ||= u, u) var d = !0;
							let m = c;
							Zt(n, {
								instancePath: t + "/data",
								parentData: e,
								parentDataProperty: "data",
								rootData: a,
								dynamicAnchors: o
							}) || (s = s === null ? Zt.errors : s.concat(Zt.errors), c = s.length);
							var u = m === c;
							if (l ||= u, u && d !== !0 && (d = !0), l) c = i, s !== null && (i ? s.length = i : s = null);
							else {
								let e = {
									instancePath: t + "/data",
									schemaPath: "#/properties/data/anyOf",
									keyword: "anyOf",
									params: {}
								};
								return s === null ? s = [e] : s.push(e), c++, Qt.errors = s, !1;
							}
							var f = r === c;
						} else var f = !0;
						if (f) {
							if (e.meta !== void 0 && n.call(e, "meta")) {
								let n = c;
								y(e.meta, {
									instancePath: t + "/meta",
									parentData: e,
									parentDataProperty: "meta",
									rootData: a,
									dynamicAnchors: o
								}) || (s = s === null ? y.errors : s.concat(y.errors), c = s.length);
								var f = n === c;
							} else var f = !0;
						}
					}
				}
			} else return Qt.errors = [{
				instancePath: t,
				schemaPath: "#/type",
				keyword: "type",
				params: { type: "object" }
			}], !1;
		}
		return Qt.errors = s, c === 0;
	}
	Qt.evaluated = {
		props: !0,
		dynamicProps: !1,
		dynamicItems: !1
	}, e.v52 = nn;
	var $t = {
		additionalProperties: !1,
		properties: {
			calculated_at: {
				pattern: "^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}(?:\\.\\d{1,6})?Z$",
				title: "Calculated At",
				type: "string"
			},
			eligibility_version: {
				anyOf: [{
					maxLength: 200,
					minLength: 1,
					type: "string"
				}, { type: "null" }],
				title: "Eligibility Version"
			},
			no_hold: {
				const: !0,
				default: !0,
				title: "No Hold",
				type: "boolean"
			},
			ref: { $ref: "urn:car-shopping-assistant:contract:1#/$defs/InventoryRef" },
			rules_version: {
				anyOf: [{
					maxLength: 200,
					minLength: 1,
					type: "string"
				}, { type: "null" }],
				title: "Rules Version"
			},
			slots: {
				items: { $ref: "urn:car-shopping-assistant:contract:1#/$defs/ViewingSlot" },
				maxItems: 24,
				title: "Slots",
				type: "array"
			},
			state: {
				enum: [
					"available",
					"no_valid_slots",
					"ineligible",
					"unconfigured"
				],
				title: "State",
				type: "string"
			}
		},
		required: [
			"ref",
			"state",
			"rules_version",
			"eligibility_version",
			"calculated_at",
			"slots"
		],
		title: "ViewingOptions",
		type: "object"
	};
	function en(e, { instancePath: t = "", parentData: r, parentDataProperty: a, rootData: o = e, dynamicAnchors: s = {} } = {}) {
		let c = en.evaluated;
		if (c.dynamicProps && (c.props = void 0), c.dynamicItems && (c.items = void 0), e && typeof e == "object" && !Array.isArray(e)) {
			let r;
			if ((e.starts_at_utc === void 0 || !n.call(e, "starts_at_utc")) && (r = "starts_at_utc") || (e.ends_at_utc === void 0 || !n.call(e, "ends_at_utc")) && (r = "ends_at_utc")) return en.errors = [{
				instancePath: t,
				schemaPath: "#/required",
				keyword: "required",
				params: { missingProperty: r }
			}], !1;
			for (let n of Object.keys(e)) if (n !== "ends_at_utc" && n !== "starts_at_utc" && n !== "timezone") return en.errors = [{
				instancePath: t,
				schemaPath: "#/additionalProperties",
				keyword: "additionalProperties",
				params: { additionalProperty: n }
			}], !1;
			if (e.ends_at_utc !== void 0 && n.call(e, "ends_at_utc")) {
				let n = e.ends_at_utc;
				if (typeof n == "string") {
					if (!i.test(n)) return en.errors = [{
						instancePath: t + "/ends_at_utc",
						schemaPath: "#/properties/ends_at_utc/pattern",
						keyword: "pattern",
						params: { pattern: "^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}(?:\\.\\d{1,6})?Z$" }
					}], !1;
				} else return en.errors = [{
					instancePath: t + "/ends_at_utc",
					schemaPath: "#/properties/ends_at_utc/type",
					keyword: "type",
					params: { type: "string" }
				}], !1;
				var l = !0;
			} else var l = !0;
			if (l) {
				if (e.starts_at_utc !== void 0 && n.call(e, "starts_at_utc")) {
					let n = e.starts_at_utc;
					if (typeof n == "string") {
						if (!i.test(n)) return en.errors = [{
							instancePath: t + "/starts_at_utc",
							schemaPath: "#/properties/starts_at_utc/pattern",
							keyword: "pattern",
							params: { pattern: "^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}(?:\\.\\d{1,6})?Z$" }
						}], !1;
					} else return en.errors = [{
						instancePath: t + "/starts_at_utc",
						schemaPath: "#/properties/starts_at_utc/type",
						keyword: "type",
						params: { type: "string" }
					}], !1;
					var l = !0;
				} else var l = !0;
				if (l) {
					if (e.timezone !== void 0 && n.call(e, "timezone")) {
						let n = e.timezone;
						if (typeof n != "string") return en.errors = [{
							instancePath: t + "/timezone",
							schemaPath: "#/properties/timezone/type",
							keyword: "type",
							params: { type: "string" }
						}], !1;
						if (n !== "Asia/Dubai") return en.errors = [{
							instancePath: t + "/timezone",
							schemaPath: "#/properties/timezone/const",
							keyword: "const",
							params: { allowedValue: "Asia/Dubai" }
						}], !1;
						var l = !0;
					} else var l = !0;
				}
			}
		} else return en.errors = [{
			instancePath: t,
			schemaPath: "#/type",
			keyword: "type",
			params: { type: "object" }
		}], !1;
		return en.errors = null, !0;
	}
	en.evaluated = {
		props: !0,
		dynamicProps: !1,
		dynamicItems: !1
	};
	function tn(e, { instancePath: t = "", parentData: r, parentDataProperty: a, rootData: o = e, dynamicAnchors: s = {} } = {}) {
		let c = null, u = 0, d = tn.evaluated;
		if (d.dynamicProps && (d.props = void 0), d.dynamicItems && (d.items = void 0), u === 0) {
			if (e && typeof e == "object" && !Array.isArray(e)) {
				let r;
				if ((e.ref === void 0 || !n.call(e, "ref")) && (r = "ref") || (e.state === void 0 || !n.call(e, "state")) && (r = "state") || (e.rules_version === void 0 || !n.call(e, "rules_version")) && (r = "rules_version") || (e.eligibility_version === void 0 || !n.call(e, "eligibility_version")) && (r = "eligibility_version") || (e.calculated_at === void 0 || !n.call(e, "calculated_at")) && (r = "calculated_at") || (e.slots === void 0 || !n.call(e, "slots")) && (r = "slots")) return tn.errors = [{
					instancePath: t,
					schemaPath: "#/required",
					keyword: "required",
					params: { missingProperty: r }
				}], !1;
				{
					let r = u;
					for (let n of Object.keys(e)) if (n !== "calculated_at" && n !== "eligibility_version" && n !== "no_hold" && n !== "ref" && n !== "rules_version" && n !== "slots" && n !== "state") return tn.errors = [{
						instancePath: t,
						schemaPath: "#/additionalProperties",
						keyword: "additionalProperties",
						params: { additionalProperty: n }
					}], !1;
					if (r === u) {
						if (e.calculated_at !== void 0 && n.call(e, "calculated_at")) {
							let n = e.calculated_at, r = u;
							if (u === r) {
								if (typeof n == "string") {
									if (!i.test(n)) return tn.errors = [{
										instancePath: t + "/calculated_at",
										schemaPath: "#/properties/calculated_at/pattern",
										keyword: "pattern",
										params: { pattern: "^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}(?:\\.\\d{1,6})?Z$" }
									}], !1;
								} else return tn.errors = [{
									instancePath: t + "/calculated_at",
									schemaPath: "#/properties/calculated_at/type",
									keyword: "type",
									params: { type: "string" }
								}], !1;
							}
							var f = r === u;
						} else var f = !0;
						if (f) {
							if (e.eligibility_version !== void 0 && n.call(e, "eligibility_version")) {
								let n = e.eligibility_version, r = u, i = u, a = !1, o = u;
								if (u === o) {
									if (typeof n == "string") {
										if (h(n) > 200) {
											let e = {
												instancePath: t + "/eligibility_version",
												schemaPath: "#/properties/eligibility_version/anyOf/0/maxLength",
												keyword: "maxLength",
												params: { limit: 200 }
											};
											c === null ? c = [e] : c.push(e), u++;
										} else if (h(n) < 1) {
											let e = {
												instancePath: t + "/eligibility_version",
												schemaPath: "#/properties/eligibility_version/anyOf/0/minLength",
												keyword: "minLength",
												params: { limit: 1 }
											};
											c === null ? c = [e] : c.push(e), u++;
										}
									} else {
										let e = {
											instancePath: t + "/eligibility_version",
											schemaPath: "#/properties/eligibility_version/anyOf/0/type",
											keyword: "type",
											params: { type: "string" }
										};
										c === null ? c = [e] : c.push(e), u++;
									}
								}
								var p = o === u;
								a ||= p;
								let s = u;
								if (n !== null) {
									let e = {
										instancePath: t + "/eligibility_version",
										schemaPath: "#/properties/eligibility_version/anyOf/1/type",
										keyword: "type",
										params: { type: "null" }
									};
									c === null ? c = [e] : c.push(e), u++;
								}
								var p = s === u;
								if (a ||= p, a) u = i, c !== null && (i ? c.length = i : c = null);
								else {
									let e = {
										instancePath: t + "/eligibility_version",
										schemaPath: "#/properties/eligibility_version/anyOf",
										keyword: "anyOf",
										params: {}
									};
									return c === null ? c = [e] : c.push(e), u++, tn.errors = c, !1;
								}
								var f = r === u;
							} else var f = !0;
							if (f) {
								if (e.no_hold !== void 0 && n.call(e, "no_hold")) {
									let n = e.no_hold, r = u;
									if (typeof n != "boolean") return tn.errors = [{
										instancePath: t + "/no_hold",
										schemaPath: "#/properties/no_hold/type",
										keyword: "type",
										params: { type: "boolean" }
									}], !1;
									if (!0 !== n) return tn.errors = [{
										instancePath: t + "/no_hold",
										schemaPath: "#/properties/no_hold/const",
										keyword: "const",
										params: { allowedValue: !0 }
									}], !1;
									var f = r === u;
								} else var f = !0;
								if (f) {
									if (e.ref !== void 0 && n.call(e, "ref")) {
										let n = u;
										l(e.ref, {
											instancePath: t + "/ref",
											parentData: e,
											parentDataProperty: "ref",
											rootData: o,
											dynamicAnchors: s
										}) || (c = c === null ? l.errors : c.concat(l.errors), u = c.length);
										var f = n === u;
									} else var f = !0;
									if (f) {
										if (e.rules_version !== void 0 && n.call(e, "rules_version")) {
											let n = e.rules_version, r = u, i = u, a = !1, o = u;
											if (u === o) {
												if (typeof n == "string") {
													if (h(n) > 200) {
														let e = {
															instancePath: t + "/rules_version",
															schemaPath: "#/properties/rules_version/anyOf/0/maxLength",
															keyword: "maxLength",
															params: { limit: 200 }
														};
														c === null ? c = [e] : c.push(e), u++;
													} else if (h(n) < 1) {
														let e = {
															instancePath: t + "/rules_version",
															schemaPath: "#/properties/rules_version/anyOf/0/minLength",
															keyword: "minLength",
															params: { limit: 1 }
														};
														c === null ? c = [e] : c.push(e), u++;
													}
												} else {
													let e = {
														instancePath: t + "/rules_version",
														schemaPath: "#/properties/rules_version/anyOf/0/type",
														keyword: "type",
														params: { type: "string" }
													};
													c === null ? c = [e] : c.push(e), u++;
												}
											}
											var m = o === u;
											a ||= m;
											let s = u;
											if (n !== null) {
												let e = {
													instancePath: t + "/rules_version",
													schemaPath: "#/properties/rules_version/anyOf/1/type",
													keyword: "type",
													params: { type: "null" }
												};
												c === null ? c = [e] : c.push(e), u++;
											}
											var m = s === u;
											if (a ||= m, a) u = i, c !== null && (i ? c.length = i : c = null);
											else {
												let e = {
													instancePath: t + "/rules_version",
													schemaPath: "#/properties/rules_version/anyOf",
													keyword: "anyOf",
													params: {}
												};
												return c === null ? c = [e] : c.push(e), u++, tn.errors = c, !1;
											}
											var f = r === u;
										} else var f = !0;
										if (f) {
											if (e.slots !== void 0 && n.call(e, "slots")) {
												let n = e.slots, r = u;
												if (u === r) {
													if (Array.isArray(n)) {
														if (n.length > 24) return tn.errors = [{
															instancePath: t + "/slots",
															schemaPath: "#/properties/slots/maxItems",
															keyword: "maxItems",
															params: { limit: 24 }
														}], !1;
														{
															let e = n.length;
															for (let r = 0; r < e; r++) {
																let e = u;
																if (en(n[r], {
																	instancePath: t + "/slots/" + r,
																	parentData: n,
																	parentDataProperty: r,
																	rootData: o,
																	dynamicAnchors: s
																}) || (c = c === null ? en.errors : c.concat(en.errors), u = c.length), e !== u) break;
															}
														}
													} else return tn.errors = [{
														instancePath: t + "/slots",
														schemaPath: "#/properties/slots/type",
														keyword: "type",
														params: { type: "array" }
													}], !1;
												}
												var f = r === u;
											} else var f = !0;
											if (f) {
												if (e.state !== void 0 && n.call(e, "state")) {
													let n = e.state, r = u;
													if (typeof n != "string") return tn.errors = [{
														instancePath: t + "/state",
														schemaPath: "#/properties/state/type",
														keyword: "type",
														params: { type: "string" }
													}], !1;
													if (n !== "available" && n !== "no_valid_slots" && n !== "ineligible" && n !== "unconfigured") return tn.errors = [{
														instancePath: t + "/state",
														schemaPath: "#/properties/state/enum",
														keyword: "enum",
														params: { allowedValues: $t.properties.state.enum }
													}], !1;
													var f = r === u;
												} else var f = !0;
											}
										}
									}
								}
							}
						}
					}
				}
			} else return tn.errors = [{
				instancePath: t,
				schemaPath: "#/type",
				keyword: "type",
				params: { type: "object" }
			}], !1;
		}
		return tn.errors = c, u === 0;
	}
	tn.evaluated = {
		props: !0,
		dynamicProps: !1,
		dynamicItems: !1
	};
	function nn(e, { instancePath: t = "", parentData: r, parentDataProperty: i, rootData: a = e, dynamicAnchors: o = {} } = {}) {
		let s = null, c = 0, l = nn.evaluated;
		if (l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0) {
			if (e && typeof e == "object" && !Array.isArray(e)) {
				let r;
				if ((e.data === void 0 || !n.call(e, "data")) && (r = "data") || (e.meta === void 0 || !n.call(e, "meta")) && (r = "meta")) return nn.errors = [{
					instancePath: t,
					schemaPath: "#/required",
					keyword: "required",
					params: { missingProperty: r }
				}], !1;
				{
					let r = c;
					for (let n of Object.keys(e)) if (n !== "data" && n !== "meta") return nn.errors = [{
						instancePath: t,
						schemaPath: "#/additionalProperties",
						keyword: "additionalProperties",
						params: { additionalProperty: n }
					}], !1;
					if (r === c) {
						if (e.data !== void 0 && n.call(e, "data")) {
							let n = c;
							tn(e.data, {
								instancePath: t + "/data",
								parentData: e,
								parentDataProperty: "data",
								rootData: a,
								dynamicAnchors: o
							}) || (s = s === null ? tn.errors : s.concat(tn.errors), c = s.length);
							var u = n === c;
						} else var u = !0;
						if (u) {
							if (e.meta !== void 0 && n.call(e, "meta")) {
								let n = c;
								y(e.meta, {
									instancePath: t + "/meta",
									parentData: e,
									parentDataProperty: "meta",
									rootData: a,
									dynamicAnchors: o
								}) || (s = s === null ? y.errors : s.concat(y.errors), c = s.length);
								var u = n === c;
							} else var u = !0;
						}
					}
				}
			} else return nn.errors = [{
				instancePath: t,
				schemaPath: "#/type",
				keyword: "type",
				params: { type: "object" }
			}], !1;
		}
		return nn.errors = s, c === 0;
	}
	nn.evaluated = {
		props: !0,
		dynamicProps: !1,
		dynamicItems: !1
	}, e.v53 = on;
	var rn = {
		additionalProperties: !1,
		properties: {
			code: {
				enum: /* @__PURE__ */ "VALIDATION_ERROR.INPUT_TOO_LARGE.UNSUPPORTED_CONTENT_TYPE.IDENTITY_REQUIRED.ORIGIN_DENIED.CSRF_DENIED.HOST_DENIED.NOT_FOUND.REVISION_CONFLICT.REVIEW_STALE.IDEMPOTENCY_CONFLICT.CAPACITY_UNAVAILABLE.ELIGIBILITY_UNAVAILABLE.RULES_UNAVAILABLE.UNSUPPORTED_STATE.SNAPSHOT_STALE.PRESENTATION_INVALID.OPERATION_UNRESOLVED.STORE_GENERATION_CHANGED.REPLAY_EXPIRED.STORE_UNAVAILABLE.STORE_BUSY.PROVIDER_UNAVAILABLE.PROVIDER_TIMEOUT.RATE_LIMITED.INTERNAL_ERROR.LEAD_EXISTS.LEAD_REVISION_CONFLICT".split("."),
				title: "Code",
				type: "string"
			},
			fields: {
				default: [],
				items: { $ref: "urn:car-shopping-assistant:contract:1#/$defs/FieldIssue" },
				maxItems: 24,
				title: "Fields",
				type: "array"
			},
			message: {
				maxLength: 2e3,
				minLength: 1,
				title: "Message",
				type: "string"
			},
			operation_key: {
				anyOf: [{
					pattern: "^[A-Za-z0-9_-]{43}$",
					type: "string"
				}, { type: "null" }],
				title: "Operation Key"
			},
			outcome_state: {
				anyOf: [{
					enum: [
						"unresolved",
						"rejected",
						"succeeded"
					],
					type: "string"
				}, { type: "null" }],
				title: "Outcome State"
			},
			request_id: {
				pattern: "^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$",
				title: "Request Id",
				type: "string"
			},
			retry_action: {
				enum: [
					"none",
					"read",
					"same_operation_only"
				],
				title: "Retry Action",
				type: "string"
			},
			retryable: {
				title: "Retryable",
				type: "boolean"
			}
		},
		required: [
			"code",
			"message",
			"request_id",
			"retryable",
			"retry_action"
		],
		title: "ApiError",
		type: "object"
	};
	function an(e, { instancePath: t = "", parentData: r, parentDataProperty: i, rootData: a = e, dynamicAnchors: o = {} } = {}) {
		let s = an.evaluated;
		if (s.dynamicProps && (s.props = void 0), s.dynamicItems && (s.items = void 0), e && typeof e == "object" && !Array.isArray(e)) {
			let r;
			if ((e.path === void 0 || !n.call(e, "path")) && (r = "path") || (e.code === void 0 || !n.call(e, "code")) && (r = "code")) return an.errors = [{
				instancePath: t,
				schemaPath: "#/required",
				keyword: "required",
				params: { missingProperty: r }
			}], !1;
			for (let n of Object.keys(e)) if (n !== "code" && n !== "path") return an.errors = [{
				instancePath: t,
				schemaPath: "#/additionalProperties",
				keyword: "additionalProperties",
				params: { additionalProperty: n }
			}], !1;
			if (e.code !== void 0 && n.call(e, "code")) {
				let n = e.code;
				if (typeof n == "string") {
					if (h(n) > 200) return an.errors = [{
						instancePath: t + "/code",
						schemaPath: "#/properties/code/maxLength",
						keyword: "maxLength",
						params: { limit: 200 }
					}], !1;
					if (h(n) < 1) return an.errors = [{
						instancePath: t + "/code",
						schemaPath: "#/properties/code/minLength",
						keyword: "minLength",
						params: { limit: 1 }
					}], !1;
				} else return an.errors = [{
					instancePath: t + "/code",
					schemaPath: "#/properties/code/type",
					keyword: "type",
					params: { type: "string" }
				}], !1;
				var c = !0;
			} else var c = !0;
			if (c) {
				if (e.path !== void 0 && n.call(e, "path")) {
					let n = e.path;
					if (Array.isArray(n)) {
						if (n.length > 8) return an.errors = [{
							instancePath: t + "/path",
							schemaPath: "#/properties/path/maxItems",
							keyword: "maxItems",
							params: { limit: 8 }
						}], !1;
						{
							let e = n.length;
							for (let r = 0; r < e; r++) {
								let e = n[r];
								if (typeof e == "string") {
									if (h(e) > 200) return an.errors = [{
										instancePath: t + "/path/" + r,
										schemaPath: "#/properties/path/items/maxLength",
										keyword: "maxLength",
										params: { limit: 200 }
									}], !1;
									if (h(e) < 1) return an.errors = [{
										instancePath: t + "/path/" + r,
										schemaPath: "#/properties/path/items/minLength",
										keyword: "minLength",
										params: { limit: 1 }
									}], !1;
								} else return an.errors = [{
									instancePath: t + "/path/" + r,
									schemaPath: "#/properties/path/items/type",
									keyword: "type",
									params: { type: "string" }
								}], !1;
							}
						}
					} else return an.errors = [{
						instancePath: t + "/path",
						schemaPath: "#/properties/path/type",
						keyword: "type",
						params: { type: "array" }
					}], !1;
					var c = !0;
				} else var c = !0;
			}
		} else return an.errors = [{
			instancePath: t,
			schemaPath: "#/type",
			keyword: "type",
			params: { type: "object" }
		}], !1;
		return an.errors = null, !0;
	}
	an.evaluated = {
		props: !0,
		dynamicProps: !1,
		dynamicItems: !1
	};
	function Z(e, { instancePath: t = "", parentData: r, parentDataProperty: i, rootData: a = e, dynamicAnchors: o = {} } = {}) {
		let s = null, c = 0, l = Z.evaluated;
		if (l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0) {
			if (e && typeof e == "object" && !Array.isArray(e)) {
				let r;
				if ((e.code === void 0 || !n.call(e, "code")) && (r = "code") || (e.message === void 0 || !n.call(e, "message")) && (r = "message") || (e.request_id === void 0 || !n.call(e, "request_id")) && (r = "request_id") || (e.retryable === void 0 || !n.call(e, "retryable")) && (r = "retryable") || (e.retry_action === void 0 || !n.call(e, "retry_action")) && (r = "retry_action")) return Z.errors = [{
					instancePath: t,
					schemaPath: "#/required",
					keyword: "required",
					params: { missingProperty: r }
				}], !1;
				{
					let r = c;
					for (let n of Object.keys(e)) if (n !== "code" && n !== "fields" && n !== "message" && n !== "operation_key" && n !== "outcome_state" && n !== "request_id" && n !== "retry_action" && n !== "retryable") return Z.errors = [{
						instancePath: t,
						schemaPath: "#/additionalProperties",
						keyword: "additionalProperties",
						params: { additionalProperty: n }
					}], !1;
					if (r === c) {
						if (e.code !== void 0 && n.call(e, "code")) {
							let n = e.code, r = c;
							if (typeof n != "string") return Z.errors = [{
								instancePath: t + "/code",
								schemaPath: "#/properties/code/type",
								keyword: "type",
								params: { type: "string" }
							}], !1;
							if (n !== "VALIDATION_ERROR" && n !== "INPUT_TOO_LARGE" && n !== "UNSUPPORTED_CONTENT_TYPE" && n !== "IDENTITY_REQUIRED" && n !== "ORIGIN_DENIED" && n !== "CSRF_DENIED" && n !== "HOST_DENIED" && n !== "NOT_FOUND" && n !== "REVISION_CONFLICT" && n !== "REVIEW_STALE" && n !== "IDEMPOTENCY_CONFLICT" && n !== "CAPACITY_UNAVAILABLE" && n !== "ELIGIBILITY_UNAVAILABLE" && n !== "RULES_UNAVAILABLE" && n !== "UNSUPPORTED_STATE" && n !== "SNAPSHOT_STALE" && n !== "PRESENTATION_INVALID" && n !== "OPERATION_UNRESOLVED" && n !== "STORE_GENERATION_CHANGED" && n !== "REPLAY_EXPIRED" && n !== "STORE_UNAVAILABLE" && n !== "STORE_BUSY" && n !== "PROVIDER_UNAVAILABLE" && n !== "PROVIDER_TIMEOUT" && n !== "RATE_LIMITED" && n !== "INTERNAL_ERROR" && n !== "LEAD_EXISTS" && n !== "LEAD_REVISION_CONFLICT") return Z.errors = [{
								instancePath: t + "/code",
								schemaPath: "#/properties/code/enum",
								keyword: "enum",
								params: { allowedValues: rn.properties.code.enum }
							}], !1;
							var d = r === c;
						} else var d = !0;
						if (d) {
							if (e.fields !== void 0 && n.call(e, "fields")) {
								let n = e.fields, r = c;
								if (c === r) {
									if (Array.isArray(n)) {
										if (n.length > 24) return Z.errors = [{
											instancePath: t + "/fields",
											schemaPath: "#/properties/fields/maxItems",
											keyword: "maxItems",
											params: { limit: 24 }
										}], !1;
										{
											let e = n.length;
											for (let r = 0; r < e; r++) {
												let e = c;
												if (an(n[r], {
													instancePath: t + "/fields/" + r,
													parentData: n,
													parentDataProperty: r,
													rootData: a,
													dynamicAnchors: o
												}) || (s = s === null ? an.errors : s.concat(an.errors), c = s.length), e !== c) break;
											}
										}
									} else return Z.errors = [{
										instancePath: t + "/fields",
										schemaPath: "#/properties/fields/type",
										keyword: "type",
										params: { type: "array" }
									}], !1;
								}
								var d = r === c;
							} else var d = !0;
							if (d) {
								if (e.message !== void 0 && n.call(e, "message")) {
									let n = e.message, r = c;
									if (c === r) {
										if (typeof n == "string") {
											if (h(n) > 2e3) return Z.errors = [{
												instancePath: t + "/message",
												schemaPath: "#/properties/message/maxLength",
												keyword: "maxLength",
												params: { limit: 2e3 }
											}], !1;
											if (h(n) < 1) return Z.errors = [{
												instancePath: t + "/message",
												schemaPath: "#/properties/message/minLength",
												keyword: "minLength",
												params: { limit: 1 }
											}], !1;
										} else return Z.errors = [{
											instancePath: t + "/message",
											schemaPath: "#/properties/message/type",
											keyword: "type",
											params: { type: "string" }
										}], !1;
									}
									var d = r === c;
								} else var d = !0;
								if (d) {
									if (e.operation_key !== void 0 && n.call(e, "operation_key")) {
										let n = e.operation_key, r = c, i = c, a = !1, o = c;
										if (c === o) {
											if (typeof n == "string") {
												if (!g.test(n)) {
													let e = {
														instancePath: t + "/operation_key",
														schemaPath: "#/properties/operation_key/anyOf/0/pattern",
														keyword: "pattern",
														params: { pattern: "^[A-Za-z0-9_-]{43}$" }
													};
													s === null ? s = [e] : s.push(e), c++;
												}
											} else {
												let e = {
													instancePath: t + "/operation_key",
													schemaPath: "#/properties/operation_key/anyOf/0/type",
													keyword: "type",
													params: { type: "string" }
												};
												s === null ? s = [e] : s.push(e), c++;
											}
										}
										var f = o === c;
										a ||= f;
										let l = c;
										if (n !== null) {
											let e = {
												instancePath: t + "/operation_key",
												schemaPath: "#/properties/operation_key/anyOf/1/type",
												keyword: "type",
												params: { type: "null" }
											};
											s === null ? s = [e] : s.push(e), c++;
										}
										var f = l === c;
										if (a ||= f, a) c = i, s !== null && (i ? s.length = i : s = null);
										else {
											let e = {
												instancePath: t + "/operation_key",
												schemaPath: "#/properties/operation_key/anyOf",
												keyword: "anyOf",
												params: {}
											};
											return s === null ? s = [e] : s.push(e), c++, Z.errors = s, !1;
										}
										var d = r === c;
									} else var d = !0;
									if (d) {
										if (e.outcome_state !== void 0 && n.call(e, "outcome_state")) {
											let n = e.outcome_state, r = c, i = c, a = !1, o = c;
											if (typeof n != "string") {
												let e = {
													instancePath: t + "/outcome_state",
													schemaPath: "#/properties/outcome_state/anyOf/0/type",
													keyword: "type",
													params: { type: "string" }
												};
												s === null ? s = [e] : s.push(e), c++;
											}
											if (n !== "unresolved" && n !== "rejected" && n !== "succeeded") {
												let e = {
													instancePath: t + "/outcome_state",
													schemaPath: "#/properties/outcome_state/anyOf/0/enum",
													keyword: "enum",
													params: { allowedValues: rn.properties.outcome_state.anyOf[0].enum }
												};
												s === null ? s = [e] : s.push(e), c++;
											}
											var p = o === c;
											a ||= p;
											let l = c;
											if (n !== null) {
												let e = {
													instancePath: t + "/outcome_state",
													schemaPath: "#/properties/outcome_state/anyOf/1/type",
													keyword: "type",
													params: { type: "null" }
												};
												s === null ? s = [e] : s.push(e), c++;
											}
											var p = l === c;
											if (a ||= p, a) c = i, s !== null && (i ? s.length = i : s = null);
											else {
												let e = {
													instancePath: t + "/outcome_state",
													schemaPath: "#/properties/outcome_state/anyOf",
													keyword: "anyOf",
													params: {}
												};
												return s === null ? s = [e] : s.push(e), c++, Z.errors = s, !1;
											}
											var d = r === c;
										} else var d = !0;
										if (d) {
											if (e.request_id !== void 0 && n.call(e, "request_id")) {
												let n = e.request_id, r = c;
												if (c === r) {
													if (typeof n == "string") {
														if (!u.test(n)) return Z.errors = [{
															instancePath: t + "/request_id",
															schemaPath: "#/properties/request_id/pattern",
															keyword: "pattern",
															params: { pattern: "^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$" }
														}], !1;
													} else return Z.errors = [{
														instancePath: t + "/request_id",
														schemaPath: "#/properties/request_id/type",
														keyword: "type",
														params: { type: "string" }
													}], !1;
												}
												var d = r === c;
											} else var d = !0;
											if (d) {
												if (e.retry_action !== void 0 && n.call(e, "retry_action")) {
													let n = e.retry_action, r = c;
													if (typeof n != "string") return Z.errors = [{
														instancePath: t + "/retry_action",
														schemaPath: "#/properties/retry_action/type",
														keyword: "type",
														params: { type: "string" }
													}], !1;
													if (n !== "none" && n !== "read" && n !== "same_operation_only") return Z.errors = [{
														instancePath: t + "/retry_action",
														schemaPath: "#/properties/retry_action/enum",
														keyword: "enum",
														params: { allowedValues: rn.properties.retry_action.enum }
													}], !1;
													var d = r === c;
												} else var d = !0;
												if (d) {
													if (e.retryable !== void 0 && n.call(e, "retryable")) {
														let n = c;
														if (typeof e.retryable != "boolean") return Z.errors = [{
															instancePath: t + "/retryable",
															schemaPath: "#/properties/retryable/type",
															keyword: "type",
															params: { type: "boolean" }
														}], !1;
														var d = n === c;
													} else var d = !0;
												}
											}
										}
									}
								}
							}
						}
					}
				}
			} else return Z.errors = [{
				instancePath: t,
				schemaPath: "#/type",
				keyword: "type",
				params: { type: "object" }
			}], !1;
		}
		return Z.errors = s, c === 0;
	}
	Z.evaluated = {
		props: !0,
		dynamicProps: !1,
		dynamicItems: !1
	};
	function on(e, { instancePath: t = "", parentData: r, parentDataProperty: i, rootData: a = e, dynamicAnchors: o = {} } = {}) {
		let s = null, c = 0, l = on.evaluated;
		if (l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0) {
			if (e && typeof e == "object" && !Array.isArray(e)) {
				let r;
				if ((e.error === void 0 || !n.call(e, "error")) && (r = "error")) return on.errors = [{
					instancePath: t,
					schemaPath: "#/required",
					keyword: "required",
					params: { missingProperty: r }
				}], !1;
				{
					let r = c;
					for (let n of Object.keys(e)) if (n !== "error") return on.errors = [{
						instancePath: t,
						schemaPath: "#/additionalProperties",
						keyword: "additionalProperties",
						params: { additionalProperty: n }
					}], !1;
					r === c && e.error !== void 0 && n.call(e, "error") && (Z(e.error, {
						instancePath: t + "/error",
						parentData: e,
						parentDataProperty: "error",
						rootData: a,
						dynamicAnchors: o
					}) || (s = s === null ? Z.errors : s.concat(Z.errors), c = s.length));
				}
			} else return on.errors = [{
				instancePath: t,
				schemaPath: "#/type",
				keyword: "type",
				params: { type: "object" }
			}], !1;
		}
		return on.errors = s, c === 0;
	}
	on.evaluated = {
		props: !0,
		dynamicProps: !1,
		dynamicItems: !1
	}, e.v65 = sn;
	function sn(e, { instancePath: t = "", parentData: r, parentDataProperty: i, rootData: a = e, dynamicAnchors: o = {} } = {}) {
		let s = null, c = 0, l = sn.evaluated;
		if (l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0) {
			if (e && typeof e == "object" && !Array.isArray(e)) {
				let r;
				if ((e.notice_version === void 0 || !n.call(e, "notice_version")) && (r = "notice_version") || (e.notice_acknowledged === void 0 || !n.call(e, "notice_acknowledged")) && (r = "notice_acknowledged")) return sn.errors = [{
					instancePath: t,
					schemaPath: "#/required",
					keyword: "required",
					params: { missingProperty: r }
				}], !1;
				{
					let r = c;
					for (let n of Object.keys(e)) if (n !== "display_name" && n !== "notice_acknowledged" && n !== "notice_version") return sn.errors = [{
						instancePath: t,
						schemaPath: "#/additionalProperties",
						keyword: "additionalProperties",
						params: { additionalProperty: n }
					}], !1;
					if (r === c) {
						if (e.display_name !== void 0 && n.call(e, "display_name")) {
							let n = e.display_name, r = c, i = c, a = !1, o = c;
							if (c === o) {
								if (typeof n == "string") {
									if (h(n) > 100) {
										let e = {
											instancePath: t + "/display_name",
											schemaPath: "#/properties/display_name/anyOf/0/maxLength",
											keyword: "maxLength",
											params: { limit: 100 }
										};
										s === null ? s = [e] : s.push(e), c++;
									} else if (h(n) < 1) {
										let e = {
											instancePath: t + "/display_name",
											schemaPath: "#/properties/display_name/anyOf/0/minLength",
											keyword: "minLength",
											params: { limit: 1 }
										};
										s === null ? s = [e] : s.push(e), c++;
									}
								} else {
									let e = {
										instancePath: t + "/display_name",
										schemaPath: "#/properties/display_name/anyOf/0/type",
										keyword: "type",
										params: { type: "string" }
									};
									s === null ? s = [e] : s.push(e), c++;
								}
							}
							var u = o === c;
							a ||= u;
							let l = c;
							if (n !== null) {
								let e = {
									instancePath: t + "/display_name",
									schemaPath: "#/properties/display_name/anyOf/1/type",
									keyword: "type",
									params: { type: "null" }
								};
								s === null ? s = [e] : s.push(e), c++;
							}
							var u = l === c;
							if (a ||= u, a) c = i, s !== null && (i ? s.length = i : s = null);
							else {
								let e = {
									instancePath: t + "/display_name",
									schemaPath: "#/properties/display_name/anyOf",
									keyword: "anyOf",
									params: {}
								};
								return s === null ? s = [e] : s.push(e), c++, sn.errors = s, !1;
							}
							var d = r === c;
						} else var d = !0;
						if (d) {
							if (e.notice_acknowledged !== void 0 && n.call(e, "notice_acknowledged")) {
								let n = c;
								if (typeof e.notice_acknowledged != "boolean") return sn.errors = [{
									instancePath: t + "/notice_acknowledged",
									schemaPath: "#/properties/notice_acknowledged/type",
									keyword: "type",
									params: { type: "boolean" }
								}], !1;
								var d = n === c;
							} else var d = !0;
							if (d) {
								if (e.notice_version !== void 0 && n.call(e, "notice_version")) {
									let n = e.notice_version, r = c;
									if (typeof n != "string") return sn.errors = [{
										instancePath: t + "/notice_version",
										schemaPath: "#/properties/notice_version/type",
										keyword: "type",
										params: { type: "string" }
									}], !1;
									if (n !== "DEMO-POLICY-1") return sn.errors = [{
										instancePath: t + "/notice_version",
										schemaPath: "#/properties/notice_version/const",
										keyword: "const",
										params: { allowedValue: "DEMO-POLICY-1" }
									}], !1;
									var d = r === c;
								} else var d = !0;
							}
						}
					}
				}
			} else return sn.errors = [{
				instancePath: t,
				schemaPath: "#/type",
				keyword: "type",
				params: { type: "object" }
			}], !1;
		}
		return sn.errors = s, c === 0;
	}
	sn.evaluated = {
		props: !0,
		dynamicProps: !1,
		dynamicItems: !1
	}, e.v66 = cn;
	function cn(e, { instancePath: t = "", parentData: r, parentDataProperty: i, rootData: a = e, dynamicAnchors: o = {} } = {}) {
		let s = cn.evaluated;
		if (s.dynamicProps && (s.props = void 0), s.dynamicItems && (s.items = void 0), e && typeof e == "object" && !Array.isArray(e)) {
			let r;
			if ((e.acknowledge_loss_of_access === void 0 || !n.call(e, "acknowledge_loss_of_access")) && (r = "acknowledge_loss_of_access")) return cn.errors = [{
				instancePath: t,
				schemaPath: "#/required",
				keyword: "required",
				params: { missingProperty: r }
			}], !1;
			for (let n of Object.keys(e)) if (n !== "acknowledge_loss_of_access") return cn.errors = [{
				instancePath: t,
				schemaPath: "#/additionalProperties",
				keyword: "additionalProperties",
				params: { additionalProperty: n }
			}], !1;
			if (e.acknowledge_loss_of_access !== void 0 && n.call(e, "acknowledge_loss_of_access") && typeof e.acknowledge_loss_of_access != "boolean") return cn.errors = [{
				instancePath: t + "/acknowledge_loss_of_access",
				schemaPath: "#/properties/acknowledge_loss_of_access/type",
				keyword: "type",
				params: { type: "boolean" }
			}], !1;
		} else return cn.errors = [{
			instancePath: t,
			schemaPath: "#/type",
			keyword: "type",
			params: { type: "object" }
		}], !1;
		return cn.errors = null, !0;
	}
	cn.evaluated = {
		props: !0,
		dynamicProps: !1,
		dynamicItems: !1
	}, e.v75 = ln;
	function ln(e, { instancePath: t = "", parentData: r, parentDataProperty: i, rootData: a = e, dynamicAnchors: o = {} } = {}) {
		let s = null, c = 0, l = ln.evaluated;
		if (l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0) {
			if (e && typeof e == "object" && !Array.isArray(e)) {
				let r;
				if ((e.client_action_id === void 0 || !n.call(e, "client_action_id")) && (r = "client_action_id") || (e.session_id === void 0 || !n.call(e, "session_id")) && (r = "session_id") || (e.intent === void 0 || !n.call(e, "intent")) && (r = "intent") || (e.values === void 0 || !n.call(e, "values")) && (r = "values")) return ln.errors = [{
					instancePath: t,
					schemaPath: "#/required",
					keyword: "required",
					params: { missingProperty: r }
				}], !1;
				{
					let r = c;
					for (let n of Object.keys(e)) if (n !== "client_action_id" && n !== "intent" && n !== "session_id" && n !== "values") return ln.errors = [{
						instancePath: t,
						schemaPath: "#/additionalProperties",
						keyword: "additionalProperties",
						params: { additionalProperty: n }
					}], !1;
					if (r === c) {
						if (e.client_action_id !== void 0 && n.call(e, "client_action_id")) {
							let n = e.client_action_id, r = c;
							if (c === r) {
								if (typeof n == "string") {
									if (!u.test(n)) return ln.errors = [{
										instancePath: t + "/client_action_id",
										schemaPath: "#/properties/client_action_id/pattern",
										keyword: "pattern",
										params: { pattern: "^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$" }
									}], !1;
								} else return ln.errors = [{
									instancePath: t + "/client_action_id",
									schemaPath: "#/properties/client_action_id/type",
									keyword: "type",
									params: { type: "string" }
								}], !1;
							}
							var d = r === c;
						} else var d = !0;
						if (d) {
							if (e.intent !== void 0 && n.call(e, "intent")) {
								let n = e.intent, r = c;
								if (typeof n != "string") return ln.errors = [{
									instancePath: t + "/intent",
									schemaPath: "#/properties/intent/type",
									keyword: "type",
									params: { type: "string" }
								}], !1;
								if (n !== "save_local_enquiry") return ln.errors = [{
									instancePath: t + "/intent",
									schemaPath: "#/properties/intent/const",
									keyword: "const",
									params: { allowedValue: "save_local_enquiry" }
								}], !1;
								var d = r === c;
							} else var d = !0;
							if (d) {
								if (e.session_id !== void 0 && n.call(e, "session_id")) {
									let n = e.session_id, r = c;
									if (c === r) {
										if (typeof n == "string") {
											if (!u.test(n)) return ln.errors = [{
												instancePath: t + "/session_id",
												schemaPath: "#/properties/session_id/pattern",
												keyword: "pattern",
												params: { pattern: "^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$" }
											}], !1;
										} else return ln.errors = [{
											instancePath: t + "/session_id",
											schemaPath: "#/properties/session_id/type",
											keyword: "type",
											params: { type: "string" }
										}], !1;
									}
									var d = r === c;
								} else var d = !0;
								if (d) {
									if (e.values !== void 0 && n.call(e, "values")) {
										let n = c;
										E(e.values, {
											instancePath: t + "/values",
											parentData: e,
											parentDataProperty: "values",
											rootData: a,
											dynamicAnchors: o
										}) || (s = s === null ? E.errors : s.concat(E.errors), c = s.length);
										var d = n === c;
									} else var d = !0;
								}
							}
						}
					}
				}
			} else return ln.errors = [{
				instancePath: t,
				schemaPath: "#/type",
				keyword: "type",
				params: { type: "object" }
			}], !1;
		}
		return ln.errors = s, c === 0;
	}
	ln.evaluated = {
		props: !0,
		dynamicProps: !1,
		dynamicItems: !1
	}, e.v78 = un;
	function un(e, { instancePath: t = "", parentData: r, parentDataProperty: i, rootData: a = e, dynamicAnchors: o = {} } = {}) {
		let s = null, c = 0, l = un.evaluated;
		if (l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0) {
			if (e && typeof e == "object" && !Array.isArray(e)) {
				let r;
				if ((e.client_action_id === void 0 || !n.call(e, "client_action_id")) && (r = "client_action_id") || (e.expected_revision === void 0 || !n.call(e, "expected_revision")) && (r = "expected_revision") || (e.session_id === void 0 || !n.call(e, "session_id")) && (r = "session_id") || (e.intent === void 0 || !n.call(e, "intent")) && (r = "intent") || (e.values === void 0 || !n.call(e, "values")) && (r = "values")) return un.errors = [{
					instancePath: t,
					schemaPath: "#/required",
					keyword: "required",
					params: { missingProperty: r }
				}], !1;
				{
					let r = c;
					for (let n of Object.keys(e)) if (n !== "client_action_id" && n !== "expected_revision" && n !== "intent" && n !== "session_id" && n !== "values") return un.errors = [{
						instancePath: t,
						schemaPath: "#/additionalProperties",
						keyword: "additionalProperties",
						params: { additionalProperty: n }
					}], !1;
					if (r === c) {
						if (e.client_action_id !== void 0 && n.call(e, "client_action_id")) {
							let n = e.client_action_id, r = c;
							if (c === r) {
								if (typeof n == "string") {
									if (!u.test(n)) return un.errors = [{
										instancePath: t + "/client_action_id",
										schemaPath: "#/properties/client_action_id/pattern",
										keyword: "pattern",
										params: { pattern: "^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$" }
									}], !1;
								} else return un.errors = [{
									instancePath: t + "/client_action_id",
									schemaPath: "#/properties/client_action_id/type",
									keyword: "type",
									params: { type: "string" }
								}], !1;
							}
							var d = r === c;
						} else var d = !0;
						if (d) {
							if (e.expected_revision !== void 0 && n.call(e, "expected_revision")) {
								let n = e.expected_revision, r = c;
								if (typeof n != "number" || n % 1 || isNaN(n) || !isFinite(n)) return un.errors = [{
									instancePath: t + "/expected_revision",
									schemaPath: "#/properties/expected_revision/type",
									keyword: "type",
									params: { type: "integer" }
								}], !1;
								if (c === r && typeof n == "number" && isFinite(n)) {
									if (n > 2147483647 || isNaN(n)) return un.errors = [{
										instancePath: t + "/expected_revision",
										schemaPath: "#/properties/expected_revision/maximum",
										keyword: "maximum",
										params: {
											comparison: "<=",
											limit: 2147483647
										}
									}], !1;
									if (n < 0 || isNaN(n)) return un.errors = [{
										instancePath: t + "/expected_revision",
										schemaPath: "#/properties/expected_revision/minimum",
										keyword: "minimum",
										params: {
											comparison: ">=",
											limit: 0
										}
									}], !1;
								}
								var d = r === c;
							} else var d = !0;
							if (d) {
								if (e.intent !== void 0 && n.call(e, "intent")) {
									let n = e.intent, r = c;
									if (typeof n != "string") return un.errors = [{
										instancePath: t + "/intent",
										schemaPath: "#/properties/intent/type",
										keyword: "type",
										params: { type: "string" }
									}], !1;
									if (n !== "correct_local_enquiry") return un.errors = [{
										instancePath: t + "/intent",
										schemaPath: "#/properties/intent/const",
										keyword: "const",
										params: { allowedValue: "correct_local_enquiry" }
									}], !1;
									var d = r === c;
								} else var d = !0;
								if (d) {
									if (e.session_id !== void 0 && n.call(e, "session_id")) {
										let n = e.session_id, r = c;
										if (c === r) {
											if (typeof n == "string") {
												if (!u.test(n)) return un.errors = [{
													instancePath: t + "/session_id",
													schemaPath: "#/properties/session_id/pattern",
													keyword: "pattern",
													params: { pattern: "^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$" }
												}], !1;
											} else return un.errors = [{
												instancePath: t + "/session_id",
												schemaPath: "#/properties/session_id/type",
												keyword: "type",
												params: { type: "string" }
											}], !1;
										}
										var d = r === c;
									} else var d = !0;
									if (d) {
										if (e.values !== void 0 && n.call(e, "values")) {
											let n = c;
											E(e.values, {
												instancePath: t + "/values",
												parentData: e,
												parentDataProperty: "values",
												rootData: a,
												dynamicAnchors: o
											}) || (s = s === null ? E.errors : s.concat(E.errors), c = s.length);
											var d = n === c;
										} else var d = !0;
									}
								}
							}
						}
					}
				}
			} else return un.errors = [{
				instancePath: t,
				schemaPath: "#/type",
				keyword: "type",
				params: { type: "object" }
			}], !1;
		}
		return un.errors = s, c === 0;
	}
	un.evaluated = {
		props: !0,
		dynamicProps: !1,
		dynamicItems: !1
	}, e.v84 = dn;
	function dn(e, { instancePath: t = "", parentData: r, parentDataProperty: i, rootData: a = e, dynamicAnchors: o = {} } = {}) {
		let s = dn.evaluated;
		if (s.dynamicProps && (s.props = void 0), s.dynamicItems && (s.items = void 0), e && typeof e == "object" && !Array.isArray(e)) {
			let r;
			if ((e.client_action_id === void 0 || !n.call(e, "client_action_id")) && (r = "client_action_id") || (e.expected_revision === void 0 || !n.call(e, "expected_revision")) && (r = "expected_revision")) return dn.errors = [{
				instancePath: t,
				schemaPath: "#/required",
				keyword: "required",
				params: { missingProperty: r }
			}], !1;
			for (let n of Object.keys(e)) if (n !== "client_action_id" && n !== "expected_revision") return dn.errors = [{
				instancePath: t,
				schemaPath: "#/additionalProperties",
				keyword: "additionalProperties",
				params: { additionalProperty: n }
			}], !1;
			if (e.client_action_id !== void 0 && n.call(e, "client_action_id")) {
				let n = e.client_action_id;
				if (typeof n == "string") {
					if (!u.test(n)) return dn.errors = [{
						instancePath: t + "/client_action_id",
						schemaPath: "#/properties/client_action_id/pattern",
						keyword: "pattern",
						params: { pattern: "^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$" }
					}], !1;
				} else return dn.errors = [{
					instancePath: t + "/client_action_id",
					schemaPath: "#/properties/client_action_id/type",
					keyword: "type",
					params: { type: "string" }
				}], !1;
				var c = !0;
			} else var c = !0;
			if (c) {
				if (e.expected_revision !== void 0 && n.call(e, "expected_revision")) {
					let n = e.expected_revision;
					if (typeof n != "number" || n % 1 || isNaN(n) || !isFinite(n)) return dn.errors = [{
						instancePath: t + "/expected_revision",
						schemaPath: "#/properties/expected_revision/type",
						keyword: "type",
						params: { type: "integer" }
					}], !1;
					if (typeof n == "number" && isFinite(n)) {
						if (n > 2147483647 || isNaN(n)) return dn.errors = [{
							instancePath: t + "/expected_revision",
							schemaPath: "#/properties/expected_revision/maximum",
							keyword: "maximum",
							params: {
								comparison: "<=",
								limit: 2147483647
							}
						}], !1;
						if (n < 0 || isNaN(n)) return dn.errors = [{
							instancePath: t + "/expected_revision",
							schemaPath: "#/properties/expected_revision/minimum",
							keyword: "minimum",
							params: {
								comparison: ">=",
								limit: 0
							}
						}], !1;
					}
					var c = !0;
				} else var c = !0;
			}
		} else return dn.errors = [{
			instancePath: t,
			schemaPath: "#/type",
			keyword: "type",
			params: { type: "object" }
		}], !1;
		return dn.errors = null, !0;
	}
	dn.evaluated = {
		props: !0,
		dynamicProps: !1,
		dynamicItems: !1
	}, e.v87 = pn;
	function fn(e, { instancePath: t = "", parentData: r, parentDataProperty: i, rootData: a = e, dynamicAnchors: o = {} } = {}) {
		let s = fn.evaluated;
		if (s.dynamicProps && (s.props = void 0), s.dynamicItems && (s.items = void 0), e && typeof e == "object" && !Array.isArray(e)) {
			let r;
			if ((e.intent_id === void 0 || !n.call(e, "intent_id")) && (r = "intent_id") || (e.created_revision === void 0 || !n.call(e, "created_revision")) && (r = "created_revision")) return fn.errors = [{
				instancePath: t,
				schemaPath: "#/required",
				keyword: "required",
				params: { missingProperty: r }
			}], !1;
			for (let n of Object.keys(e)) if (n !== "created_revision" && n !== "intent_id") return fn.errors = [{
				instancePath: t,
				schemaPath: "#/additionalProperties",
				keyword: "additionalProperties",
				params: { additionalProperty: n }
			}], !1;
			if (e.created_revision !== void 0 && n.call(e, "created_revision")) {
				let n = e.created_revision;
				if (typeof n != "number" || n % 1 || isNaN(n) || !isFinite(n)) return fn.errors = [{
					instancePath: t + "/created_revision",
					schemaPath: "#/properties/created_revision/type",
					keyword: "type",
					params: { type: "integer" }
				}], !1;
				if (typeof n == "number" && isFinite(n)) {
					if (n > 2147483647 || isNaN(n)) return fn.errors = [{
						instancePath: t + "/created_revision",
						schemaPath: "#/properties/created_revision/maximum",
						keyword: "maximum",
						params: {
							comparison: "<=",
							limit: 2147483647
						}
					}], !1;
					if (n < 0 || isNaN(n)) return fn.errors = [{
						instancePath: t + "/created_revision",
						schemaPath: "#/properties/created_revision/minimum",
						keyword: "minimum",
						params: {
							comparison: ">=",
							limit: 0
						}
					}], !1;
				}
				var c = !0;
			} else var c = !0;
			if (c) {
				if (e.intent_id !== void 0 && n.call(e, "intent_id")) {
					let n = e.intent_id;
					if (typeof n == "string") {
						if (!u.test(n)) return fn.errors = [{
							instancePath: t + "/intent_id",
							schemaPath: "#/properties/intent_id/pattern",
							keyword: "pattern",
							params: { pattern: "^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$" }
						}], !1;
					} else return fn.errors = [{
						instancePath: t + "/intent_id",
						schemaPath: "#/properties/intent_id/type",
						keyword: "type",
						params: { type: "string" }
					}], !1;
					var c = !0;
				} else var c = !0;
			}
		} else return fn.errors = [{
			instancePath: t,
			schemaPath: "#/type",
			keyword: "type",
			params: { type: "object" }
		}], !1;
		return fn.errors = null, !0;
	}
	fn.evaluated = {
		props: !0,
		dynamicProps: !1,
		dynamicItems: !1
	};
	function Q(e, { instancePath: t = "", parentData: r, parentDataProperty: i, rootData: a = e, dynamicAnchors: o = {} } = {}) {
		let s = Q.evaluated;
		if (s.dynamicProps && (s.props = void 0), s.dynamicItems && (s.items = void 0), e && typeof e == "object" && !Array.isArray(e)) {
			let r;
			if ((e.review_id === void 0 || !n.call(e, "review_id")) && (r = "review_id") || (e.expected_draft_revision === void 0 || !n.call(e, "expected_draft_revision")) && (r = "expected_draft_revision") || (e.operation_key === void 0 || !n.call(e, "operation_key")) && (r = "operation_key") || (e.rules_version === void 0 || !n.call(e, "rules_version")) && (r = "rules_version") || (e.store_generation === void 0 || !n.call(e, "store_generation")) && (r = "store_generation") || (e.confirmation === void 0 || !n.call(e, "confirmation")) && (r = "confirmation") || (e.draft_id === void 0 || !n.call(e, "draft_id")) && (r = "draft_id")) return Q.errors = [{
				instancePath: t,
				schemaPath: "#/required",
				keyword: "required",
				params: { missingProperty: r }
			}], !1;
			for (let n of Object.keys(e)) if (n !== "confirmation" && n !== "draft_id" && n !== "expected_draft_revision" && n !== "operation_key" && n !== "review_id" && n !== "rules_version" && n !== "store_generation") return Q.errors = [{
				instancePath: t,
				schemaPath: "#/additionalProperties",
				keyword: "additionalProperties",
				params: { additionalProperty: n }
			}], !1;
			if (e.confirmation !== void 0 && n.call(e, "confirmation")) {
				let n = e.confirmation;
				if (typeof n != "string") return Q.errors = [{
					instancePath: t + "/confirmation",
					schemaPath: "#/properties/confirmation/type",
					keyword: "type",
					params: { type: "string" }
				}], !1;
				if (n !== "confirm_simulated_viewing") return Q.errors = [{
					instancePath: t + "/confirmation",
					schemaPath: "#/properties/confirmation/const",
					keyword: "const",
					params: { allowedValue: "confirm_simulated_viewing" }
				}], !1;
				var c = !0;
			} else var c = !0;
			if (c) {
				if (e.draft_id !== void 0 && n.call(e, "draft_id")) {
					let n = e.draft_id;
					if (typeof n == "string") {
						if (!u.test(n)) return Q.errors = [{
							instancePath: t + "/draft_id",
							schemaPath: "#/properties/draft_id/pattern",
							keyword: "pattern",
							params: { pattern: "^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$" }
						}], !1;
					} else return Q.errors = [{
						instancePath: t + "/draft_id",
						schemaPath: "#/properties/draft_id/type",
						keyword: "type",
						params: { type: "string" }
					}], !1;
					var c = !0;
				} else var c = !0;
				if (c) {
					if (e.expected_draft_revision !== void 0 && n.call(e, "expected_draft_revision")) {
						let n = e.expected_draft_revision;
						if (typeof n != "number" || n % 1 || isNaN(n) || !isFinite(n)) return Q.errors = [{
							instancePath: t + "/expected_draft_revision",
							schemaPath: "#/properties/expected_draft_revision/type",
							keyword: "type",
							params: { type: "integer" }
						}], !1;
						if (typeof n == "number" && isFinite(n)) {
							if (n > 2147483647 || isNaN(n)) return Q.errors = [{
								instancePath: t + "/expected_draft_revision",
								schemaPath: "#/properties/expected_draft_revision/maximum",
								keyword: "maximum",
								params: {
									comparison: "<=",
									limit: 2147483647
								}
							}], !1;
							if (n < 0 || isNaN(n)) return Q.errors = [{
								instancePath: t + "/expected_draft_revision",
								schemaPath: "#/properties/expected_draft_revision/minimum",
								keyword: "minimum",
								params: {
									comparison: ">=",
									limit: 0
								}
							}], !1;
						}
						var c = !0;
					} else var c = !0;
					if (c) {
						if (e.operation_key !== void 0 && n.call(e, "operation_key")) {
							let n = e.operation_key;
							if (typeof n == "string") {
								if (!g.test(n)) return Q.errors = [{
									instancePath: t + "/operation_key",
									schemaPath: "#/properties/operation_key/pattern",
									keyword: "pattern",
									params: { pattern: "^[A-Za-z0-9_-]{43}$" }
								}], !1;
							} else return Q.errors = [{
								instancePath: t + "/operation_key",
								schemaPath: "#/properties/operation_key/type",
								keyword: "type",
								params: { type: "string" }
							}], !1;
							var c = !0;
						} else var c = !0;
						if (c) {
							if (e.review_id !== void 0 && n.call(e, "review_id")) {
								let n = e.review_id;
								if (typeof n == "string") {
									if (!u.test(n)) return Q.errors = [{
										instancePath: t + "/review_id",
										schemaPath: "#/properties/review_id/pattern",
										keyword: "pattern",
										params: { pattern: "^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$" }
									}], !1;
								} else return Q.errors = [{
									instancePath: t + "/review_id",
									schemaPath: "#/properties/review_id/type",
									keyword: "type",
									params: { type: "string" }
								}], !1;
								var c = !0;
							} else var c = !0;
							if (c) {
								if (e.rules_version !== void 0 && n.call(e, "rules_version")) {
									let n = e.rules_version;
									if (typeof n == "string") {
										if (h(n) > 200) return Q.errors = [{
											instancePath: t + "/rules_version",
											schemaPath: "#/properties/rules_version/maxLength",
											keyword: "maxLength",
											params: { limit: 200 }
										}], !1;
										if (h(n) < 1) return Q.errors = [{
											instancePath: t + "/rules_version",
											schemaPath: "#/properties/rules_version/minLength",
											keyword: "minLength",
											params: { limit: 1 }
										}], !1;
									} else return Q.errors = [{
										instancePath: t + "/rules_version",
										schemaPath: "#/properties/rules_version/type",
										keyword: "type",
										params: { type: "string" }
									}], !1;
									var c = !0;
								} else var c = !0;
								if (c) {
									if (e.store_generation !== void 0 && n.call(e, "store_generation")) {
										let n = e.store_generation;
										if (typeof n == "string") {
											if (!u.test(n)) return Q.errors = [{
												instancePath: t + "/store_generation",
												schemaPath: "#/properties/store_generation/pattern",
												keyword: "pattern",
												params: { pattern: "^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$" }
											}], !1;
										} else return Q.errors = [{
											instancePath: t + "/store_generation",
											schemaPath: "#/properties/store_generation/type",
											keyword: "type",
											params: { type: "string" }
										}], !1;
										var c = !0;
									} else var c = !0;
								}
							}
						}
					}
				}
			}
		} else return Q.errors = [{
			instancePath: t,
			schemaPath: "#/type",
			keyword: "type",
			params: { type: "object" }
		}], !1;
		return Q.errors = null, !0;
	}
	Q.evaluated = {
		props: !0,
		dynamicProps: !1,
		dynamicItems: !1
	};
	function pn(e, { instancePath: t = "", parentData: r, parentDataProperty: i, rootData: a = e, dynamicAnchors: o = {} } = {}) {
		let s = null, c = 0, d = pn.evaluated;
		if (d.dynamicProps && (d.props = void 0), d.dynamicItems && (d.items = void 0), c === 0) {
			if (e && typeof e == "object" && !Array.isArray(e)) {
				let r;
				if ((e.client_message_id === void 0 || !n.call(e, "client_message_id")) && (r = "client_message_id") || (e.expected_revision === void 0 || !n.call(e, "expected_revision")) && (r = "expected_revision") || (e.text === void 0 || !n.call(e, "text")) && (r = "text")) return pn.errors = [{
					instancePath: t,
					schemaPath: "#/required",
					keyword: "required",
					params: { missingProperty: r }
				}], !1;
				{
					let r = c;
					for (let n of Object.keys(e)) if (n !== "clarification_reply" && n !== "client_message_id" && n !== "expected_revision" && n !== "explicit_confirmation" && n !== "presentation_id" && n !== "selected_ref" && n !== "text") return pn.errors = [{
						instancePath: t,
						schemaPath: "#/additionalProperties",
						keyword: "additionalProperties",
						params: { additionalProperty: n }
					}], !1;
					if (r === c) {
						if (e.clarification_reply !== void 0 && n.call(e, "clarification_reply")) {
							let n = e.clarification_reply, r = c, i = c, l = !1, u = c;
							fn(n, {
								instancePath: t + "/clarification_reply",
								parentData: e,
								parentDataProperty: "clarification_reply",
								rootData: a,
								dynamicAnchors: o
							}) || (s = s === null ? fn.errors : s.concat(fn.errors), c = s.length);
							var f = u === c;
							l ||= f;
							let d = c;
							if (n !== null) {
								let e = {
									instancePath: t + "/clarification_reply",
									schemaPath: "#/properties/clarification_reply/anyOf/1/type",
									keyword: "type",
									params: { type: "null" }
								};
								s === null ? s = [e] : s.push(e), c++;
							}
							var f = d === c;
							if (l ||= f, l) c = i, s !== null && (i ? s.length = i : s = null);
							else {
								let e = {
									instancePath: t + "/clarification_reply",
									schemaPath: "#/properties/clarification_reply/anyOf",
									keyword: "anyOf",
									params: {}
								};
								return s === null ? s = [e] : s.push(e), c++, pn.errors = s, !1;
							}
							var p = r === c;
						} else var p = !0;
						if (p) {
							if (e.client_message_id !== void 0 && n.call(e, "client_message_id")) {
								let n = e.client_message_id, r = c;
								if (c === r) {
									if (typeof n == "string") {
										if (!u.test(n)) return pn.errors = [{
											instancePath: t + "/client_message_id",
											schemaPath: "#/properties/client_message_id/pattern",
											keyword: "pattern",
											params: { pattern: "^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$" }
										}], !1;
									} else return pn.errors = [{
										instancePath: t + "/client_message_id",
										schemaPath: "#/properties/client_message_id/type",
										keyword: "type",
										params: { type: "string" }
									}], !1;
								}
								var p = r === c;
							} else var p = !0;
							if (p) {
								if (e.expected_revision !== void 0 && n.call(e, "expected_revision")) {
									let n = e.expected_revision, r = c;
									if (typeof n != "number" || n % 1 || isNaN(n) || !isFinite(n)) return pn.errors = [{
										instancePath: t + "/expected_revision",
										schemaPath: "#/properties/expected_revision/type",
										keyword: "type",
										params: { type: "integer" }
									}], !1;
									if (c === r && typeof n == "number" && isFinite(n)) {
										if (n > 2147483647 || isNaN(n)) return pn.errors = [{
											instancePath: t + "/expected_revision",
											schemaPath: "#/properties/expected_revision/maximum",
											keyword: "maximum",
											params: {
												comparison: "<=",
												limit: 2147483647
											}
										}], !1;
										if (n < 0 || isNaN(n)) return pn.errors = [{
											instancePath: t + "/expected_revision",
											schemaPath: "#/properties/expected_revision/minimum",
											keyword: "minimum",
											params: {
												comparison: ">=",
												limit: 0
											}
										}], !1;
									}
									var p = r === c;
								} else var p = !0;
								if (p) {
									if (e.explicit_confirmation !== void 0 && n.call(e, "explicit_confirmation")) {
										let n = e.explicit_confirmation, r = c, i = c, l = !1, u = c;
										Q(n, {
											instancePath: t + "/explicit_confirmation",
											parentData: e,
											parentDataProperty: "explicit_confirmation",
											rootData: a,
											dynamicAnchors: o
										}) || (s = s === null ? Q.errors : s.concat(Q.errors), c = s.length);
										var m = u === c;
										l ||= m;
										let d = c;
										if (n !== null) {
											let e = {
												instancePath: t + "/explicit_confirmation",
												schemaPath: "#/properties/explicit_confirmation/anyOf/1/type",
												keyword: "type",
												params: { type: "null" }
											};
											s === null ? s = [e] : s.push(e), c++;
										}
										var m = d === c;
										if (l ||= m, l) c = i, s !== null && (i ? s.length = i : s = null);
										else {
											let e = {
												instancePath: t + "/explicit_confirmation",
												schemaPath: "#/properties/explicit_confirmation/anyOf",
												keyword: "anyOf",
												params: {}
											};
											return s === null ? s = [e] : s.push(e), c++, pn.errors = s, !1;
										}
										var p = r === c;
									} else var p = !0;
									if (p) {
										if (e.presentation_id !== void 0 && n.call(e, "presentation_id")) {
											let n = e.presentation_id, r = c, i = c, a = !1, o = c;
											if (c === o) {
												if (typeof n == "string") {
													if (!u.test(n)) {
														let e = {
															instancePath: t + "/presentation_id",
															schemaPath: "#/properties/presentation_id/anyOf/0/pattern",
															keyword: "pattern",
															params: { pattern: "^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$" }
														};
														s === null ? s = [e] : s.push(e), c++;
													}
												} else {
													let e = {
														instancePath: t + "/presentation_id",
														schemaPath: "#/properties/presentation_id/anyOf/0/type",
														keyword: "type",
														params: { type: "string" }
													};
													s === null ? s = [e] : s.push(e), c++;
												}
											}
											var g = o === c;
											a ||= g;
											let l = c;
											if (n !== null) {
												let e = {
													instancePath: t + "/presentation_id",
													schemaPath: "#/properties/presentation_id/anyOf/1/type",
													keyword: "type",
													params: { type: "null" }
												};
												s === null ? s = [e] : s.push(e), c++;
											}
											var g = l === c;
											if (a ||= g, a) c = i, s !== null && (i ? s.length = i : s = null);
											else {
												let e = {
													instancePath: t + "/presentation_id",
													schemaPath: "#/properties/presentation_id/anyOf",
													keyword: "anyOf",
													params: {}
												};
												return s === null ? s = [e] : s.push(e), c++, pn.errors = s, !1;
											}
											var p = r === c;
										} else var p = !0;
										if (p) {
											if (e.selected_ref !== void 0 && n.call(e, "selected_ref")) {
												let n = e.selected_ref, r = c, i = c, u = !1, d = c;
												l(n, {
													instancePath: t + "/selected_ref",
													parentData: e,
													parentDataProperty: "selected_ref",
													rootData: a,
													dynamicAnchors: o
												}) || (s = s === null ? l.errors : s.concat(l.errors), c = s.length);
												var _ = d === c;
												u ||= _;
												let f = c;
												if (n !== null) {
													let e = {
														instancePath: t + "/selected_ref",
														schemaPath: "#/properties/selected_ref/anyOf/1/type",
														keyword: "type",
														params: { type: "null" }
													};
													s === null ? s = [e] : s.push(e), c++;
												}
												var _ = f === c;
												if (u ||= _, u) c = i, s !== null && (i ? s.length = i : s = null);
												else {
													let e = {
														instancePath: t + "/selected_ref",
														schemaPath: "#/properties/selected_ref/anyOf",
														keyword: "anyOf",
														params: {}
													};
													return s === null ? s = [e] : s.push(e), c++, pn.errors = s, !1;
												}
												var p = r === c;
											} else var p = !0;
											if (p) {
												if (e.text !== void 0 && n.call(e, "text")) {
													let n = e.text, r = c;
													if (c === r) {
														if (typeof n == "string") {
															if (h(n) > 4e3) return pn.errors = [{
																instancePath: t + "/text",
																schemaPath: "#/properties/text/maxLength",
																keyword: "maxLength",
																params: { limit: 4e3 }
															}], !1;
															if (h(n) < 1) return pn.errors = [{
																instancePath: t + "/text",
																schemaPath: "#/properties/text/minLength",
																keyword: "minLength",
																params: { limit: 1 }
															}], !1;
														} else return pn.errors = [{
															instancePath: t + "/text",
															schemaPath: "#/properties/text/type",
															keyword: "type",
															params: { type: "string" }
														}], !1;
													}
													var p = r === c;
												} else var p = !0;
											}
										}
									}
								}
							}
						}
					}
				}
			} else return pn.errors = [{
				instancePath: t,
				schemaPath: "#/type",
				keyword: "type",
				params: { type: "object" }
			}], !1;
		}
		return pn.errors = s, c === 0;
	}
	pn.evaluated = {
		props: !0,
		dynamicProps: !1,
		dynamicItems: !1
	}, e.v102 = mn;
	function mn(e, { instancePath: t = "", parentData: r, parentDataProperty: i, rootData: a = e, dynamicAnchors: o = {} } = {}) {
		let s = null, c = 0, l = mn.evaluated;
		if (l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0) {
			if (e && typeof e == "object" && !Array.isArray(e)) {
				let r;
				if ((e.expected_revision === void 0 || !n.call(e, "expected_revision")) && (r = "expected_revision") || (e.client_action_id === void 0 || !n.call(e, "client_action_id")) && (r = "client_action_id") || (e.presentation === void 0 || !n.call(e, "presentation")) && (r = "presentation")) return mn.errors = [{
					instancePath: t,
					schemaPath: "#/required",
					keyword: "required",
					params: { missingProperty: r }
				}], !1;
				{
					let r = c;
					for (let n of Object.keys(e)) if (n !== "client_action_id" && n !== "expected_revision" && n !== "presentation") return mn.errors = [{
						instancePath: t,
						schemaPath: "#/additionalProperties",
						keyword: "additionalProperties",
						params: { additionalProperty: n }
					}], !1;
					if (r === c) {
						if (e.client_action_id !== void 0 && n.call(e, "client_action_id")) {
							let n = e.client_action_id, r = c;
							if (c === r) {
								if (typeof n == "string") {
									if (!u.test(n)) return mn.errors = [{
										instancePath: t + "/client_action_id",
										schemaPath: "#/properties/client_action_id/pattern",
										keyword: "pattern",
										params: { pattern: "^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$" }
									}], !1;
								} else return mn.errors = [{
									instancePath: t + "/client_action_id",
									schemaPath: "#/properties/client_action_id/type",
									keyword: "type",
									params: { type: "string" }
								}], !1;
							}
							var d = r === c;
						} else var d = !0;
						if (d) {
							if (e.expected_revision !== void 0 && n.call(e, "expected_revision")) {
								let n = e.expected_revision, r = c;
								if (typeof n != "number" || n % 1 || isNaN(n) || !isFinite(n)) return mn.errors = [{
									instancePath: t + "/expected_revision",
									schemaPath: "#/properties/expected_revision/type",
									keyword: "type",
									params: { type: "integer" }
								}], !1;
								if (c === r && typeof n == "number" && isFinite(n)) {
									if (n > 2147483647 || isNaN(n)) return mn.errors = [{
										instancePath: t + "/expected_revision",
										schemaPath: "#/properties/expected_revision/maximum",
										keyword: "maximum",
										params: {
											comparison: "<=",
											limit: 2147483647
										}
									}], !1;
									if (n < 0 || isNaN(n)) return mn.errors = [{
										instancePath: t + "/expected_revision",
										schemaPath: "#/properties/expected_revision/minimum",
										keyword: "minimum",
										params: {
											comparison: ">=",
											limit: 0
										}
									}], !1;
								}
								var d = r === c;
							} else var d = !0;
							if (d) {
								if (e.presentation !== void 0 && n.call(e, "presentation")) {
									let n = c;
									G(e.presentation, {
										instancePath: t + "/presentation",
										parentData: e,
										parentDataProperty: "presentation",
										rootData: a,
										dynamicAnchors: o
									}) || (s = s === null ? G.errors : s.concat(G.errors), c = s.length);
									var d = n === c;
								} else var d = !0;
							}
						}
					}
				}
			} else return mn.errors = [{
				instancePath: t,
				schemaPath: "#/type",
				keyword: "type",
				params: { type: "object" }
			}], !1;
		}
		return mn.errors = s, c === 0;
	}
	mn.evaluated = {
		props: !0,
		dynamicProps: !1,
		dynamicItems: !1
	}, e.v105 = hn;
	function hn(e, { instancePath: t = "", parentData: r, parentDataProperty: a, rootData: o = e, dynamicAnchors: s = {} } = {}) {
		let c = null, l = 0, d = hn.evaluated;
		if (d.dynamicProps && (d.props = void 0), d.dynamicItems && (d.items = void 0), l === 0) {
			if (e && typeof e == "object" && !Array.isArray(e)) {
				let r;
				if ((e.state === void 0 || !n.call(e, "state")) && (r = "state") || (e.context_id === void 0 || !n.call(e, "context_id")) && (r = "context_id") || (e.csrf_token === void 0 || !n.call(e, "csrf_token")) && (r = "csrf_token") || (e.expires_at === void 0 || !n.call(e, "expires_at")) && (r = "expires_at") || (e.display_name === void 0 || !n.call(e, "display_name")) && (r = "display_name")) return hn.errors = [{
					instancePath: t,
					schemaPath: "#/required",
					keyword: "required",
					params: { missingProperty: r }
				}], !1;
				{
					let r = l;
					for (let n of Object.keys(e)) if (n !== "context_id" && n !== "continuity" && n !== "csrf_token" && n !== "display_name" && n !== "expires_at" && n !== "state") return hn.errors = [{
						instancePath: t,
						schemaPath: "#/additionalProperties",
						keyword: "additionalProperties",
						params: { additionalProperty: n }
					}], !1;
					if (r === l) {
						if (e.context_id !== void 0 && n.call(e, "context_id")) {
							let n = e.context_id, r = l;
							if (l === r) {
								if (typeof n == "string") {
									if (!u.test(n)) return hn.errors = [{
										instancePath: t + "/context_id",
										schemaPath: "#/properties/context_id/pattern",
										keyword: "pattern",
										params: { pattern: "^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$" }
									}], !1;
								} else return hn.errors = [{
									instancePath: t + "/context_id",
									schemaPath: "#/properties/context_id/type",
									keyword: "type",
									params: { type: "string" }
								}], !1;
							}
							var f = r === l;
						} else var f = !0;
						if (f) {
							if (e.continuity !== void 0 && n.call(e, "continuity")) {
								let n = e.continuity, r = l;
								if (typeof n != "string") return hn.errors = [{
									instancePath: t + "/continuity",
									schemaPath: "#/properties/continuity/type",
									keyword: "type",
									params: { type: "string" }
								}], !1;
								if (n !== "this_browser_only") return hn.errors = [{
									instancePath: t + "/continuity",
									schemaPath: "#/properties/continuity/const",
									keyword: "const",
									params: { allowedValue: "this_browser_only" }
								}], !1;
								var f = r === l;
							} else var f = !0;
							if (f) {
								if (e.csrf_token !== void 0 && n.call(e, "csrf_token")) {
									let n = e.csrf_token, r = l;
									if (l === r) {
										if (typeof n == "string") {
											if (!g.test(n)) return hn.errors = [{
												instancePath: t + "/csrf_token",
												schemaPath: "#/properties/csrf_token/pattern",
												keyword: "pattern",
												params: { pattern: "^[A-Za-z0-9_-]{43}$" }
											}], !1;
										} else return hn.errors = [{
											instancePath: t + "/csrf_token",
											schemaPath: "#/properties/csrf_token/type",
											keyword: "type",
											params: { type: "string" }
										}], !1;
									}
									var f = r === l;
								} else var f = !0;
								if (f) {
									if (e.display_name !== void 0 && n.call(e, "display_name")) {
										let n = e.display_name, r = l, i = l, a = !1, o = l;
										if (l === o) {
											if (typeof n == "string") {
												if (h(n) > 100) {
													let e = {
														instancePath: t + "/display_name",
														schemaPath: "#/properties/display_name/anyOf/0/maxLength",
														keyword: "maxLength",
														params: { limit: 100 }
													};
													c === null ? c = [e] : c.push(e), l++;
												}
											} else {
												let e = {
													instancePath: t + "/display_name",
													schemaPath: "#/properties/display_name/anyOf/0/type",
													keyword: "type",
													params: { type: "string" }
												};
												c === null ? c = [e] : c.push(e), l++;
											}
										}
										var p = o === l;
										a ||= p;
										let s = l;
										if (n !== null) {
											let e = {
												instancePath: t + "/display_name",
												schemaPath: "#/properties/display_name/anyOf/1/type",
												keyword: "type",
												params: { type: "null" }
											};
											c === null ? c = [e] : c.push(e), l++;
										}
										var p = s === l;
										if (a ||= p, a) l = i, c !== null && (i ? c.length = i : c = null);
										else {
											let e = {
												instancePath: t + "/display_name",
												schemaPath: "#/properties/display_name/anyOf",
												keyword: "anyOf",
												params: {}
											};
											return c === null ? c = [e] : c.push(e), l++, hn.errors = c, !1;
										}
										var f = r === l;
									} else var f = !0;
									if (f) {
										if (e.expires_at !== void 0 && n.call(e, "expires_at")) {
											let n = e.expires_at, r = l;
											if (l === r) {
												if (typeof n == "string") {
													if (!i.test(n)) return hn.errors = [{
														instancePath: t + "/expires_at",
														schemaPath: "#/properties/expires_at/pattern",
														keyword: "pattern",
														params: { pattern: "^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}(?:\\.\\d{1,6})?Z$" }
													}], !1;
												} else return hn.errors = [{
													instancePath: t + "/expires_at",
													schemaPath: "#/properties/expires_at/type",
													keyword: "type",
													params: { type: "string" }
												}], !1;
											}
											var f = r === l;
										} else var f = !0;
										if (f) {
											if (e.state !== void 0 && n.call(e, "state")) {
												let n = e.state, r = l;
												if (typeof n != "string") return hn.errors = [{
													instancePath: t + "/state",
													schemaPath: "#/properties/state/type",
													keyword: "type",
													params: { type: "string" }
												}], !1;
												if (n !== "recognized") return hn.errors = [{
													instancePath: t + "/state",
													schemaPath: "#/properties/state/const",
													keyword: "const",
													params: { allowedValue: "recognized" }
												}], !1;
												var f = r === l;
											} else var f = !0;
										}
									}
								}
							}
						}
					}
				}
			} else return hn.errors = [{
				instancePath: t,
				schemaPath: "#/type",
				keyword: "type",
				params: { type: "object" }
			}], !1;
		}
		return hn.errors = c, l === 0;
	}
	hn.evaluated = {
		props: !0,
		dynamicProps: !1,
		dynamicItems: !1
	}, e.v111 = gn;
	function gn(e, { instancePath: t = "", parentData: r, parentDataProperty: i, rootData: a = e, dynamicAnchors: o = {} } = {}) {
		let c = null, l = 0, d = gn.evaluated;
		if (d.dynamicProps && (d.props = void 0), d.dynamicItems && (d.items = void 0), l === 0) {
			if (e && typeof e == "object" && !Array.isArray(e)) {
				let r;
				if ((e.client_request_id === void 0 || !n.call(e, "client_request_id")) && (r = "client_request_id")) return gn.errors = [{
					instancePath: t,
					schemaPath: "#/required",
					keyword: "required",
					params: { missingProperty: r }
				}], !1;
				{
					let r = l;
					for (let n of Object.keys(e)) if (n !== "client_request_id" && n !== "cursor" && n !== "filters" && n !== "page_size" && n !== "query" && n !== "snapshot_id" && n !== "soft_preferences") return gn.errors = [{
						instancePath: t,
						schemaPath: "#/additionalProperties",
						keyword: "additionalProperties",
						params: { additionalProperty: n }
					}], !1;
					if (r === l) {
						if (e.client_request_id !== void 0 && n.call(e, "client_request_id")) {
							let n = e.client_request_id, r = l;
							if (l === r) {
								if (typeof n == "string") {
									if (!u.test(n)) return gn.errors = [{
										instancePath: t + "/client_request_id",
										schemaPath: "#/properties/client_request_id/pattern",
										keyword: "pattern",
										params: { pattern: "^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$" }
									}], !1;
								} else return gn.errors = [{
									instancePath: t + "/client_request_id",
									schemaPath: "#/properties/client_request_id/type",
									keyword: "type",
									params: { type: "string" }
								}], !1;
							}
							var f = r === l;
						} else var f = !0;
						if (f) {
							if (e.cursor !== void 0 && n.call(e, "cursor")) {
								let n = e.cursor, r = l, i = l, a = !1, o = l;
								if (l === o) {
									if (typeof n == "string") {
										if (h(n) > 2048) {
											let e = {
												instancePath: t + "/cursor",
												schemaPath: "#/properties/cursor/anyOf/0/maxLength",
												keyword: "maxLength",
												params: { limit: 2048 }
											};
											c === null ? c = [e] : c.push(e), l++;
										}
									} else {
										let e = {
											instancePath: t + "/cursor",
											schemaPath: "#/properties/cursor/anyOf/0/type",
											keyword: "type",
											params: { type: "string" }
										};
										c === null ? c = [e] : c.push(e), l++;
									}
								}
								var p = o === l;
								a ||= p;
								let s = l;
								if (n !== null) {
									let e = {
										instancePath: t + "/cursor",
										schemaPath: "#/properties/cursor/anyOf/1/type",
										keyword: "type",
										params: { type: "null" }
									};
									c === null ? c = [e] : c.push(e), l++;
								}
								var p = s === l;
								if (a ||= p, a) l = i, c !== null && (i ? c.length = i : c = null);
								else {
									let e = {
										instancePath: t + "/cursor",
										schemaPath: "#/properties/cursor/anyOf",
										keyword: "anyOf",
										params: {}
									};
									return c === null ? c = [e] : c.push(e), l++, gn.errors = c, !1;
								}
								var f = r === l;
							} else var f = !0;
							if (f) {
								if (e.filters !== void 0 && n.call(e, "filters")) {
									let n = l;
									U(e.filters, {
										instancePath: t + "/filters",
										parentData: e,
										parentDataProperty: "filters",
										rootData: a,
										dynamicAnchors: o
									}) || (c = c === null ? U.errors : c.concat(U.errors), l = c.length);
									var f = n === l;
								} else var f = !0;
								if (f) {
									if (e.page_size !== void 0 && n.call(e, "page_size")) {
										let n = e.page_size, r = l;
										if (typeof n != "number" || n % 1 || isNaN(n) || !isFinite(n)) return gn.errors = [{
											instancePath: t + "/page_size",
											schemaPath: "#/properties/page_size/type",
											keyword: "type",
											params: { type: "integer" }
										}], !1;
										if (l === r && typeof n == "number" && isFinite(n)) {
											if (n > 50 || isNaN(n)) return gn.errors = [{
												instancePath: t + "/page_size",
												schemaPath: "#/properties/page_size/maximum",
												keyword: "maximum",
												params: {
													comparison: "<=",
													limit: 50
												}
											}], !1;
											if (n < 1 || isNaN(n)) return gn.errors = [{
												instancePath: t + "/page_size",
												schemaPath: "#/properties/page_size/minimum",
												keyword: "minimum",
												params: {
													comparison: ">=",
													limit: 1
												}
											}], !1;
										}
										var f = r === l;
									} else var f = !0;
									if (f) {
										if (e.query !== void 0 && n.call(e, "query")) {
											let n = e.query, r = l;
											if (l === r) {
												if (typeof n == "string") {
													if (h(n) > 1e3) return gn.errors = [{
														instancePath: t + "/query",
														schemaPath: "#/properties/query/maxLength",
														keyword: "maxLength",
														params: { limit: 1e3 }
													}], !1;
												} else return gn.errors = [{
													instancePath: t + "/query",
													schemaPath: "#/properties/query/type",
													keyword: "type",
													params: { type: "string" }
												}], !1;
											}
											var f = r === l;
										} else var f = !0;
										if (f) {
											if (e.snapshot_id !== void 0 && n.call(e, "snapshot_id")) {
												let n = e.snapshot_id, r = l, i = l, a = !1, o = l;
												if (l === o) {
													if (typeof n == "string") {
														if (!s.test(n)) {
															let e = {
																instancePath: t + "/snapshot_id",
																schemaPath: "#/properties/snapshot_id/anyOf/0/pattern",
																keyword: "pattern",
																params: { pattern: "^[0-9a-f]{64}$" }
															};
															c === null ? c = [e] : c.push(e), l++;
														}
													} else {
														let e = {
															instancePath: t + "/snapshot_id",
															schemaPath: "#/properties/snapshot_id/anyOf/0/type",
															keyword: "type",
															params: { type: "string" }
														};
														c === null ? c = [e] : c.push(e), l++;
													}
												}
												var m = o === l;
												a ||= m;
												let u = l;
												if (n !== null) {
													let e = {
														instancePath: t + "/snapshot_id",
														schemaPath: "#/properties/snapshot_id/anyOf/1/type",
														keyword: "type",
														params: { type: "null" }
													};
													c === null ? c = [e] : c.push(e), l++;
												}
												var m = u === l;
												if (a ||= m, a) l = i, c !== null && (i ? c.length = i : c = null);
												else {
													let e = {
														instancePath: t + "/snapshot_id",
														schemaPath: "#/properties/snapshot_id/anyOf",
														keyword: "anyOf",
														params: {}
													};
													return c === null ? c = [e] : c.push(e), l++, gn.errors = c, !1;
												}
												var f = r === l;
											} else var f = !0;
											if (f) {
												if (e.soft_preferences !== void 0 && n.call(e, "soft_preferences")) {
													let n = e.soft_preferences, r = l;
													if (l === r) {
														if (Array.isArray(n)) {
															if (n.length > 12) return gn.errors = [{
																instancePath: t + "/soft_preferences",
																schemaPath: "#/properties/soft_preferences/maxItems",
																keyword: "maxItems",
																params: { limit: 12 }
															}], !1;
															{
																let e = n.length;
																for (let r = 0; r < e; r++) {
																	let e = n[r], i = l;
																	if (l === i) {
																		if (typeof e == "string") {
																			if (h(e) > 200) return gn.errors = [{
																				instancePath: t + "/soft_preferences/" + r,
																				schemaPath: "#/properties/soft_preferences/items/maxLength",
																				keyword: "maxLength",
																				params: { limit: 200 }
																			}], !1;
																			if (h(e) < 1) return gn.errors = [{
																				instancePath: t + "/soft_preferences/" + r,
																				schemaPath: "#/properties/soft_preferences/items/minLength",
																				keyword: "minLength",
																				params: { limit: 1 }
																			}], !1;
																		} else return gn.errors = [{
																			instancePath: t + "/soft_preferences/" + r,
																			schemaPath: "#/properties/soft_preferences/items/type",
																			keyword: "type",
																			params: { type: "string" }
																		}], !1;
																	}
																	if (i !== l) break;
																}
															}
														} else return gn.errors = [{
															instancePath: t + "/soft_preferences",
															schemaPath: "#/properties/soft_preferences/type",
															keyword: "type",
															params: { type: "array" }
														}], !1;
													}
													var f = r === l;
												} else var f = !0;
											}
										}
									}
								}
							}
						}
					}
				}
			} else return gn.errors = [{
				instancePath: t,
				schemaPath: "#/type",
				keyword: "type",
				params: { type: "object" }
			}], !1;
		}
		return gn.errors = c, l === 0;
	}
	gn.evaluated = {
		props: !0,
		dynamicProps: !1,
		dynamicItems: !1
	}, e.v113 = _n;
	function _n(e, { instancePath: t = "", parentData: r, parentDataProperty: i, rootData: a = e, dynamicAnchors: o = {} } = {}) {
		let s = _n.evaluated;
		if (s.dynamicProps && (s.props = void 0), s.dynamicItems && (s.items = void 0), e && typeof e == "object" && !Array.isArray(e)) {
			let r;
			if ((e.client_action_id === void 0 || !n.call(e, "client_action_id")) && (r = "client_action_id")) return _n.errors = [{
				instancePath: t,
				schemaPath: "#/required",
				keyword: "required",
				params: { missingProperty: r }
			}], !1;
			for (let n of Object.keys(e)) if (n !== "client_action_id") return _n.errors = [{
				instancePath: t,
				schemaPath: "#/additionalProperties",
				keyword: "additionalProperties",
				params: { additionalProperty: n }
			}], !1;
			if (e.client_action_id !== void 0 && n.call(e, "client_action_id")) {
				let n = e.client_action_id;
				if (typeof n == "string") {
					if (!u.test(n)) return _n.errors = [{
						instancePath: t + "/client_action_id",
						schemaPath: "#/properties/client_action_id/pattern",
						keyword: "pattern",
						params: { pattern: "^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$" }
					}], !1;
				} else return _n.errors = [{
					instancePath: t + "/client_action_id",
					schemaPath: "#/properties/client_action_id/type",
					keyword: "type",
					params: { type: "string" }
				}], !1;
			}
		} else return _n.errors = [{
			instancePath: t,
			schemaPath: "#/type",
			keyword: "type",
			params: { type: "object" }
		}], !1;
		return _n.errors = null, !0;
	}
	_n.evaluated = {
		props: !0,
		dynamicProps: !1,
		dynamicItems: !1
	}, e.v114 = vn;
	function vn(e, { instancePath: t = "", parentData: r, parentDataProperty: i, rootData: a = e, dynamicAnchors: o = {} } = {}) {
		let s = null, c = 0, d = vn.evaluated;
		if (d.dynamicProps && (d.props = void 0), d.dynamicItems && (d.items = void 0), c === 0) {
			if (e && typeof e == "object" && !Array.isArray(e)) {
				let r;
				if ((e.expected_revision === void 0 || !n.call(e, "expected_revision")) && (r = "expected_revision") || (e.client_action_id === void 0 || !n.call(e, "client_action_id")) && (r = "client_action_id") || (e.selected_ref === void 0 || !n.call(e, "selected_ref")) && (r = "selected_ref")) return vn.errors = [{
					instancePath: t,
					schemaPath: "#/required",
					keyword: "required",
					params: { missingProperty: r }
				}], !1;
				{
					let r = c;
					for (let n of Object.keys(e)) if (n !== "client_action_id" && n !== "expected_revision" && n !== "presentation_id" && n !== "selected_ref") return vn.errors = [{
						instancePath: t,
						schemaPath: "#/additionalProperties",
						keyword: "additionalProperties",
						params: { additionalProperty: n }
					}], !1;
					if (r === c) {
						if (e.client_action_id !== void 0 && n.call(e, "client_action_id")) {
							let n = e.client_action_id, r = c;
							if (c === r) {
								if (typeof n == "string") {
									if (!u.test(n)) return vn.errors = [{
										instancePath: t + "/client_action_id",
										schemaPath: "#/properties/client_action_id/pattern",
										keyword: "pattern",
										params: { pattern: "^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$" }
									}], !1;
								} else return vn.errors = [{
									instancePath: t + "/client_action_id",
									schemaPath: "#/properties/client_action_id/type",
									keyword: "type",
									params: { type: "string" }
								}], !1;
							}
							var f = r === c;
						} else var f = !0;
						if (f) {
							if (e.expected_revision !== void 0 && n.call(e, "expected_revision")) {
								let n = e.expected_revision, r = c;
								if (typeof n != "number" || n % 1 || isNaN(n) || !isFinite(n)) return vn.errors = [{
									instancePath: t + "/expected_revision",
									schemaPath: "#/properties/expected_revision/type",
									keyword: "type",
									params: { type: "integer" }
								}], !1;
								if (c === r && typeof n == "number" && isFinite(n)) {
									if (n > 2147483647 || isNaN(n)) return vn.errors = [{
										instancePath: t + "/expected_revision",
										schemaPath: "#/properties/expected_revision/maximum",
										keyword: "maximum",
										params: {
											comparison: "<=",
											limit: 2147483647
										}
									}], !1;
									if (n < 0 || isNaN(n)) return vn.errors = [{
										instancePath: t + "/expected_revision",
										schemaPath: "#/properties/expected_revision/minimum",
										keyword: "minimum",
										params: {
											comparison: ">=",
											limit: 0
										}
									}], !1;
								}
								var f = r === c;
							} else var f = !0;
							if (f) {
								if (e.presentation_id !== void 0 && n.call(e, "presentation_id")) {
									let n = e.presentation_id, r = c, i = c, a = !1, o = c;
									if (c === o) {
										if (typeof n == "string") {
											if (!u.test(n)) {
												let e = {
													instancePath: t + "/presentation_id",
													schemaPath: "#/properties/presentation_id/anyOf/0/pattern",
													keyword: "pattern",
													params: { pattern: "^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$" }
												};
												s === null ? s = [e] : s.push(e), c++;
											}
										} else {
											let e = {
												instancePath: t + "/presentation_id",
												schemaPath: "#/properties/presentation_id/anyOf/0/type",
												keyword: "type",
												params: { type: "string" }
											};
											s === null ? s = [e] : s.push(e), c++;
										}
									}
									var p = o === c;
									a ||= p;
									let l = c;
									if (n !== null) {
										let e = {
											instancePath: t + "/presentation_id",
											schemaPath: "#/properties/presentation_id/anyOf/1/type",
											keyword: "type",
											params: { type: "null" }
										};
										s === null ? s = [e] : s.push(e), c++;
									}
									var p = l === c;
									if (a ||= p, a) c = i, s !== null && (i ? s.length = i : s = null);
									else {
										let e = {
											instancePath: t + "/presentation_id",
											schemaPath: "#/properties/presentation_id/anyOf",
											keyword: "anyOf",
											params: {}
										};
										return s === null ? s = [e] : s.push(e), c++, vn.errors = s, !1;
									}
									var f = r === c;
								} else var f = !0;
								if (f) {
									if (e.selected_ref !== void 0 && n.call(e, "selected_ref")) {
										let n = c;
										l(e.selected_ref, {
											instancePath: t + "/selected_ref",
											parentData: e,
											parentDataProperty: "selected_ref",
											rootData: a,
											dynamicAnchors: o
										}) || (s = s === null ? l.errors : s.concat(l.errors), c = s.length);
										var f = n === c;
									} else var f = !0;
								}
							}
						}
					}
				}
			} else return vn.errors = [{
				instancePath: t,
				schemaPath: "#/type",
				keyword: "type",
				params: { type: "object" }
			}], !1;
		}
		return vn.errors = s, c === 0;
	}
	vn.evaluated = {
		props: !0,
		dynamicProps: !1,
		dynamicItems: !1
	}, e.v126 = bn;
	var yn = /* @__PURE__ */ RegExp("^\\d{4}-\\d{2}-\\d{2}$", "u");
	function bn(e, { instancePath: t = "", parentData: r, parentDataProperty: i, rootData: a = e, dynamicAnchors: o = {} } = {}) {
		let s = null, c = 0, u = bn.evaluated;
		if (u.dynamicProps && (u.props = void 0), u.dynamicItems && (u.items = void 0), c === 0) {
			if (e && typeof e == "object" && !Array.isArray(e)) {
				let r;
				if ((e.ref === void 0 || !n.call(e, "ref")) && (r = "ref") || (e.from_date === void 0 || !n.call(e, "from_date")) && (r = "from_date")) return bn.errors = [{
					instancePath: t,
					schemaPath: "#/required",
					keyword: "required",
					params: { missingProperty: r }
				}], !1;
				{
					let r = c;
					for (let n of Object.keys(e)) if (n !== "days" && n !== "from_date" && n !== "ref") return bn.errors = [{
						instancePath: t,
						schemaPath: "#/additionalProperties",
						keyword: "additionalProperties",
						params: { additionalProperty: n }
					}], !1;
					if (r === c) {
						if (e.days !== void 0 && n.call(e, "days")) {
							let n = e.days, r = c;
							if (typeof n != "number" || n % 1 || isNaN(n) || !isFinite(n)) return bn.errors = [{
								instancePath: t + "/days",
								schemaPath: "#/properties/days/type",
								keyword: "type",
								params: { type: "integer" }
							}], !1;
							if (c === r && typeof n == "number" && isFinite(n)) {
								if (n > 7 || isNaN(n)) return bn.errors = [{
									instancePath: t + "/days",
									schemaPath: "#/properties/days/maximum",
									keyword: "maximum",
									params: {
										comparison: "<=",
										limit: 7
									}
								}], !1;
								if (n < 1 || isNaN(n)) return bn.errors = [{
									instancePath: t + "/days",
									schemaPath: "#/properties/days/minimum",
									keyword: "minimum",
									params: {
										comparison: ">=",
										limit: 1
									}
								}], !1;
							}
							var d = r === c;
						} else var d = !0;
						if (d) {
							if (e.from_date !== void 0 && n.call(e, "from_date")) {
								let n = e.from_date, r = c;
								if (c === r) {
									if (typeof n == "string") {
										if (!yn.test(n)) return bn.errors = [{
											instancePath: t + "/from_date",
											schemaPath: "#/properties/from_date/pattern",
											keyword: "pattern",
											params: { pattern: "^\\d{4}-\\d{2}-\\d{2}$" }
										}], !1;
									} else return bn.errors = [{
										instancePath: t + "/from_date",
										schemaPath: "#/properties/from_date/type",
										keyword: "type",
										params: { type: "string" }
									}], !1;
								}
								var d = r === c;
							} else var d = !0;
							if (d) {
								if (e.ref !== void 0 && n.call(e, "ref")) {
									let n = c;
									l(e.ref, {
										instancePath: t + "/ref",
										parentData: e,
										parentDataProperty: "ref",
										rootData: a,
										dynamicAnchors: o
									}) || (s = s === null ? l.errors : s.concat(l.errors), c = s.length);
									var d = n === c;
								} else var d = !0;
							}
						}
					}
				}
			} else return bn.errors = [{
				instancePath: t,
				schemaPath: "#/type",
				keyword: "type",
				params: { type: "object" }
			}], !1;
		}
		return bn.errors = s, c === 0;
	}
	bn.evaluated = {
		props: !0,
		dynamicProps: !1,
		dynamicItems: !1
	}, e.v129 = xn;
	function xn(e, { instancePath: t = "", parentData: n, parentDataProperty: r, rootData: i = e, dynamicAnchors: a = {} } = {}) {
		let o = xn.evaluated;
		if (o.dynamicProps && (o.props = void 0), o.dynamicItems && (o.items = void 0), typeof e == "string") {
			if (!u.test(e)) return xn.errors = [{
				instancePath: t,
				schemaPath: "#/pattern",
				keyword: "pattern",
				params: { pattern: "^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$" }
			}], !1;
		} else return xn.errors = [{
			instancePath: t,
			schemaPath: "#/type",
			keyword: "type",
			params: { type: "string" }
		}], !1;
		return xn.errors = null, !0;
	}
	xn.evaluated = {
		dynamicProps: !1,
		dynamicItems: !1
	}, e.v130 = Sn;
	function Sn(e, { instancePath: t = "", parentData: n, parentDataProperty: r, rootData: i = e, dynamicAnchors: a = {} } = {}) {
		let o = Sn.evaluated;
		if (o.dynamicProps && (o.props = void 0), o.dynamicItems && (o.items = void 0), typeof e == "string") {
			if (!g.test(e)) return Sn.errors = [{
				instancePath: t,
				schemaPath: "#/pattern",
				keyword: "pattern",
				params: { pattern: "^[A-Za-z0-9_-]{43}$" }
			}], !1;
		} else return Sn.errors = [{
			instancePath: t,
			schemaPath: "#/type",
			keyword: "type",
			params: { type: "string" }
		}], !1;
		return Sn.errors = null, !0;
	}
	Sn.evaluated = {
		dynamicProps: !1,
		dynamicItems: !1
	}, e.v131 = Cn;
	function Cn(e, { instancePath: t = "", parentData: n, parentDataProperty: r, rootData: i = e, dynamicAnchors: a = {} } = {}) {
		let o = Cn.evaluated;
		return o.dynamicProps && (o.props = void 0), o.dynamicItems && (o.items = void 0), typeof e == "string" ? (Cn.errors = null, !0) : (Cn.errors = [{
			instancePath: t,
			schemaPath: "#/type",
			keyword: "type",
			params: { type: "string" }
		}], !1);
	}
	Cn.evaluated = {
		dynamicProps: !1,
		dynamicItems: !1
	}, e.v132 = wn;
	function wn(e, { instancePath: t = "", parentData: n, parentDataProperty: r, rootData: i = e, dynamicAnchors: a = {} } = {}) {
		let o = wn.evaluated;
		if (o.dynamicProps && (o.props = void 0), o.dynamicItems && (o.items = void 0), typeof e == "string") {
			if (!u.test(e)) return wn.errors = [{
				instancePath: t,
				schemaPath: "#/pattern",
				keyword: "pattern",
				params: { pattern: "^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$" }
			}], !1;
		} else return wn.errors = [{
			instancePath: t,
			schemaPath: "#/type",
			keyword: "type",
			params: { type: "string" }
		}], !1;
		return wn.errors = null, !0;
	}
	wn.evaluated = {
		dynamicProps: !1,
		dynamicItems: !1
	}, e.v133 = En;
	function Tn(e, { instancePath: t = "", parentData: r, parentDataProperty: i, rootData: a = e, dynamicAnchors: o = {} } = {}) {
		let s = null, c = 0, l = Tn.evaluated;
		if (l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0) {
			if (e && typeof e == "object" && !Array.isArray(e)) {
				let r;
				if ((e.data === void 0 || !n.call(e, "data")) && (r = "data") || (e.meta === void 0 || !n.call(e, "meta")) && (r = "meta")) return Tn.errors = [{
					instancePath: t,
					schemaPath: "#/required",
					keyword: "required",
					params: { missingProperty: r }
				}], !1;
				{
					let r = c;
					for (let n of Object.keys(e)) if (n !== "data" && n !== "meta") return Tn.errors = [{
						instancePath: t,
						schemaPath: "#/additionalProperties",
						keyword: "additionalProperties",
						params: { additionalProperty: n }
					}], !1;
					if (r === c) {
						if (e.data !== void 0 && n.call(e, "data")) {
							let n = c;
							j(e.data, {
								instancePath: t + "/data",
								parentData: e,
								parentDataProperty: "data",
								rootData: a,
								dynamicAnchors: o
							}) || (s = s === null ? j.errors : s.concat(j.errors), c = s.length);
							var u = n === c;
						} else var u = !0;
						if (u) {
							if (e.meta !== void 0 && n.call(e, "meta")) {
								let n = c;
								y(e.meta, {
									instancePath: t + "/meta",
									parentData: e,
									parentDataProperty: "meta",
									rootData: a,
									dynamicAnchors: o
								}) || (s = s === null ? y.errors : s.concat(y.errors), c = s.length);
								var u = n === c;
							} else var u = !0;
						}
					}
				}
			} else return Tn.errors = [{
				instancePath: t,
				schemaPath: "#/type",
				keyword: "type",
				params: { type: "object" }
			}], !1;
		}
		return Tn.errors = s, c === 0;
	}
	Tn.evaluated = {
		props: !0,
		dynamicProps: !1,
		dynamicItems: !1
	};
	function En(e, { instancePath: t = "", parentData: n, parentDataProperty: r, rootData: i = e, dynamicAnchors: a = {} } = {}) {
		let o = null, s = 0, c = En.evaluated;
		c.dynamicProps && (c.props = void 0), c.dynamicItems && (c.items = void 0);
		let l = s, u = !1, d = s;
		on(e, {
			instancePath: t,
			parentData: n,
			parentDataProperty: r,
			rootData: i,
			dynamicAnchors: a
		}) || (o = o === null ? on.errors : o.concat(on.errors), s = o.length);
		var f = d === s;
		if (u ||= f, f) var p = !0;
		let m = s;
		Tn(e, {
			instancePath: t,
			parentData: n,
			parentDataProperty: r,
			rootData: i,
			dynamicAnchors: a
		}) || (o = o === null ? Tn.errors : o.concat(Tn.errors), s = o.length);
		var f = m === s;
		if (u ||= f, f && p !== !0 && (p = !0), u) s = l, o !== null && (l ? o.length = l : o = null);
		else {
			let e = {
				instancePath: t,
				schemaPath: "#/anyOf",
				keyword: "anyOf",
				params: {}
			};
			return o === null ? o = [e] : o.push(e), s++, En.errors = o, !1;
		}
		return En.errors = o, c.props = p, s === 0;
	}
	En.evaluated = {
		dynamicProps: !0,
		dynamicItems: !1
	}, e.v134 = Dn;
	function Dn(e, { instancePath: t = "", parentData: n, parentDataProperty: r, rootData: i = e, dynamicAnchors: a = {} } = {}) {
		let o = Dn.evaluated;
		if (o.dynamicProps && (o.props = void 0), o.dynamicItems && (o.items = void 0), typeof e == "string") {
			if (!u.test(e)) return Dn.errors = [{
				instancePath: t,
				schemaPath: "#/pattern",
				keyword: "pattern",
				params: { pattern: "^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$" }
			}], !1;
		} else return Dn.errors = [{
			instancePath: t,
			schemaPath: "#/type",
			keyword: "type",
			params: { type: "string" }
		}], !1;
		return Dn.errors = null, !0;
	}
	Dn.evaluated = {
		dynamicProps: !1,
		dynamicItems: !1
	}, e.v135 = On;
	function On(e, { instancePath: t = "", parentData: n, parentDataProperty: r, rootData: i = e, dynamicAnchors: a = {} } = {}) {
		let o = On.evaluated;
		if (o.dynamicProps && (o.props = void 0), o.dynamicItems && (o.items = void 0), typeof e == "string") {
			if (!u.test(e)) return On.errors = [{
				instancePath: t,
				schemaPath: "#/pattern",
				keyword: "pattern",
				params: { pattern: "^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$" }
			}], !1;
		} else return On.errors = [{
			instancePath: t,
			schemaPath: "#/type",
			keyword: "type",
			params: { type: "string" }
		}], !1;
		return On.errors = null, !0;
	}
	On.evaluated = {
		dynamicProps: !1,
		dynamicItems: !1
	}, e.v136 = kn;
	function kn(e, { instancePath: t = "", parentData: n, parentDataProperty: r, rootData: i = e, dynamicAnchors: a = {} } = {}) {
		let s = kn.evaluated;
		if (s.dynamicProps && (s.props = void 0), s.dynamicItems && (s.items = void 0), typeof e == "string") {
			if (!o.test(e)) return kn.errors = [{
				instancePath: t,
				schemaPath: "#/pattern",
				keyword: "pattern",
				params: { pattern: "^[a-z0-9_-]{1,64}$" }
			}], !1;
		} else return kn.errors = [{
			instancePath: t,
			schemaPath: "#/type",
			keyword: "type",
			params: { type: "string" }
		}], !1;
		return kn.errors = null, !0;
	}
	kn.evaluated = {
		dynamicProps: !1,
		dynamicItems: !1
	}, e.v137 = An;
	function An(e, { instancePath: t = "", parentData: n, parentDataProperty: r, rootData: i = e, dynamicAnchors: a = {} } = {}) {
		let o = An.evaluated;
		if (o.dynamicProps && (o.props = void 0), o.dynamicItems && (o.items = void 0), typeof e == "string") {
			if (!s.test(e)) return An.errors = [{
				instancePath: t,
				schemaPath: "#/pattern",
				keyword: "pattern",
				params: { pattern: "^[0-9a-f]{64}$" }
			}], !1;
		} else return An.errors = [{
			instancePath: t,
			schemaPath: "#/type",
			keyword: "type",
			params: { type: "string" }
		}], !1;
		return An.errors = null, !0;
	}
	An.evaluated = {
		dynamicProps: !1,
		dynamicItems: !1
	}, e.v138 = jn;
	function jn(e, { instancePath: t = "", parentData: n, parentDataProperty: r, rootData: i = e, dynamicAnchors: a = {} } = {}) {
		let o = jn.evaluated;
		if (o.dynamicProps && (o.props = void 0), o.dynamicItems && (o.items = void 0), typeof e == "string") {
			if (!c.test(e)) return jn.errors = [{
				instancePath: t,
				schemaPath: "#/pattern",
				keyword: "pattern",
				params: { pattern: "^[A-Za-z0-9._-]{1,128}$" }
			}], !1;
		} else return jn.errors = [{
			instancePath: t,
			schemaPath: "#/type",
			keyword: "type",
			params: { type: "string" }
		}], !1;
		return jn.errors = null, !0;
	}
	jn.evaluated = {
		dynamicProps: !1,
		dynamicItems: !1
	}, e.v139 = Mn;
	function Mn(e, { instancePath: t = "", parentData: n, parentDataProperty: r, rootData: i = e, dynamicAnchors: a = {} } = {}) {
		let o = Mn.evaluated;
		if (o.dynamicProps && (o.props = void 0), o.dynamicItems && (o.items = void 0), typeof e == "string") {
			if (!g.test(e)) return Mn.errors = [{
				instancePath: t,
				schemaPath: "#/pattern",
				keyword: "pattern",
				params: { pattern: "^[A-Za-z0-9_-]{43}$" }
			}], !1;
		} else return Mn.errors = [{
			instancePath: t,
			schemaPath: "#/type",
			keyword: "type",
			params: { type: "string" }
		}], !1;
		return Mn.errors = null, !0;
	}
	Mn.evaluated = {
		dynamicProps: !1,
		dynamicItems: !1
	}, e.v140 = Nn;
	function Nn(e, { instancePath: t = "", parentData: n, parentDataProperty: r, rootData: i = e, dynamicAnchors: a = {} } = {}) {
		let o = null, s = 0, c = Nn.evaluated;
		c.dynamicProps && (c.props = void 0), c.dynamicItems && (c.items = void 0);
		let l = s, d = !1, f = s;
		if (s === f) {
			if (typeof e == "string") {
				if (!u.test(e)) {
					let e = {
						instancePath: t,
						schemaPath: "#/anyOf/0/pattern",
						keyword: "pattern",
						params: { pattern: "^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$" }
					};
					o === null ? o = [e] : o.push(e), s++;
				}
			} else {
				let e = {
					instancePath: t,
					schemaPath: "#/anyOf/0/type",
					keyword: "type",
					params: { type: "string" }
				};
				o === null ? o = [e] : o.push(e), s++;
			}
		}
		var p = f === s;
		d ||= p;
		let m = s;
		if (e !== null) {
			let e = {
				instancePath: t,
				schemaPath: "#/anyOf/1/type",
				keyword: "type",
				params: { type: "null" }
			};
			o === null ? o = [e] : o.push(e), s++;
		}
		var p = m === s;
		if (d ||= p, d) s = l, o !== null && (l ? o.length = l : o = null);
		else {
			let e = {
				instancePath: t,
				schemaPath: "#/anyOf",
				keyword: "anyOf",
				params: {}
			};
			return o === null ? o = [e] : o.push(e), s++, Nn.errors = o, !1;
		}
		return Nn.errors = o, s === 0;
	}
	Nn.evaluated = {
		dynamicProps: !1,
		dynamicItems: !1
	}, e.v141 = Ln;
	var Pn = {
		additionalProperties: !1,
		properties: {
			changes: {
				items: {
					discriminator: { propertyName: "key" },
					oneOf: [{ $ref: "urn:car-shopping-assistant:contract:1#/$defs/BudgetPreference" }, { $ref: "urn:car-shopping-assistant:contract:1#/$defs/CategoryPreference" }],
					type: "object",
					required: ["key"],
					properties: { key: { type: "string" } }
				},
				maxItems: 4,
				minItems: 1,
				title: "Changes",
				type: "array"
			},
			client_action_id: {
				pattern: "^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$",
				title: "Client Action Id",
				type: "string"
			},
			expected_revision: {
				maximum: 2147483647,
				minimum: 0,
				title: "Expected Revision",
				type: "integer"
			},
			intent: {
				enum: ["remember", "correct"],
				title: "Intent",
				type: "string"
			},
			scope: {
				const: "durable",
				title: "Scope",
				type: "string"
			},
			session_id: {
				pattern: "^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$",
				title: "Session Id",
				type: "string"
			}
		},
		required: [
			"expected_revision",
			"session_id",
			"client_action_id",
			"scope",
			"intent",
			"changes"
		],
		title: "PreferencesUpdate",
		type: "object"
	};
	function $(e, { instancePath: t = "", parentData: r, parentDataProperty: i, rootData: a = e, dynamicAnchors: o = {} } = {}) {
		let s = null, c = 0, l = $.evaluated;
		if (l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0) {
			if (e && typeof e == "object" && !Array.isArray(e)) {
				let r;
				if ((e.expected_revision === void 0 || !n.call(e, "expected_revision")) && (r = "expected_revision") || (e.session_id === void 0 || !n.call(e, "session_id")) && (r = "session_id") || (e.client_action_id === void 0 || !n.call(e, "client_action_id")) && (r = "client_action_id") || (e.scope === void 0 || !n.call(e, "scope")) && (r = "scope") || (e.intent === void 0 || !n.call(e, "intent")) && (r = "intent") || (e.changes === void 0 || !n.call(e, "changes")) && (r = "changes")) return $.errors = [{
					instancePath: t,
					schemaPath: "#/required",
					keyword: "required",
					params: { missingProperty: r }
				}], !1;
				{
					let r = c;
					for (let n of Object.keys(e)) if (n !== "changes" && n !== "client_action_id" && n !== "expected_revision" && n !== "intent" && n !== "scope" && n !== "session_id") return $.errors = [{
						instancePath: t,
						schemaPath: "#/additionalProperties",
						keyword: "additionalProperties",
						params: { additionalProperty: n }
					}], !1;
					if (r === c) {
						if (e.changes !== void 0 && n.call(e, "changes")) {
							let r = e.changes, i = c;
							if (c === i) {
								if (Array.isArray(r)) {
									if (r.length > 4) return $.errors = [{
										instancePath: t + "/changes",
										schemaPath: "#/properties/changes/maxItems",
										keyword: "maxItems",
										params: { limit: 4 }
									}], !1;
									if (r.length < 1) return $.errors = [{
										instancePath: t + "/changes",
										schemaPath: "#/properties/changes/minItems",
										keyword: "minItems",
										params: { limit: 1 }
									}], !1;
									{
										let e = r.length;
										for (let i = 0; i < e; i++) {
											let e = r[i], l = c;
											if (c === l) {
												if (e && typeof e == "object" && !Array.isArray(e)) {
													let l;
													if ((e.key === void 0 || !n.call(e, "key")) && (l = "key")) return $.errors = [{
														instancePath: t + "/changes/" + i,
														schemaPath: "#/properties/changes/items/required",
														keyword: "required",
														params: { missingProperty: l }
													}], !1;
													if (e.key !== void 0 && n.call(e, "key")) {
														let n = c;
														if (typeof e.key != "string") return $.errors = [{
															instancePath: t + "/changes/" + i + "/key",
															schemaPath: "#/properties/changes/items/properties/key/type",
															keyword: "type",
															params: { type: "string" }
														}], !1;
														var d = n === c;
													} else var d = !0;
													if (d) {
														let n = e.key;
														if (typeof n == "string") {
															if (n === "budget") {
																gt(e, {
																	instancePath: t + "/changes/" + i,
																	parentData: r,
																	parentDataProperty: i,
																	rootData: a,
																	dynamicAnchors: o
																}) || (s = s === null ? gt.errors : s.concat(gt.errors), c = s.length);
																var f = !0;
															} else if (n === "makes") z(e, {
																instancePath: t + "/changes/" + i,
																parentData: r,
																parentDataProperty: i,
																rootData: a,
																dynamicAnchors: o
															}) || (s = s === null ? z.errors : s.concat(z.errors), c = s.length), f !== !0 && (f = !0);
															else if (n === "use_cases") z(e, {
																instancePath: t + "/changes/" + i,
																parentData: r,
																parentDataProperty: i,
																rootData: a,
																dynamicAnchors: o
															}) || (s = s === null ? z.errors : s.concat(z.errors), c = s.length), f !== !0 && (f = !0);
															else if (n === "requirements") z(e, {
																instancePath: t + "/changes/" + i,
																parentData: r,
																parentDataProperty: i,
																rootData: a,
																dynamicAnchors: o
															}) || (s = s === null ? z.errors : s.concat(z.errors), c = s.length), f !== !0 && (f = !0);
															else return $.errors = [{
																instancePath: t + "/changes/" + i,
																schemaPath: "#/properties/changes/items/discriminator",
																keyword: "discriminator",
																params: {
																	error: "mapping",
																	tag: "key",
																	tagValue: n
																}
															}], !1;
														} else return $.errors = [{
															instancePath: t + "/changes/" + i,
															schemaPath: "#/properties/changes/items/discriminator",
															keyword: "discriminator",
															params: {
																error: "tag",
																tag: "key",
																tagValue: n
															}
														}], !1;
													}
												} else return $.errors = [{
													instancePath: t + "/changes/" + i,
													schemaPath: "#/properties/changes/items/type",
													keyword: "type",
													params: { type: "object" }
												}], !1;
											}
											if (l !== c) break;
										}
									}
								} else return $.errors = [{
									instancePath: t + "/changes",
									schemaPath: "#/properties/changes/type",
									keyword: "type",
									params: { type: "array" }
								}], !1;
							}
							var p = i === c;
						} else var p = !0;
						if (p) {
							if (e.client_action_id !== void 0 && n.call(e, "client_action_id")) {
								let n = e.client_action_id, r = c;
								if (c === r) {
									if (typeof n == "string") {
										if (!u.test(n)) return $.errors = [{
											instancePath: t + "/client_action_id",
											schemaPath: "#/properties/client_action_id/pattern",
											keyword: "pattern",
											params: { pattern: "^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$" }
										}], !1;
									} else return $.errors = [{
										instancePath: t + "/client_action_id",
										schemaPath: "#/properties/client_action_id/type",
										keyword: "type",
										params: { type: "string" }
									}], !1;
								}
								var p = r === c;
							} else var p = !0;
							if (p) {
								if (e.expected_revision !== void 0 && n.call(e, "expected_revision")) {
									let n = e.expected_revision, r = c;
									if (typeof n != "number" || n % 1 || isNaN(n) || !isFinite(n)) return $.errors = [{
										instancePath: t + "/expected_revision",
										schemaPath: "#/properties/expected_revision/type",
										keyword: "type",
										params: { type: "integer" }
									}], !1;
									if (c === r && typeof n == "number" && isFinite(n)) {
										if (n > 2147483647 || isNaN(n)) return $.errors = [{
											instancePath: t + "/expected_revision",
											schemaPath: "#/properties/expected_revision/maximum",
											keyword: "maximum",
											params: {
												comparison: "<=",
												limit: 2147483647
											}
										}], !1;
										if (n < 0 || isNaN(n)) return $.errors = [{
											instancePath: t + "/expected_revision",
											schemaPath: "#/properties/expected_revision/minimum",
											keyword: "minimum",
											params: {
												comparison: ">=",
												limit: 0
											}
										}], !1;
									}
									var p = r === c;
								} else var p = !0;
								if (p) {
									if (e.intent !== void 0 && n.call(e, "intent")) {
										let n = e.intent, r = c;
										if (typeof n != "string") return $.errors = [{
											instancePath: t + "/intent",
											schemaPath: "#/properties/intent/type",
											keyword: "type",
											params: { type: "string" }
										}], !1;
										if (n !== "remember" && n !== "correct") return $.errors = [{
											instancePath: t + "/intent",
											schemaPath: "#/properties/intent/enum",
											keyword: "enum",
											params: { allowedValues: Pn.properties.intent.enum }
										}], !1;
										var p = r === c;
									} else var p = !0;
									if (p) {
										if (e.scope !== void 0 && n.call(e, "scope")) {
											let n = e.scope, r = c;
											if (typeof n != "string") return $.errors = [{
												instancePath: t + "/scope",
												schemaPath: "#/properties/scope/type",
												keyword: "type",
												params: { type: "string" }
											}], !1;
											if (n !== "durable") return $.errors = [{
												instancePath: t + "/scope",
												schemaPath: "#/properties/scope/const",
												keyword: "const",
												params: { allowedValue: "durable" }
											}], !1;
											var p = r === c;
										} else var p = !0;
										if (p) {
											if (e.session_id !== void 0 && n.call(e, "session_id")) {
												let n = e.session_id, r = c;
												if (c === r) {
													if (typeof n == "string") {
														if (!u.test(n)) return $.errors = [{
															instancePath: t + "/session_id",
															schemaPath: "#/properties/session_id/pattern",
															keyword: "pattern",
															params: { pattern: "^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$" }
														}], !1;
													} else return $.errors = [{
														instancePath: t + "/session_id",
														schemaPath: "#/properties/session_id/type",
														keyword: "type",
														params: { type: "string" }
													}], !1;
												}
												var p = r === c;
											} else var p = !0;
										}
									}
								}
							}
						}
					}
				}
			} else return $.errors = [{
				instancePath: t,
				schemaPath: "#/type",
				keyword: "type",
				params: { type: "object" }
			}], !1;
		}
		return $.errors = s, c === 0;
	}
	$.evaluated = {
		props: !0,
		dynamicProps: !1,
		dynamicItems: !1
	};
	var Fn = {
		additionalProperties: !1,
		properties: {
			client_action_id: {
				pattern: "^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$",
				title: "Client Action Id",
				type: "string"
			},
			expected_revision: {
				maximum: 2147483647,
				minimum: 0,
				title: "Expected Revision",
				type: "integer"
			},
			intent: {
				enum: ["stop_saving", "resume_saving"],
				title: "Intent",
				type: "string"
			},
			session_id: {
				pattern: "^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$",
				title: "Session Id",
				type: "string"
			}
		},
		required: [
			"expected_revision",
			"session_id",
			"client_action_id",
			"intent"
		],
		title: "PreferenceCollectionUpdate",
		type: "object"
	};
	function In(e, { instancePath: t = "", parentData: r, parentDataProperty: i, rootData: a = e, dynamicAnchors: o = {} } = {}) {
		let s = In.evaluated;
		if (s.dynamicProps && (s.props = void 0), s.dynamicItems && (s.items = void 0), e && typeof e == "object" && !Array.isArray(e)) {
			let r;
			if ((e.expected_revision === void 0 || !n.call(e, "expected_revision")) && (r = "expected_revision") || (e.session_id === void 0 || !n.call(e, "session_id")) && (r = "session_id") || (e.client_action_id === void 0 || !n.call(e, "client_action_id")) && (r = "client_action_id") || (e.intent === void 0 || !n.call(e, "intent")) && (r = "intent")) return In.errors = [{
				instancePath: t,
				schemaPath: "#/required",
				keyword: "required",
				params: { missingProperty: r }
			}], !1;
			for (let n of Object.keys(e)) if (n !== "client_action_id" && n !== "expected_revision" && n !== "intent" && n !== "session_id") return In.errors = [{
				instancePath: t,
				schemaPath: "#/additionalProperties",
				keyword: "additionalProperties",
				params: { additionalProperty: n }
			}], !1;
			if (e.client_action_id !== void 0 && n.call(e, "client_action_id")) {
				let n = e.client_action_id;
				if (typeof n == "string") {
					if (!u.test(n)) return In.errors = [{
						instancePath: t + "/client_action_id",
						schemaPath: "#/properties/client_action_id/pattern",
						keyword: "pattern",
						params: { pattern: "^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$" }
					}], !1;
				} else return In.errors = [{
					instancePath: t + "/client_action_id",
					schemaPath: "#/properties/client_action_id/type",
					keyword: "type",
					params: { type: "string" }
				}], !1;
				var c = !0;
			} else var c = !0;
			if (c) {
				if (e.expected_revision !== void 0 && n.call(e, "expected_revision")) {
					let n = e.expected_revision;
					if (typeof n != "number" || n % 1 || isNaN(n) || !isFinite(n)) return In.errors = [{
						instancePath: t + "/expected_revision",
						schemaPath: "#/properties/expected_revision/type",
						keyword: "type",
						params: { type: "integer" }
					}], !1;
					if (typeof n == "number" && isFinite(n)) {
						if (n > 2147483647 || isNaN(n)) return In.errors = [{
							instancePath: t + "/expected_revision",
							schemaPath: "#/properties/expected_revision/maximum",
							keyword: "maximum",
							params: {
								comparison: "<=",
								limit: 2147483647
							}
						}], !1;
						if (n < 0 || isNaN(n)) return In.errors = [{
							instancePath: t + "/expected_revision",
							schemaPath: "#/properties/expected_revision/minimum",
							keyword: "minimum",
							params: {
								comparison: ">=",
								limit: 0
							}
						}], !1;
					}
					var c = !0;
				} else var c = !0;
				if (c) {
					if (e.intent !== void 0 && n.call(e, "intent")) {
						let n = e.intent;
						if (typeof n != "string") return In.errors = [{
							instancePath: t + "/intent",
							schemaPath: "#/properties/intent/type",
							keyword: "type",
							params: { type: "string" }
						}], !1;
						if (n !== "stop_saving" && n !== "resume_saving") return In.errors = [{
							instancePath: t + "/intent",
							schemaPath: "#/properties/intent/enum",
							keyword: "enum",
							params: { allowedValues: Fn.properties.intent.enum }
						}], !1;
						var c = !0;
					} else var c = !0;
					if (c) {
						if (e.session_id !== void 0 && n.call(e, "session_id")) {
							let n = e.session_id;
							if (typeof n == "string") {
								if (!u.test(n)) return In.errors = [{
									instancePath: t + "/session_id",
									schemaPath: "#/properties/session_id/pattern",
									keyword: "pattern",
									params: { pattern: "^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$" }
								}], !1;
							} else return In.errors = [{
								instancePath: t + "/session_id",
								schemaPath: "#/properties/session_id/type",
								keyword: "type",
								params: { type: "string" }
							}], !1;
							var c = !0;
						} else var c = !0;
					}
				}
			}
		} else return In.errors = [{
			instancePath: t,
			schemaPath: "#/type",
			keyword: "type",
			params: { type: "object" }
		}], !1;
		return In.errors = null, !0;
	}
	In.evaluated = {
		props: !0,
		dynamicProps: !1,
		dynamicItems: !1
	};
	function Ln(e, { instancePath: t = "", parentData: r, parentDataProperty: i, rootData: a = e, dynamicAnchors: o = {} } = {}) {
		let s = null, c = 0, l = Ln.evaluated;
		if (l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0) {
			if (e && typeof e == "object" && !Array.isArray(e)) {
				let l;
				if ((e.intent === void 0 || !n.call(e, "intent")) && (l = "intent")) return Ln.errors = [{
					instancePath: t,
					schemaPath: "#/required",
					keyword: "required",
					params: { missingProperty: l }
				}], !1;
				if (e.intent !== void 0 && n.call(e, "intent")) {
					let n = c;
					if (typeof e.intent != "string") return Ln.errors = [{
						instancePath: t + "/intent",
						schemaPath: "#/properties/intent/type",
						keyword: "type",
						params: { type: "string" }
					}], !1;
					var u = n === c;
				} else var u = !0;
				if (u) {
					let n = e.intent;
					if (typeof n == "string") {
						if (n === "remember") {
							$(e, {
								instancePath: t,
								parentData: r,
								parentDataProperty: i,
								rootData: a,
								dynamicAnchors: o
							}) || (s = s === null ? $.errors : s.concat($.errors), c = s.length);
							var d = !0;
						} else if (n === "correct") $(e, {
							instancePath: t,
							parentData: r,
							parentDataProperty: i,
							rootData: a,
							dynamicAnchors: o
						}) || (s = s === null ? $.errors : s.concat($.errors), c = s.length), d !== !0 && (d = !0);
						else if (n === "stop_saving") In(e, {
							instancePath: t,
							parentData: r,
							parentDataProperty: i,
							rootData: a,
							dynamicAnchors: o
						}) || (s = s === null ? In.errors : s.concat(In.errors), c = s.length), d !== !0 && (d = !0);
						else if (n === "resume_saving") In(e, {
							instancePath: t,
							parentData: r,
							parentDataProperty: i,
							rootData: a,
							dynamicAnchors: o
						}) || (s = s === null ? In.errors : s.concat(In.errors), c = s.length), d !== !0 && (d = !0);
						else return Ln.errors = [{
							instancePath: t,
							schemaPath: "#/discriminator",
							keyword: "discriminator",
							params: {
								error: "mapping",
								tag: "intent",
								tagValue: n
							}
						}], !1;
					} else return Ln.errors = [{
						instancePath: t,
						schemaPath: "#/discriminator",
						keyword: "discriminator",
						params: {
							error: "tag",
							tag: "intent",
							tagValue: n
						}
					}], !1;
				}
			} else return Ln.errors = [{
				instancePath: t,
				schemaPath: "#/type",
				keyword: "type",
				params: { type: "object" }
			}], !1;
		}
		return Ln.errors = s, l.props = d, c === 0;
	}
	Ln.evaluated = {
		dynamicProps: !0,
		dynamicItems: !1
	}, e.v142 = Rn;
	function Rn(e, { instancePath: t = "", parentData: n, parentDataProperty: r, rootData: i = e, dynamicAnchors: a = {} } = {}) {
		let o = Rn.evaluated;
		if (o.dynamicProps && (o.props = void 0), o.dynamicItems && (o.items = void 0), typeof e == "string") {
			if (!u.test(e)) return Rn.errors = [{
				instancePath: t,
				schemaPath: "#/pattern",
				keyword: "pattern",
				params: { pattern: "^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$" }
			}], !1;
		} else return Rn.errors = [{
			instancePath: t,
			schemaPath: "#/type",
			keyword: "type",
			params: { type: "string" }
		}], !1;
		return Rn.errors = null, !0;
	}
	Rn.evaluated = {
		dynamicProps: !1,
		dynamicItems: !1
	}, e.v143 = zn;
	function zn(e, { instancePath: t = "", parentData: n, parentDataProperty: r, rootData: i = e, dynamicAnchors: a = {} } = {}) {
		let o = zn.evaluated;
		if (o.dynamicProps && (o.props = void 0), o.dynamicItems && (o.items = void 0), typeof e != "number" || e % 1 || isNaN(e) || !isFinite(e)) return zn.errors = [{
			instancePath: t,
			schemaPath: "#/type",
			keyword: "type",
			params: { type: "integer" }
		}], !1;
		if (typeof e == "number" && isFinite(e)) {
			if (e > 50 || isNaN(e)) return zn.errors = [{
				instancePath: t,
				schemaPath: "#/maximum",
				keyword: "maximum",
				params: {
					comparison: "<=",
					limit: 50
				}
			}], !1;
			if (e < 1 || isNaN(e)) return zn.errors = [{
				instancePath: t,
				schemaPath: "#/minimum",
				keyword: "minimum",
				params: {
					comparison: ">=",
					limit: 1
				}
			}], !1;
		}
		return zn.errors = null, !0;
	}
	zn.evaluated = {
		dynamicProps: !1,
		dynamicItems: !1
	}, e.v144 = Bn;
	function Bn(e, { instancePath: t = "", parentData: n, parentDataProperty: r, rootData: i = e, dynamicAnchors: a = {} } = {}) {
		let o = null, s = 0, c = Bn.evaluated;
		c.dynamicProps && (c.props = void 0), c.dynamicItems && (c.items = void 0);
		let l = s, u = !1, d = s;
		if (s === d) {
			if (typeof e == "string") {
				if (h(e) > 2048) {
					let e = {
						instancePath: t,
						schemaPath: "#/anyOf/0/maxLength",
						keyword: "maxLength",
						params: { limit: 2048 }
					};
					o === null ? o = [e] : o.push(e), s++;
				}
			} else {
				let e = {
					instancePath: t,
					schemaPath: "#/anyOf/0/type",
					keyword: "type",
					params: { type: "string" }
				};
				o === null ? o = [e] : o.push(e), s++;
			}
		}
		var f = d === s;
		u ||= f;
		let p = s;
		if (e !== null) {
			let e = {
				instancePath: t,
				schemaPath: "#/anyOf/1/type",
				keyword: "type",
				params: { type: "null" }
			};
			o === null ? o = [e] : o.push(e), s++;
		}
		var f = p === s;
		if (u ||= f, u) s = l, o !== null && (l ? o.length = l : o = null);
		else {
			let e = {
				instancePath: t,
				schemaPath: "#/anyOf",
				keyword: "anyOf",
				params: {}
			};
			return o === null ? o = [e] : o.push(e), s++, Bn.errors = o, !1;
		}
		return Bn.errors = o, s === 0;
	}
	Bn.evaluated = {
		dynamicProps: !1,
		dynamicItems: !1
	}, e.v145 = Vn;
	function Vn(e, { instancePath: t = "", parentData: n, parentDataProperty: r, rootData: i = e, dynamicAnchors: a = {} } = {}) {
		let o = Vn.evaluated;
		if (o.dynamicProps && (o.props = void 0), o.dynamicItems && (o.items = void 0), typeof e == "string") {
			if (!u.test(e)) return Vn.errors = [{
				instancePath: t,
				schemaPath: "#/pattern",
				keyword: "pattern",
				params: { pattern: "^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$" }
			}], !1;
		} else return Vn.errors = [{
			instancePath: t,
			schemaPath: "#/type",
			keyword: "type",
			params: { type: "string" }
		}], !1;
		return Vn.errors = null, !0;
	}
	Vn.evaluated = {
		dynamicProps: !1,
		dynamicItems: !1
	}, e.v146 = Hn;
	function Hn(e, { instancePath: t = "", parentData: n, parentDataProperty: r, rootData: i = e, dynamicAnchors: a = {} } = {}) {
		let o = Hn.evaluated;
		if (o.dynamicProps && (o.props = void 0), o.dynamicItems && (o.items = void 0), typeof e != "number" || e % 1 || isNaN(e) || !isFinite(e)) return Hn.errors = [{
			instancePath: t,
			schemaPath: "#/type",
			keyword: "type",
			params: { type: "integer" }
		}], !1;
		if (typeof e == "number" && isFinite(e)) {
			if (e > 2147483647 || isNaN(e)) return Hn.errors = [{
				instancePath: t,
				schemaPath: "#/maximum",
				keyword: "maximum",
				params: {
					comparison: "<=",
					limit: 2147483647
				}
			}], !1;
			if (e < 0 || isNaN(e)) return Hn.errors = [{
				instancePath: t,
				schemaPath: "#/minimum",
				keyword: "minimum",
				params: {
					comparison: ">=",
					limit: 0
				}
			}], !1;
		}
		return Hn.errors = null, !0;
	}
	Hn.evaluated = {
		dynamicProps: !1,
		dynamicItems: !1
	};
}));
//#endregion
export default n();
