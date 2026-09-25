import { Fact } from "../Fact";

export type ComparisonFactValue = Parameters<typeof Fact>[0]["fact"];

/** Keep every conflict value visible; the exact source remains one disclosure away. */
export function ComparisonFact({
  fact,
  unit,
  showSources = true,
}: {
  fact: ComparisonFactValue;
  unit?: string;
  showSources?: boolean;
}) {
  const evidence =
    fact.status === "known"
      ? fact.evidence
      : fact.status === "conflicting"
        ? fact.claims.flatMap((claim) => claim.evidence)
        : [];
  return (
    <div className="comparison-fact" data-fact-state={fact.status}>
      <Fact fact={fact} unit={unit} />
      {showSources && evidence.length > 0 && (
        <details className="comparison-source">
          <summary>Source details</summary>
          <p>Listing claims, not independently verified.</p>
          <ul>
            {evidence.map((source, index) => (
              <li key={`${source.evidence_id}-${index}`}>
                <strong>
                  {source.sheet} · {source.cell}
                </strong>
                <q dir="auto">
                  <bdi>{source.raw_text}</bdi>
                </q>
              </li>
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}
