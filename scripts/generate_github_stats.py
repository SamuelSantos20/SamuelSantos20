from __future__ import annotations

import html
import json
import math
import os
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

API_BASE = "https://api.github.com"
USERNAME = os.getenv("GITHUB_USERNAME", "SamuelSantos20")
TOKEN = os.getenv("GITHUB_TOKEN", "")
FEATURED_REPOSITORIES = {
    name.strip().lower()
    for name in os.getenv("STATS_REPOSITORIES", "").split(",")
    if name.strip()
}
OUTPUT_DIR = Path("assets")

BACKGROUND = "#0d1117"
BORDER = "#30363d"
TITLE = "#a78bfa"
TEXT = "#e6edf3"
MUTED = "#8b949e"
LANGUAGE_COLORS = ["#7c3aed", "#58a6ff", "#3fb950", "#d29922", "#f778ba"]


def request_json(path: str) -> Any:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "SamuelSantos20-profile-stats",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"

    request = urllib.request.Request(f"{API_BASE}{path}", headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GitHub API retornou HTTP {exc.code}: {detail}") from exc


def paginated(path: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    page = 1
    separator = "&" if "?" in path else "?"

    while True:
        batch = request_json(f"{path}{separator}per_page=100&page={page}")
        if not isinstance(batch, list):
            raise RuntimeError("Resposta inesperada da API ao listar repositórios.")
        items.extend(batch)
        if len(batch) < 100:
            break
        page += 1

    return items


def write_svg(filename: str, content: str) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / filename).write_text(content, encoding="utf-8")


def svg_header(width: int, height: int) -> str:
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img">
  <title>Estatísticas do GitHub de {html.escape(USERNAME)}</title>
  <style>
    .title {{ font: 600 18px -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; fill: {TITLE}; }}
    .label {{ font: 400 12px -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; fill: {MUTED}; }}
    .value {{ font: 700 24px -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; fill: {TEXT}; }}
    .language {{ font: 600 13px -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; fill: {TEXT}; }}
  </style>
  <rect x="0.5" y="0.5" width="{width - 1}" height="{height - 1}" rx="10" fill="{BACKGROUND}" stroke="{BORDER}" />
'''


def render_stats(profile: dict[str, Any], repos: list[dict[str, Any]]) -> str:
    owned = [repo for repo in repos if not repo.get("fork")]
    total_stars = sum(int(repo.get("stargazers_count", 0)) for repo in owned)
    total_forks = sum(int(repo.get("forks_count", 0)) for repo in owned)
    public_repos = int(profile.get("public_repos", len(repos)))
    followers = int(profile.get("followers", 0))
    updated = datetime.now(timezone.utc).strftime("%d/%m/%Y")

    metrics = [
        ("Repositórios públicos", public_repos),
        ("Estrelas recebidas", total_stars),
        ("Forks", total_forks),
        ("Seguidores", followers),
    ]
    positions = [(28, 68), (250, 68), (28, 138), (250, 138)]

    svg = [svg_header(480, 205), '  <text x="24" y="34" class="title">Resumo do perfil</text>']
    for (label, value), (x, y) in zip(metrics, positions, strict=True):
        svg.append(f'  <text x="{x}" y="{y}" class="value">{value}</text>')
        svg.append(f'  <text x="{x}" y="{y + 20}" class="label">{html.escape(label)}</text>')

    svg.append(f'  <text x="24" y="184" class="label">Atualizado automaticamente em {updated}</text>')
    svg.append("</svg>\n")
    return "\n".join(svg)


def render_languages(repos: list[dict[str, Any]]) -> str:
    totals: Counter[str] = Counter()
    eligible = [repo for repo in repos if not repo.get("fork") and not repo.get("archived")]

    if FEATURED_REPOSITORIES:
        eligible = [
            repo
            for repo in eligible
            if str(repo.get("name", "")).lower() in FEATURED_REPOSITORIES
        ]

    for repo in eligible:
        full_name = repo.get("full_name")
        if not full_name:
            continue
        encoded = urllib.parse.quote(str(full_name), safe="/")
        languages = request_json(f"/repos/{encoded}/languages")
        if isinstance(languages, dict):
            totals.update({str(name): int(value) for name, value in languages.items()})

    top = totals.most_common(5)
    grand_total = sum(value for _, value in top) or 1
    heading = (
        "Linguagens nos projetos em destaque"
        if FEATURED_REPOSITORIES
        else "Linguagens mais usadas"
    )

    svg = [svg_header(480, 205), f'  <text x="24" y="34" class="title">{heading}</text>']

    if not top:
        svg.append('  <text x="24" y="80" class="label">Nenhum dado de linguagem disponível.</text>')
    else:
        center_x = 122
        center_y = 112
        radius = 58
        stroke_width = 22
        circumference = 2 * math.pi * radius
        offset = 0.0

        svg.append(
            f'  <circle cx="{center_x}" cy="{center_y}" r="{radius}" fill="none" '
            f'stroke="{BORDER}" stroke-width="{stroke_width}" />'
        )

        for index, (language, value) in enumerate(top):
            segment = circumference * value / grand_total
            color = LANGUAGE_COLORS[index % len(LANGUAGE_COLORS)]
            legend_y = 68 + index * 27
            svg.extend(
                [
                    f'  <circle cx="{center_x}" cy="{center_y}" r="{radius}" fill="none" '
                    f'stroke="{color}" stroke-width="{stroke_width}" '
                    f'stroke-dasharray="{segment:.2f} {circumference - segment:.2f}" '
                    f'stroke-dashoffset="{-offset:.2f}" '
                    f'transform="rotate(-90 {center_x} {center_y})" />',
                    f'  <rect x="232" y="{legend_y - 10}" width="12" height="12" rx="3" fill="{color}" />',
                    f'  <text x="253" y="{legend_y}" class="language">{html.escape(language)}</text>',
                ]
            )
            offset += segment

        svg.extend(
            [
                f'  <text x="{center_x}" y="108" text-anchor="middle" class="language">TOP 5</text>',
                f'  <text x="{center_x}" y="126" text-anchor="middle" class="label">linguagens</text>',
            ]
        )

    svg.append("</svg>\n")
    return "\n".join(svg)


def main() -> None:
    profile = request_json(f"/users/{urllib.parse.quote(USERNAME)}")
    repos = paginated(
        f"/users/{urllib.parse.quote(USERNAME)}/repos?type=owner&sort=updated&direction=desc"
    )

    if not isinstance(profile, dict):
        raise RuntimeError("Resposta inesperada da API ao carregar o perfil.")

    write_svg("github-stats.svg", render_stats(profile, repos))
    write_svg("github-languages-bars.svg", render_languages(repos))


if __name__ == "__main__":
    main()
