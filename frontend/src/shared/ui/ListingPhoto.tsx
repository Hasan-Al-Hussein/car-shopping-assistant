import { useState } from "react";

type ListingPhotoProps = {
  /** Exact immutable listing reference, including its snapshot namespace. */
  identity: string;
  /** Unmodified source URL approved by the inventory API; null if unavailable. */
  src: string | null;
  /** Describe provenance, not inferred condition; use empty text in a titled link. */
  alt: string;
  loading?: "eager" | "lazy";
  className?: string;
};

export function ListingPhoto(props: ListingPhotoProps) {
  // Replacing the resource also isolates callbacks from the previous photograph.
  return (
    <PhotoResource
      key={JSON.stringify([props.identity, props.src])}
      {...props}
    />
  );
}

function PhotoResource({
  src,
  alt,
  loading = "lazy",
  className = "",
}: ListingPhotoProps) {
  const [state, setState] = useState<"loading" | "loaded" | "unavailable">(
    src ? "loading" : "unavailable",
  );

  return (
    <div className={`folio-photo ${className}`.trim()} data-state={state}>
      {src && state !== "unavailable" ? (
        <img
          className="folio-photo__image"
          src={src}
          alt={alt}
          aria-hidden={state === "loading" ? true : undefined}
          loading={loading}
          decoding="async"
          referrerPolicy="no-referrer"
          onLoad={() => setState("loaded")}
          onError={() => setState("unavailable")}
        />
      ) : null}
      {state !== "loaded" ? (
        <span className="folio-photo__placeholder">
          {state === "loading" ? "Loading listing photo…" : "Photo unavailable"}
        </span>
      ) : null}
    </div>
  );
}
