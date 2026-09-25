import { QueryClient, queryOptions } from "@tanstack/react-query";
import { operationContracts } from "../../../contracts/generated/runtime";
import { ApiClient } from "../shared/api/ApiClient";
import { ClientFailure } from "../shared/api/ClientFailure";
import { OwnerSession } from "../shared/api/OwnerSession";
import type { Operation, RequestOf } from "../shared/api/contracts";

function normalized(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(normalized);
  if (value !== null && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value)
        .filter(([, item]) => item !== undefined)
        .sort(([a], [b]) => a.localeCompare(b, "en"))
        .map(([key, item]) => [key, normalized(item)]),
    );
  }
  return value;
}

function requestKey<Name extends Operation>(request: RequestOf<Name>): unknown {
  const { signal: _signal, ...values } = request;
  void _signal;
  return normalized(values);
}

function snapshotRequest<Name extends Operation>(
  request: RequestOf<Name>,
): RequestOf<Name> {
  const { signal, ...values } = request;
  try {
    return { ...structuredClone(values), signal } as RequestOf<Name>;
  } catch {
    throw new ClientFailure("invalid-request", "correct-request");
  }
}

export function createQueryPolicy(owner: OwnerSession, api: ApiClient) {
  const client = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        refetchOnWindowFocus: false,
        refetchOnReconnect: false,
        refetchOnMount: false,
        staleTime: 0,
        gcTime: 5 * 60_000,
        networkMode: "always",
      },
      mutations: {
        retry: false,
        networkMode: "always",
        gcTime: 0,
      },
    },
  });
  const isPrivate = (key: readonly unknown[]) => key[0] === "private";
  const unsubscribe = owner.subscribe(() => {
    void client.cancelQueries({
      predicate: (query) => isPrivate(query.queryKey),
    });
    client.removeQueries({ predicate: (query) => isPrivate(query.queryKey) });
    client.getMutationCache().clear();
  });

  return {
    client,
    publicRead<Name extends Operation>(
      operation: Name,
      request: RequestOf<Name>,
      snapshot: string | null,
    ) {
      request = snapshotRequest(request);
      const contract = operationContracts[operation];
      // Identity is a credential-context read even though it permits anonymous callers.
      if (
        contract.isPrivate ||
        contract.mutates ||
        operation === "get_identity"
      ) {
        throw new ClientFailure("invalid-request", "correct-request");
      }
      return queryOptions({
        queryKey: ["public", snapshot, operation, requestKey(request)] as const,
        queryFn: ({ signal }) =>
          api.read(operation, {
            ...request,
            signal: request.signal
              ? AbortSignal.any([signal, request.signal])
              : signal,
          }),
      });
    },
    privateRead<Name extends Operation>(
      operation: Name,
      request: RequestOf<Name>,
      version: {
        sessionId?: string;
        entityRevision?: number;
        snapshotId?: string;
      } = {},
    ) {
      request = snapshotRequest(request);
      const contract = operationContracts[operation];
      if (!contract.isPrivate || contract.mutates)
        throw new ClientFailure("invalid-request", "correct-request");
      const snapshot = owner.capture();
      if (!snapshot.contextId)
        throw new ClientFailure("stale-owner", "reidentify");
      return queryOptions({
        queryKey: [
          "private",
          snapshot.epoch,
          snapshot.contextId,
          operation,
          normalized(version),
          requestKey(request),
        ] as const,
        gcTime: 0,
        queryFn: async ({ signal }) => {
          owner.assertCurrent(snapshot);
          const result = await api.read(operation, {
            ...request,
            signal: request.signal
              ? AbortSignal.any([signal, request.signal])
              : signal,
          });
          owner.assertCurrent(snapshot);
          return result;
        },
      });
    },
    dispose() {
      unsubscribe();
      void client.cancelQueries();
      client.clear();
    },
  };
}
