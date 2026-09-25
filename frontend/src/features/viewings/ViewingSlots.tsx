import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import type { Schema } from "../../shared/api/contracts";
import { useServices } from "../../app/ServicesProvider";
import { Button } from "../../shared/ui/Button";
import { TextField } from "../../shared/ui/TextField";
import { ReadFailure } from "../inventory/InventoryRoutes";
import { viewingTime } from "./ViewingFacts";

const todayInDubai = () => {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Dubai",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(new Date());
  const part = (name: string) =>
    parts.find((value) => value.type === name)?.value;
  return `${part("year")}-${part("month")}-${part("day")}`;
};

/** Availability is a public read; selected slots remain local until an explicit draft action. */
export function ViewingSlots({
  inventoryRef,
  selected,
  onSelect,
  disabled = false,
}: {
  inventoryRef: Schema<"InventoryRef">;
  selected: Schema<"AppointmentSelection"> | null;
  onSelect: (selection: Schema<"AppointmentSelection"> | null) => void;
  disabled?: boolean;
}) {
  const services = useServices();
  const [day, setDay] = useState(todayInDubai),
    [requestedDay, setRequestedDay] = useState<string | null>(null);
  const result = useQuery({
    ...services.queries.publicRead(
      "get_viewing_options",
      {
        body: {
          ref: inventoryRef,
          from_date: requestedDay ?? todayInDubai(),
          days: 1,
        },
      },
      inventoryRef.snapshot_id,
    ),
    enabled: requestedDay !== null,
  });
  const options = result.data?.data;
  return (
    <section className="inner-viewing-slots" aria-label="Viewing times">
      <h3>Choose a viewing time</h3>
      <p>
        Choose a time to review. Checking or choosing a time does not reserve
        it.
      </p>
      <form
        className="workspace-form"
        onSubmit={(event) => {
          event.preventDefault();
          if (disabled || !day) return;
          onSelect(null);
          if (requestedDay === day) void result.refetch();
          else setRequestedDay(day);
        }}
      >
        <TextField
          label="Viewing date (Asia/Dubai)"
          type="date"
          value={day}
          required
          disabled={disabled}
          onChange={(event) => {
            setDay(event.target.value);
            onSelect(null);
            setRequestedDay(null);
          }}
        />
        <Button
          type="submit"
          variant="secondary"
          disabled={disabled || !day || result.isFetching}
        >
          Check viewing times
        </Button>
      </form>
      {requestedDay &&
        (result.isFetching ? (
          <p role="status">Checking the selected day…</p>
        ) : result.isError ? (
          <ReadFailure
            error={result.error}
            retry={() => void result.refetch()}
          />
        ) : (
          options && (
            <>
              <p>
                Calculated {viewingTime(options.calculated_at, "Asia/Dubai")} ·
                Asia/Dubai. Availability is checked again at confirmation.
              </p>
              {options.state === "available" ? (
                <fieldset className="inner-slot-options" disabled={disabled}>
                  <legend>Available simulated intervals · Asia/Dubai</legend>
                  {options.slots.map((slot) => (
                    <label key={slot.starts_at_utc}>
                      <input
                        type="radio"
                        name="viewing-slot"
                        checked={selected?.starts_at_utc === slot.starts_at_utc}
                        onChange={() =>
                          onSelect({
                            starts_at_utc: slot.starts_at_utc,
                            timezone: slot.timezone,
                            appointment_type: "viewing",
                          })
                        }
                      />
                      <span>
                        <time dateTime={slot.starts_at_utc}>
                          {viewingTime(slot.starts_at_utc, slot.timezone)}
                        </time>
                        <br />
                        to{" "}
                        <time dateTime={slot.ends_at_utc}>
                          {viewingTime(slot.ends_at_utc, slot.timezone)}
                        </time>
                      </span>
                    </label>
                  ))}
                </fieldset>
              ) : (
                <p role="status">
                  {options.state === "unconfigured"
                    ? "Viewing rules are not configured. No times can be offered."
                    : options.state === "ineligible"
                      ? "This exact car is not eligible for a simulated viewing."
                      : "No valid viewing times were returned for this day. Choose another date."}
                </p>
              )}
            </>
          )
        ))}
    </section>
  );
}
