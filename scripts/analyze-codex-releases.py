#!/usr/bin/env python3
"""Analyze Codex release churn by category and change type.

The analyzer reads release tags from a local openai/codex checkout and writes:
- release_changes.csv
- release_summary.csv
- release_change_chart.html

It uses only the Python standard library and git CLI so the output is easy to
reproduce from a pinned source checkout.
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import math
import re
import subprocess
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


VALID_TAG_RE = re.compile(
    r"^rust-v(?:0\.0\.\d{10}|\d+\.\d+\.\d+(?:-(?:alpha(?:\.\d+)?|beta(?:\.\d+)?))?)$"
)

FILE_CAP = 1200
TEST_WEIGHT = 0.7
GENERATED_WEIGHT = 0.2

AREAS = [
    "Core Runtime",
    "TUI / CLI UX",
    "App Server / Desktop Integration",
    "Tools / MCP / Plugins / Skills",
    "Sandbox / Permissions / Security",
    "Patch / Editing",
    "State / Storage",
    "Identity / Auth",
    "Artifacts",
    "Cloud / Remote Agents",
    "Analytics / Telemetry",
    "SDKs / API Clients",
    "Packaging / Release / Install",
    "CI / Build / Dependencies",
    "Docs / Examples",
    "Tests / Fixtures",
    "Vendored / Third Party",
    "Other",
]

CHANGE_TYPES = [
    "Feature",
    "Bug Fix",
    "Refactor / Cleanup",
    "Reliability / Performance",
    "Security / Policy",
    "Build / Release",
    "Docs / Tests",
]


@dataclass(frozen=True)
class ReleaseTag:
    name: str
    commit: str
    date_iso: str
    timestamp: int
    kind: str


def run_git(codex_repo: Path, args: list[str]) -> str:
    proc = subprocess.run(
        ["git", "-C", str(codex_repo), *args],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"git {' '.join(args)} failed with {proc.returncode}:\n{proc.stderr.strip()}"
        )
    return proc.stdout


def release_kind(tag: str) -> str:
    if "-alpha" in tag or "-beta" in tag:
        return "prerelease"
    return "stable"


def list_release_tags(codex_repo: Path) -> list[ReleaseTag]:
    fmt = "%(refname:short)%09%(objectname)%09%(creatordate:iso-strict)%09%(creatordate:unix)"
    raw = run_git(codex_repo, ["for-each-ref", "refs/tags", f"--format={fmt}"])
    tags: list[ReleaseTag] = []
    seen_commits: set[str] = set()
    for line in raw.splitlines():
        parts = line.split("\t")
        if len(parts) != 4:
            continue
        name, commit, date_iso, timestamp_text = parts
        if not VALID_TAG_RE.match(name):
            continue
        # If duplicated aliases point to the same commit, keep the first valid
        # tag by creation time to avoid zero-width release intervals.
        if commit in seen_commits:
            continue
        seen_commits.add(commit)
        tags.append(
            ReleaseTag(
                name=name,
                commit=commit,
                date_iso=date_iso,
                timestamp=int(timestamp_text or "0"),
                kind=release_kind(name),
            )
        )
    tags.sort(key=lambda t: (t.timestamp, t.name))
    return tags


def is_test_path(path: str) -> bool:
    lowered = path.lower()
    parts = lowered.split("/")
    basename = parts[-1]
    return (
        "tests" in parts
        or "test" in parts
        or "fixtures" in parts
        or "snapshots" in parts
        or "__snapshots__" in parts
        or basename.endswith("_test.rs")
        or basename.endswith("_tests.rs")
        or basename.endswith(".snap")
        or basename.startswith("test_")
        or ".test." in basename
    )


def is_generated_path(path: str) -> bool:
    lowered = path.lower()
    basename = lowered.rsplit("/", 1)[-1]
    generated_markers = (
        "/generated/",
        "/schema/json/",
        "/schema/typescript/",
        "/snapshots/",
        "__snapshots__",
        "/frames/",
        "cargo.lock",
        "pnpm-lock.yaml",
        "module.bazel.lock",
        "uv.lock",
        ".sha256",
        ".snap",
    )
    return any(marker in lowered for marker in generated_markers) or basename.endswith(
        (".lock", ".min.js")
    )


def classify_area(path: str) -> str:
    lowered = path.lower()
    parts = lowered.split("/")
    basename = parts[-1]

    if is_test_path(path):
        return "Tests / Fixtures"
    if lowered.startswith(
        (
            "codex-rs/tui/",
            "codex-rs/tui2/",
            "codex-rs/tui_app_server/",
            "codex-rs/cli/",
        )
    ):
        return "TUI / CLI UX"
    if lowered.startswith(
        (
            "codex-rs/app-server",
            "codex-rs/app-server-client",
            "codex-rs/app-server-daemon",
            "codex-rs/app-server-protocol",
            "codex-rs/app-server-transport",
        )
    ):
        return "App Server / Desktop Integration"
    if lowered.startswith(("sdk/python", "sdk/typescript")):
        return "SDKs / API Clients"
    if lowered.startswith(("codex-rs/analytics/", "codex-rs/otel/")):
        return "Analytics / Telemetry"
    if lowered.startswith(("codex-rs/artifact-", "artifact-runtime")):
        return "Artifacts"
    if lowered.startswith(
        (
            "codex-rs/login/",
            "codex-rs/device-key/",
            "codex-rs/agent-identity/",
            "codex-rs/install-context/",
        )
    ):
        return "Identity / Auth"
    if lowered.startswith(
        (
            "codex-rs/thread-store/",
            "codex-rs/state/",
            "codex-rs/agent-graph-store/",
        )
    ):
        return "State / Storage"
    if lowered.startswith(("codex-rs/apply-patch/", "codex-rs/git-utils/")):
        return "Patch / Editing"
    if lowered.startswith(
        (
            "codex-rs/cloud-",
            "codex-rs/external-agent-",
            "codex-rs/code-mode/",
        )
    ):
        return "Cloud / Remote Agents"
    if lowered.startswith(("codex-rs/vendor/", "vendor/")):
        return "Vendored / Third Party"
    if lowered.startswith(("docs/", "examples/")) or basename in {
        "readme.md",
        "contributing.md",
        "security.md",
        "notice",
        "license",
    }:
        return "Docs / Examples"
    if lowered.startswith(("codex-cli/", "scripts/install/", "scripts/codex_package/")):
        return "Packaging / Release / Install"
    if lowered.startswith((".github/workflows/rust-release", ".github/scripts/")):
        return "Packaging / Release / Install"
    if lowered.startswith(("third_party/",)):
        return "Vendored / Third Party"
    if lowered.startswith((".github/", "patches/")):
        return "CI / Build / Dependencies"
    if basename in {
        "cargo.toml",
        "cargo.lock",
        "package.json",
        "pnpm-lock.yaml",
        "module.bazel",
        "module.bazel.lock",
        "build.bazel",
        "defs.bzl",
        "justfile",
        "flake.nix",
        "flake.lock",
        "pnpm-workspace.yaml",
        "cliff.toml",
    }:
        return "CI / Build / Dependencies"
    if any(
        token in lowered
        for token in (
            "sandbox",
            "permission",
            "approval",
            "policy",
            "security",
            "auth",
            "seatbelt",
            "landlock",
            "deny",
            "allow",
        )
    ):
        return "Sandbox / Permissions / Security"
    if any(
        token in lowered
        for token in (
            "mcp",
            "plugin",
            "skill",
            "tool",
            "extension",
            "connector",
            "hook",
        )
    ):
        return "Tools / MCP / Plugins / Skills"
    if lowered.startswith(
        (
            "codex-rs/core/",
            "codex-rs/config/",
            "codex-rs/protocol/",
            "codex-rs/codex-api/",
            "codex-rs/core-api/",
            "codex-rs/rollout",
            "codex-rs/exec/",
            "codex-rs/exec-server/",
        )
    ):
        return "Core Runtime"
    return "Other"


def classify_change_type(text: str) -> str:
    lowered = text.lower()
    if re.search(r"\b(ci|build|release|package|install|publish|dependency|bump|cargo|bazel|npm|wheel)\b", lowered):
        return "Build / Release"
    if re.search(r"\b(doc|docs|readme|example|guide|changelog|notebook)\b", lowered):
        return "Docs / Tests"
    if re.search(r"\b(test|tests|fixture|snapshot|flake|nextest)\b", lowered):
        return "Docs / Tests"
    if re.search(r"\b(approval|sandbox|permission|deny|allow|auth|security|policy|mitm|seatbelt|landlock)\b", lowered):
        return "Security / Policy"
    if re.search(r"\b(timeout|retry|speed|performance|perf|startup|shutdown|memory|cache|reliab|race|deadlock|hang)\b", lowered):
        return "Reliability / Performance"
    if re.search(r"\b(refactor|cleanup|remove|rename|move|split|dedupe|simplify|unused)\b", lowered):
        return "Refactor / Cleanup"
    if re.search(r"\b(fix|bug|regression|crash|restore|preserve|correct|repair)\b", lowered):
        return "Bug Fix"
    if re.search(r"\b(feat|feature|add|support|enable|expose|implement|introduce|new)\b", lowered):
        return "Feature"
    return "Feature"


def parse_numstat(raw: str) -> list[tuple[int, int, str]]:
    rows: list[tuple[int, int, str]] = []
    for line in raw.splitlines():
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        adds_text, dels_text = parts[0], parts[1]
        path = parts[-1]
        try:
            additions = 0 if adds_text == "-" else int(adds_text)
            deletions = 0 if dels_text == "-" else int(dels_text)
        except ValueError:
            continue
        rows.append((additions, deletions, normalize_path(path)))
    return rows


def normalize_path(path: str) -> str:
    # Git rename numstat may render "{old => new}/file"; use a compact, stable
    # representation but keep enough text for classification.
    return path.replace("\\", "/")


def file_score(additions: int, deletions: int, path: str, area: str) -> float:
    churn = min(additions + deletions, FILE_CAP)
    category_weight = TEST_WEIGHT if area == "Tests / Fixtures" or is_test_path(path) else 1.0
    generated_weight = GENERATED_WEIGHT if is_generated_path(path) else 1.0
    return churn * category_weight * generated_weight


def top_paths(rows: Iterable[tuple[int, int, str]], limit: int = 5) -> str:
    scored = sorted(rows, key=lambda r: (r[0] + r[1], r[2]), reverse=True)
    return "; ".join(f"{path} ({adds + dels})" for adds, dels, path in scored[:limit])


def collect_interval(
    codex_repo: Path,
    previous: ReleaseTag,
    current: ReleaseTag,
    release_kind_override: str | None = None,
) -> tuple[list[dict[str, object]], dict[str, object], list[dict[str, object]]]:
    diff_rows = parse_numstat(
        run_git(codex_repo, ["diff", "--numstat", f"{previous.name}..{current.name}"])
    )
    commit_count_text = run_git(
        codex_repo, ["rev-list", "--count", f"{previous.name}..{current.name}"]
    ).strip()
    commit_count = int(commit_count_text or "0")
    commit_messages = run_git(
        codex_repo, ["log", "--format=%s%n%b%n---END-COMMIT---", f"{previous.name}..{current.name}"]
    )
    change_type_counter = Counter(
        classify_change_type(block)
        for block in commit_messages.split("---END-COMMIT---")
        if block.strip()
    )
    dominant_change_type = (
        change_type_counter.most_common(1)[0][0] if change_type_counter else "Feature"
    )

    area_files: dict[str, set[str]] = defaultdict(set)
    area_paths: dict[str, list[tuple[int, int, str]]] = defaultdict(list)
    area_totals: dict[str, dict[str, float]] = defaultdict(
        lambda: {
            "weighted_churn_points": 0.0,
            "raw_insertions": 0.0,
            "raw_deletions": 0.0,
            "raw_churn": 0.0,
        }
    )
    raw_insertions = 0
    raw_deletions = 0
    generated_weighted = 0.0
    generated_raw_churn = 0

    for additions, deletions, path in diff_rows:
        area = classify_area(path)
        score = file_score(additions, deletions, path, area)
        area_files[area].add(path)
        area_paths[area].append((additions, deletions, path))
        area_totals[area]["weighted_churn_points"] += score
        area_totals[area]["raw_insertions"] += additions
        area_totals[area]["raw_deletions"] += deletions
        area_totals[area]["raw_churn"] += additions + deletions
        raw_insertions += additions
        raw_deletions += deletions
        if is_generated_path(path):
            generated_weighted += score
            generated_raw_churn += additions + deletions

    change_type_shares = type_shares_from_commits(codex_repo, previous, current)

    change_rows: list[dict[str, object]] = []
    output_release_kind = release_kind_override or current.kind
    for area in AREAS:
        totals = area_totals.get(area)
        if not totals:
            continue
        shares = change_type_shares.get(area) or {dominant_change_type: 1.0}
        for change_type, share in shares.items():
            if share <= 0:
                continue
            change_rows.append(
                {
                    "release": current.name,
                    "previous_release": previous.name,
                    "release_date": current.date_iso,
                    "previous_release_date": previous.date_iso,
                    "release_kind": output_release_kind,
                    "area_category": area,
                    "change_type": change_type,
                    "weighted_churn_points": round(
                        totals["weighted_churn_points"] * share, 3
                    ),
                    "raw_insertions": round(totals["raw_insertions"] * share, 3),
                    "raw_deletions": round(totals["raw_deletions"] * share, 3),
                    "raw_churn": round(totals["raw_churn"] * share, 3),
                    "files_changed": len(area_files[area]),
                    "commits": commit_count,
                    "top_paths": top_paths(area_paths[area]),
                }
            )

    weighted_total = sum(t["weighted_churn_points"] for t in area_totals.values())
    summary = {
        "release": current.name,
        "previous_release": previous.name,
        "release_date": current.date_iso,
        "previous_release_date": previous.date_iso,
        "release_kind": output_release_kind,
        "commit": current.commit,
        "previous_commit": previous.commit,
        "commits": commit_count,
        "files_changed": len({path for _, _, path in diff_rows}),
        "raw_insertions": raw_insertions,
        "raw_deletions": raw_deletions,
        "raw_churn": raw_insertions + raw_deletions,
        "weighted_churn_points": round(weighted_total, 3),
        "generated_raw_churn": generated_raw_churn,
        "generated_weighted_churn_points": round(generated_weighted, 3),
        "dominant_change_type": dominant_change_type,
        "top_paths": top_paths(diff_rows),
    }

    other_rows: list[dict[str, object]] = []
    other = area_totals.get("Other")
    if other and weighted_total:
        share = other["weighted_churn_points"] / weighted_total
        if share > 0.05:
            other_rows.append(
                {
                    "release": current.name,
                    "release_kind": output_release_kind,
                    "release_date": current.date_iso,
                    "other_share": round(share, 4),
                    "other_weighted_churn_points": round(
                        other["weighted_churn_points"], 3
                    ),
                    "total_weighted_churn_points": round(weighted_total, 3),
                    "top_paths": top_paths(area_paths["Other"], 8),
                }
            )
    return change_rows, summary, other_rows


def type_shares_from_commits(
    codex_repo: Path, previous: ReleaseTag, current: ReleaseTag
) -> dict[str, dict[str, float]]:
    """Estimate per-area change-type shares from commit-level numstats.

    The final area totals come from release diff numstat for reconciliation.
    Commit-level churn is used only to divide each area across change types.
    """

    raw_commits = run_git(
        codex_repo,
        [
            "log",
            "--numstat",
            "--format=@@@COMMIT@@@%x09%H%x09%s",
            f"{previous.name}..{current.name}",
        ],
    )
    area_type_points: dict[str, Counter[str]] = defaultdict(Counter)
    current_change_type = "Feature"
    for line in raw_commits.splitlines():
        if not line.strip():
            continue
        if line.startswith("@@@COMMIT@@@\t"):
            current_change_type = classify_change_type(line)
            continue
        parsed = parse_numstat(line)
        if not parsed:
            continue
        for additions, deletions, path in parsed:
            area = classify_area(path)
            area_type_points[area][current_change_type] += file_score(
                additions, deletions, path, area
            )

    shares: dict[str, dict[str, float]] = {}
    for area, counter in area_type_points.items():
        total = sum(counter.values())
        if total <= 0:
            continue
        shares[area] = {change_type: value / total for change_type, value in counter.items()}
    return shares


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def build_html(
    output_path: Path,
    change_rows: list[dict[str, object]],
    summary_rows: list[dict[str, object]],
    other_rows: list[dict[str, object]],
    source_repo: Path,
) -> None:
    raw_area_rows = aggregate_for_chart(change_rows, "area_category")
    raw_type_rows = aggregate_for_chart(change_rows, "change_type")
    summary_compact = compact_summary_rows(summary_rows)
    stable_changes = [
        row for row in change_rows if str(row.get("release_kind")) == "stable-rollup"
    ]
    stable_summaries = [
        row for row in summary_rows if str(row.get("release_kind")) == "stable-rollup"
    ]
    payload = {
        "rawAreaRows": raw_area_rows,
        "rawTypeRows": raw_type_rows,
        "rawSummaryRows": [
            row for row in summary_compact if row["release_kind"] != "stable-rollup"
        ],
        "stableAreaRows": aggregate_for_chart(stable_changes, "area_category"),
        "stableTypeRows": aggregate_for_chart(stable_changes, "change_type"),
        "stableSummaryRows": compact_summary_rows(stable_summaries),
        "otherRows": other_rows,
        "areas": AREAS,
        "changeTypes": CHANGE_TYPES,
    }
    source = html.escape(str(source_repo))
    output_path.write_text(
        HTML_TEMPLATE.replace("__DATA__", json.dumps(payload, separators=(",", ":")))
        .replace("__SOURCE_REPO__", source),
        encoding="utf-8",
    )


def compact_summary_rows(summary_rows: list[dict[str, object]]) -> list[dict[str, object]]:
    return [
        {
            "release": row["release"],
            "previous_release": row["previous_release"],
            "release_date": row["release_date"],
            "previous_release_date": row["previous_release_date"],
            "release_kind": row["release_kind"],
            "commits": row["commits"],
            "files_changed": row["files_changed"],
            "raw_churn": row["raw_churn"],
            "weighted_churn_points": row["weighted_churn_points"],
            "top_paths": row["top_paths"],
        }
        for row in summary_rows
    ]


def aggregate_for_chart(rows: list[dict[str, object]], field: str) -> list[dict[str, object]]:
    bucket: dict[tuple[str, str], dict[str, object]] = {}
    for row in rows:
        key = (str(row["release"]), str(row[field]))
        current = bucket.setdefault(
            key,
            {
                "release": row["release"],
                "release_kind": row["release_kind"],
                "release_date": row["release_date"],
                "previous_release_date": row["previous_release_date"],
                "category": row[field],
                "weighted_churn_points": 0.0,
                "raw_churn": 0.0,
                "files_changed": 0,
                "commits": row["commits"],
                "top_paths": row["top_paths"],
            },
        )
        current["weighted_churn_points"] = round(
            float(current["weighted_churn_points"]) + float(row["weighted_churn_points"]), 3
        )
        current["raw_churn"] = round(float(current["raw_churn"]) + float(row["raw_churn"]), 3)
        current["files_changed"] = max(int(current["files_changed"]), int(row["files_changed"]))
    return list(bucket.values())


HTML_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Codex Release Change Analysis</title>
  <style>
    :root {
      --bg: #f7f8fa;
      --panel: #ffffff;
      --text: #1f2937;
      --muted: #64748b;
      --line: #d8dee8;
      --accent: #2563eb;
    }
    body {
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font: 14px/1.45 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }
    header, main {
      max-width: 1180px;
      margin: 0 auto;
      padding: 22px;
    }
    header {
      padding-bottom: 8px;
    }
    h1 {
      font-size: 24px;
      margin: 0 0 6px;
    }
    p {
      margin: 0 0 12px;
      color: var(--muted);
    }
    .controls {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 12px;
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 14px;
      margin-bottom: 16px;
    }
    label {
      display: grid;
      gap: 5px;
      color: var(--muted);
      font-size: 12px;
      font-weight: 600;
    }
    select {
      min-height: 36px;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 6px 8px;
      background: white;
      color: var(--text);
      font-size: 14px;
    }
    .chart-wrap, .table-wrap {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 14px;
      overflow-x: auto;
      margin-bottom: 16px;
    }
    svg {
      display: block;
      min-width: 960px;
    }
    .axis {
      stroke: #9aa6b2;
      stroke-width: 1;
    }
    .grid {
      stroke: #e7ebf0;
      stroke-width: 1;
    }
    .tick {
      fill: #64748b;
      font-size: 11px;
    }
    .legend {
      display: flex;
      flex-wrap: wrap;
      gap: 8px 14px;
      margin-top: 12px;
    }
    .legend-item {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      color: #334155;
      font-size: 12px;
    }
    .swatch {
      width: 12px;
      height: 12px;
      border-radius: 3px;
      display: inline-block;
    }
    .tooltip {
      position: fixed;
      pointer-events: none;
      opacity: 0;
      background: #111827;
      color: white;
      border-radius: 7px;
      padding: 9px 10px;
      max-width: 360px;
      box-shadow: 0 10px 28px rgba(15, 23, 42, .28);
      font-size: 12px;
      z-index: 10;
    }
    .tooltip strong {
      display: block;
      font-size: 13px;
      margin-bottom: 4px;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      font-size: 13px;
    }
    th, td {
      border-bottom: 1px solid var(--line);
      padding: 8px 9px;
      text-align: left;
      vertical-align: top;
    }
    th {
      color: #475569;
      font-size: 12px;
      background: #f8fafc;
    }
    .empty {
      color: var(--muted);
      padding: 12px 0;
    }
  </style>
</head>
<body>
  <header>
    <h1>Codex Release Change Analysis</h1>
    <p>Source checkout: __SOURCE_REPO__. Primary metric is weighted churn points from git release diffs.</p>
  </header>
  <main>
    <section class="controls">
      <label>Release set
        <select id="releaseKind">
      <option value="stable">Stable release rollups</option>
          <option value="all">All valid rust-v tags</option>
          <option value="prerelease">Prereleases only</option>
        </select>
      </label>
      <label>Stack by
        <select id="stackBy">
          <option value="area">Area category</option>
          <option value="type">Change type</option>
        </select>
      </label>
      <label>Metric
        <select id="metric">
          <option value="weighted_churn_points">Weighted churn points</option>
          <option value="raw_churn">Raw churn</option>
        </select>
      </label>
      <label>X-axis
        <select id="xAxis">
          <option value="release">Release</option>
          <option value="day">Date</option>
          <option value="week">Week</option>
          <option value="month">Month</option>
        </select>
      </label>
      <label>Scale
        <select id="scaleMode">
          <option value="absolute">Absolute</option>
          <option value="normalized">Normalized 100%</option>
        </select>
      </label>
    </section>
    <section class="chart-wrap">
      <svg id="chart" width="1120" height="560" role="img" aria-label="Stacked bar chart"></svg>
      <div id="legend" class="legend"></div>
    </section>
    <section class="table-wrap">
      <h2>Releases With Other Above 5%</h2>
      <div id="otherTable"></div>
    </section>
  </main>
  <div id="tooltip" class="tooltip"></div>
  <script>
    const DATA = __DATA__;
    const COLORS = [
      "#2563eb", "#16a34a", "#dc2626", "#9333ea", "#ea580c", "#0891b2",
      "#4f46e5", "#65a30d", "#be123c", "#0f766e", "#64748b"
    ];
    const chart = document.getElementById("chart");
    const tooltip = document.getElementById("tooltip");
    const releaseKind = document.getElementById("releaseKind");
    const stackBy = document.getElementById("stackBy");
    const metric = document.getElementById("metric");
    const xAxis = document.getElementById("xAxis");
    const scaleMode = document.getElementById("scaleMode");

    function fmt(value) {
      return Number(value).toLocaleString(undefined, {maximumFractionDigits: 1});
    }
    function rowsForState() {
      if (releaseKind.value === "stable") {
        return stackBy.value === "area" ? DATA.stableAreaRows : DATA.stableTypeRows;
      }
      const rows = stackBy.value === "area" ? DATA.rawAreaRows : DATA.rawTypeRows;
      return rows.filter(row => releaseKind.value === "all" || row.release_kind === releaseKind.value);
    }
    function baseOrder(rows) {
      const seen = new Set();
      const order = [];
      const summaries = releaseKind.value === "stable" ? DATA.stableSummaryRows : DATA.rawSummaryRows;
      const targetKind = releaseKind.value === "stable" ? "stable-rollup" : releaseKind.value;
      for (const summary of summaries) {
        if (targetKind !== "all" && summary.release_kind !== targetKind) continue;
        if (!seen.has(summary.release)) {
          seen.add(summary.release);
          order.push(summary.release);
        }
      }
      return order.filter(release => rows.some(row => row.release === release));
    }
    function rowsForChart() {
      const rows = rowsForState();
      if (xAxis.value === "release") {
        return {rows, labels: baseOrder(rows), timeBucketed: false};
      }
      return bucketRowsByTime(rows, xAxis.value);
    }
    function categories(rows) {
      const configured = stackBy.value === "area" ? DATA.areas : DATA.changeTypes;
      const present = new Set(rows.map(row => row.category));
      return configured.filter(category => present.has(category));
    }
    function render() {
      const chartData = rowsForChart();
      const rows = chartData.rows;
      const releases = chartData.labels;
      const cats = categories(rows);
      const width = Math.max(1120, releases.length * (releaseKind.value === "all" || chartData.timeBucketed ? 9 : 20) + 160);
      const height = 560;
      chart.setAttribute("width", width);
      chart.setAttribute("height", height);
      chart.innerHTML = "";
      const margin = {top: 24, right: 24, bottom: 116, left: 88};
      const plotW = width - margin.left - margin.right;
      const plotH = height - margin.top - margin.bottom;
      const totals = new Map(releases.map(r => [r, 0]));
      for (const row of rows) totals.set(row.release, (totals.get(row.release) || 0) + Number(row[metric.value]));
      const maxY = scaleMode.value === "normalized" ? 100 : Math.max(1, ...Array.from(totals.values()));
      const niceMax = scaleMode.value === "normalized" ? 100 : Math.ceil(maxY / Math.pow(10, Math.floor(Math.log10(maxY)))) * Math.pow(10, Math.floor(Math.log10(maxY)));
      const barGap = releaseKind.value === "all" || chartData.timeBucketed ? 1 : 4;
      const barW = Math.max(3, plotW / Math.max(1, releases.length) - barGap);
      for (let i = 0; i <= 5; i++) {
        const y = margin.top + plotH - (plotH * i / 5);
        const line = svgEl("line", {x1: margin.left, y1: y, x2: width - margin.right, y2: y, class: "grid"});
        chart.appendChild(line);
        const tickValue = niceMax * i / 5;
        chart.appendChild(svgEl("text", {x: margin.left - 8, y: y + 4, "text-anchor": "end", class: "tick"}, scaleMode.value === "normalized" ? `${fmt(tickValue)}%` : fmt(tickValue)));
      }
      chart.appendChild(svgEl("line", {x1: margin.left, y1: margin.top + plotH, x2: width - margin.right, y2: margin.top + plotH, class: "axis"}));
      chart.appendChild(svgEl("line", {x1: margin.left, y1: margin.top, x2: margin.left, y2: margin.top + plotH, class: "axis"}));

      const rowMap = new Map();
      for (const row of rows) rowMap.set(row.release + "\\u0000" + row.category, row);
      releases.forEach((release, i) => {
        const x = margin.left + i * (barW + barGap);
        let yBase = margin.top + plotH;
        cats.forEach((cat, catIndex) => {
          const row = rowMap.get(release + "\\u0000" + cat);
          if (!row) return;
          const rawValue = Number(row[metric.value]);
          const total = totals.get(release) || 0;
          const value = scaleMode.value === "normalized" && total ? rawValue / total * 100 : rawValue;
          if (!value) return;
          const h = plotH * value / niceMax;
          yBase -= h;
          const rect = svgEl("rect", {x, y: yBase, width: barW, height: Math.max(0.5, h), fill: COLORS[catIndex % COLORS.length]});
          rect.addEventListener("mousemove", event => showTooltip(event, row, cat, value, rawValue, total));
          rect.addEventListener("mouseleave", hideTooltip);
          chart.appendChild(rect);
        });
        if (releaseKind.value !== "all" && !chartData.timeBucketed || i % Math.max(1, Math.ceil(releases.length / 40)) === 0) {
          chart.appendChild(svgEl("text", {
            x: x + barW / 2,
            y: margin.top + plotH + 14,
            transform: `rotate(55 ${x + barW / 2} ${margin.top + plotH + 14})`,
            "text-anchor": "start",
            class: "tick"
          }, release.replace("rust-v", "")));
        }
      });
      renderLegend(cats);
      renderOtherTable();
    }
    function bucketRowsByTime(rows, unit) {
      const buckets = new Map();
      const labels = [];
      for (const row of rows) {
        const start = new Date(row.previous_release_date);
        const end = new Date(row.release_date);
        if (!Number.isFinite(start.getTime()) || !Number.isFinite(end.getTime())) continue;
        const startMs = start.getTime();
        const endMs = end.getTime();
        const duration = Math.max(1, endMs - startMs);
        for (const bucket of overlappingBuckets(startMs, endMs, unit)) {
          const share = Math.max(0, Math.min(endMs, bucket.end) - Math.max(startMs, bucket.start)) / duration;
          if (share <= 0) continue;
          const key = bucket.label + "\\u0000" + row.category;
          const current = buckets.get(key) || {
            release: bucket.label,
            release_kind: row.release_kind,
            release_date: bucket.label,
            previous_release_date: bucket.label,
            category: row.category,
            weighted_churn_points: 0,
            raw_churn: 0,
            files_changed: 0,
            commits: 0,
            top_paths: "",
            source_releases: new Set(),
          };
          current.weighted_churn_points += Number(row.weighted_churn_points) * share;
          current.raw_churn += Number(row.raw_churn) * share;
          current.files_changed += Number(row.files_changed) * share;
          current.commits += Number(row.commits) * share;
          current.source_releases.add(row.release);
          buckets.set(key, current);
          if (!labels.includes(bucket.label)) labels.push(bucket.label);
        }
      }
      const bucketRows = Array.from(buckets.values()).map(row => ({
        ...row,
        weighted_churn_points: Number(row.weighted_churn_points.toFixed(3)),
        raw_churn: Number(row.raw_churn.toFixed(3)),
        files_changed: Number(row.files_changed.toFixed(1)),
        commits: Number(row.commits.toFixed(1)),
        top_paths: `${row.source_releases.size} source release interval(s) allocated by elapsed-time overlap`,
        source_releases: undefined,
      }));
      labels.sort();
      return {rows: bucketRows, labels, timeBucketed: true};
    }
    function overlappingBuckets(startMs, endMs, unit) {
      const buckets = [];
      let cursor = bucketStart(new Date(startMs), unit).getTime();
      while (cursor < endMs) {
        const next = nextBucketStart(new Date(cursor), unit).getTime();
        buckets.push({label: bucketLabel(new Date(cursor), unit), start: cursor, end: next});
        cursor = next;
      }
      return buckets;
    }
    function bucketStart(date, unit) {
      const d = new Date(Date.UTC(date.getUTCFullYear(), date.getUTCMonth(), date.getUTCDate()));
      if (unit === "month") return new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), 1));
      if (unit === "week") {
        const day = d.getUTCDay() || 7;
        d.setUTCDate(d.getUTCDate() - day + 1);
      }
      return d;
    }
    function nextBucketStart(date, unit) {
      const d = new Date(date.getTime());
      if (unit === "month") return new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth() + 1, 1));
      d.setUTCDate(d.getUTCDate() + (unit === "week" ? 7 : 1));
      return d;
    }
    function bucketLabel(date, unit) {
      const y = date.getUTCFullYear();
      const m = String(date.getUTCMonth() + 1).padStart(2, "0");
      const d = String(date.getUTCDate()).padStart(2, "0");
      if (unit === "month") return `${y}-${m}`;
      if (unit === "week") return `${y}-W${String(isoWeek(date)).padStart(2, "0")}`;
      return `${y}-${m}-${d}`;
    }
    function isoWeek(date) {
      const d = new Date(Date.UTC(date.getUTCFullYear(), date.getUTCMonth(), date.getUTCDate()));
      d.setUTCDate(d.getUTCDate() + 4 - (d.getUTCDay() || 7));
      const yearStart = new Date(Date.UTC(d.getUTCFullYear(), 0, 1));
      return Math.ceil((((d - yearStart) / 86400000) + 1) / 7);
    }
    function renderLegend(cats) {
      const legend = document.getElementById("legend");
      legend.innerHTML = "";
      cats.forEach((cat, i) => {
        const item = document.createElement("span");
        item.className = "legend-item";
        item.innerHTML = `<span class="swatch" style="background:${COLORS[i % COLORS.length]}"></span>${escapeHtml(cat)}`;
        legend.appendChild(item);
      });
    }
    function renderOtherTable() {
      const targetKind = releaseKind.value === "stable" ? "stable-rollup" : releaseKind.value;
      const rows = DATA.otherRows.filter(row => targetKind === "all" || row.release_kind === targetKind);
      const el = document.getElementById("otherTable");
      if (!rows.length) {
        el.innerHTML = '<div class="empty">No releases in this filter have Other above 5%.</div>';
        return;
      }
      el.innerHTML = `<table><thead><tr><th>Release</th><th>Date</th><th>Other share</th><th>Top Other paths</th></tr></thead><tbody>${
        rows.map(row => `<tr><td>${escapeHtml(row.release)}</td><td>${escapeHtml(row.release_date)}</td><td>${fmt(row.other_share * 100)}%</td><td>${escapeHtml(row.top_paths)}</td></tr>`).join("")
      }</tbody></table>`;
    }
    function showTooltip(event, row, category, value, rawValue, total) {
      tooltip.style.opacity = "1";
      tooltip.style.left = Math.min(window.innerWidth - 380, event.clientX + 14) + "px";
      tooltip.style.top = Math.min(window.innerHeight - 160, event.clientY + 14) + "px";
      tooltip.innerHTML = `<strong>${escapeHtml(row.release)}</strong>
        ${escapeHtml(category)}<br>
        ${scaleMode.value === "normalized" ? "Share" : metric.options[metric.selectedIndex].text}: ${scaleMode.value === "normalized" ? `${fmt(value)}%` : fmt(value)}<br>
        ${metric.options[metric.selectedIndex].text}: ${fmt(rawValue)} of ${fmt(total)}<br>
        Raw churn: ${fmt(row.raw_churn)}<br>
        Files: ${fmt(row.files_changed)} | Commits: ${fmt(row.commits)}<br>
        <span>${escapeHtml(row.top_paths || "")}</span>`;
    }
    function hideTooltip() {
      tooltip.style.opacity = "0";
    }
    function svgEl(name, attrs, text) {
      const el = document.createElementNS("http://www.w3.org/2000/svg", name);
      for (const [key, value] of Object.entries(attrs)) el.setAttribute(key, value);
      if (text !== undefined) el.textContent = text;
      return el;
    }
    function escapeHtml(value) {
      return String(value).replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;","\\"":"&quot;","'":"&#39;"}[c]));
    }
    releaseKind.addEventListener("change", render);
    stackBy.addEventListener("change", render);
    metric.addEventListener("change", render);
    xAxis.addEventListener("change", render);
    scaleMode.addEventListener("change", render);
    render();
  </script>
</body>
</html>
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--codex-repo",
        type=Path,
        default=Path("/Users/fridiculous/projects/codex"),
        help="Path to the local openai/codex checkout.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("reports/codex-release-history"),
        help="Directory for CSV and HTML report outputs.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Optional limit for recent intervals, useful for quick validation.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    codex_repo = args.codex_repo.resolve()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    if not (codex_repo / ".git").exists():
        print(f"Codex repo is not a git checkout: {codex_repo}", file=sys.stderr)
        return 2

    tags = list_release_tags(codex_repo)
    if len(tags) < 2:
        print("Need at least two valid rust-v release tags.", file=sys.stderr)
        return 2

    intervals = list(zip(tags, tags[1:]))
    if args.limit:
        intervals = intervals[-args.limit :]

    change_rows: list[dict[str, object]] = []
    summary_rows: list[dict[str, object]] = []
    other_rows: list[dict[str, object]] = []

    for index, (previous, current) in enumerate(intervals, start=1):
        print(f"[{index}/{len(intervals)}] {previous.name}..{current.name}", file=sys.stderr)
        rows, summary, other = collect_interval(codex_repo, previous, current)
        change_rows.extend(rows)
        summary_rows.append(summary)
        other_rows.extend(other)

    stable_change_rows: list[dict[str, object]] = []
    stable_summary_rows: list[dict[str, object]] = []
    stable_other_rows: list[dict[str, object]] = []
    stable_tags = [tag for tag in tags if tag.kind == "stable"]
    stable_intervals = list(zip(stable_tags, stable_tags[1:]))
    if args.limit:
        stable_intervals = stable_intervals[-args.limit :]
    for index, (previous, current) in enumerate(stable_intervals, start=1):
        print(
            f"[stable {index}/{len(stable_intervals)}] {previous.name}..{current.name}",
            file=sys.stderr,
        )
        rows, summary, other = collect_interval(
            codex_repo, previous, current, release_kind_override="stable-rollup"
        )
        stable_change_rows.extend(rows)
        stable_summary_rows.append(summary)
        stable_other_rows.extend(other)

    write_csv(
        output_dir / "release_changes.csv",
        change_rows,
        [
            "release",
            "previous_release",
            "release_date",
            "previous_release_date",
            "release_kind",
            "area_category",
            "change_type",
            "weighted_churn_points",
            "raw_insertions",
            "raw_deletions",
            "raw_churn",
            "files_changed",
            "commits",
            "top_paths",
        ],
    )
    write_csv(
        output_dir / "stable_release_changes.csv",
        stable_change_rows,
        [
            "release",
            "previous_release",
            "release_date",
            "previous_release_date",
            "release_kind",
            "area_category",
            "change_type",
            "weighted_churn_points",
            "raw_insertions",
            "raw_deletions",
            "raw_churn",
            "files_changed",
            "commits",
            "top_paths",
        ],
    )
    write_csv(
        output_dir / "release_summary.csv",
        summary_rows,
        [
            "release",
            "previous_release",
            "release_date",
            "previous_release_date",
            "release_kind",
            "commit",
            "previous_commit",
            "commits",
            "files_changed",
            "raw_insertions",
            "raw_deletions",
            "raw_churn",
            "weighted_churn_points",
            "generated_raw_churn",
            "generated_weighted_churn_points",
            "dominant_change_type",
            "top_paths",
        ],
    )
    write_csv(
        output_dir / "stable_release_summary.csv",
        stable_summary_rows,
        [
            "release",
            "previous_release",
            "release_date",
            "previous_release_date",
            "release_kind",
            "commit",
            "previous_commit",
            "commits",
            "files_changed",
            "raw_insertions",
            "raw_deletions",
            "raw_churn",
            "weighted_churn_points",
            "generated_raw_churn",
            "generated_weighted_churn_points",
            "dominant_change_type",
            "top_paths",
        ],
    )
    write_csv(
        output_dir / "other_review.csv",
        other_rows,
        [
            "release",
            "release_kind",
            "release_date",
            "other_share",
            "other_weighted_churn_points",
            "total_weighted_churn_points",
            "top_paths",
        ],
    )
    write_csv(
        output_dir / "stable_other_review.csv",
        stable_other_rows,
        [
            "release",
            "release_kind",
            "release_date",
            "other_share",
            "other_weighted_churn_points",
            "total_weighted_churn_points",
            "top_paths",
        ],
    )
    build_html(
        output_dir / "release_change_chart.html",
        change_rows + stable_change_rows,
        summary_rows + stable_summary_rows,
        other_rows + stable_other_rows,
        codex_repo,
    )

    stable_count = sum(1 for row in summary_rows if row["release_kind"] == "stable")
    prerelease_count = len(summary_rows) - stable_count
    print(
        f"Wrote {len(summary_rows)} release intervals "
        f"({stable_count} stable tag-to-tag, {prerelease_count} prerelease) "
        f"and {len(stable_summary_rows)} stable rollups to {output_dir}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
