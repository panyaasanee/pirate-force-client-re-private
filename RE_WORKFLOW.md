# Remote static-RE pilot

This private repository is a binary-analysis lane deliberately separated from the sanitized server source repository.

## Invariants

- Treat client input as read-only.
- Verify pinned size and SHA-256 before every analysis.
- Never rewrite the client binary.
- Static results may include reports, schemas, bounded pseudocode summaries, and test vectors.
- Do not promote runtime, Frida, UI, or network claims from this lane.
- Move results to the server repository only after sanitization and evidence classification.

## Pilot gate

Run:

    python tools/analyze_pilot.py client/GameClient.bin

Success proves only that the cloud workspace received the pinned binary and can parse bounded PE metadata. It does not prove that the client executes in the cloud environment.
