/** Original UAE app tile and existing wordmark; the parent link names the brand. */
export function BrandSignature() {
  return (
    <>
      <span className="cinema-brand-symbol" aria-hidden="true">
        <img
          src="/cinematic/brand/dubizzle-uae-app-icon.webp"
          width={48}
          height={48}
          alt=""
        />
      </span>
      <span className="cinema-brand-copy" aria-hidden="true">
        <span className="cinema-brand-name">dubizzle</span>
        <span className="cinema-brand-tagline">FIND YOUR NEXT CAR.</span>
      </span>
    </>
  );
}
