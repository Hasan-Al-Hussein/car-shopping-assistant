import { afterEach, describe, expect, test, vi } from "vitest";
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
} from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router";
import { BrowserServices } from "../../src/app/BrowserServices";
import { OwnedOperationRoute } from "../../src/app/OwnedRoutes";
import { ServicesProvider } from "../../src/app/ServicesProvider";
import { operationPath } from "../../src/app/routes";
import { deferred } from "../harness/fixtures";
import { identity, listingDetail, meta } from "./apiFixtures";
import {
  viewingDraft,
  viewingEnvelope,
  viewingGeneration,
  viewingSuccess,
} from "./viewingFixtures";

const services: BrowserServices[] = [];
afterEach(() => {
  cleanup();
  services.splice(0).forEach((service) => service.dispose());
});
const flush = async () => {
  await act(async () => {
    for (let i = 0; i < 20; i++) await Promise.resolve();
    await vi.advanceTimersByTimeAsync(1);
  });
};

async function setup() {
  const service = new BrowserServices();
  services.push(service);
  let currentIdentity = identity();
  let gate: Promise<void> | undefined;
  vi.spyOn(service.api, "revalidateIdentity").mockImplementation(async () => {
    await gate;
    service.owner.accept(service.owner.invalidate(), currentIdentity);
    return { meta: meta(currentIdentity.context_id), data: currentIdentity };
  });
  const read = vi
    .spyOn(service.api, "read")
    .mockImplementation(async (operation) => {
      if (operation === "get_operation") {
        const result = viewingEnvelope(viewingSuccess());
        result.meta.identity_context_id = currentIdentity.context_id;
        return result;
      }
      if (operation === "get_listing") {
        const detail = listingDetail();
        detail.listing.ref = structuredClone(viewingDraft().ref);
        return {
          meta: {
            ...meta(),
            inventory_snapshot_id: detail.listing.ref.snapshot_id,
          },
          data: detail,
        };
      }
      throw Error(`UNSCRIPTED_READ:${operation}`);
    });
  const write = vi
    .spyOn(service.api, "mutate")
    .mockRejectedValue(Error("UNSCRIPTED_MUTATION"));
  service.start();
  await flush();
  render(
    <ServicesProvider services={service}>
      <MemoryRouter
        initialEntries={[
          operationPath(viewingSuccess().operation_key, viewingGeneration),
        ]}
      >
        <Routes>
          <Route
            path="/operations/:operationKey"
            element={<OwnedOperationRoute openIdentity={() => {}} />}
          />
        </Routes>
      </MemoryRouter>
    </ServicesProvider>,
  );
  await flush();
  return {
    service,
    read,
    write,
    recheck: (ownerIndex: number, pending: Promise<void>) => {
      currentIdentity = identity(ownerIndex);
      gate = pending;
      return service.revalidate();
    },
  };
}

describe("operation disclosure across the real owner gate with synthetic service results", () => {
  test.each([0, 1])(
    "private content unmounts during recheck; expansion is scoped to resolved owner %s",
    async (ownerIndex) => {
      const { service, read, write, recheck } = await setup();
      const original = screen
        .getByText("Request reference and record details")
        .closest("details")!;
      fireEvent.click(screen.getByText("Request reference and record details"));
      await flush();
      expect(original.open).toBe(true);
      const pending = deferred<void>();
      let finished: Promise<void>;
      act(() => {
        finished = recheck(ownerIndex, pending.promise);
      });
      await flush();
      expect(original.isConnected).toBe(false);
      expect(
        screen.queryByText("Request reference and record details"),
      ).not.toBeInTheDocument();
      expect(
        screen.getByText("Checking your local access…"),
      ).toBeInTheDocument();
      await act(async () => {
        pending.resolve();
        await finished!;
      });
      await flush();
      const replacement = screen
        .getByText("Request reference and record details")
        .closest("details")!;
      expect(replacement).not.toBe(original);
      expect(replacement.open).toBe(ownerIndex === 0);
      expect(service.getSnapshot().identity?.context_id).toBe(
        identity(ownerIndex).context_id,
      );
      expect(
        read.mock.calls.filter(([operation]) => operation === "get_operation"),
      ).toHaveLength(2);
      if (ownerIndex === 1) {
        await act(async () => {
          await recheck(0, Promise.resolve());
        });
        await flush();
        // A -> B -> A must not resurrect A's discarded presentation preference.
        expect(
          screen
            .getByText("Request reference and record details")
            .closest("details")!.open,
        ).toBe(false);
      }
      expect(write).not.toHaveBeenCalled();
    },
  );
});
