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
const label = (run) =>
  `${run.model.includes("astra") ? "Astra" : "Sol"} ${run.effort} #${run.sample}`;
const escapeHTML = (value) =>
  String(value).replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
const groups = ["astra-low", "astra-xhigh", "sol6-xhigh", "sol6-low"].map(
  (id) => {
    const sample = runs.filter((r) => r.id.startsWith(id + "-"));
    return {
      id,
      runs: sample,
      model: sample[0].model.includes("astra") ? "GPT-6 Astra" : "GPT-6 Sol",
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
      `<tr><td><strong>${groupName(g)}</strong></td><td>${g.runs.length}</td><td><strong>${g.score.toFixed(g.runs.length > 1 ? 1 : 0)}</strong>${observedRange(g.runs.map((r) => r.passed))}</td><td>${g.history.toFixed(g.runs.length > 1 ? 1 : 0)}${observedRange(g.runs.map((r) => r.retained_passed))}</td><td>${time(g.seconds)}</td><td>${money(g.cost)}</td><td>${number(median(g.runs.map((r) => r.code.production)))}</td><td>${number(median(g.runs.map((r) => r.code.test)))}</td></tr>`,
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
      `<tr><td>${label(r)}</td><td>${number(r.code.production)}</td><td>${number(r.code.test)}</td><td>${r.code.production_files}</td><td><code>${escapeHTML(r.code.largest.path)}</code><span class="secondary">${number(r.code.largest.lines)} lines</span></td><td><a href="https://github.com/kkondaurov/billingbench/releases/download/v1.0.0/${r.source_archive.file}">Source</a></td></tr>`,
  )
  .join("");
$("growth-body").innerHTML = runs
  .map(
    (r) =>
      `<tr><td>${label(r)}</td>${r.releases.map((m) => `<td>${number(m.code.production)} <span class="secondary">${Math.round(m.seconds / 60)} min</span></td>`).join("")}</tr>`,
  )
  .join("");
$("usage-body").innerHTML = runs
  .map(
    (r) =>
      `<tr><td>${label(r)}</td><td>${(r.usage.input_tokens / 1e6).toFixed(2)}M</td><td>${((100 * r.usage.cached_input_tokens) / r.usage.input_tokens).toFixed(1)}%</td><td>${number(r.usage.output_tokens)}</td><td>${number(r.usage.reasoning_output_tokens)}</td><td>${number(r.usage.requests)}</td><td>${money(r.usage.api_equivalent_usd)}</td></tr>`,
  )
  .join("");

function drawChart() {
  const svg = $("comparison-chart"),
    host = $("plot"),
    tooltip = $("tooltip");
  tooltip.hidden = true;
  const width = Math.round(host.getBoundingClientRect().width),
    mobile = width < 700;
  const height = mobile ? 330 : 400;
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
      max: 80,
      ticks: [0, 20, 40, 60, 80],
      format: (v) => `$${v}`,
      title: "API-equivalent cost per run (USD)",
    },
    time: {
      value: (r) => r.seconds / 3600,
      max: 5.5,
      ticks: [0, 1, 2, 3, 4, 5],
      format: (v) => `${v}h`,
      title: "Implementation time per run (hours)",
    },
    code: {
      value: (r) => r.code.production,
      max: 16000,
      ticks: [0, 4000, 8000, 12000, 16000],
      format: (v) => `${v / 1000}k`,
      title: "Production lines in the final application",
    },
    output: {
      value: (r) => r.usage.output_tokens,
      max: 800000,
      ticks: [0, 200000, 400000, 600000, 800000],
      format: (v) => `${v / 1000}k`,
      title: "Output tokens per run (including reasoning)",
    },
  }[axis];
  const style = getComputedStyle(document.documentElement),
    css = (key) => style.getPropertyValue(key).trim();
  const x = (value) =>
    margin.left + (value / setting.max) * (width - margin.left - margin.right);
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
    "Eight individual runs in four model and effort groups. Astra low averages 108.7 of 123 passed cases; Astra xhigh 114; Sol xhigh 87; Sol low 76. Exact values appear in the table below.",
  );
  setting.ticks.forEach((t) => {
    add("line", {
      x1: x(t),
      x2: x(t),
      y1: margin.top,
      y2: height - margin.bottom,
      stroke: css("--line"),
    });
    add(
      "text",
      {
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
      x1: margin.left,
      x2: width - margin.right,
      y1: y(t * 1.23),
      y2: y(t * 1.23),
      stroke: css("--line"),
    });
    add(
      "text",
      {
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
  groups.forEach((g, index) => {
    const color = css(g.id.startsWith("astra") ? "--astra" : "--sol"),
      xs = g.runs.map(setting.value),
      ys = g.runs.map((r) => r.passed),
      cx = x(mean(xs)),
      cy = y(g.score);
    if (g.runs.length > 1) {
      add("line", {
        x1: x(Math.min(...xs)),
        x2: x(Math.max(...xs)),
        y1: cy,
        y2: cy,
        stroke: color,
        "stroke-width": 1.5,
      });
      add("line", {
        x1: cx,
        x2: cx,
        y1: y(Math.min(...ys)),
        y2: y(Math.max(...ys)),
        stroke: color,
        "stroke-width": 1.5,
      });
    }
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
    if (g.runs.length > 1)
      g.runs.forEach((r) => {
        const px = x(setting.value(r)),
          py = y(r.passed);
        const dot = add("circle", {
          cx: px,
          cy: py,
          r: 4,
          fill: css("--bg"),
          stroke: color,
          "stroke-width": 1.8,
          tabindex: 0,
          "aria-label": `${label(r)}: ${r.passed}/123 cases, ${money(r.usage.api_equivalent_usd)}, ${time(r.seconds)}`,
        });
        bind(
          dot,
          `<strong>${label(r)}</strong><br>${r.passed}/123 API · ${r.retained_passed}/20 histories<br>${money(r.usage.api_equivalent_usd)} · ${time(r.seconds)}`,
          px,
          py,
        );
      });
    const point = add("circle", {
      cx,
      cy,
      r: 8,
      fill: color,
      stroke: css("--bg"),
      "stroke-width": 2,
      tabindex: 0,
      "aria-label": `${g.model} ${g.effort}: mean ${g.score.toFixed(1)}/123, ${money(g.cost)}, ${time(g.seconds)}`,
    });
    if (g.runs.length === 1)
      add("circle", {
        cx,
        cy,
        r: 12,
        fill: "none",
        stroke: color,
        "stroke-width": 1,
        "stroke-dasharray": "3 3",
        "pointer-events": "none",
      });
    bind(
      point,
      `<strong>${g.model} · ${g.effort}</strong><br>${g.score.toFixed(1)}/123 API · ${g.history.toFixed(1)}/20 histories<br>${money(g.cost)} · ${time(g.seconds)}<br>${g.runs.length} ${g.runs.length === 1 ? "run" : "runs"}`,
      cx,
      cy,
    );
    // Fixed placements differ by axis to keep neighboring labels clear.
    const offsets =
      axis === "cost"
        ? [
            [-8, 29],
            [-10, -22],
            [-12, -16],
            [12, 28],
          ]
        : axis === "time"
          ? [
              [-8, -22],
              [-14, -25],
              [12, -15],
              [-10, 30],
            ]
          : [
              [-12, -16],
              [12, -24],
              [12, -16],
              [-12, 28],
            ];
    const [dx, dy] = offsets[index];
    const raw = cx + dx,
      anchor =
        raw > width - 130
          ? "end"
          : raw < 130
            ? "start"
            : dx < 0
              ? "end"
              : "start";
    const tx = Math.max(
      margin.left + 4,
      Math.min(width - margin.right - 4, raw),
    );
    add(
      "text",
      {
        x: tx,
        y: Math.max(18, cy + dy),
        fill: css("--ink"),
        "font-size": mobile ? 10 : 12,
        "font-weight": 550,
        "text-anchor": anchor,
        stroke: css("--bg"),
        "stroke-width": 4,
        "paint-order": "stroke fill",
      },
      `${g.model.replace("GPT-6 ", "")} ${g.effort}`,
    );
  });
}
$("x-axis").addEventListener("change", drawChart);
new ResizeObserver(drawChart).observe($("plot"));
matchMedia("(prefers-color-scheme: dark)").addEventListener(
  "change",
  drawChart,
);
drawChart();
