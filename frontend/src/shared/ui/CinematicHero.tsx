import { useState } from "react";
import { Link } from "react-router";
import { TextField } from "./TextField";
import { CinemaIcon as Icon } from "./CinemaIcon";

export function CinematicHero({
  applySearch,
  browseLink = "/#collection",
  searchLabel = "Search the sample listings",
  mobileDisclosure = "Local search · AI is not connected",
  disclosure = "Local search works here. AI conversation is not connected in this design preview.",
}: {
  applySearch: (query: string) => void;
  browseLink?: string;
  searchLabel?: string;
  mobileDisclosure?: string;
  disclosure?: string;
}) {
  const [assistantEntry, setAssistantEntry] = useState("");
  const [assistantOpen, setAssistantOpen] = useState(false);
  return (
    <section className="cinema-hero" aria-labelledby="page-heading">
      <div className="cinema-hero-content cinema-width">
        <div className="cinema-hero-copy">
          <p className="cinema-eyebrow">A LITTLE CLARITY. A NEW DIRECTION.</p>
          <h1 id="page-heading" tabIndex={-1}>
            Find your
            <br />
            next <em>chapter.</em>
          </h1>
          <p className="cinema-hero-support">
            <span className="cinema-desktop-copy">
              Explore the cars. Understand the details.
              <br />
              Make your next move with perspective.
            </span>
            <span className="cinema-mobile-copy">
              Explore real listings, with perspective.
            </span>
          </p>
          <div className="cinema-hero-actions">
            <Link
              className="folio-button folio-button--primary"
              to={browseLink}
            >
              Explore the cars <span aria-hidden="true">↗</span>
            </Link>
            <Link
              className="folio-button folio-button--secondary cinema-compare-cta"
              to="/compare"
            >
              <Icon kind="compare" /> Compare options
            </Link>
          </div>
        </div>
        <figure className="cinema-hero-scene">
          <img
            className="cinema-hero-art"
            src="/cinematic/editorial/user-supplied-generated-hero.png"
            alt="AI-generated illustration of a silver SUV beside a mountain lake at sunset; not an inventory listing"
            fetchPriority="high"
            width={1916}
            height={821}
          />
        </figure>
        <div className="cinema-assistant-entry" id="assistant" tabIndex={-1}>
          <button
            type="button"
            className="cinema-assistant-toggle"
            aria-expanded={assistantOpen}
            aria-controls="assistant-panel"
            onClick={() => setAssistantOpen(!assistantOpen)}
          >
            <Icon kind="search" />
            <span>
              Search by make or model
              <small>{mobileDisclosure}</small>
            </span>
            <span aria-hidden="true">{assistantOpen ? "−" : "+"}</span>
          </button>
          <section
            className="cinema-assistant"
            id="assistant-panel"
            data-open={assistantOpen}
            aria-labelledby="assistant-heading"
          >
            <div className="cinema-assistant-heading">
              <span className="cinema-assistant-symbol">
                <Icon kind="search" />
              </span>
              <div>
                <h2 id="assistant-heading" tabIndex={-1}>
                  A clearer starting point.
                </h2>
                <p>Search the cars. Find your direction.</p>
              </div>
            </div>
            <p className="cinema-assistant-prompt">
              Have a car in mind?
              <br /> Start with a make or model.
            </p>
            <div className="cinema-quick-choices" aria-label="Search a make">
              {["Mercedes", "Mazda", "Bentley"].map((make) => (
                <button
                  key={make}
                  type="button"
                  onClick={() => applySearch(make)}
                >
                  {make} <span aria-hidden="true">↗</span>
                </button>
              ))}
            </div>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                applySearch(assistantEntry);
              }}
            >
              <TextField
                label={searchLabel}
                value={assistantEntry}
                onChange={(e) => setAssistantEntry(e.target.value)}
                placeholder="Try “Mercedes”"
              />
              <button
                className="cinema-assistant-submit"
                type="submit"
                aria-label="Search listings"
              >
                <Icon kind="arrow" />
              </button>
            </form>
            <p className="cinema-assistant-disclosure">{disclosure}</p>
          </section>
        </div>
      </div>
    </section>
  );
}
