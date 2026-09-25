import type {
  components,
  operations,
} from "../../../../contracts/generated/api";

export type Operation = keyof operations;
export type Schema<Name extends keyof components["schemas"]> =
  components["schemas"][Name];
type JsonPayload<T> = T extends {
  content: { "application/json": infer Payload };
}
  ? Payload
  : never;
export type ResponseOf<Name extends Operation> = JsonPayload<
  operations[Name]["responses"][Extract<
    keyof operations[Name]["responses"],
    200 | 201
  >]
>;
export type BodyOf<Name extends Operation> = JsonPayload<
  NonNullable<operations[Name]["requestBody"]>
>;
type Params<
  Name extends Operation,
  Location extends "path" | "query" | "header",
> = NonNullable<operations[Name]["parameters"][Location]>;
type CallerHeaders<Name extends Operation> = [Params<Name, "header">] extends [
  never,
]
  ? never
  : Omit<
      Params<Name, "header">,
      "Origin" | "X-Identity-Context" | "X-CSRF-Token"
    >;
type RequiredPart<Key extends string, Value> = [Value] extends [never]
  ? { [Part in Key]?: never }
  : keyof Value extends never
    ? { [Part in Key]?: never }
    : { [Part in Key]: Value };

export type RequestOf<Name extends Operation> = RequiredPart<
  "body",
  BodyOf<Name>
> &
  RequiredPart<"path", Params<Name, "path">> &
  RequiredPart<"headers", CallerHeaders<Name>> & {
    query?: Params<Name, "query">;
    signal?: AbortSignal;
  };
