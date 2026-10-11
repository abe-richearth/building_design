"""Regenerate every output from model/design.py.

    pip install -r requirements.txt
    python build.py

Outputs land in output/.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT / "model"))

import design  # noqa: E402
import walls  # noqa: E402
import export  # noqa: E402

OUT = ROOT / "output"


def brief_html(s, rooms):
    rows = "".join(
        f"<tr><td>{'Ground' if lvl == 'ground' else 'Upper'}</td><td>{name}</td>"
        f"<td class='n'>{design.room_area(r, sub):,.0f} sf</td></tr>"
        for lvl, name, r, sub in rooms)
    wall_rows = "".join(
        f"<tr><td>{layer}</td><td class='n'>{'' if t is None else f'{t:g}&quot;'}</td>"
        f"<td class='n'>{'' if r is None else f'R-{r:g}'}</td></tr>"
        for layer, t, r in walls.ASSEMBLY_TABLE)
    r_total = sum(r for _, _, r in walls.ASSEMBLY_TABLE if r)
    return f"""
<div>
  <h2>The idea</h2>
  <p>A two-storey carriage-house type. The print studio sits on the ground floor, where the
  concrete slab can carry an etching press (often 1,000 to 2,500 lb) and where an 8-foot sliding
  door lets you move the press, paper and flat files in and out. The ADU sits above with its own
  enclosed stair and street-side entry, so the dwelling never shares air with solvents or acid.</p>
  <p>The studio's long north wall gets tall windows for even, shadow-free light over the inking
  table. Wet work (sink, fume hood, etching) is grouped in one room on the north side, directly
  under the ADU kitchen, so plumbing and exhaust stack.</p>
</div>
<div>
  <h2>Key numbers</h2>
  <table>
    <tr><td>Footprint</td><td class="n">{s['footprint']}</td></tr>
    <tr><td>Gross area per floor</td><td class="n">{s['gross_per_floor']:,.0f} sf</td></tr>
    <tr><td>Studio (gross, excl. stair)</td><td class="n">{s['studio_gross']:,.0f} sf</td></tr>
    <tr><td>ADU (gross, excl. stair)</td><td class="n">{s['adu_gross']:,.0f} sf</td></tr>
    <tr><td>Shared stair / entry, each floor</td><td class="n">{s['shared_stair_gross']:,.0f} sf</td></tr>
    <tr><td>Studio clear height</td><td class="n">{s['studio_clear_height']:g} ft</td></tr>
    <tr><td>ADU wall height</td><td class="n">{s['adu_plate_height']:g} ft</td></tr>
    <tr><td>Roof pitch / ridge height</td><td class="n">{s['roof_pitch']} / {s['ridge_height']:.1f} ft</td></tr>
  </table>
</div>
<div>
  <h2>Rooms (net)</h2>
  <table><tr><th>Floor</th><th>Room</th><th style="text-align:right">Area</th></tr>{rows}</table>
</div>
<div>
  <h2>Assumptions in this draft</h2>
  <ul>
    <li>Intaglio and relief printing with one etching press (30&quot; × 60&quot; bed), so the
    layout reserves a 12' × 7' clear zone for bed travel and walking around it.</li>
    <li>Ferric chloride or similar etching in a ducted fume hood. No solvent-heavy screen washout booth yet.</li>
    <li>One-bedroom ADU, about 750 sf, with a vaulted ceiling under the roof.</li>
    <li>Flat site, with the street to the south. Wood frame on a slab-on-grade.</li>
    <li>Footprint held at 36' &times; 24' to the outside of the sheathing, so the 9&quot; walls
    take their thickness from the rooms.</li>
    <li>Dimensions are in feet; the model origin is the building's southwest corner.</li>
  </ul>
</div>
<div class="wide">
  <h2>Exterior wall: 8&quot; double-stud, dense-pack cellulose</h2>
  <p>Two rows of 2x4 studs at 24&quot; on centre with a 1&quot; gap between them make an 8&quot;
  cavity filled with dense-pack cellulose. The gap means no stud runs from inside to outside,
  so the only thermal bridges are the plates, headers and rim. The outer row carries the floor and roof;
  the inner row is non-bearing and holds wiring and plumbing without breaching the air barrier.
  Overall thickness is 9&quot; plus siding.</p>
  <table><tr><th>Layer, outside to inside</th><th style="text-align:right">Thickness</th>
  <th style="text-align:right">Approx. R</th></tr>{wall_rows}
  <tr><td><b>Centre-of-wall, nominal</b></td><td class="n">9&quot;</td><td class="n"><b>about R-{r_total:.0f}</b></td></tr></table>
  <p>Whole-wall R after framing losses is closer to R-26. In cold or mixed climates, use a
  vapour-open sheathing or a ventilated rainscreen so the sheathing can dry; I can tune this
  once we know the climate zone.</p>
</div>
<div class="wide q">
  <h2>Questions for you</h2>
  <ol>
    <li><b>Printmaking processes.</b> Which do you do (etching, relief, lithography, screenprint,
    letterpress)? Each changes the press count, the wet room, and ventilation.</li>
    <li><b>Press.</b> Do you own a press already? Its make, bed size and weight set the clear zone
    and the slab design.</li>
    <li><b>Site.</b> Lot size, which way the street and north are, setbacks, and the local ADU rules
    on size and height. Many cities cap a two-storey ADU around 25 ft; this draft's ridge is
    {s['ridge_height']:.0f} ft.</li>
    <li><b>Who lives upstairs?</b> You, a tenant, or family? That decides whether the stair
    should also open into the studio (drawn now) or stay fully separate.</li>
    <li><b>Arrangement.</b> Stacked like this, or side by side on one level (studio and ADU
    sharing a wall), which is easier for accessibility and heavy equipment?</li>
    <li><b>Teaching or open studio.</b> Will other people use the studio? That brings
    accessibility, a larger WC and occupancy rules into play.</li>
  </ol>
</div>
"""


def main():
    OUT.mkdir(exist_ok=True)
    els = design.build()
    summary = design.summary()

    export.write_3dm(els, design.LAYERS, OUT / "building.3dm")
    export.write_meshes(els, design.LAYERS, OUT)

    plans = {}
    for lvl in design.LEVELS:
        args = (els, design.ROOMS, design.LEVELS, design.LABEL_AT, lvl, design.LENGTH, design.DEPTH)
        kw = {"vertical": design.LABEL_VERTICAL}
        (OUT / f"plan-{lvl}.svg").write_text(export.plan_svg(*args, **kw))
        plans[lvl] = export.plan_svg(*args, inline=True, **kw)

    data = export.viewer_data(els, design.LAYERS, design.ROOMS, design.LEVELS,
                              design.LABEL_AT, summary)
    import json
    page = ((ROOT / "viewer" / "template.html").read_text()
            .replace("__PLAN_GROUND__", f"<style>{export.PLAN_CSS}</style>" + plans["ground"])
            .replace("__PLAN_UPPER__", plans["upper"])
            .replace("__BRIEF__", brief_html(summary, design.ROOMS))
            .replace("__DATA__", json.dumps(data, separators=(",", ":"))))
    # artifact body (the host adds <html>/<head>) and a standalone copy for local use
    (OUT / "viewer-artifact.html").write_text(page)
    (OUT / "viewer.html").write_text(
        '<!doctype html>\n<html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<style>body{margin:0}[hidden]{display:none!important}</style></head><body>\n'
        + page + "\n</body></html>\n")

    print(f"{len(els)} elements")
    for p in sorted(OUT.iterdir()):
        print(f"  {p.name:22s} {p.stat().st_size / 1024:8.1f} KB")


if __name__ == "__main__":
    main()
