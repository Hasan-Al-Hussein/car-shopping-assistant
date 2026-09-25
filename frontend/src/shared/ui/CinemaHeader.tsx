import { useLayoutEffect, useRef, useState } from "react";
import { Link } from "react-router";
import { BrandSignature } from "./BrandSignature";
import { CinemaIcon } from "./CinemaIcon";

/** One navigation contract across the homepage, results and private routes. */
export function CinemaHeader({
  count,
  path,
  compareHref = "/compare",
  browseKey,
  onAssistant,
  onHelp,
}: {
  count: number;
  path: string;
  compareHref?: string;
  browseKey?: string;
  viewingPath?: string;
  onAssistant?: () => void;
  onHelp?: () => void;
}) {
  const [menuOpen, setMenuOpen] = useState(false);
  const menuButton = useRef<HTMLButtonElement>(null);
  const header = useRef<HTMLElement>(null);
  useLayoutEffect(() => {
    if (!header.current) return;
    const update = () =>
      document.documentElement.style.setProperty(
        "--app-header-height",
        `${header.current!.getBoundingClientRect().height + 24}px`,
      );
    const observer = new ResizeObserver(update);
    observer.observe(header.current);
    update();
    return () => observer.disconnect();
  }, []);
  return (
    <header
      ref={header}
      className="cinema-header cinema-width feedback-header"
      onKeyDown={(event) => {
        if (event.key === "Escape" && menuOpen) {
          setMenuOpen(false);
          menuButton.current?.focus();
        }
      }}
    >
      <Link className="cinema-brand" to="/" aria-label="dubizzle home">
        <BrandSignature />
      </Link>
      <button
        className="feedback-menu-toggle"
        ref={menuButton}
        type="button"
        aria-expanded={menuOpen}
        aria-controls="main-navigation"
        onClick={() => setMenuOpen(!menuOpen)}
      >
        {menuOpen ? "Close menu" : "Menu"}
      </button>
      <nav
        id="main-navigation"
        aria-label="Main"
        data-open={menuOpen}
        onClick={(event) => {
          if ((event.target as HTMLElement).closest("a")) setMenuOpen(false);
        }}
      >
        <Link to="/" aria-current={path === "/" ? "page" : undefined}>
          Home
        </Link>
        <Link
          to={compareHref}
          state={{ browseKey }}
          aria-current={path === "/compare" ? "page" : undefined}
        >
          Compare <span className="cinema-count">{count}</span>
        </Link>
        <Link
          to="/shortlist"
          aria-current={path === "/shortlist" ? "page" : undefined}
        >
          Shortlist
        </Link>
        {onHelp ? (
          <button
            type="button"
            onClick={() => {
              if (menuOpen) {
                setMenuOpen(false);
                menuButton.current?.focus();
              }
              onHelp();
            }}
          >
            Help
          </button>
        ) : (
          <Link to="/about">Help</Link>
        )}
        <Link to="/about" aria-current={path === "/about" ? "page" : undefined}>
          About
        </Link>
      </nav>
      {onAssistant ? (
        <button
          className="feedback-ask-ai"
          type="button"
          onClick={() => {
            setMenuOpen(false);
            onAssistant();
          }}
        >
          <CinemaIcon kind="robot" />
          <span>Ask AI</span>
        </button>
      ) : (
        <Link className="feedback-ask-ai" to="/#assistant">
          <CinemaIcon kind="robot" />
          <span>Ask AI</span>
        </Link>
      )}
    </header>
  );
}
