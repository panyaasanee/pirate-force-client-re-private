# Pirate Force RE cloud runner

The cloud runner lives in `.github/workflows/pirate-force-re-runner.yml`. It runs from this repository because the immutable client image is already here. It checks out the bridge and server repositories read-only, runs one static RE ticket, then publishes only a validated result letter to `panyaasanee/pf_bridge` through the GitHub contents API.

## Required repository secrets

Create these Actions secrets in this repository:

- `OPENAI_API_KEY`: an OpenAI API key used only by `openai/codex-action`.
- `PF_BRIDGE_TOKEN`: a fine-grained GitHub token limited to `panyaasanee/pf_bridge`, with repository `Contents: Read and write`. It is used only by the separate publish job; Codex never receives it.

Never commit either value to a file.

## Optional raw-scene bundle

`RE-073` and `RE-093` need source scene files that are not in the bridge tables. Upload the prepared `PF_RE_CLOUD_SCENES_20260826.zip` as `inputs/PF_RE_CLOUD_SCENES_20260826.zip` in this repository. The archive contains 60 files from `FilmScene`, `Bg1181`, `Bg2033`, and `bg0001`, is 13,765,502 bytes, and has SHA-256 `7e9ef01e12e12b1121774f8d5bc02a9a1fd20aef42267ac9d33fa50eb47126ec`.

The workflow verifies that exact hash, extracts it under `work/scene_inputs`, verifies the required paths, and makes the extracted tree read-only. Without the archive, the runner skips those two tickets when another eligible ticket is runnable; the rest of the current static queue still has the client image, bridge tables, gamedata, and server source it needs.

## Safe activation

1. Keep `cloud/runner_enabled` equal to `false`.
2. Add both secrets.
3. Run `pirate-force-re-runner-cloud` manually with **Run workflow**. A successful manual run either reports `NO_WORK` or publishes exactly one validated result letter.
4. Pause the local `pirate-force-re-runner` automation.
5. Change `cloud/runner_enabled` to `true` on `main`. Scheduled hourly runs now execute. Set it back to `false` to stop cloud runs.

The scheduled workflow is a no-op while the file is `false` or either secret is absent. GitHub concurrency prevents overlapping runs, and the 50-minute job timeout is stricter than the former 110-minute stale-lock takeover.

The committed legacy registry preserves all 327 data rows from the local source. Its Git blob uses LF line endings (`60d5beb9...e869`); the original Windows CRLF file was `b5880451...ce1f`. The row content and computed wire IDs are identical.
