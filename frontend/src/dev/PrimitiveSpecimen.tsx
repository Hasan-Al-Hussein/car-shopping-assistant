import { useState } from "react";
import sourceFacts from "../../../fixtures/shared/source-facts.json";
import { Button } from "../shared/ui/Button";
import { FactStatus } from "../shared/ui/FactStatus";
import { ListingPhoto } from "../shared/ui/ListingPhoto";
import { StatusNotice } from "../shared/ui/StatusNotice";
import { TextField } from "../shared/ui/TextField";
import "./specimen.css";

const arabicTitle = sourceFacts.cases.find(
  (item) => item.id === "arabic-title-exact-unicode",
)?.raw_value;
const factKinds = [
  "source",
  "claim",
  "not-stated",
  "unknown",
  "conflict",
  "invalid",
  "not-applicable",
  "corrected",
] as const;

/** Development specimen only: no identity, inventory request or domain mutation. */
export function PrimitiveSpecimen() {
  const [largeText, setLargeText] = useState(false);
  const [query, setQuery] = useState("Mazda 3 / DBX 707");
  const [budget, setBudget] = useState("not a number");
  const [feedback, setFeedback] = useState("Nothing has been saved.");
  const invalidBudget = budget.length > 0 && !/^\d+$/.test(budget);

  return (
    <main
      className="specimen"
      id="specimen-main"
      data-text-size={largeText ? "double" : "normal"}
    >
      <header className="specimen__header">
        <p className="specimen__eyebrow">
          Car decision folio · Component study
        </p>
        <h1>Clarity, even when details are missing.</h1>
        <p className="specimen__intro">
          Read a fact, find the next action, and understand what still needs a
          check. This is an interface specimen; its controls do not search
          inventory or save a viewing.
        </p>
        <Button
          variant="quiet"
          aria-pressed={largeText}
          onClick={() => setLargeText(!largeText)}
        >
          {largeText ? "Restore normal text" : "Preview 200% text"}
        </Button>
        <p className="specimen__note">
          Development text-enlargement check; this does not change browser zoom.
        </p>
      </header>

      <section className="specimen__section" aria-labelledby="control-heading">
        <div className="specimen__section-heading">
          <span className="specimen__index" aria-hidden="true">
            01
          </span>
          <h2 id="control-heading">Actions &amp; clear labels</h2>
        </div>
        <div className="specimen__two-column">
          <form
            onSubmit={(event) => {
              event.preventDefault();
              setFeedback("Specimen checked. No search or save was sent.");
            }}
          >
            <TextField
              label="Search within the specimen"
              hint="Numeric model names keep their meaning: Mazda 3 and DBX 707."
              name="specimen-query"
              required
              value={query}
              onChange={(event) => setQuery(event.target.value)}
            />
            <TextField
              label="Example budget in AED"
              hint="Correct the example to see the error clear. This is not a listing price."
              name="specimen-budget"
              inputMode="numeric"
              value={budget}
              error={
                invalidBudget ? "Enter a whole amount using digits." : undefined
              }
              onChange={(event) => setBudget(event.target.value)}
            />
            <Button type="submit" disabled={invalidBudget}>
              Check specimen
            </Button>
          </form>
          <div className="specimen__controls">
            <div className="specimen__actions">
              <Button
                onClick={() =>
                  setFeedback(
                    "Review wording selected. No viewing was requested.",
                  )
                }
              >
                Review simulated viewing
              </Button>
              <Button
                variant="secondary"
                onClick={() =>
                  setFeedback(
                    "Comparison wording selected. No cars were added.",
                  )
                }
              >
                Compare selected cars
              </Button>
              <Button
                variant="quiet"
                onClick={() =>
                  setFeedback(
                    "Continue wording selected. No navigation or save was sent.",
                  )
                }
              >
                Continue browsing
              </Button>
              <Button variant="secondary" disabled>
                Saving is unavailable in this specimen
              </Button>
            </div>
            <a className="folio-link" href="#source-heading">
              Read the source-text examples
            </a>
            <TextField
              label="Read-only source title"
              readOnly
              value={String(arabicTitle ?? "")}
              dir="auto"
            />
            <TextField
              label="Unavailable field"
              disabled
              value="No input required"
            />
            <StatusNotice title={feedback} announcement="polite" />
          </div>
        </div>
      </section>

      <section className="specimen__section" aria-labelledby="source-heading">
        <div className="specimen__section-heading">
          <span className="specimen__index" aria-hidden="true">
            02
          </span>
          <h2 id="source-heading" tabIndex={-1}>
            Source text keeps its meaning
          </h2>
        </div>
        <p className="specimen__note">
          Preserved source examples: Mazda model 3 (D13), DBX trim 707 (E23),
          and the complete Arabic title (F36).
        </p>
        <p className="specimen__source folio-source-text" dir="auto">
          {arabicTitle}
        </p>
        <p className="folio-source-text">
          {
            "Synthetic long-text probe: Mazda 3 / DBX 707 — title, trim, units and negation must remain readable when a buyer enlarges text. لا يوجد ضمان — listing text is a source claim, not a verified inspection."
          }
        </p>
        <div className="specimen__facts" aria-label="Evidence wording examples">
          {factKinds.map((kind) => (
            <FactStatus key={kind} kind={kind} />
          ))}
        </div>
        <p className="specimen__note">
          Price not stated · A missing amount is different from zero. A source
          value is different from an independent inspection.
        </p>
      </section>

      <section className="specimen__section" aria-labelledby="photo-heading">
        <div className="specimen__section-heading">
          <span className="specimen__index" aria-hidden="true">
            03
          </span>
          <h2 id="photo-heading">The facts stay usable without a photo</h2>
        </div>
        <p className="specimen__note">
          Media-state fixtures for the same preserved title. The unavailable
          image is a deliberate local failure injection; it does not change the
          source workbook.
        </p>
        <div className="specimen__photos">
          <figure>
            <ListingPhoto
              identity={`fixture:${sourceFacts.workbook_sha256}:cleaned:35:missing`}
              src={null}
              alt="Photo supplied with this car listing"
            />
            <figcaption>
              <bdi dir="auto">{arabicTitle}</bdi> · Missing-photo fixture
            </figcaption>
          </figure>
          <figure>
            <ListingPhoto
              identity={`fixture:${sourceFacts.workbook_sha256}:cleaned:35:failed`}
              src="/__fe01__/intentional-image-failure"
              alt="Photo supplied with this car listing"
              loading="eager"
            />
            <figcaption>
              <bdi dir="auto">{arabicTitle}</bdi> · Failed-photo fixture
            </figcaption>
          </figure>
        </div>
      </section>

      <section className="specimen__section" aria-labelledby="status-heading">
        <div className="specimen__section-heading">
          <span className="specimen__index" aria-hidden="true">
            04
          </span>
          <h2 id="status-heading">State is explained in words</h2>
        </div>
        <p className="specimen__note">
          Illustrative wording only. These are not outcomes of an actual
          request.
        </p>
        <div className="specimen__notices">
          <StatusNotice title="Checking the original request">
            The result is still being checked.
          </StatusNotice>
          <StatusNotice tone="attention" title="Outcome not yet known">
            The original request may have completed. Check its status before
            starting another attempt.
          </StatusNotice>
          <StatusNotice tone="success" title="Saved locally">
            A local save does not mean an enquiry was sent to a dealer.
          </StatusNotice>
          <StatusNotice tone="error" title="Could not load the listing">
            The read failed. This does not establish that the car was sold.
          </StatusNotice>
        </div>
      </section>
      <footer className="specimen__footer">
        Native controls · Visible focus · Source text preserved · No product
        action connected
      </footer>
    </main>
  );
}
