import { afterEach, expect, test, vi } from "vitest";
import { act, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router";
import { BrowserServices } from "../../src/app/BrowserServices";
import { ServicesProvider } from "../../src/app/ServicesProvider";
import { OperationRoute } from "../../src/app/OwnedRoutes";
import { operationPath } from "../../src/app/routes";
import { scriptedFetch } from "../harness/fixtures";
import { identity, meta, operationFixture, schemaFixture } from "./apiFixtures";

const services: BrowserServices[] = [];
afterEach(() => services.splice(0).forEach((service) => service.dispose()));
const flush = async () => {
  await act(async () => {
    for (let i = 0; i < 16; i++) await Promise.resolve();
    await vi.advanceTimersByTimeAsync(1);
  });
};

test("real operation component and typed transport keep original generation across repeated status GETs", async () => {
  const data = schemaFixture(
    "OperationGenerationUnresolved",
    operationFixture("restore-generation-unresolved"),
  );
  if (data.state !== "unresolved_generation")
    throw Error("Wrong synthetic fixture");
  const response = {
    meta: {
      ...meta(identity().context_id),
      store_generation: data.observed_store_generation,
    },
    data,
  };
  const transport = vi.fn(
    scriptedFetch(
      [1, 2].map(() => ({
        method: "GET",
        path: `/api/v1/operations/${data.operation_key}`,
        body: response,
      })),
    ),
  );
  const service = new BrowserServices(transport);
  services.push(service);
  vi.spyOn(service.api, "revalidateIdentity").mockImplementation(async () => {
    service.owner.accept(service.owner.invalidate(), identity());
    return { meta: meta(identity().context_id), data: identity() };
  });
  service.start();
  await flush();
  const write = vi.spyOn(service.api, "mutate");
  render(
    <ServicesProvider services={service}>
      <MemoryRouter
        initialEntries={[
          operationPath(data.operation_key, data.submitted_store_generation),
        ]}
      >
        <Routes>
          <Route
            path="/operations/:operationKey"
            element={<OperationRoute />}
          />
        </Routes>
      </MemoryRouter>
    </ServicesProvider>,
  );
  await flush();
  expect(screen.getByText("Outcome unknown.")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Check viewing status" }));
  await flush();
  expect(transport).toHaveBeenCalledTimes(2);
  for (const [url, init] of transport.mock.calls) {
    expect(String(url)).toContain(
      `submitted_store_generation=${data.submitted_store_generation}`,
    );
    expect(String(url)).not.toContain(data.observed_store_generation);
    expect(init?.method).toBe("GET");
  }
  expect(write).not.toHaveBeenCalled();
  expect(localStorage.length).toBe(0);
  expect(sessionStorage.length).toBe(0);
});
