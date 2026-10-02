"use strict";
const data = window.BILLING_RESULTS;
const runs = data.runs;
const $ = (id) => document.getElementById(id);
const number = (n) => Math.round(n).toLocaleString("en-US");
const money = (n) => `$${n.toFixed(2)}`;
const time = (seconds) =>
  `${Math.floor(Math.round(seconds / 60) / 60)}h ${String(Math.round(seconds / 60) % 60).padStart(2, "0")}m`;
const mean = (values) => values.reduce((a, b) => a + b, 0) / values.length;
const median = (values) => {
  const a = [...values].sort((x, y) => x - y);
  return a[Math.floor(a.length / 2)];
};
const models = {
  "gpt-6-astra": { name: "GPT-6 Astra", short: "Astra", color: "astra" },
  "gpt-6.1-sol": { name: "GPT-6.1 Sol", short: "Sol 6.1", color: "sol61" },
  "gpt-6-sol": { name: "GPT-6 Sol", short: "Sol 6", color: "sol" },
  "gpt-6-luna": { name: "GPT-6 Luna", short: "Luna", color: "luna" },
  "claude-opus-5-5": { name: "Claude Opus 5.5", short: "Opus 5.5", color: "opus" },
};
const label = (run) => `${models[run.model].short} ${run.effort} #${run.sample}`;
const escapeHTML = (value) =>
  String(value).replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
const groups = ["astra-low", "sol61-xhigh", "opus55-xhigh", "sol6-xhigh", "luna6-xhigh"]
  .filter((id) => runs.some((r) => r.id.startsWith(id + "-"))).map(
  (id) => {
    const sample = runs.filter((r) => r.id.startsWith(id + "-"));
    return {
      id,
      runs: sample,
      model: models[sample[0].model].name,
      effort: sample[0].effort,
      score: mean(sample.map((r) => r.passed)),
      history: mean(sample.map((r) => r.retained_passed)),
      seconds: mean(sample.map((r) => r.seconds)),
      cost: mean(sample.map((r) => r.usage.api_equivalent_usd)),
    };
  },
);
const observedRange = (values) =>
  values.length > 1
    ? `<span class="range">${Math.min(...values)}–${Math.max(...values)}</span>`
    : '<span class="range">single run</span>';
const groupName = (g) =>
  `${g.model} <span class="secondary">${g.effort} effort</span>`;
$("summary-body").innerHTML = groups
  .map(
    (g) =>
      `<tr><td><strong>${groupName(g)}</strong><span class="secondary">${g.runs[0].harness}</span></td><td>${g.runs.length}</td><td><strong>${g.score.toFixed(g.runs.length > 1 ? 1 : 0)}</strong>${observedRange(g.runs.map((r) => r.passed))}</td><td>${g.history.toFixed(g.runs.length > 1 ? 1 : 0)}${observedRange(g.runs.map((r) => r.retained_passed))}</td><td>${time(g.seconds)}</td><td>${money(g.cost)}</td><td>${number(median(g.runs.map((r) => r.code.production)))}</td><td>${number(median(g.runs.map((r) => r.code.test)))}</td></tr>`,
  )
  .join("");
$("run-details").innerHTML = groups
  .map(
    (g) =>
      `<details class="run-detail"><summary>${g.model} · ${g.effort}: ${g.runs.length === 1 ? "individual run" : "all three runs"}</summary><div class="table-scroll"><table><thead><tr><th>Run</th><th>Date</th><th>API cases</th><th>Histories</th><th>Time</th><th>API cost</th><th>Prod LOC</th><th>Test LOC</th></tr></thead><tbody>${g.runs.map((r) => `<tr><td>${label(r)}</td><td>${r.cohort}</td><td>${r.passed}/123</td><td>${r.retained_passed}/20</td><td>${time(r.seconds)}</td><td>${money(r.usage.api_equivalent_usd)}</td><td>${number(r.code.production)}</td><td>${number(r.code.test)}</td></tr>`).join("")}</tbody></table></div></details>`,
  )
  .join("");
const areas = {
  billing_settlement: "Billing and settlement",
  changed_coverage: "Amendments and coverage",
  shared_ownership: "Shared pricing and funding",
  retained_agreements: "Agreements and retained rights",
  revenue_accounting: "Revenue and accounting",
  policy_evolution: "Policy and metering evolution",
  combined_regression: "Combined financial histories",
  durability_delivery: "Restart and concurrency",
};
$("matrix-head").innerHTML =
  `<tr><th>Capability area</th>${groups.map((g) => `<th>${g.model}<small>${g.effort} · n=${g.runs.length}</small></th>`).join("")}</tr>`;
$("matrix-body").innerHTML = Object.entries(areas)
  .map(
    ([key, name]) =>
      `<tr><td>${name}</td>${groups
        .map((g) => {
          const pass = g.runs.reduce(
            (a, r) => a + (r.families[key]?.passed || 0),
            0,
          );
          const total = g.runs.reduce(
            (a, r) =>
              a +
              Object.values(r.families[key] || {}).reduce((x, y) => x + y, 0),
            0,
          );
          return `<td><span class="cell-result" style="--strength:${Math.round((18 * pass) / total)}%">${pass}/${total} <span class="range">${Math.round((100 * pass) / total)}%</span></span></td>`;
        })
        .join("")}</tr>`,
  )
  .join("");
$("code-body").innerHTML = runs
  .map(
    (r) =>
      `<tr><td>${label(r)}</td><td>${number(r.code.production)}</td><td>${number(r.code.test)}</td><td>${r.code.production_files}</td><td>${r.code.files.filter((f) => f.category === "test").length}</td><td><code>${escapeHTML(r.code.largest.path)}</code><span class="secondary">${number(r.code.largest.lines)} lines</span></td><td><a href="https://github.com/kkondaurov/billingbench/releases/download/v${data.version}/${r.source_archive.file}">Source</a></td></tr>`,
  )
  .join("");
$("growth-body").innerHTML = runs
  .map(
    (r) =>
      `<tr><td>${label(r)}</td>${r.releases.map((m) => `<td>${number(m.code.production)} <span class="secondary">${Math.round(m.seconds / 60)} min${m.reused ? " · reused" : ""}</span></td>`).join("")}</tr>`,
  )
  .join("");
$("usage-body").innerHTML = runs
  .map(
    (r) =>
      `<tr><td>${label(r)}</td><td>${(r.usage.input_tokens / 1e6).toFixed(2)}M</td><td>${((100 * r.usage.cached_input_tokens) / r.usage.input_tokens).toFixed(1)}%</td><td>${number(r.usage.cache_write_5m_tokens + r.usage.cache_write_1h_tokens)}</td><td>${number(r.usage.output_tokens)}</td><td>${number(r.usage.reasoning_output_tokens)}</td><td>${r.usage.requests === null ? "Not recorded" : number(r.usage.requests)}</td><td>${money(r.usage.api_equivalent_usd)}</td></tr>`,
  )
  .join("");

$("timing-body").innerHTML = runs.map((r) => `<tr><td>${label(r)}</td><td>${time(r.reused_seconds)}</td><td>${money(r.reused_usage.api_equivalent_usd)}</td><td>${time(r.new_seconds)}</td><td>${money(r.new_usage.api_equivalent_usd)}</td><td>${time(r.seconds)}</td><td>${money(r.usage.api_equivalent_usd)}</td></tr>`).join("");
$("release-body").innerHTML = runs.map((r) => `<tr><td>${label(r)}</td>${r.releases.map((m) => `<td>${m.passed}/${m.total}</td>`).join("")}<td>${r.uncontested_passed}/121</td></tr>`).join("");

function drawChart() {
  const svg = $("comparison-chart"),
    host = $("plot"),
    tooltip = $("tooltip");
  tooltip.hidden = true;
  const width = Math.round(host.getBoundingClientRect().width),
    mobile = width < 700;
  const height = mobile ? 560 : 430;
  svg.style.height = `${height}px`;
  const margin = {
    left: mobile ? 43 : 58,
    right: mobile ? 20 : 28,
    top: 24,
    bottom: 55,
  };
  const axis = $("x-axis").value;
  const setting = {
    cost: {
      value: (r) => r.usage.api_equivalent_usd,
      min: 0,
      format: (v) => `$${v}`,
      title: "API-equivalent cost per run (USD)",
    },
    time: {
      value: (r) => r.seconds / 3600,
      min: 0,
      format: (v) => `${v}h`,
      title: "Implementation time per run (hours)",
    },
    code: {
      value: (r) => r.code.production,
      min: 0,
      format: (v) => `${v / 1000}k`,
      title: "Production lines in the final application",
    },
    output: {
      value: (r) => r.usage.output_tokens,
      min: 0,
      format: (v) => `${v / 1000}k`,
      title: "Output tokens per run (including reasoning)",
    },
  }[axis];
  const maximum = Math.max(...runs.map(setting.value)) * 1.08;
  const magnitude = 10 ** Math.floor(Math.log10(maximum / 4));
  const step = [1, 2, 2.5, 5, 10].map((n) => n * magnitude).find((n) => n >= maximum / 4);
  setting.max = Math.ceil(maximum / step) * step;
  setting.ticks = Array.from({ length: Math.round(setting.max / step) + 1 }, (_, i) => i * step);
  const style = getComputedStyle(document.documentElement),
    css = (key) => style.getPropertyValue(key).trim();
  const x = (value) =>
    margin.left +
    ((value - setting.min) / (setting.max - setting.min)) *
      (width - margin.left - margin.right);
  const y = (score) =>
    height -
    margin.bottom -
    (score / 123) * (height - margin.top - margin.bottom);
  svg.replaceChildren();
  svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
  const add = (tag, attrs = {}, text) => {
    const el = document.createElementNS("http://www.w3.org/2000/svg", tag);
    Object.entries(attrs).forEach(([k, v]) => el.setAttribute(k, v));
    if (text !== undefined) el.textContent = text;
    svg.appendChild(el);
    return el;
  };
  add(
    "title",
    { id: "chart-title" },
    "Final API correctness versus " + setting.title.toLowerCase(),
  );
  add(
    "desc",
    { id: "chart-description" },
    `${runs.length} individually labeled runs. Both axes start at zero. Each point is one run, not an average.`,
  );
  setting.ticks.forEach((t) => {
    add("line", {
      class: "grid-line",
      x1: x(t),
      x2: x(t),
      y1: margin.top,
      y2: height - margin.bottom,
      stroke: css("--line"),
    });
    add(
      "text",
      {
        class: "x-axis-tick",
        "data-value": t,
        x: x(t),
        y: height - margin.bottom + 23,
        "text-anchor": "middle",
        fill: css("--muted"),
        "font-size": 11,
      },
      setting.format(t),
    );
  });
  [0, 25, 50, 75, 100].forEach((t) => {
    add("line", {
      class: "grid-line",
      x1: margin.left,
      x2: width - margin.right,
      y1: y(t * 1.23),
      y2: y(t * 1.23),
      stroke: css("--line"),
    });
    add(
      "text",
      {
        class: "y-axis-tick",
        "data-value": t,
        x: margin.left - 9,
        y: y(t * 1.23) + 4,
        "text-anchor": "end",
        fill: css("--muted"),
        "font-size": 11,
      },
      `${t}%`,
    );
  });
  add(
    "text",
    { x: margin.left, y: 13, fill: css("--muted"), "font-size": 11 },
    "Final API cases passed",
  );
  add(
    "text",
    {
      x: margin.left + (width - margin.left - margin.right) / 2,
      y: height - 9,
      "text-anchor": "middle",
      fill: css("--muted"),
      "font-size": 11,
    },
    setting.title,
  );
  const points = [];
  runs.forEach((run) => {
    const cx = x(setting.value(run)),
      cy = y(run.passed),
      color = css(`--${models[run.model].color}`);
    const show = (event, html) => {
      tooltip.innerHTML = html;
      tooltip.hidden = false;
      const box = host.getBoundingClientRect();
      const ex = event.clientX ?? box.left + cx,
        ey = event.clientY ?? box.top + cy;
      tooltip.style.left = `${Math.max(0, Math.min(ex - box.left + 14, width - tooltip.offsetWidth))}px`;
      tooltip.style.top = `${Math.max(0, ey - box.top - tooltip.offsetHeight - 10)}px`;
    };
    const bind = (node, html, px, py) => {
      node.addEventListener("pointerenter", (e) => show(e, html));
      node.addEventListener("pointerleave", () => (tooltip.hidden = true));
      node.addEventListener("focus", () => {
        const b = host.getBoundingClientRect();
        show({ clientX: b.left + px, clientY: b.top + py }, html);
      });
      node.addEventListener("blur", () => (tooltip.hidden = true));
      node.addEventListener("click", (e) => show(e, html));
      node.addEventListener("keydown", (e) => {
        if (e.key === "Escape") tooltip.hidden = true;
      });
    };
    const point = add("circle", {
      cx, cy, r: 6,
      class: "run-point",
      "data-run": run.id,
      "data-model": run.model,
      "data-effort": run.effort,
      fill: color,
      stroke: css("--bg"),
      "stroke-width": 1.5,
      tabindex: 0,
      "aria-label": `${label(run)}: ${run.passed}/123 cases, ${money(run.usage.api_equivalent_usd)}, ${time(run.seconds)}`,
    });
    bind(
      point,
      `<strong>${label(run)}</strong><br>${run.passed}/123 API · ${run.retained_passed}/20 histories<br>${money(run.usage.api_equivalent_usd)} · ${time(run.seconds)}<br>${number(run.code.production)} production lines · ${number(run.usage.output_tokens)} output tokens`,
      cx,
      cy,
    );
    points.push({ run, cx, cy });
  });

  // Place labels around the real coordinates, avoiding labels and every marker.
  const boxes = [];
  const connectors = [];
  const overlaps = (a, b, gap = 4) =>
    a.x < b.x + b.width + gap &&
    a.x + a.width + gap > b.x &&
    a.y < b.y + b.height + gap &&
    a.y + a.height + gap > b.y;
  const crossesBox = (line, box, gap = 3) => {
    let enter = 0,
      leave = 1;
    for (const [start, end, min, max] of [
      [line.x1, line.x2, box.x - gap, box.x + box.width + gap],
      [line.y1, line.y2, box.y - gap, box.y + box.height + gap],
    ]) {
      const delta = end - start;
      if (Math.abs(delta) < 0.001) {
        if (start < min || start > max) return false;
      } else {
        const a = (min - start) / delta,
          b = (max - start) / delta;
        enter = Math.max(enter, Math.min(a, b));
        leave = Math.min(leave, Math.max(a, b));
        if (enter > leave) return false;
      }
    }
    return true;
  };
  const crossesLine = (a, b) => {
    const cross = (x, y, u, v) => x * v - y * u;
    const dx = a.x2 - a.x1,
      dy = a.y2 - a.y1;
    const ex = b.x2 - b.x1,
      ey = b.y2 - b.y1;
    const denominator = cross(dx, dy, ex, ey);
    if (Math.abs(denominator) < 0.001) return false;
    const t = cross(b.x1 - a.x1, b.y1 - a.y1, ex, ey) / denominator;
    const u = cross(b.x1 - a.x1, b.y1 - a.y1, dx, dy) / denominator;
    return t > 0 && t < 1 && u > 0 && u < 1;
  };
  points
    .sort((a, b) => a.cy - b.cy)
    .forEach(({ run, cx, cy }) => {
      const name = add(
        "text",
        {
          class: "run-label",
          "data-run": run.id,
          "font-size": mobile ? 11 : 12,
          "font-weight": 550,
          fill: css("--ink"),
          stroke: css("--bg"),
          "stroke-width": 4,
          "paint-order": "stroke fill",
          "pointer-events": "none",
        },
        label(run),
      );
      let measured = name.getBBox();
      if (mobile) {
        name.textContent = "";
        const title = document.createElementNS(svg.namespaceURI, "tspan");
        title.textContent = models[run.model].short;
        title.setAttribute("x", "0");
        const sample = document.createElementNS(svg.namespaceURI, "tspan");
        sample.textContent = `${run.effort} #${run.sample}`;
        sample.setAttribute("x", "0");
        sample.setAttribute("dy", "1.2em");
        sample.setAttribute("fill", css("--muted"));
        name.append(title, sample);
        measured = name.getBBox();
      }
      const candidates = [];
      for (const distance of [10, 12, 24, 40, 60, 85, 110, 150]) {
        for (const [dx, dy] of [
          [1, 0],
          [-1, 0],
          [0, -1],
          [0, 1],
          [1, -1],
          [-1, -1],
          [1, 1],
          [-1, 1],
        ]) {
          const box = {
            x: Math.max(
              margin.left + 5,
              Math.min(
                width - measured.width - 4,
                cx +
                  dx * distance -
                  (dx < 0 ? measured.width : dx === 0 ? measured.width / 2 : 0),
              ),
            ),
            y: Math.max(
              margin.top + 5,
              Math.min(
                height - margin.bottom - measured.height - 5,
                cy +
                  dy * distance -
                  (dy < 0
                    ? measured.height
                    : dy === 0
                      ? measured.height / 2
                      : 0),
              ),
            ),
            width: measured.width,
            height: measured.height,
          };
          let conflicts =
            boxes.filter((b) => overlaps(box, b)).length +
            points.filter((p) =>
              overlaps(
                box,
                { x: p.cx - 7, y: p.cy - 7, width: 14, height: 14 },
                2,
              ),
            ).length;
          conflicts *= 100;
          const nearX = Math.max(box.x, Math.min(cx, box.x + box.width));
          const nearY = Math.max(box.y, Math.min(cy, box.y + box.height));
          const labelDistance = Math.hypot(cx - nearX, cy - nearY);
          const line = {
            x1: cx + ((nearX - cx) * 8) / Math.max(1, labelDistance),
            y1: cy + ((nearY - cy) * 8) / Math.max(1, labelDistance),
            x2: nearX,
            y2: nearY,
          };
          conflicts += connectors.filter((c) => crossesBox(c, box)).length;
          if (labelDistance > 0) {
            conflicts += boxes.filter((b) => crossesBox(line, b)).length;
            conflicts += points.filter(
              (p) =>
                p.run.id !== run.id &&
                crossesBox(
                  line,
                  { x: p.cx - 6, y: p.cy - 6, width: 12, height: 12 },
                  1,
                ),
            ).length;
            conflicts += connectors.filter((c) => crossesLine(line, c)).length;
          }
          candidates.push({
            box,
            nearX,
            nearY,
            line,
            distance: labelDistance,
            score: conflicts * 10000 + labelDistance,
          });
        }
      }
      const best = candidates.sort((a, b) => a.score - b.score)[0];
      boxes.push(best.box);
      name.setAttribute("x", best.box.x - measured.x);
      name.setAttribute("y", best.box.y - measured.y);
      name
        .querySelectorAll("tspan")
        .forEach((line) => line.setAttribute("x", best.box.x - measured.x));
      if (best.distance > 12 || Math.abs(cy - best.nearY) > 2) {
        connectors.push(best.line);
        const connector = add("path", {
          class: "label-connector",
          "data-run": run.id,
          d: `M ${best.line.x1} ${best.line.y1} L ${best.line.x2} ${best.line.y2}`,
          stroke: css("--muted"),
          "stroke-width": 0.8,
          fill: "none",
          "pointer-events": "none",
        });
        svg.insertBefore(connector, svg.querySelector(".run-point"));
      }
    });
}
$("x-axis").addEventListener("change", drawChart);
new ResizeObserver(drawChart).observe($("plot"));
matchMedia("(prefers-color-scheme: dark)").addEventListener(
  "change",
  drawChart,
);
drawChart();
