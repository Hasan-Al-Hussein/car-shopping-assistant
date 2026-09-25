/** Compile only the committed local contract; browser output contains no schema compiler. */
import { createHash } from "node:crypto";
import { readFile, mkdir, writeFile } from "node:fs/promises";
import { createRequire } from "node:module";
import { dirname, join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { gzipSync } from "node:zlib";

const contracts = dirname(fileURLToPath(import.meta.url));
const project = dirname(contracts);
const frontend = join(project, "frontend");
const require = createRequire(join(frontend, "package.json"));
const Ajv2020 = require("ajv/dist/2020").default;
const addFormats = require("ajv-formats").default;
const standalone = require("ajv/dist/standalone").default;
const { build } = await import(pathToFileURL(require.resolve("vite")).href);
export const schemaId = "urn:car-shopping-assistant:contract:1";

/** Resolve local component refs only. No loadSchema/network fallback is configured. */
export function normalizeSchema(
  schema,
  components,
  tally = { discriminators: 0 },
) {
  if (typeof schema === "boolean") return schema;
  if (!schema || typeof schema !== "object" || Array.isArray(schema)) {
    throw new Error("Expected JSON Schema object");
  }
  const out = structuredClone(schema);
  for (const keyword of [
    "$id",
    "$schema",
    "$dynamicRef",
    "$anchor",
    "$dynamicAnchor",
  ]) {
    if (Object.hasOwn(out, keyword))
      throw new Error(`Unsupported schema scope keyword: ${keyword}`);
  }
  if (Object.hasOwn(out, "$ref")) {
    const prefix = "#/components/schemas/";
    if (
      typeof out.$ref !== "string" ||
      !out.$ref.startsWith(prefix) ||
      !Object.hasOwn(components, out.$ref.slice(prefix.length))
    ) {
      throw new Error(`Nonlocal or missing schema reference: ${out.$ref}`);
    }
    out.$ref = `${schemaId}#/$defs/${out.$ref.slice(prefix.length)}`;
  }
  if (out.discriminator) {
    const { propertyName, mapping, ...unknown } = out.discriminator;
    if (
      typeof propertyName !== "string" ||
      !mapping ||
      Object.keys(unknown).length ||
      !out.oneOf
    ) {
      throw new Error("Unsupported discriminator shape");
    }
    const tags = new Map();
    for (const branch of out.oneOf) {
      if (Object.keys(branch).length !== 1 || typeof branch.$ref !== "string") {
        throw new Error("Discriminator branches must be local component refs");
      }
      const component =
        components[branch.$ref.replace("#/components/schemas/", "")];
      const property = component?.properties?.[propertyName];
      const branchTags =
        property?.const !== undefined ? [property.const] : property?.enum;
      if (!Array.isArray(branchTags) || branchTags.length === 0) {
        throw new Error(`Missing discriminator const/enum: ${branch.$ref}`);
      }
      for (const tag of branchTags) {
        if (
          typeof tag !== "string" ||
          tags.has(tag) ||
          mapping[tag] !== branch.$ref
        ) {
          throw new Error(
            `Discriminator mapping does not match branch: ${branch.$ref}`,
          );
        }
        tags.set(tag, branch.$ref);
      }
    }
    if (Object.keys(mapping).length !== tags.size)
      throw new Error("Unmatched discriminator mapping");
    // OpenAPI discriminator dispatch requires its tag even when a branch has a default.
    // Translate mapping to verified Ajv dispatch; retain every original oneOf constraint.
    out.discriminator = { propertyName };
    out.type = "object";
    out.required = [...new Set([...(out.required ?? []), propertyName])];
    out.properties = {
      ...out.properties,
      [propertyName]: out.properties?.[propertyName] ?? { type: "string" },
    };
    tally.discriminators += 1;
  }
  for (const keyword of [
    "properties",
    "patternProperties",
    "$defs",
    "dependentSchemas",
  ]) {
    if (out[keyword])
      out[keyword] = Object.fromEntries(
        Object.entries(out[keyword]).map(([key, value]) => [
          key,
          normalizeSchema(value, components, tally),
        ]),
      );
  }
  for (const keyword of [
    "items",
    "additionalProperties",
    "unevaluatedProperties",
    "not",
    "if",
    "then",
    "else",
    "contains",
  ]) {
    if (out[keyword] !== undefined)
      out[keyword] = normalizeSchema(out[keyword], components, tally);
  }
  for (const keyword of ["oneOf", "anyOf", "allOf", "prefixItems"]) {
    if (out[keyword])
      out[keyword] = out[keyword].map((value) =>
        normalizeSchema(value, components, tally),
      );
  }
  return out;
}

export function newCompiler() {
  const ajv = new Ajv2020({
    strict: true,
    allErrors: false,
    messages: false,
    discriminator: true,
    inlineRefs: false,
    useDefaults: false,
    coerceTypes: false,
    removeAdditional: false,
    validateFormats: true,
    ownProperties: true,
    code: { source: true, esm: false },
  });
  addFormats(ajv, { mode: "full" });
  return ajv;
}

export async function generate() {
  const bytes = await readFile(join(contracts, "v1/openapi.json"));
  const document = JSON.parse(bytes);
  if (document.openapi !== "3.1.0")
    throw new Error("Unsupported OpenAPI dialect");
  const components = document.components.schemas;
  const tally = { discriminators: 0 };
  const definitions = Object.fromEntries(
    Object.keys(components)
      .sort()
      .map((name) => [
        name,
        normalizeSchema(components[name], components, tally),
      ]),
  );
  const operationContracts = {};
  const bodies = {};
  const responses = {};
  const parameters = {};
  const exports = {};
  const schemaValidators = {};
  const registeredSchemas = new Map();
  let sequence = 0;
  const register = (schema) => {
    if (
      Object.keys(schema).length === 1 &&
      schema.$ref?.startsWith("#/components/schemas/")
    ) {
      const existing =
        schemaValidators[schema.$ref.slice("#/components/schemas/".length)];
      if (existing) return existing;
    }
    const identity = JSON.stringify(schema);
    if (registeredSchemas.has(identity)) return registeredSchemas.get(identity);
    const key = `v${sequence++}`;
    definitions[key] = normalizeSchema(schema, components, tally);
    exports[key] = `${schemaId}#/$defs/${key}`;
    registeredSchemas.set(identity, key);
    return key;
  };
  for (const name of Object.keys(components).sort()) {
    const key = `v${sequence++}`;
    exports[key] = `${schemaId}#/$defs/${name}`;
    schemaValidators[name] = key;
  }
  for (const [path, methods] of Object.entries(document.paths)) {
    for (const [method, operation] of Object.entries(methods)) {
      if (
        !["get", "post", "patch", "put", "delete", "head", "options"].includes(
          method,
        )
      ) {
        throw new Error(`Unsupported path entry ${method}`);
      }
      const op = operation.operationId;
      if (
        !op ||
        operationContracts[op] ||
        typeof operation["x-private"] !== "boolean" ||
        typeof operation["x-mutates-state"] !== "boolean"
      )
        throw new Error("Operation metadata incomplete");
      const parameterList = operation.parameters ?? [];
      parameters[op] = {};
      for (const parameter of parameterList) {
        if (
          !["path", "query", "header"].includes(parameter.in) ||
          !parameter.schema ||
          parameter.$ref
        ) {
          throw new Error("Unsupported parameter shape");
        }
        const key = `${parameter.in}:${parameter.in === "header" ? parameter.name.toLowerCase() : parameter.name}`;
        if (Object.hasOwn(parameters[op], key))
          throw new Error("Duplicate parameter");
        parameters[op][key] = {
          validator: register(parameter.schema),
          required: parameter.required === true,
        };
      }
      if (operation.requestBody) {
        if (
          Object.keys(operation.requestBody.content).join() !==
            "application/json" ||
          operation.requestBody.required !== true
        )
          throw new Error("Unsupported request body");
        bodies[op] = register(
          operation.requestBody.content["application/json"].schema,
        );
      }
      responses[op] = {};
      for (const [status, response] of Object.entries(operation.responses)) {
        if (
          !/^\d{3}$/.test(status) ||
          Object.keys(response.content ?? {}).join() !== "application/json"
        ) {
          throw new Error("Unsupported response shape");
        }
        responses[op][status] = register(
          response.content["application/json"].schema,
        );
      }
      operationContracts[op] = {
        method: method.toUpperCase(),
        path,
        isPrivate: operation["x-private"],
        mutates: operation["x-mutates-state"],
        parameters: parameterList.map(({ in: location, name, required }) => ({
          in: location,
          name,
          required: required === true,
        })),
        hasBody: Object.hasOwn(bodies, op),
        successStatuses: Object.keys(responses[op])
          .map(Number)
          .filter((status) => status >= 200 && status < 300),
      };
    }
  }
  const ajv = newCompiler();
  ajv.addSchema({
    $id: schemaId,
    $schema: "https://json-schema.org/draft/2020-12/schema",
    $defs: definitions,
  });
  const raw = standalone(ajv, exports);
  const evidence = join(project, "Records/build/FE-02-platform");
  await mkdir(evidence, { recursive: true });
  const rawPath = join(evidence, "standalone-input.cjs");
  await writeFile(rawPath, raw);
  const endpointKeys = new Set([
    ...Object.values(bodies),
    ...Object.values(responses).flatMap(Object.values),
    ...Object.values(parameters).flatMap((items) =>
      Object.values(items).map((item) => item.validator),
    ),
    schemaValidators.AnonymousIdentity,
    schemaValidators.RecognizedIdentity,
  ]);
  if (endpointKeys.has(undefined))
    throw new Error("Missing canonical identity components");
  const endpointPath = join(evidence, "standalone-endpoints.cjs");
  await writeFile(
    endpointPath,
    standalone(
      ajv,
      Object.fromEntries(
        Object.entries(exports).filter(([key]) => endpointKeys.has(key)),
      ),
    ),
  );
  // Use the already selected Vite bundler to include only generated runtime helpers.
  async function bundleStandalone(entry) {
    const bundle = await build({
      configFile: false,
      root: frontend,
      publicDir: false,
      logLevel: "silent",
      resolve: {
        alias: [
          { find: /^ajv\//, replacement: join(frontend, "node_modules/ajv/") },
          {
            find: /^ajv-formats\//,
            replacement: join(frontend, "node_modules/ajv-formats/"),
          },
        ],
      },
      build: {
        write: false,
        emptyOutDir: false,
        minify: true,
        target: "es2022",
        sourcemap: false,
        lib: { entry, formats: ["es"], fileName: "runtime.validators" },
      },
    });
    const builds = Array.isArray(bundle) ? bundle : [bundle];
    const chunks = builds
      .flatMap((result) => result.output ?? [])
      .filter((item) => item.type === "chunk");
    if (
      chunks.length !== 1 ||
      chunks[0].imports.length ||
      chunks[0].dynamicImports.length
    ) {
      throw new Error("Standalone output must be a single import-free module");
    }
    const code = chunks[0].code;
    if (
      /\beval\s*\(|\bnew\s+Function\s*\(|\bFunction\s*\(/.test(code) ||
      /ajv\/dist\/(?:compile|2020|core)/.test(code)
    )
      throw new Error("Runtime compiler detected");
    return code;
  }
  const code = await bundleStandalone(rawPath);
  const endpointCode = await bundleStandalone(endpointPath);
  const output = join(contracts, "generated");
  await writeFile(join(output, "runtime.validators.mjs"), code);
  await writeFile(join(output, "runtime.endpoints.mjs"), endpointCode);
  for (const name of ["runtime.validators.d.mts", "runtime.endpoints.d.mts"]) {
    await writeFile(
      join(output, name),
      "declare const validators: Readonly<Record<string, (value: unknown) => boolean>>;\nexport default validators;\n",
    );
  }
  const render = (value) => JSON.stringify(value, null, 2);
  await writeFile(
    join(output, "runtime.schemas.ts"),
    `// Generated by contracts/generate_runtime.mjs. Do not edit.\n` +
      `import type { components } from './api';\n` +
      `import validators from './runtime.validators.mjs';\n` +
      `type SchemaName = keyof components['schemas'];\n` +
      `const schemaValidators: Readonly<Record<SchemaName,string>> = ${render(schemaValidators)};\n` +
      `export function validateSchema(name: SchemaName, value: unknown): boolean { if (!Object.hasOwn(schemaValidators,name)) return false; const key = schemaValidators[name]; return Object.hasOwn(validators,key) && validators[key]!(value) === true; }\n`,
  );
  const facade =
    `// Generated by contracts/generate_runtime.mjs. Do not edit.\n` +
    `import type { components, operations } from './api';\n` +
    `import validators from './runtime.endpoints.mjs';\n` +
    `export const contractVersion = ${JSON.stringify(document.info.version)} as const;\n` +
    `export type OperationId = keyof operations;\nexport type SchemaName = keyof components['schemas'];\n` +
    `export type ParameterLocation = 'path' | 'query' | 'header';\n` +
    `export interface OperationContract { readonly method: string; readonly path: string; readonly isPrivate: boolean; readonly mutates: boolean; readonly parameters: readonly { readonly in: ParameterLocation; readonly name: string; readonly required: boolean }[]; readonly hasBody: boolean; readonly successStatuses: readonly number[]; }\n` +
    `export const operationContracts: Readonly<Record<OperationId, OperationContract>> = ${render(operationContracts)};\n` +
    `const bodies: Readonly<Partial<Record<OperationId, string>>> = ${render(bodies)};\n` +
    `const responses: Readonly<Record<OperationId, Readonly<Record<string,string>>>> = ${render(responses)};\n` +
    `const parameters: Readonly<Record<OperationId, Readonly<Record<string,{validator:string;required:boolean}>>>> = ${render(parameters)};\n` +
    `const has = (object: object, key: PropertyKey): boolean => Object.hasOwn(object, key);\n` +
    `const check = (key: string | undefined, value: unknown): boolean => key !== undefined && has(validators,key) && validators[key]!(value) === true;\n` +
    `export function validateIdentity(value: unknown): boolean { return check(${render(schemaValidators.AnonymousIdentity)},value) || check(${render(schemaValidators.RecognizedIdentity)},value); }\n` +
    `export function validateRequestBody(op: OperationId, value: unknown): boolean { return has(operationContracts,op) && (has(bodies,op) ? check(bodies[op],value) : value === undefined); }\n` +
    `export function validateResponse(op: OperationId, status: number, value: unknown): boolean { return has(responses,op) && has(responses[op],status) && check(responses[op][String(status)],value); }\n` +
    `export function validateParameter(op: OperationId, location: ParameterLocation, name: string, value: unknown): boolean { if (!has(parameters,op)) return false; const key = location + ':' + (location === 'header' ? name.toLowerCase() : name); if (!has(parameters[op],key)) return false; const parameter = parameters[op][key]!; return value === undefined && !parameter.required ? true : check(parameter.validator,value); }\n`;
  await writeFile(join(output, "runtime.ts"), facade);
  const manifest = {
    contract_version: document.info.version,
    openapi_sha256: createHash("sha256").update(bytes).digest("hex"),
    dialect: "2020-12",
    operations: Object.keys(operationContracts).length,
    components: Object.keys(components).length,
    validators: Object.keys(exports).length,
    discriminator_translations: tally.discriminators,
    standalone_bytes: Buffer.byteLength(code),
    standalone_gzip_bytes: gzipSync(code).byteLength,
    endpoint_validators: endpointKeys.size,
    endpoint_standalone_bytes: Buffer.byteLength(endpointCode),
    endpoint_standalone_gzip_bytes: gzipSync(endpointCode).byteLength,
    ajv: require("ajv/package.json").version,
    formats: require("ajv-formats/package.json").version,
    vite: require("vite/package.json").version,
  };
  await writeFile(
    join(output, "runtime-manifest.json"),
    JSON.stringify(manifest, null, 2) + "\n",
  );
  return manifest;
}

if (
  process.argv[1] &&
  fileURLToPath(import.meta.url) ===
    fileURLToPath(pathToFileURL(process.argv[1]))
) {
  console.log(JSON.stringify(await generate(), null, 2));
}
