#!/usr/bin/env python3
"""Genera los SVG animados del perfil: assets/header.svg y assets/activity.svg.

Lee el calendario de contribuciones con la API GraphQL de GitHub. Solo usa
conteos por día, así que nunca expone nombres de repos ni mensajes de commit.

Uso:
    GITHUB_TOKEN=... PROFILE_USER=Oalvarado031 python3 scripts/build_profile.py
"""
import datetime as dt
import json
import os
import pathlib
import urllib.request

LOGIN = os.environ.get("PROFILE_USER", "Oalvarado031")
TOKEN = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
ROLE = "DESARROLLADOR DE SOFTWARE"
TAGLINE = "ERP y CRM a medida · Apps móviles · Web"

ASSETS = pathlib.Path(__file__).resolve().parent.parent / "assets"
API = "https://api.github.com/graphql"
MONTHS = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
LEVELS = {
    "NONE": 0,
    "FIRST_QUARTILE": 1,
    "SECOND_QUARTILE": 2,
    "THIRD_QUARTILE": 3,
    "FOURTH_QUARTILE": 4,
}

# Colores de GitHub (Primer) para que las tarjetas se integren con la página
# tanto en tema claro como oscuro.
THEME_CSS = """
:root{--bg:#ffffff;--bd:#d1d9e0;--fg:#1f2328;--mut:#59636e;--grid:#eaeef2;
--l0:#eff2f5;--l1:#aceebb;--l2:#4ac26b;--l3:#2da44e;--l4:#116329;
--green:#1a7f37;--blue:#0969da;--purple:#8250df}
@media (prefers-color-scheme:dark){:root{--bg:#0d1117;--bd:#3d444d;--fg:#f0f6fc;--mut:#9198a1;--grid:#21262d;
--l0:#151b23;--l1:#033a16;--l2:#196c2e;--l3:#2ea043;--l4:#56d364;
--green:#3fb950;--blue:#4493f8;--purple:#ab7df8}}
text{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Noto Sans",Helvetica,Arial,sans-serif;font-variant-numeric:tabular-nums}
.mono{font-family:ui-monospace,SFMono-Regular,"SF Mono",Menlo,Consolas,monospace}
.card{fill:var(--bg);stroke:var(--bd)}
@media (prefers-reduced-motion:reduce){*{animation:none!important}}
"""


def graphql(query, variables):
    body = json.dumps({"query": query, "variables": variables}).encode()
    request = urllib.request.Request(
        API,
        data=body,
        headers={
            "Authorization": "bearer " + TOKEN,
            "Content-Type": "application/json",
            "User-Agent": "profile-readme",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.load(response)
    if payload.get("errors"):
        raise SystemExit("GitHub API: %s" % payload["errors"])
    return payload["data"]


def fetch():
    """Devuelve (nombre, semanas del último año, total del año, {fecha: conteo} histórico)."""
    data = graphql(
        """query($login:String!){user(login:$login){name contributionsCollection{
        contributionYears contributionCalendar{totalContributions
        weeks{contributionDays{date weekday contributionCount contributionLevel}}}}}}""",
        {"login": LOGIN},
    )["user"]
    collection = data["contributionsCollection"]
    calendar = collection["contributionCalendar"]

    now = dt.datetime.now(dt.timezone.utc)
    history = {}
    for year in collection["contributionYears"]:
        end = min(dt.datetime(year, 12, 31, 23, 59, 59, tzinfo=dt.timezone.utc), now)
        year_data = graphql(
            """query($login:String!,$from:DateTime!,$to:DateTime!){user(login:$login){
            contributionsCollection(from:$from,to:$to){contributionCalendar{
            weeks{contributionDays{date contributionCount}}}}}}""",
            {
                "login": LOGIN,
                "from": "%d-01-01T00:00:00Z" % year,
                "to": end.strftime("%Y-%m-%dT%H:%M:%SZ"),
            },
        )["user"]["contributionsCollection"]["contributionCalendar"]
        for week in year_data["weeks"]:
            for day in week["contributionDays"]:
                history[day["date"]] = day["contributionCount"]

    return data["name"] or LOGIN, calendar["weeks"], calendar["totalContributions"], history


def short_date(iso, with_year=False):
    date = dt.date.fromisoformat(iso)
    text = "%d %s" % (date.day, MONTHS[date.month - 1])
    return "%s %d" % (text, date.year) if with_year else text


def smooth_path(points):
    """Curva cúbica monótona (Fritsch-Carlson): pasa por los puntos sin rebasar el eje."""
    count = len(points)
    if count < 2:
        return ""
    step = points[1][0] - points[0][0]
    delta = [(points[i + 1][1] - points[i][1]) / step for i in range(count - 1)]
    slope = [delta[0]] + [
        (delta[i - 1] + delta[i]) / 2 if delta[i - 1] * delta[i] > 0 else 0.0
        for i in range(1, count - 1)
    ] + [delta[-1]]
    for i in range(count - 1):
        if delta[i] == 0:
            slope[i] = slope[i + 1] = 0.0
            continue
        a, b = slope[i] / delta[i], slope[i + 1] / delta[i]
        norm = a * a + b * b
        if norm > 9:
            scale = 3 / norm ** 0.5
            slope[i], slope[i + 1] = scale * a * delta[i], scale * b * delta[i]
    parts = ["M%.1f %.1f" % points[0]]
    for i in range(count - 1):
        (x0, y0), (x1, y1) = points[i], points[i + 1]
        parts.append(
            "C%.1f %.1f %.1f %.1f %.1f %.1f"
            % (x0 + step / 3, y0 + slope[i] * step / 3, x1 - step / 3, y1 - slope[i + 1] * step / 3, x1, y1)
        )
    return "".join(parts)


def build_header(name):
    width, height = 840, 190
    speed = 240.0  # px/s con que se dibujan las ramas

    # (clase de color, trazado, inicio en s, longitud aproximada en px)
    lanes = [
        ("green", "M472 132H808", 0.20, 336),
        ("blue", "M522 132C548 132 548 92 574 92H668C694 92 694 132 720 132", 0.41, 226),
        ("purple", "M606 92C632 92 632 52 658 52H796", 0.82, 204),
    ]
    # (clase de color, x, y, aparición en s)
    commits = [
        ("green", 492, 132, 0.28), ("green", 522, 132, 0.41), ("green", 620, 132, 0.82),
        ("green", 720, 132, 1.35), ("green", 776, 132, 1.47),
        ("blue", 574, 92, 0.69), ("blue", 606, 92, 0.82), ("blue", 668, 92, 1.08),
        ("purple", 658, 52, 1.10), ("purple", 704, 52, 1.29), ("purple", 750, 52, 1.48),
    ]
    head_x, head_y, head_at = 796, 52, 1.67

    out = [
        '<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
        'viewBox="0 0 %d %d" width="%d" height="%d" role="img" aria-label="%s — %s">'
        % (width, height, width, height, name, TAGLINE),
        "<style>%s" % THEME_CSS,
        ".eyebrow{font-size:12px;font-weight:600;letter-spacing:.16em;fill:var(--mut)}",
        ".name{font-size:42px;font-weight:700;fill:var(--fg);letter-spacing:-.01em}",
        ".tag{font-size:16px;fill:var(--mut)}",
        ".label{font-size:11px;fill:var(--mut);animation:fade .5s ease-out both}",
        ".green{--c:var(--green)}.blue{--c:var(--blue)}.purple{--c:var(--purple)}",
        ".lane{fill:none;stroke:var(--c);stroke-width:2.5;stroke-linecap:round;"
        "stroke-dasharray:1;animation:draw 1s linear both}",
        ".commit{fill:var(--c);stroke:var(--bg);stroke-width:3;transform-box:fill-box;"
        "transform-origin:center;animation:pop .4s ease-out both}",
        ".ring{fill:none;stroke:var(--purple);stroke-width:2;transform-box:fill-box;"
        "transform-origin:center;animation:ring 2.2s ease-out infinite both}",
        ".pulse{fill:var(--fg)}",
        ".glow{fill:url(#glow)}.g0{stop-color:var(--blue);stop-opacity:.16}.g1{stop-color:var(--blue);stop-opacity:0}",
        ".intro{animation:rise .7s ease-out both}",
        "@keyframes draw{from{stroke-dashoffset:1}to{stroke-dashoffset:0}}",
        "@keyframes pop{from{opacity:0;transform:scale(0)}60%{opacity:1;transform:scale(1.4)}to{opacity:1;transform:scale(1)}}",
        "@keyframes ring{from{opacity:0;transform:scale(1)}15%{opacity:.7}to{opacity:0;transform:scale(2.8)}}",
        "@keyframes fade{from{opacity:0}to{opacity:1}}",
        "@keyframes rise{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:translateY(0)}}",
        "</style>",
        '<defs><radialGradient id="glow"><stop class="g0" offset="0"/><stop class="g1" offset="1"/></radialGradient>'
        '<clipPath id="clip"><rect x="1" y="1" width="%d" height="%d" rx="11"/></clipPath></defs>'
        % (width - 2, height - 2),
        '<rect class="card" x=".5" y=".5" width="%d" height="%d" rx="12"/>' % (width - 1, height - 1),
        '<g clip-path="url(#clip)"><circle class="glow" cx="660" cy="92" r="230"/></g>',
        '<text class="eyebrow intro" x="36" y="62">%s</text>' % ROLE,
        '<text class="name intro" x="34" y="108" style="animation-delay:.1s">%s</text>' % name,
        '<text class="tag intro" x="36" y="140" style="animation-delay:.2s">%s</text>' % TAGLINE,
    ]

    for index, (color, path, start, length) in enumerate(lanes):
        out.append(
            '<path id="lane%d" class="lane %s" pathLength="1" d="%s" '
            'style="animation-delay:%.2fs;animation-duration:%.2fs"/>'
            % (index, color, path, start, length / speed)
        )
    # Destellos que recorren cada rama una vez terminada la intro.
    for index, duration in enumerate((3.4, 2.8, 2.5)):
        out.append(
            '<circle class="pulse" r="2.5" opacity="0">'
            '<animateMotion dur="%.1fs" begin="2.4s" repeatCount="indefinite"><mpath xlink:href="#lane%d"/></animateMotion>'
            '<animate attributeName="opacity" values="0;.9;.9;0" keyTimes="0;.12;.88;1" dur="%.1fs" begin="2.4s" repeatCount="indefinite"/>'
            "</circle>" % (duration, index, duration)
        )
    for color, x, y, at in commits:
        out.append('<circle class="commit %s" cx="%d" cy="%d" r="6" style="animation-delay:%.2fs"/>' % (color, x, y, at))
    out += [
        '<circle class="ring" cx="%d" cy="%d" r="7" style="animation-delay:%.2fs"/>' % (head_x, head_y, head_at + 0.3),
        '<circle class="commit purple" cx="%d" cy="%d" r="7.5" style="animation-delay:%.2fs"/>' % (head_x, head_y, head_at),
        '<text class="label mono" x="%d" y="%d" text-anchor="end" style="animation-delay:%.2fs">HEAD</text>'
        % (head_x + 8, head_y - 18, head_at + 0.2),
        '<text class="label mono" x="776" y="158" text-anchor="middle" style="animation-delay:1.7s">main</text>',
        "</svg>",
    ]
    return "\n".join(out)


def build_activity(weeks, total_year, history):
    width, height = 840, 388
    left, pitch, cell = 58.0, 14.2, 11
    chart_top, baseline = 122.0, 206.0
    grid_top = 240.0
    cycle = 16  # segundos que dura cada repetición de la animación

    days = [day for week in weeks for day in week["contributionDays"]]
    active_days = sum(1 for day in days if day["contributionCount"])
    best = max(days, key=lambda day: day["contributionCount"])
    total_all = sum(history.values()) or total_year
    weekly = [sum(day["contributionCount"] for day in week["contributionDays"]) for week in weeks]
    peak = max(max(weekly), 1)

    points = [
        (left + i * pitch + cell / 2, baseline - (value / peak) * (baseline - chart_top))
        for i, value in enumerate(weekly)
    ]
    line = smooth_path(points)
    area = "%sL%.1f %.1fL%.1f %.1fZ" % (line, points[-1][0], baseline, points[0][0], baseline)

    out = [
        '<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
        'viewBox="0 0 %d %d" width="%d" height="%d" role="img" '
        'aria-label="%s contribuciones en el último año">' % (width, height, width, height, format(total_year, ",")),
        "<style>%s" % THEME_CSS,
        ".big{font-size:44px;font-weight:700;fill:var(--fg);letter-spacing:-.02em}",
        ".value{font-size:22px;font-weight:600;fill:var(--fg)}",
        ".caption{font-size:13px;fill:var(--mut)}",
        ".small{font-size:11px;fill:var(--mut)}",
        ".tiny{font-size:10px;fill:var(--mut)}",
        ".gridline{stroke:var(--grid);stroke-width:1}",
        ".l0{fill:var(--l0)}.l1{fill:var(--l1)}.l2{fill:var(--l2)}.l3{fill:var(--l3)}.l4{fill:var(--l4)}",
        ".day{transform-box:fill-box;transform-origin:center;animation:cell %ds ease-out infinite both}" % cycle,
        ".chart{animation:cycle %ds linear infinite both}" % cycle,
        ".line{fill:none;stroke:url(#stroke);stroke-width:2.5;stroke-linecap:round;stroke-linejoin:round;"
        "stroke-dasharray:1;animation:draw %ds ease-in-out infinite both}" % cycle,
        ".halo{fill:none;stroke:var(--green);stroke-width:7;opacity:.18;stroke-linecap:round;"
        "stroke-dasharray:1;animation:draw %ds ease-in-out infinite both}" % cycle,
        ".area{fill:url(#area);animation:reveal %ds ease-out infinite both}" % cycle,
        ".s0{stop-color:var(--blue)}.s1{stop-color:var(--green)}",
        ".a0{stop-color:var(--green);stop-opacity:.32}.a1{stop-color:var(--green);stop-opacity:0}",
        ".spark{fill:var(--green)}.sparkglow{fill:var(--green);opacity:.25}",
        ".intro{animation:rise .7s ease-out both}",
        "@keyframes cell{0%{opacity:0;transform:scale(.2)}3%{opacity:1;transform:scale(1.15)}5%,93%{opacity:1;transform:scale(1)}97%,100%{opacity:0;transform:scale(.2)}}",
        "@keyframes cycle{0%,93%{opacity:1}97%,100%{opacity:0}}",
        "@keyframes draw{0%{stroke-dashoffset:1}14%,100%{stroke-dashoffset:0}}",
        "@keyframes reveal{0%,8%{opacity:0}20%,100%{opacity:1}}",
        "@keyframes rise{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:translateY(0)}}",
        "</style>",
        '<defs><linearGradient id="stroke" gradientUnits="userSpaceOnUse" x1="%.0f" y1="0" x2="%.0f" y2="0">'
        '<stop class="s0" offset="0"/><stop class="s1" offset="1"/></linearGradient>'
        '<linearGradient id="area" x1="0" y1="0" x2="0" y2="1"><stop class="a0" offset="0"/><stop class="a1" offset="1"/></linearGradient></defs>'
        % (left, width - 28),
        '<rect class="card" x=".5" y=".5" width="%d" height="%d" rx="12"/>' % (width - 1, height - 1),
        '<text class="big intro" x="27" y="68">%s</text>' % format(total_year, ","),
        '<text class="caption intro" x="28" y="92" style="animation-delay:.1s">contribuciones en el último año</text>',
    ]

    stats = [
        (format(total_all, ","), "total histórico"),
        (str(active_days), "días activos"),
        (str(best["contributionCount"]), "mejor día · %s" % short_date(best["date"])),
    ]
    for index, (value, caption) in enumerate(stats):
        x = width - 28 - (len(stats) - 1 - index) * 150
        delay = 0.15 + index * 0.08
        out.append('<text class="value intro" x="%d" y="62" text-anchor="end" style="animation-delay:%.2fs">%s</text>' % (x, delay, value))
        out.append('<text class="small intro" x="%d" y="82" text-anchor="end" style="animation-delay:%.2fs">%s</text>' % (x, delay, caption))

    for y in (chart_top, (chart_top + baseline) / 2, baseline):
        out.append('<line class="gridline" x1="%.0f" y1="%.1f" x2="%d" y2="%.1f"/>' % (left, y, width - 28, y))
    out += [
        '<text class="tiny" x="%d" y="%.0f" text-anchor="end">%d / sem</text>' % (left - 8, chart_top + 3, peak),
        '<g class="chart">',
        '<path class="area" d="%s"/>' % area,
        '<path class="halo" pathLength="1" d="%s"/>' % line,
        '<path id="trend" class="line" pathLength="1" d="%s"/>' % line,
        '<circle class="sparkglow" r="9"><animateMotion dur="%ds" repeatCount="indefinite"><mpath xlink:href="#trend"/></animateMotion></circle>' % (cycle // 2),
        '<circle class="spark" r="3.5"><animateMotion dur="%ds" repeatCount="indefinite"><mpath xlink:href="#trend"/></animateMotion></circle>' % (cycle // 2),
        "</g>",
    ]

    last_label_col, last_month = -4, None
    for col, week in enumerate(weeks):
        month = int(week["contributionDays"][0]["date"][5:7])
        if month != last_month and col - last_label_col >= 3 and col < len(weeks) - 1:
            if last_month is not None or week["contributionDays"][0]["date"][8:10] <= "07":
                out.append('<text class="small" x="%.1f" y="228">%s</text>' % (left + col * pitch, MONTHS[month - 1]))
                last_label_col = col
        last_month = month

    for row, name in ((1, "lun"), (3, "mié"), (5, "vie")):
        out.append('<text class="tiny" x="28" y="%.1f">%s</text>' % (grid_top + row * pitch + 9, name))

    for col, week in enumerate(weeks):
        for day in week["contributionDays"]:
            row = day["weekday"]
            out.append(
                '<rect class="day l%d" x="%.1f" y="%.1f" width="%d" height="%d" rx="2.5" style="animation-delay:%.2fs"/>'
                % (
                    LEVELS.get(day["contributionLevel"], 0),
                    left + col * pitch,
                    grid_top + row * pitch,
                    cell,
                    cell,
                    col * 0.04 + row * 0.02,
                )
            )

    footer_y = 368
    out.append('<text class="small" x="28" y="%d">Actualizado el %s</text>' % (footer_y, short_date(days[-1]["date"], True)))
    legend_x = width - 28 - 28 - 5 * 14
    out.append('<text class="small" x="%d" y="%d" text-anchor="end">Menos</text>' % (legend_x - 6, footer_y))
    for level in range(5):
        out.append('<rect class="l%d" x="%d" y="%d" width="11" height="11" rx="2.5"/>' % (level, legend_x + level * 14, footer_y - 10))
    out.append('<text class="small" x="%d" y="%d" text-anchor="end">Más</text>' % (width - 28, footer_y))
    out.append("</svg>")
    return "\n".join(out)


def main():
    if not TOKEN:
        raise SystemExit("Falta GITHUB_TOKEN (o GH_TOKEN).")
    name, weeks, total_year, history = fetch()
    ASSETS.mkdir(exist_ok=True)
    (ASSETS / "header.svg").write_text(build_header(name) + "\n", encoding="utf-8")
    (ASSETS / "activity.svg").write_text(build_activity(weeks, total_year, history) + "\n", encoding="utf-8")
    print("OK: %d contribuciones en el último año, %d en total" % (total_year, sum(history.values())))


if __name__ == "__main__":
    main()
