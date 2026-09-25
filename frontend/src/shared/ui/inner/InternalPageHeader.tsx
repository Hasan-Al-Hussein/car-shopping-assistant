import type { ReactNode } from "react";
import { ListingPhoto } from "../ListingPhoto";

export function InternalPageHeader({
  eyebrow,
  title,
  children,
  architecturalAccent = false,
  compact = false,
  detail = false,
  art,
  listingPhoto,
}: {
  eyebrow: string;
  title: ReactNode;
  children: ReactNode;
  architecturalAccent?: boolean;
  compact?: boolean;
  detail?: boolean;
  listingPhoto?: { identity: string; src: string | null };
  art?: {
    src: string;
    width: number;
    height: number;
    position?: string;
    fade?: "short";
  };
}) {
  const HeadingContainer = detail ? "header" : "div";
  return (
    <HeadingContainer
      className={`inner-masthead${architecturalAccent ? " inner-masthead--architecture" : ""}${compact ? " inner-masthead--compact" : ""}${detail ? " inner-detail-heading" : ""}${art || listingPhoto ? " inner-masthead--editorial" : ""}${art && !listingPhoto?.src ? " inner-masthead--automotive" : ""}`}
      data-reveal={`masthead-${eyebrow}`}
    >
      {listingPhoto?.src ? (
        <figure
          className="inner-header-art inner-header-art--short-fade inner-header-art--listing"
          aria-hidden="true"
        >
          <ListingPhoto
            identity={listingPhoto.identity}
            src={listingPhoto.src}
            alt=""
            loading="eager"
          />
        </figure>
      ) : (
        art && (
          <img
            className={`inner-header-art${art.fade === "short" ? " inner-header-art--short-fade" : ""}`}
            src={art.src}
            width={art.width}
            height={art.height}
            style={{ objectPosition: art.position ?? "center" }}
            alt=""
            aria-hidden="true"
            decoding="async"
          />
        )
      )}
      <div>
        <p className="inner-eyebrow">{eyebrow}</p>
        <h1 id="page-heading" tabIndex={-1}>
          {title}
        </h1>
      </div>
      <div className="inner-masthead-copy">{children}</div>
    </HeadingContainer>
  );
}
