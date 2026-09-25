/** Presentation casing only; exact source titles, claims and identity remain untouched. */
export function displayCarName(value: string) {
  return value.replace(/\b(?:dbx|glc)\b/gi, (abbreviation) =>
    abbreviation.toUpperCase(),
  );
}
