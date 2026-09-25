const labels = {
  source: "Source value",
  claim: "Listing claim",
  "not-stated": "Not stated",
  unknown: "Unknown",
  conflict: "Conflicting details",
  invalid: "Invalid source value",
  "not-applicable": "Not applicable",
  corrected: "Reviewed correction",
} as const;

type FactStatusProps = {
  kind: keyof typeof labels;
};

/** Presentation vocabulary only; the API adapter supplies the evidence kind. */
export function FactStatus({ kind }: FactStatusProps) {
  return (
    <span className="folio-fact-status" data-kind={kind}>
      {labels[kind]}
    </span>
  );
}
