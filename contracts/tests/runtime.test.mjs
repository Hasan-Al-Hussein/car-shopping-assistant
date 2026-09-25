import assert from "node:assert/strict";
import { readFile, writeFile } from "node:fs/promises";
import { spawnSync } from "node:child_process";
import { test, after } from "node:test";
import {
  contractVersion,
  operationContracts,
  validateParameter,
  validateRequestBody,
  validateResponse,
  validateIdentity,
} from "../generated/runtime.ts";
import { validateSchema } from "../generated/runtime.schemas.ts";
import {
  newCompiler,
  normalizeSchema,
  schemaId,
} from "../generate_runtime.mjs";

const document = JSON.parse(
  await readFile(new URL("../v1/openapi.json", import.meta.url)),
);
const cases = JSON.parse(
  await readFile(new URL("../fixtures/cases.json", import.meta.url)),
);
const semantic = JSON.parse(
  await readFile(new URL("../fixtures/semantic_cases.json", import.meta.url)),
);
const meta = { request_id: "00000000-0000-4000-8000-000000000001" };
const checkedSamples = [];

test("all operation metadata matches the committed route authority", () => {
  assert.equal(contractVersion, "1.0.0");
  let count = 0;
  for (const [path, methods] of Object.entries(document.paths)) {
    for (const [method, operation] of Object.entries(methods)) {
      const value = operationContracts[operation.operationId];
      assert.equal(value.method, method.toUpperCase());
      assert.equal(value.path, path);
      assert.equal(value.isPrivate, operation["x-private"]);
      assert.equal(value.mutates, operation["x-mutates-state"]);
      assert.equal(value.hasBody, Boolean(operation.requestBody));
      assert.deepEqual(
        value.successStatuses,
        Object.keys(operation.responses)
          .map(Number)
          .filter((status) => status >= 200 && status < 300),
      );
      assert.deepEqual(
        value.parameters,
        (operation.parameters ?? []).map((parameter) => ({
          in: parameter.in,
          name: parameter.name,
          required: parameter.required === true,
        })),
      );
      count++;
    }
  }
  assert.equal(Object.keys(operationContracts).length, count);
  assert.equal(count, 30);
});

test("valid frozen component fixtures and semantic baselines validate without mutation", () => {
  for (const sample of cases.filter((item) => item.valid)) {
    const before = structuredClone(sample.payload);
    if (sample.model === "OperationStatus") {
      assert.equal(
        validateResponse("get_operation", 200, { data: sample.payload, meta }),
        true,
        sample.id,
      );
    } else {
      assert.equal(
        validateSchema(sample.model, sample.payload),
        true,
        sample.id,
      );
    }
    assert.deepEqual(sample.payload, before);
    checkedSamples.push(sample.id);
  }
  for (const [name, value] of Object.entries(semantic.baselines)) {
    assert.equal(
      Object.hasOwn(document.components.schemas, name),
      true,
      `Missing ${name}`,
    );
    const before = structuredClone(value);
    assert.equal(validateSchema(name, value), true, name);
    assert.deepEqual(value, before);
    checkedSamples.push(`baseline:${name}`);
  }
});

test("schema-expressed invalid fixture cases fail; semantic-only rules remain server owned", () => {
  const ids = [
    "identity-owner-injection",
    "identity-string-bool",
    "budget-float-rejected",
    "budget-finance-not-cash",
    "search-too-many-results",
    "search-string-page",
    "search-unsupported-hard-filter",
    "membership-missing-revision",
    "confirm-time-replacement",
  ];
  for (const id of ids) {
    const sample = cases.find((item) => item.id === id);
    assert.ok(sample);
    assert.equal(validateSchema(sample.model, sample.payload), false, id);
    checkedSamples.push(id);
  }
  // Budget endpoint ordering is a Pydantic semantic validator, absent from JSON Schema.
  const semanticOnly = cases.find((item) => item.id === "budget-reversed");
  assert.equal(validateSchema("BudgetRange", semanticOnly.payload), true);
});

test("tagged unions reject missing, unknown and mismatched branches including default tags", () => {
  const good = {
    preferences: { state: "not_requested" },
    shortlist: { state: "not_requested" },
    lead: { state: "not_requested" },
  };
  assert.equal(validateSchema("MessageActionResults", good), true);
  for (const bad of [
    {},
    { state: "invented" },
    { state: "succeeded" },
    { state: "not_requested", action_id: meta.request_id },
  ]) {
    assert.equal(
      validateSchema("MessageActionResults", { ...good, preferences: bad }),
      false,
    );
  }
  assert.equal(
    validateResponse("get_identity", 200, {
      data: { state: "anonymous" },
      meta,
    }),
    true,
  );
  for (const data of [{}, { state: "unknown" }, { state: "recognized" }]) {
    assert.equal(validateResponse("get_identity", 200, { data, meta }), false);
    assert.equal(validateIdentity(data), false);
  }
  assert.equal(validateIdentity({ state: "anonymous" }), true);
  const recognized = {
    state: "recognized",
    context_id: meta.request_id,
    csrf_token: "x".repeat(43),
    expires_at: "2026-09-24T10:00:00Z",
    display_name: null,
  };
  assert.equal(validateIdentity(recognized), true);
  for (const change of [
    { context_id: "bad" },
    { csrf_token: "bad" },
    { owner_id: "bad" },
  ]) {
    assert.equal(validateIdentity({ ...recognized, ...change }), false);
  }
});

test("responses distinguish documented error schemas and reject unsupported status/operation", () => {
  const error = {
    error: {
      code: "STORE_BUSY",
      message: "Synthetic unavailable state",
      request_id: meta.request_id,
      retryable: true,
      retry_action: "read",
    },
  };
  assert.equal(validateResponse("get_identity", 503, error), true);
  assert.equal(validateResponse("get_identity", 200, error), false);
  assert.equal(validateResponse("get_identity", 299, error), false);
  assert.equal(validateResponse("__proto__", 200, error), false);
  assert.equal(validateSchema("__proto__", {}), false);
});

test("body and parameter boundaries use no coercion, defaults or field removal", () => {
  const sample = cases.find((item) => item.id === "search-trim-and-budget");
  assert.equal(validateRequestBody("search_inventory", sample.payload), true);
  assert.equal(validateRequestBody("get_identity", undefined), true);
  assert.equal(validateRequestBody("get_identity", {}), false);
  assert.equal(validateRequestBody("__proto__", undefined), false);
  const withoutDefaults = Object.freeze({
    notice_version: "DEMO-POLICY-1",
    notice_acknowledged: true,
  });
  assert.equal(
    validateSchema("IdentityBootstrapRequest", withoutDefaults),
    true,
  );
  assert.equal(Object.hasOwn(withoutDefaults, "display_name"), false);
  const bad = { ...withoutDefaults, owner_id: "bad" };
  const before = structuredClone(bad);
  assert.equal(validateSchema("IdentityBootstrapRequest", bad), false);
  assert.deepEqual(bad, before);
  assert.equal(
    validateParameter("get_session_messages", "query", "page_size", 20),
    true,
  );
  assert.equal(
    validateParameter("get_session_messages", "query", "page_size", "20"),
    false,
  );
  assert.equal(
    validateParameter("get_session_messages", "query", "page_size", 51),
    false,
  );
  assert.equal(
    validateParameter("get_session_messages", "query", "PAGE_SIZE", 20),
    false,
  );
  assert.equal(
    validateParameter(
      "get_session_messages",
      "header",
      "x-identity-context",
      "01234567-89ab-4cde-8fab-0123456789ab",
    ),
    true,
  );
  assert.equal(
    validateParameter(
      "get_session_messages",
      "header",
      "X-IDENTITY-CONTEXT",
      undefined,
    ),
    false,
  );
  assert.equal(
    validateParameter("get_session", "path", "session_id", 12),
    false,
  );
  // Exported UUID shape is enforced before dispatch; semantic ownership stays server-side.
  assert.equal(
    validateParameter("get_session", "path", "session_id", "not-a-uuid"),
    false,
  );
});

test("UUID and key parameters enforce all published shape boundaries", () => {
  const uuid = "01234567-89ab-4cde-8fab-0123456789ab";
  const key = "A_z-".repeat(10) + "0ab";
  const samples = new Map([
    [
      "^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$",
      {
        valid: [uuid, "00000000-0000-0000-0000-000000000000"],
        invalid: [
          "",
          "synthetic",
          uuid.toUpperCase(),
          uuid.replaceAll("-", ""),
          uuid + "\n",
          12,
          null,
        ],
      },
    ],
    [
      "^[A-Za-z0-9_-]{43}$",
      {
        valid: [key, "a".repeat(43)],
        invalid: [
          "",
          "a".repeat(42),
          "a".repeat(44),
          "a".repeat(42) + "+",
          "a".repeat(42) + "=",
          key + "\n",
          12,
          null,
        ],
      },
    ],
  ]);
  const counts = [0, 0];
  for (const methods of Object.values(document.paths)) {
    for (const operation of Object.values(methods)) {
      for (const parameter of operation.parameters ?? []) {
        const boundary = samples.get(parameter.schema?.pattern);
        if (!boundary) continue;
        counts[parameter.schema.pattern === "^[A-Za-z0-9_-]{43}$" ? 1 : 0]++;
        const name =
          parameter.in === "header"
            ? parameter.name.toLowerCase()
            : parameter.name;
        for (const value of boundary.valid) {
          assert.equal(
            validateParameter(operation.operationId, parameter.in, name, value),
            true,
            `${operation.operationId}.${name} accepts ${JSON.stringify(value)}`,
          );
        }
        for (const value of boundary.invalid) {
          assert.equal(
            validateParameter(operation.operationId, parameter.in, name, value),
            false,
            `${operation.operationId}.${name} rejects ${JSON.stringify(value)}`,
          );
        }
        assert.equal(
          validateParameter(
            operation.operationId,
            parameter.in,
            name,
            undefined,
          ),
          !parameter.required,
          `${operation.operationId}.${name} preserves requiredness`,
        );
      }
    }
  }
  assert.deepEqual(counts, [34, 14]);
});

test("listing reference path parameters enforce exported boundaries", () => {
  const boundaries = {
    namespace: {
      valid: ["a", "inventory_1-main", "a".repeat(64)],
      invalid: [
        "",
        "a".repeat(65),
        "Inventory",
        "a/b",
        "a b",
        "a\n",
        12,
        null,
        undefined,
      ],
    },
    snapshot_id: {
      valid: ["0".repeat(64), "abcdef0123456789".repeat(4)],
      invalid: [
        "",
        "a".repeat(63),
        "a".repeat(65),
        "A".repeat(64),
        "g".repeat(64),
        "a".repeat(64) + "\n",
        12,
        null,
        undefined,
      ],
    },
    source_id: {
      valid: ["a", "Car_2026.09-24", "A".repeat(128)],
      invalid: [
        "",
        "a".repeat(129),
        "a/b",
        "a b",
        "a%2Fb",
        "a\n",
        12,
        null,
        undefined,
      ],
    },
  };
  for (const operation of [
    "get_listing",
    "add_shortlist_membership",
    "remove_shortlist_membership",
  ]) {
    for (const [name, samples] of Object.entries(boundaries)) {
      for (const value of samples.valid) {
        assert.equal(
          validateParameter(operation, "path", name, value),
          true,
          `${operation}.${name} accepts ${JSON.stringify(value)}`,
        );
      }
      for (const value of samples.invalid) {
        assert.equal(
          validateParameter(operation, "path", name, value),
          false,
          `${operation}.${name} rejects ${JSON.stringify(value)}`,
        );
      }
    }
  }
});

test("compiler fails on unknown validation keywords, formats and external refs", () => {
  assert.throws(
    () => newCompiler().compile({ type: "string", mysteryValidation: true }),
    /unknown keyword/,
  );
  assert.throws(
    () =>
      newCompiler().compile({
        type: "string",
        format: "unsupported-secret-format",
      }),
    /unknown format/,
  );
  assert.throws(
    () => normalizeSchema({ $ref: "https://example.invalid/schema" }, {}),
    /Nonlocal/,
  );
  for (const ref of ["", null, false, 12, "#/components/schemas/Missing"]) {
    assert.throws(() => normalizeSchema({ $ref: ref }, {}), /Nonlocal/);
  }
  assert.throws(
    () =>
      normalizeSchema({ $dynamicRef: "https://example.invalid/schema" }, {}),
    /Unsupported/,
  );
  const validate = newCompiler().compile({
    type: "string",
    format: "date-time",
  });
  assert.equal(validate("2026-09-24T04:00:00Z"), true);
  assert.equal(validate("2026-02-30T04:00:00Z"), false);
});

test("discriminator translation verifies mappings and preserves oneOf constraints", () => {
  const parts = {
    A: {
      type: "object",
      properties: { kind: { const: "a" }, value: { type: "integer" } },
      required: ["value"],
      additionalProperties: false,
    },
    B: {
      type: "object",
      properties: { kind: { enum: ["b", "c"] }, value: { type: "string" } },
      required: ["value"],
      additionalProperties: false,
    },
  };
  const union = {
    discriminator: {
      propertyName: "kind",
      mapping: {
        a: "#/components/schemas/A",
        b: "#/components/schemas/B",
        c: "#/components/schemas/B",
      },
    },
    oneOf: [
      { $ref: "#/components/schemas/A" },
      { $ref: "#/components/schemas/B" },
    ],
  };
  const compiler = newCompiler();
  compiler.addSchema({ $id: schemaId, $defs: parts });
  const validate = compiler.compile(normalizeSchema(union, parts));
  for (const value of [
    { kind: "a", value: 3 },
    { kind: "b", value: "x" },
    { kind: "c", value: "x" },
  ])
    assert.equal(validate(value), true);
  for (const value of [
    { value: 3 },
    { kind: "d", value: 3 },
    { kind: "a", value: "x" },
    { kind: "c", value: 3 },
  ])
    assert.equal(validate(value), false);
  const badMapping = structuredClone(union);
  badMapping.discriminator.mapping.a = "#/components/schemas/B";
  assert.throws(() => normalizeSchema(badMapping, parts), /does not match/);
});

test("generated ESM executes with string code generation disabled", () => {
  const url = new URL("../generated/runtime.ts", import.meta.url).href;
  const script = `import {validateIdentity} from ${JSON.stringify(url)}; if(!validateIdentity({state:'anonymous'}) || validateIdentity({state:'wrong'})) process.exit(2);`;
  const result = spawnSync(
    process.execPath,
    [
      "--disallow-code-generation-from-strings",
      "--input-type=module",
      "-e",
      script,
    ],
    { encoding: "utf-8", timeout: 15000, windowsHide: true },
  );
  assert.equal(result.status, 0, result.stderr);
});

after(async () => {
  await writeFile(
    new URL("../../Records/build/FE-02-platform/samples.json", import.meta.url),
    JSON.stringify(
      {
        checkedSamples,
        semantic_boundary:
          "Pydantic/domain cross-field validators remain server-side",
      },
      null,
      2,
    ) + "\n",
  );
});
