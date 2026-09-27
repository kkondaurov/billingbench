const { chromium } = require("playwright");
const path = require("node:path");
const fs = require("node:fs");
const http = require("node:http");
const assert = require("node:assert/strict");

async function checkCachedVisit(browser, root) {
  const html = fs.readFileSync(path.join(root, "site/index.html"), "utf8");
  let updated = false;
  const requests = [];
  const types = {
    "style.css": "text/css",
    "data.js": "text/javascript",
    "report.js": "text/javascript",
  };
  const server = http.createServer((req, res) => {
    const url = new URL(req.url, "http://localhost");
    requests.push(req.url);
    if (url.pathname === "/") {
      res.writeHead(200, {
        "Content-Type": "text/html",
        "Cache-Control": "no-store",
      });
      res.end(updated ? html : html.replace(/\?v=[a-f0-9]{12}/g, ""));
      return;
    }
    const file = url.pathname.slice(1);
    if (!Object.hasOwn(types, file)) {
      res.writeHead(404);
      res.end();
      return;
    }
    res.writeHead(200, {
      "Content-Type": types[file],
      "Cache-Control": "public, max-age=31536000, immutable",
    });
    res.end(
      file === "report.js" && !updated
        ? 'document.getElementById("comparison-chart").setAttribute("data-cached-chart", "old");'
        : fs.readFileSync(path.join(root, "site", file)),
    );
  });
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  const context = await browser.newContext();
  try {
    const page = await context.newPage();
    const url = `http://127.0.0.1:${server.address().port}/`;
    await page.goto(url);
    assert.equal(
      await page.locator("#comparison-chart").getAttribute("data-cached-chart"),
      "old",
    );
    updated = true;
    await page.goto(`${url}?visit=2`);
    await page.locator(".run-label").first().waitFor();
    assert.equal(await page.locator(".run-label").count(), 8);
    assert.equal(
      await page.locator("#comparison-chart").getAttribute("data-cached-chart"),
      null,
    );
    assert.equal(
      requests.filter((request) => request === "/report.js").length,
      1,
    );
    assert.equal(
      requests.filter((request) => request.startsWith("/report.js?v=")).length,
      1,
    );
    console.log(
      "PASS: returning visitor with cached old scripts receives all eight visible run labels.",
    );
  } finally {
    await context.close();
    server.closeAllConnections();
    await new Promise((resolve) => server.close(resolve));
  }
}

(async () => {
  const root = path.resolve(__dirname, "..");
  const out = path.join(root, ".runs/v1-publication/screenshots");
  fs.mkdirSync(out, { recursive: true });
  const browser = await chromium.launch({
    headless: true,
    ...(process.env.PLAYWRIGHT_CHANNEL
      ? { channel: process.env.PLAYWRIGHT_CHANNEL }
      : {}),
  });
  try {
    await checkCachedVisit(browser, root);
    for (const width of [1440, 768, 390, 320]) {
      const page = await browser.newPage({
        viewport: { width, height: 1050 },
        colorScheme: "light",
      });
      const errors = [];
      page.on("pageerror", (error) => errors.push(error.message));
      await page.goto(
        process.env.REPORT_URL || `file://${root}/site/index.html`,
      );
      await page.waitForFunction(
        () =>
          document.querySelectorAll("#comparison-chart .run-point").length ===
          8,
      );
      assert.equal(await page.locator("#summary-body tr").count(), 4);
      assert.equal(await page.locator("#code-body tr").count(), 8);
      assert.equal(await page.locator("#matrix-body tr").count(), 8);
      assert(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth + 1,
        ),
      );
      await page.screenshot({
        path: path.join(out, `${width}-light.png`),
        fullPage: true,
      });
      await page
        .locator("#plot")
        .screenshot({ path: path.join(out, `${width}-chart.png`) });
      for (const axis of ["time", "code", "output", "cost"]) {
        await page.selectOption("#x-axis", axis);
        await page.waitForTimeout(100);
        assert.equal(await page.locator("#comparison-chart title").count(), 1);
        const marks = await page.locator(".run-point").evaluateAll((nodes) =>
          nodes.map((node) => ({
            run: node.dataset.run,
            model: node.dataset.model,
            effort: node.dataset.effort,
            shape: node.tagName,
            color: node.getAttribute("fill"),
            label: node.getAttribute("aria-label"),
          })),
        );
        assert.equal(marks.length, 8);
        assert.equal(new Set(marks.map((mark) => mark.run)).size, 8);
        assert.equal(
          await page.locator("#comparison-chart [tabindex]").count(),
          8,
        );
        assert.equal(await page.locator("#comparison-chart circle").count(), 4);
        assert.equal(await page.locator("#comparison-chart rect").count(), 4);
        assert.equal(
          await page.locator("#comparison-chart line").count(),
          axis === "time" ? 11 : 10,
        );
        assert.equal(
          await page.locator(".x-axis-tick").first().getAttribute("data-value"),
          "0",
        );
        assert.equal(
          await page.locator(".y-axis-tick").first().getAttribute("data-value"),
          "0",
        );
        assert.equal(await page.locator(".run-label").count(), 8);
        const labelIssues = await page.evaluate(() => {
          const labels = [...document.querySelectorAll(".run-label")];
          const markers = [...document.querySelectorAll(".run-point")];
          const overlaps = (a, b) =>
            a.left < b.right &&
            a.right > b.left &&
            a.top < b.bottom &&
            a.bottom > b.top;
          const issues = [];
          const xTicks = [...document.querySelectorAll(".x-axis-tick")];
          const yTicks = [...document.querySelectorAll(".y-axis-tick")];
          const x0 = +xTicks[0].getAttribute("x");
          const xLast = +xTicks.at(-1).getAttribute("x");
          const y0 = +yTicks[0].getAttribute("y") - 4;
          const y100 = +yTicks.at(-1).getAttribute("y") - 4;
          const axis = document.getElementById("x-axis").value;
          for (const point of markers) {
            const run = window.BILLING_RESULTS.runs.find(
              (r) => r.id === point.dataset.run,
            );
            const value = {
              cost: run.usage.api_equivalent_usd,
              time: run.seconds / 3600,
              code: run.code.production,
              output: run.usage.output_tokens,
            }[axis];
            const bounds = point.getBBox();
            const expectedX =
              x0 + (value / +xTicks.at(-1).dataset.value) * (xLast - x0);
            const expectedY = y0 - (run.passed / run.total) * (y0 - y100);
            if (
              Math.abs(bounds.x + bounds.width / 2 - expectedX) > 0.01 ||
              Math.abs(bounds.y + bounds.height / 2 - expectedY) > 0.01
            )
              issues.push(`Incorrect zero-based position for ${run.id}`);
          }
          labels.forEach((label, i) => {
            const box = label.getBoundingClientRect();
            if (
              !markers.some((point) => point.dataset.run === label.dataset.run)
            )
              issues.push("Unknown run label");
            for (const other of labels.slice(i + 1)) {
              if (overlaps(box, other.getBoundingClientRect()))
                issues.push(
                  `${label.textContent} overlaps ${other.textContent}`,
                );
            }
            for (const point of markers) {
              if (overlaps(box, point.getBoundingClientRect()))
                issues.push(`${label.textContent} covers ${point.dataset.run}`);
            }
          });
          return issues;
        });
        assert.deepEqual(labelIssues, [], `${width}px ${axis}`);
        await page
          .locator(".chart-figure")
          .screenshot({ path: path.join(out, `${width}-${axis}-labeled.png`) });
        for (const mark of marks) {
          assert.equal(
            mark.shape,
            mark.model.includes("astra") ? "circle" : "rect",
          );
          assert.match(mark.label, /#\d: \d+\/123 cases/);
        }
        const colors = ["low", "xhigh"].map(
          (effort) =>
            new Set(
              marks
                .filter((mark) => mark.effort === effort)
                .map((mark) => mark.color),
            ),
        );
        colors.forEach((color) => assert.equal(color.size, 1));
        assert.notEqual([...colors[0]][0], [...colors[1]][0]);
        const outside = await page
          .locator("#comparison-chart text")
          .evaluateAll((nodes) => {
            const svg = nodes[0].ownerSVGElement.getBoundingClientRect();
            return nodes
              .filter((n) => {
                const r = n.getBoundingClientRect();
                return r.left < svg.left - 1 || r.right > svg.right + 1;
              })
              .map((n) => n.textContent);
          });
        assert.deepEqual(outside, []);
      }
      await page.locator(".run-detail summary").first().click();
      assert.equal(await page.locator(".run-detail[open] tbody tr").count(), 3);
      const point = page.locator("#comparison-chart [tabindex]").first();
      await point.focus();
      assert(await page.locator("#tooltip").isVisible());
      await point.press("Escape");
      assert(await page.locator("#tooltip").isHidden());
      await page.emulateMedia({ colorScheme: "dark" });
      await page.screenshot({
        path: path.join(out, `${width}-dark.png`),
        fullPage: true,
      });
      assert.deepEqual(errors, []);
      await page.close();
    }
    console.log(
      "PASS: desktop/tablet/mobile, eight labeled runs, no overlapping labels or markers, model shapes and effort colors, no aggregates, chart axes and tooltips, run expansion, dark mode, no overflow or JS errors.",
    );
  } finally {
    await browser.close();
  }
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
