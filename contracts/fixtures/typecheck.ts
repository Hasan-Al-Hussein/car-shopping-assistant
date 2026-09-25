// Compile against generated types. These are synthetic contract examples, not runtime evidence.
import type { components, paths } from '../generated/api';

type Schemas = components['schemas'];

export const uncertain: Schemas['OperationNotObserved'] = {
  state: 'not_observed',
  operation_key: 'a'.repeat(43),
  observed_store_generation: '00000000-0000-4000-8000-000000000001',
  definitive_noncommit: false,
  recovery: 'read_original_operation',
};

export const supportedBudget: Schemas['BudgetRange'] = {
  minimum: 1_000_000,
  maximum: 2_000_000,
  currency: 'AED',
  basis: 'cash',
};

export const typedPreference: Schemas['PreferencesUpdate'] = {
  expected_revision: 0,
  session_id: '00000000-0000-4000-8000-000000000001',
  client_action_id: '00000000-0000-4000-8000-000000000002',
  intent: 'remember',
  scope: 'durable',
  changes: [{ key: 'budget', value: supportedBudget, strength: 'hard' }],
};

export type TranscriptRead = paths['/api/v1/sessions/{session_id}/messages']['get'];
export type ShortlistRead = paths['/api/v1/shortlist']['get'];
export type Confirmation = paths['/api/v1/booking-drafts/{draft_id}/confirm']['post'];

export function preserveUncertainty(result: Schemas['OperationNotObserved']): false | undefined {
  return result.definitive_noncommit;
}

// @ts-expect-error Transient store failures cannot be durable business rejection codes.
export const invalidTerminalCode: Schemas['OperationRejected']['rejection_code'] = 'STORE_BUSY';
// @ts-expect-error A one-time preference cannot silently become a durable save.
export const invalidPreferenceScope: Schemas['PreferencesUpdate']['scope'] = 'session';
// @ts-expect-error Unknown operation observation is not proof of noncommit.
export const invalidCertainty: Schemas['OperationNotObserved']['definitive_noncommit'] = true;
