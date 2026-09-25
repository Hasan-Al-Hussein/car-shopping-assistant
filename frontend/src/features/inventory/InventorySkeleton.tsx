/** Decorative shapes reserve the same space as the cards; announce once. */
export function InventorySkeleton({ home = false }: { home?: boolean }) {
  return (
    <div className="inventory-loading" aria-busy="true">
      <p className="cinema-result-count" role="status">
        Finding cars…
      </p>
      <div
        className={home ? "cinema-cards" : "inner-inventory-grid"}
        aria-hidden="true"
      >
        {[0, 1, 2].map((item) => (
          <div className="inventory-skeleton" key={item}>
            <div className="inventory-skeleton-photo" />
            <div className="inventory-skeleton-body">
              <span className="inventory-skeleton-name" />
              <span className="inventory-skeleton-price" />
              <span className="inventory-skeleton-facts" />
              <span className="inventory-skeleton-actions" />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
