# Competitor-output regression check

I found and fixed an edge case where a competitor name inside a listing fact or saved preference could be repeated in an answer. The assistant now checks rendered facts, recalled preferences and final response text, including replayed responses, against the reviewed competitor-name list.

The focused offline run passed **386 tests**, with no failures or skips. Scoped Ruff and type checks passed. The regression tests use synthetic listings and conversations; no live model request or private buyer data was used. An independent source/evidence review matched the tested file hashes and the actual test report.

This rule covers DubiCars, YallaMotor, AutoTrader and Cars24, including tested casing, punctuation, compatibility Unicode and escaped variants. It is a finite vocabulary, not a claim that every unknown platform or possible obfuscation is recognized. Original inventory data, source attachments and historical database rows are preserved; the guard applies to assistant prose. Earlier live competitor-refusal examples remain historical evidence, not a new live run of this patch.

The other assessment features remain implemented: supplied-inventory search, contextual follow-ups, saved preferences across sessions, simulated viewing slots and qualified local CSV exports. Their existing demonstrations are separate flows, not one uninterrupted live journey. External provider availability and universal error-free operation are not guaranteed.
