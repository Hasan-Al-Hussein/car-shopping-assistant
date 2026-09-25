import { lazy, Suspense } from "react";

const DevelopmentSurface =
  import.meta.env.DEV && !window.location.pathname.startsWith("/__app")
    ? lazy(() =>
        window.location.pathname.startsWith("/__specimen")
          ? import("./dev/PrimitiveSpecimen").then((module) => ({
              default: module.PrimitiveSpecimen,
            }))
          : import("./design-proof/DesignProof").then((module) => ({
              default: module.DesignProof,
            })),
      )
    : null;

const ProductionSurface = lazy(() =>
  import("./app/ProductionApp").then((module) => ({
    default: module.ProductionApp,
  })),
);

export default function App() {
  return DevelopmentSurface ? (
    <Suspense fallback={<main>Loading the development proof…</main>}>
      <DevelopmentSurface />
    </Suspense>
  ) : (
    <Suspense fallback={<main>Loading your car workspace…</main>}>
      <ProductionSurface />
    </Suspense>
  );
}
