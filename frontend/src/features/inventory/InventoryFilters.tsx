import type { Schema } from "../../shared/api/contracts";
import { Button } from "../../shared/ui/Button";
import { displayCarName } from "../../shared/ui/displayNames";
import { getInventoryFacets } from "./inventoryFacets";
import { emptyCriteria, filtersFromCriteria } from "./criteria";

type SearchCriteria = Pick<
  Schema<"SearchRequest">,
  "filters" | "query" | "soft_preferences"
>;
const terms = [
  ["makes", "Make"],
  ["models", "Model"],
  ["trims", "Trim"],
  ["body_types", "Body"],
  ["fuel_types", "Fuel"],
  ["transmissions", "Transmission"],
] as const;

export function InventoryFilters({
  criteria,
  catalog,
  loading,
  failed,
  retry,
  apply,
  advanced,
}: {
  criteria: SearchCriteria;
  catalog?: readonly Schema<"ListingSummary">[];
  loading: boolean;
  failed: boolean;
  retry: () => void;
  apply: (criteria: SearchCriteria) => void;
  advanced?: () => void;
}) {
  const filters = criteria.filters ?? filtersFromCriteria(emptyCriteria());
  const facets = getInventoryFacets(
    catalog ?? [],
    filters.makes.length === 1 ? filters.makes[0] : undefined,
  );
  const update = (next: Schema<"SearchFilters">) =>
    apply({ ...criteria, filters: next });
  const chips: { key: string; label: string; remove: () => void }[] = [];
  if (criteria.query)
    chips.push({
      key: "query",
      label: `Search: ${criteria.query}`,
      remove: () => apply({ ...criteria, query: "" }),
    });
  for (const [field, label] of terms)
    filters[field].forEach((value, index) =>
      chips.push({
        key: `${field}-${index}`,
        label: `${label}: ${displayCarName(value)}`,
        remove: () =>
          update({
            ...filters,
            [field]: filters[field].filter((_, i) => i !== index),
          }),
      }),
    );
  for (const [field, label] of [
    ["years", "Year"],
    ["mileage_km", "Mileage (km)"],
  ] as const) {
    const range = filters[field];
    if (range)
      chips.push({
        key: field,
        label: `${label}: ${range.minimum ?? "any"}–${range.maximum ?? "any"}`,
        remove: () => update({ ...filters, [field]: null }),
      });
  }
  if (filters.budget) {
    const budget = filters.budget,
      divisor = budget.currency === "AED" ? 100 : 1;
    chips.push({
      key: "budget",
      label: `Cash (${budget.currency}${divisor === 1 ? " minor units" : ""}): ${budget.minimum == null ? "any" : budget.minimum / divisor}–${budget.maximum == null ? "any" : budget.maximum / divisor}`,
      remove: () => update({ ...filters, budget: null }),
    });
  }
  criteria.soft_preferences.forEach((value, index) =>
    chips.push({
      key: `preference-${index}`,
      label: `Preference: ${value}`,
      remove: () =>
        apply({
          ...criteria,
          soft_preferences: criteria.soft_preferences.filter(
            (_, i) => i !== index,
          ),
        }),
    }),
  );
  return (
    <div className="inventory-filters">
      <div className="inventory-filter-bar" aria-label="Inventory filters">
        {(
          [
            ["makes", "Make", facets.makes],
            ["models", "Model", facets.models],
            ["trims", "Trim", facets.trims],
          ] as const
        ).map(([field, label, options]) => (
          <label key={field} className="inventory-filter-field">
            <span>{label}</span>
            <select
              aria-label={label}
              value=""
              disabled={!catalog}
              onChange={(event) => {
                const value = event.currentTarget.value;
                if (value && !filters[field].includes(value))
                  update({ ...filters, [field]: [...filters[field], value] });
              }}
            >
              <option value="">
                {filters[field].length
                  ? `Add ${label.toLowerCase()} · ${filters[field].length} selected`
                  : `All ${label.toLowerCase()}s`}
              </option>
              {options.map((option) => (
                <option
                  key={option.value}
                  value={option.value}
                  disabled={filters[field].includes(option.value)}
                >
                  {option.label} ({option.count})
                </option>
              ))}
            </select>
          </label>
        ))}
        <label className="inventory-filter-field">
          <span>Model year</span>
          <select
            aria-label="Model year"
            value=""
            disabled={!catalog}
            onChange={(event) => {
              if (event.currentTarget.value) {
                const year = Number(event.currentTarget.value);
                update({ ...filters, years: { minimum: year, maximum: year } });
              }
            }}
          >
            <option value="">
              {filters.years ? "Change year" : "All years"}
            </option>
            {facets.years.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label} ({option.count})
              </option>
            ))}
          </select>
        </label>
        {advanced && (
          <Button variant="secondary" onClick={advanced}>
            More filters +
          </Button>
        )}
      </div>
      <p className="inventory-filter-note">
        {catalog
          ? `Choices from ${catalog.length} listings · counts use known source facts`
          : loading
            ? "Loading inventory choices…"
            : "Inventory choices are unavailable. You can still search or use more filters."}
        {failed && (
          <button type="button" onClick={retry}>
            Retry choices
          </button>
        )}
      </p>
      {chips.length > 0 && (
        <div className="inventory-chips" aria-label="Applied search criteria">
          {chips.map((chip) => (
            <button
              key={chip.key}
              type="button"
              className="inventory-chip"
              onClick={chip.remove}
              aria-label={`Remove ${chip.label}`}
            >
              {chip.label}
              <span aria-hidden="true">×</span>
            </button>
          ))}
          <button
            type="button"
            className="inventory-clear"
            onClick={() =>
              apply({
                query: "",
                soft_preferences: [],
                filters: filtersFromCriteria(emptyCriteria()),
              })
            }
          >
            Clear all
          </button>
        </div>
      )}
    </div>
  );
}
