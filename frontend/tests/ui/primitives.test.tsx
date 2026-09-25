import { createRef } from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, test, vi } from "vitest";
import sourceFacts from "../../../fixtures/shared/source-facts.json";
import { Button } from "../../src/shared/ui/Button";
import { TextField } from "../../src/shared/ui/TextField";
import { FactStatus } from "../../src/shared/ui/FactStatus";
import { StatusNotice } from "../../src/shared/ui/StatusNotice";
import { ListingPhoto } from "../../src/shared/ui/ListingPhoto";

describe("FE-01 native controls and fact wording", () => {
  test("button is a named, focusable non-submit control unless submission is explicit", () => {
    const submit = vi.fn((event: React.FormEvent) => event.preventDefault());
    const clicked = vi.fn();
    const ref = createRef<HTMLButtonElement>();
    render(
      <form onSubmit={submit}>
        <Button onClick={clicked} ref={ref}>
          Compare
        </Button>
        <Button type="submit">Submit example</Button>
      </form>,
    );
    const button = screen.getByRole("button", { name: "Compare" });
    button.focus();
    expect(button).toHaveFocus();
    expect(ref.current).toBe(button);
    fireEvent.click(button);
    expect(clicked).toHaveBeenCalledOnce();
    expect(submit).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Submit example" }));
    expect(submit).toHaveBeenCalledOnce();
  });

  test("disabled native action does not run its callback", () => {
    const clicked = vi.fn();
    render(
      <Button disabled onClick={clicked}>
        Saving unavailable
      </Button>,
    );
    fireEvent.click(screen.getByRole("button", { name: "Saving unavailable" }));
    expect(clicked).not.toHaveBeenCalled();
  });

  test("label, hint, required state and error describe the correct input and retain caller descriptions", () => {
    const ref = createRef<HTMLInputElement>();
    const { rerender } = render(
      <>
        <p id="policy">Local example only</p>
        <TextField
          label="Budget in AED"
          required
          hint="Whole amounts"
          error="Enter digits"
          aria-describedby="policy"
          ref={ref}
        />
      </>,
    );
    const input = screen.getByRole("textbox", {
      name: "Budget in AED (required)",
    });
    expect(input).toBeRequired();
    expect(input).toHaveAttribute("aria-invalid", "true");
    expect(input).toHaveAccessibleDescription(
      "Local example only Whole amounts Error: Enter digits",
    );
    expect(ref.current).toBe(input);
    ref.current?.focus();
    expect(input).toHaveFocus();
    rerender(
      <>
        <p id="policy">Local example only</p>
        <TextField
          label="Budget in AED"
          required
          hint="Whole amounts"
          aria-describedby="policy"
          ref={ref}
        />
      </>,
    );
    expect(input).not.toHaveAttribute("aria-invalid");
    expect(input).toHaveAccessibleDescription(
      "Local example only Whole amounts",
    );
    expect(screen.queryByText("Enter digits")).not.toBeInTheDocument();
  });

  test("two fields with generated IDs keep separate label/error associations", () => {
    render(
      <>
        <TextField label="First" error="First error" />
        <TextField label="Second" error="Second error" />
      </>,
    );
    const first = screen.getByRole("textbox", { name: "First" });
    const second = screen.getByRole("textbox", { name: "Second" });
    expect(first.id).not.toBe(second.id);
    expect(first).toHaveAccessibleDescription("Error: First error");
    expect(second).toHaveAccessibleDescription("Error: Second error");
  });

  test("source Unicode/numeric tokens are escaped text, with isolated labels and intact negation", () => {
    const arabic = String(
      sourceFacts.cases.find((item) => item.id === "arabic-title-exact-unicode")
        ?.raw_value,
    );
    const source = `${arabic} / Mazda 3 / DBX 707 / لا يوجد ضمان <script>book()</script>`;
    render(<TextField label={source} defaultValue={source} />);
    expect(screen.getByRole("textbox", { name: source })).toHaveValue(source);
    expect(document.querySelector("script")).toBeNull();
    expect(document.querySelector("label bdi")).toHaveAttribute("dir", "auto");
  });

  test("evidence states use distinct words and preserve a true zero notice body", () => {
    render(
      <>
        <FactStatus kind="not-stated" />
        <FactStatus kind="unknown" />
        <FactStatus kind="conflict" />
        <FactStatus kind="not-applicable" />
        <StatusNotice title="Known numeric example">{0}</StatusNotice>
      </>,
    );
    for (const label of [
      "Not stated",
      "Unknown",
      "Conflicting details",
      "Not applicable",
      "0",
    ]) {
      expect(screen.getByText(label)).toBeInTheDocument();
    }
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  test("announcements are a deliberate caller choice rather than every notice", () => {
    const { rerender } = render(
      <StatusNotice title="Checking original request" announcement="polite" />,
    );
    expect(screen.getByRole("status")).toHaveTextContent(
      "Checking original request",
    );
    rerender(
      <StatusNotice
        title="Read failed"
        announcement="assertive"
        tone="error"
      />,
    );
    expect(screen.getByRole("alert")).toHaveTextContent("Read failed");
  });
});

describe("FE-01 isolated photo behavior (events, not real decode)", () => {
  test("missing and failed photos leave identity and the next action usable", () => {
    const selected = vi.fn();
    const { rerender } = render(
      <>
        <h2>Mazda 3</h2>
        <ListingPhoto
          identity="fixture:snapshot-a:12"
          src={null}
          alt="Supplied listing photo"
        />
        <Button onClick={selected}>Inspect Mazda 3</Button>
      </>,
    );
    expect(screen.getByText("Photo unavailable")).toBeInTheDocument();
    rerender(
      <>
        <h2>Mazda 3</h2>
        <ListingPhoto
          identity="fixture:snapshot-a:12"
          src="/synthetic-photo"
          alt="Supplied listing photo"
        />
        <Button onClick={selected}>Inspect Mazda 3</Button>
      </>,
    );
    const image = document.querySelector("img")!;
    expect(image).toHaveAttribute("referrerpolicy", "no-referrer");
    expect(image).toHaveAttribute("loading", "lazy");
    expect(screen.getByText("Loading listing photo…")).toBeInTheDocument();
    fireEvent.error(image);
    expect(screen.getByText("Photo unavailable")).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Mazda 3" }),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Inspect Mazda 3" }));
    expect(selected).toHaveBeenCalledOnce();
  });

  test("a changed snapshot/reference resets a pending photo even when the URL is unchanged", () => {
    const { rerender } = render(
      <ListingPhoto
        identity="fixture:snapshot-a:12"
        src="/synthetic-photo"
        alt="Supplied photo"
      />,
    );
    const oldImage = document.querySelector("img")!;
    rerender(
      <ListingPhoto
        identity="fixture:snapshot-b:12"
        src="/synthetic-photo"
        alt="Supplied photo"
      />,
    );
    const currentImage = document.querySelector("img")!;
    expect(currentImage).not.toBe(oldImage);
    fireEvent.error(oldImage);
    expect(screen.queryByText("Photo unavailable")).not.toBeInTheDocument();
    fireEvent.load(currentImage);
    expect(
      screen.queryByText("Loading listing photo…"),
    ).not.toBeInTheDocument();
    expect(screen.getByRole("img", { name: "Supplied photo" })).toBe(
      currentImage,
    );
  });

  test("changed source URL recovers from a prior failure without modifying its query", () => {
    const { rerender } = render(
      <ListingPhoto
        identity="fixture:snapshot-a:4"
        src="/first.heic?impolicy=dpv"
        alt="Supplied photo"
      />,
    );
    fireEvent.error(document.querySelector("img")!);
    rerender(
      <ListingPhoto
        identity="fixture:snapshot-a:4"
        src="/next.heic?impolicy=dpv"
        alt="Supplied photo"
        loading="eager"
      />,
    );
    expect(screen.getByText("Loading listing photo…")).toBeInTheDocument();
    expect(document.querySelector("img")).toHaveAttribute(
      "src",
      "/next.heic?impolicy=dpv",
    );
    expect(document.querySelector("img")).toHaveAttribute("loading", "eager");
  });
});
