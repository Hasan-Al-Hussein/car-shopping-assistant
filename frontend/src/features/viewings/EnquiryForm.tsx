import { useEffect, useRef, useState, useSyncExternalStore } from "react";
import type { Schema } from "../../shared/api/contracts";
import { validateRequestBody } from "../../../../contracts/generated/runtime";
import { useServices } from "../../app/ServicesProvider";
import { refKey } from "../../app/routes";
import { Button } from "../../shared/ui/Button";
import { TextField } from "../../shared/ui/TextField";
import {
  criteriaFromFilters,
  describeCriteria,
  emptyCriteria,
  filtersFromCriteria,
} from "../inventory/criteria";
import { LeadFacts } from "./ViewingFacts";

type Values = Schema<"LeadValues">;
type State = Schema<"ContactValue">["state"];
type Form = {
  budgetState: State;
  minimum: string;
  maximum: string;
  needs: string;
  emailState: State;
  email: string;
  phoneState: State;
  phone: string;
};
function formFrom(values: Values): Form {
  const filters = criteriaFromFilters({
    ...filtersFromCriteria(emptyCriteria()),
    budget: values.budget.value,
  });
  return {
    budgetState: values.budget.state,
    minimum: filters.budgetMin,
    maximum: filters.budgetMax,
    needs: values.requirements.join("\n"),
    emailState: values.email.state,
    email: values.email.value ?? "",
    phoneState: values.phone.state,
    phone: values.phone.value ?? "",
  };
}
export function enquiryValues(
  form: Form,
  original: Values,
  ref: Schema<"InventoryRef">,
): Values {
  const initial = formFrom(original),
    budgetChanged =
      form.budgetState !== initial.budgetState ||
      form.minimum !== initial.minimum ||
      form.maximum !== initial.maximum;
  const budget = budgetChanged
    ? form.budgetState === "provided"
      ? {
          state: "provided" as const,
          value:
            filtersFromCriteria({
              ...emptyCriteria(),
              budgetMin: form.minimum.trim(),
              budgetMax: form.maximum.trim(),
            }).budget ?? null,
        }
      : { state: form.budgetState, value: null }
    : original.budget;
  if (budget.state === "provided" && !budget.value)
    throw Error(
      "Enter at least one cash-budget bound, or choose not provided or declined.",
    );
  const requirements =
    form.needs === initial.needs
      ? original.requirements
      : form.needs
          .split(/\r?\n/)
          .map((line) => line.trim())
          .filter(Boolean);
  if (
    requirements.length > 24 ||
    requirements.some((line) => line.length > 200)
  )
    throw Error("Use up to 24 needs, with at most 200 characters per line.");
  const contact = (state: State, value: string): Schema<"ContactValue"> => {
    if (state === "provided" && !value.trim())
      throw Error(
        "Enter the contact value or choose not provided or declined.",
      );
    return { state, value: state === "provided" ? value.trim() : null };
  };
  const selected_refs = original.selected_refs.some(
    (item) => refKey(item) === refKey(ref),
  )
    ? original.selected_refs
    : [...original.selected_refs, ref];
  if (selected_refs.length > 10)
    throw Error(
      "The saved enquiry already names ten cars. Its existing selections have not been replaced.",
    );
  return {
    budget,
    requirements,
    selected_refs,
    email: contact(form.emailState, form.email),
    phone: contact(form.phoneState, form.phone),
  };
}

export function EnquiryForm({
  sessionId,
  refValue,
  current,
  generation,
}: {
  sessionId: string;
  refValue: Schema<"InventoryRef">;
  current: Schema<"LeadRecord"> | null;
  generation: string;
}) {
  const services = useServices(),
    flow = useSyncExternalStore(
      services.viewings.subscribe,
      services.viewings.getSnapshot,
    );
  const [base, setBase] = useState(current);
  const unsavedValues = (): Values => {
    const criteria = services.currentBrowseRequest();
    return {
      budget: criteria?.filters?.budget
        ? { state: "provided", value: criteria.filters.budget }
        : { state: "missing", value: null },
      requirements: criteria
        ? describeCriteria({
            query: criteria.query,
            filters: criteria.filters
              ? { ...criteria.filters, budget: null }
              : undefined,
            soft_preferences: criteria.soft_preferences,
          })
        : [],
      selected_refs: [refValue],
      email: { state: "missing", value: null },
      phone: { state: "missing", value: null },
    };
  };
  const [original, setOriginal] = useState<Values>(() =>
    current ? structuredClone(current.values) : unsavedValues(),
  );
  const [form, setForm] = useState(() => formFrom(original)),
    [error, setError] = useState<string | null>(null);
  const errorRef = useRef<HTMLParagraphElement>(null);
  useEffect(() => {
    if (error) errorRef.current?.focus();
  }, [error]);
  const changed =
    (base?.lead_id ?? null) !== (current?.lead_id ?? null) ||
    (base?.revision ?? null) !== (current?.revision ?? null);
  const blocked =
    (flow.phase !== "idle" && flow.phase !== "error") ||
    (!!flow.operation && !flow.operationTerminal);
  const status = (
    label: string,
    key: "budgetState" | "emailState" | "phoneState",
  ) => (
    <label className="folio-field">
      <span className="folio-field__label">{label}</span>
      <select
        className="folio-input"
        value={form[key]}
        onChange={(event) =>
          setForm({ ...form, [key]: event.target.value as State })
        }
      >
        <option value="missing">Not provided</option>
        <option value="provided">Provide a value</option>
        <option value="declined">Prefer not to provide</option>
      </select>
    </label>
  );
  return (
    <details className="inner-enquiry-form">
      <summary>Budget, needs and optional contact details</summary>
      {current && (
        <>
          <p>Current enquiry saved locally · revision {current.revision}</p>
          <LeadFacts values={current.values} />
        </>
      )}
      <p>
        These fields are optional. Prefilled search criteria are editable and
        remain unsaved until you choose Save enquiry details. Saving keeps a
        local enquiry and requests a CSV export. It contacts no dealer and
        reserves no viewing.
      </p>
      {changed && (
        <p role="status">
          Saved details changed.{" "}
          <Button
            variant="quiet"
            onClick={() => {
              const values = current
                ? structuredClone(current.values)
                : unsavedValues();
              setBase(current);
              setOriginal(values);
              setForm(formFrom(values));
              setError(null);
            }}
          >
            Reload saved details
          </Button>{" "}
          before saving another correction.
        </p>
      )}
      <form
        className="workspace-form"
        onSubmit={async (event) => {
          event.preventDefault();
          setError(null);
          if (blocked || changed) return;
          try {
            const values = enquiryValues(form, original, refValue);
            const proposed = {
              client_action_id: crypto.randomUUID(),
              session_id: sessionId,
              intent: "save_local_enquiry",
              values,
            };
            if (!validateRequestBody("save_local_enquiry", proposed))
              throw Error(
                "Check the budget, needs and contact fields before saving.",
              );
            await services.viewings.saveEnquiry(
              sessionId,
              values,
              base,
              generation,
            );
          } catch (problem) {
            setError(
              problem instanceof Error
                ? problem.message
                : "Check your enquiry details.",
            );
          }
        }}
      >
        {status("Cash budget information", "budgetState")}
        {form.budgetState === "provided" && (
          <>
            <TextField
              label="Minimum cash budget (AED)"
              inputMode="decimal"
              value={form.minimum}
              maxLength={16}
              onChange={(event) =>
                setForm({ ...form, minimum: event.target.value })
              }
            />
            <TextField
              label="Maximum cash budget (AED)"
              inputMode="decimal"
              value={form.maximum}
              maxLength={16}
              onChange={(event) =>
                setForm({ ...form, maximum: event.target.value })
              }
            />
            <p>
              Cash price, not finance instalments. Leave one bound open if
              needed.
            </p>
            {original.budget.value?.currency &&
              original.budget.value.currency !== "AED" && (
                <p>
                  The existing {original.budget.value.currency} budget is
                  preserved unless these AED bounds are edited.
                </p>
              )}
          </>
        )}
        <label className="folio-field">
          <span className="folio-field__label">
            What you need from the car (one per line)
          </span>
          <textarea
            className="folio-input"
            value={form.needs}
            maxLength={4824}
            rows={4}
            onChange={(event) =>
              setForm({ ...form, needs: event.target.value })
            }
          />
        </label>
        {status("Email information (optional)", "emailState")}
        {form.emailState === "provided" && (
          <TextField
            label="Email (optional)"
            type="email"
            value={form.email}
            maxLength={320}
            autoComplete="off"
            onChange={(event) =>
              setForm({ ...form, email: event.target.value })
            }
          />
        )}
        {status("Phone information (optional)", "phoneState")}
        {form.phoneState === "provided" && (
          <TextField
            label="Phone (optional)"
            type="tel"
            value={form.phone}
            maxLength={320}
            autoComplete="off"
            onChange={(event) =>
              setForm({ ...form, phone: event.target.value })
            }
          />
        )}
        {error && (
          <p role="alert" tabIndex={-1} ref={errorRef}>
            {error}
          </p>
        )}
        <Button type="submit" disabled={blocked || changed}>
          Save enquiry details
        </Button>
      </form>
    </details>
  );
}
