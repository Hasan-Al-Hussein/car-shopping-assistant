import type { Schema } from "../api/contracts";
type DisplayFact =
  | Schema<"ListingSummary">["make"]
  | Schema<"ListingSummary">["year"]
  | Schema<"ListingSummary">["cash_price"];

function formatValue(
  value: string | number | { currency: string; minor_units: number },
  unit?: string,
) {
  if (typeof value === "object")
    return `${value.currency} ${(value.minor_units / 100).toLocaleString("en-AE")}`;
  return `${typeof value === "number" && unit ? value.toLocaleString("en-AE") : value}${unit ? ` ${unit}` : ""}`;
}

/** No inferred preferred value: a conflict renders every supplied claim. */
export function Fact({
  fact,
  unit,
  evidence = false,
}: {
  fact: DisplayFact;
  unit?: string;
  evidence?: boolean;
}) {
  if (fact.status === "unknown")
    return (
      <span className="proof-unknown">
        {fact.reason === "not_stated" ? "Not stated" : "Unknown"}
      </span>
    );
  if (fact.status === "conflicting")
    return (
      <div className="proof-conflicting">
        <span className="proof-fact-caption">Conflicting source claims</span>
        {fact.claims.map((claim, index) => (
          <span className="proof-claim" key={index}>
            <bdi>{formatValue(claim.value, unit)}</bdi>
            <small>{claim.evidence.map((e) => e.cell).join(" / ")}</small>
          </span>
        ))}
      </div>
    );
  return (
    <span className="proof-fact-value">
      <bdi>{formatValue(fact.value, unit)}</bdi>
      {evidence && (
        <small>
          Listing claim · {fact.evidence.map((e) => e.cell).join(" / ")}
        </small>
      )}
    </span>
  );
}
