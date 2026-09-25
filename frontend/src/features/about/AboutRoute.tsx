import { Link } from "react-router";
import { InternalPageHeader } from "../../shared/ui/inner/InternalPageHeader";

export function AboutRoute() {
  return (
    <section className="inner-page cinema-width feedback-about">
      <InternalPageHeader
        eyebrow="About dubizzle"
        title={
          <>
            A new owner.
            <br />
            <em>A new chapter.</em>
          </>
        }
        art={{
          src: "/cinematic/headers/about-porsche-front.jpg",
          width: 1600,
          height: 1067,
          position: "50% 35%",
        }}
      >
        <span>Bringing people and their next car a little closer.</span>
      </InternalPageHeader>
      <div className="feedback-about-story" data-reveal="about-story">
        <p className="inner-eyebrow">A UAE community, since 2005</p>
        <h2>
          Good cars deserve
          <br />
          another story.
        </h2>
        <div>
          <p>
            Launched in 2005, dubizzle is a classifieds platform in the United
            Arab Emirates. Its car marketplace brings buyers and sellers
            together across the UAE.
          </p>
          <p>
            This car-shopping experience helps you explore listing facts,
            compare your options and keep useful questions in view before your
            next move.
          </p>
          <a
            href="https://dubai.dubizzle.com/about/"
            target="_blank"
            rel="noreferrer"
          >
            Read dubizzle’s official story ↗
          </a>
        </div>
      </div>
      <Link className="folio-button folio-button--primary" to="/#collection">
        Explore the cars <span aria-hidden="true">↗</span>
      </Link>
      <footer className="feedback-prototype-note">
        Assessment prototype. Listings come from the supplied dataset; viewing
        requests are simulated. No real dealer reservation or delivery is made.
      </footer>
    </section>
  );
}
