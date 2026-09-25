# Generated client contracts

`v1/openapi.json` is the accepted wire authority. `generated/api.ts` is its existing static TypeScript projection. Do not edit generated files by hand. The runtime generator does not modify either accepted artifact.

From `frontend/`, run `npm run generate:runtime` after an authorized contract change, then `npm run test:runtime`. Generation requires the pinned development toolchain in `package-lock.json`: Node 24.13.0, Ajv 8.20.0, ajv-formats 3.0.1 and Vite 8.3.0. It compiles JSON Schema 2020-12 locally and emits deterministic ESM. No compiler or schema download is required in the browser.

Production imports come from `generated/runtime.ts`: `contractVersion`, `operationContracts`, `validateIdentity`, `validateRequestBody`, `validateResponse` and `validateParameter`. All checks return booleans and expose no validator errors. Operation names are typed against `api.ts`; metadata comes from the same OpenAPI document. Unknown operation/status/parameter combinations fail. A no-body operation accepts only `undefined`. Parameter values must already have their intended type; header names alone are case-insensitive.

General-purpose `validateSchema` is exported separately from `generated/runtime.schemas.ts` for fixtures and callers needing arbitrary named components. Do not import that registry into the production transport: it adds duplicate public validator roots. The narrow identity helper checks the exact canonical AnonymousIdentity or RecognizedIdentity schema. The current transport registry contains 57 roots, retaining all 129 components transitively.

The generator resolves only existing local component references, rejects other schema scopes/external/missing/empty refs and unknown assertion keywords/formats, and checks each discriminator mapping against branch const/enum tags before emitting dispatch. Missing or unknown tags fail even when a selected branch has an optional default tag. It preserves oneOf branch constraints. No coercion, default insertion, extra-field removal or payload mutation is enabled.

`title`, `description`, `default`, `examples`, `readOnly`, `writeOnly` and `deprecated` are annotations: they are retained but do not become validation assertions or insert values. Validation assertions are not stripped for size. The committed graph currently has no `format` keywords; synthetic compiler checks prove installed format support and unknown-format rejection. Canonical UTC timestamps use patterns, which alone do not prove calendar validity.

Schema success does not replace server authorization, ownership, CSRF/origin checks, Pydantic cross-field validators, date semantics or revision/receipt associations. Identifier and key path/header schemas now publish the patterns already enforced by the runtime; other string parameters retain their declared constraints. The consumer must separately require matching contract/policy metadata, enforce identity epochs/expiry, and apply its request/response association checks. Defaults in a schema do not mean the server sent a value.

Evidence and replay commands: `Records/build/FE-02-platform/readiness.md`. The measured production bundle size is not a browser parse/interaction performance result.
