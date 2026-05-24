# Codex Release Change Analysis

This report is generated from the local `openai/codex` checkout at `/Users/fridiculous/projects/codex`.

Run:

```sh
scripts/analyze-codex-releases.py \
  --codex-repo /Users/fridiculous/projects/codex \
  --output-dir reports/codex-release-history
```

Outputs:

- `release_changes.csv`: release/category/type rows with weighted and raw churn.
- `release_summary.csv`: one row per release interval.
- `stable_release_changes.csv`: stable-to-stable release rollups for the default chart.
- `stable_release_summary.csv`: one row per stable-to-stable release interval.
- `other_review.csv`: releases where `Other` exceeds 5% of weighted churn.
- `stable_other_review.csv`: stable rollups where `Other` exceeds 5% of weighted churn.
- `release_change_chart.html`: self-contained interactive stacked bar chart.

## Scoring

Primary metric:

```text
weighted_churn_points = min(additions + deletions, 1200) * category_weight * generated_weight
```

Defaults:

- Product, docs, build, and release files use `category_weight = 1.0`.
- Test and fixture files use `category_weight = 0.7`.
- Generated schemas, snapshots, lockfiles, vendored files, and machine output use `generated_weight = 0.2`.
- Per-file churn is capped at `1200`.

The raw CSVs use adjacent valid tag intervals. The stable rollup CSVs use adjacent stable release intervals, so the default chart shows the full stable-to-stable change, including any intervening alpha or beta tags. Area totals use final release diff numstat so raw totals reconcile to `git diff --numstat previous..release`. Change-type shares are estimated from commit-level numstat and used to split each area total across change types.

## Chart Normalization

The chart supports two independent normalizations:

- `Scale = Normalized 100%` keeps the selected x-axis but divides each stack segment by that bar's total, so every bar has the same height and shows category/type mix.
- `X-axis = Date`, `Week`, or `Month` converts release intervals into calendar buckets. Each release diff is treated as work accumulated between `previous_release_date` and `release_date`, then allocated to every overlapping bucket by elapsed-time overlap.

For example, if a stable release interval spans 10 days and 4 of those days fall in a given week, 40% of that release interval's weighted churn contributes to that week. This avoids over-counting releases that happen near bucket boundaries and avoids treating a long release interval the same as a one-day interval.

Recommended reading modes:

- Use `Release + Absolute` to see release size.
- Use `Release + Normalized 100%` to compare mix across releases.
- Use `Week/Month + Absolute` to see calendar-period intensity.
- Use `Week/Month + Normalized 100%` to compare how the work mix shifts over time independent of total volume.

## Categories

Area categories are path-first:

- `Core Runtime`
- `TUI / CLI UX`
- `App Server / Desktop Integration`
- `Tools / MCP / Plugins / Skills`
- `Sandbox / Permissions / Security`
- `Patch / Editing`
- `State / Storage`
- `Identity / Auth`
- `Artifacts`
- `Cloud / Remote Agents`
- `Analytics / Telemetry`
- `SDKs / API Clients`
- `Packaging / Release / Install`
- `CI / Build / Dependencies`
- `Docs / Examples`
- `Tests / Fixtures`
- `Vendored / Third Party`
- `Other`

Change types are inferred from commit subject/body keywords:

- `Feature`
- `Bug Fix`
- `Refactor / Cleanup`
- `Reliability / Performance`
- `Security / Policy`
- `Build / Release`
- `Docs / Tests`

## Release Selection

The analyzer includes valid `rust-v*` tags:

- `rust-v0.0.YYMMDDHHMM`
- `rust-vX.Y.Z`
- `rust-vX.Y.Z-alpha.N`
- `rust-vX.Y.Z-beta.N`

It excludes malformed duplicate tags, non-Codex runtime tags, and one-off release-test tags.
