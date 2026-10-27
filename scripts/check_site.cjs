const { chromium } = require("playwright");
const path = require("node:path");
const fs = require("node:fs");
const http = require("node:http");
const assert = require("node:assert/strict");
const { createHash } = require("node:crypto");

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
    assert.equal(await page.locator(".run-label").count(), 23);
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
      "PASS: returning visitor with cached old scripts receives all 23 visible run labels.",
    );
  } finally {
    await context.close();
    server.closeAllConnections();
    await new Promise((resolve) => server.close(resolve));
  }
}

(async () => {
  const root = path.resolve(__dirname, "..");
  const out = path.join(root, ".runs/terra-publication-20261027/screenshots");
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
          23,
      );
      assert.equal(await page.locator("#summary-body tr").count(), 8);
      assert.equal(await page.locator("#code-body tr").count(), 23);
      assert.equal(await page.locator("#timing-body tr").count(), 23);
      assert.equal(await page.locator("#release-body tr").count(), 23);
      assert.equal(await page.locator("#terra-nudge-body tr").count(), 15);
      assert.equal(await page.locator("#terra-intermediate-body tr").count(), 3);
      const terraGroups = page.locator("#summary-body tr").filter({hasText:"GPT-6.1 Terra"});
      assert.equal(await terraGroups.count(),2);
      assert.match(await terraGroups.nth(0).innerText(), /completion-assisted.*107\.7/s);
      assert.match(await terraGroups.nth(1).innerText(), /strict one-turn.*1\.0/s);
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
      await page.screenshot({path: path.join(out, `${width}-top.png`)});
      await page.evaluate(() => window.scrollTo(0, document.getElementById("results").offsetTop - 20));
      await page.screenshot({path: path.join(out, `${width}-results.png`)});
      await page
        .locator("#plot")
        .screenshot({ path: path.join(out, `${width}-chart.png`) });
      for (const basis of ["dated", "common"]) {
      await page.selectOption("#cost-basis", basis);
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
        assert.equal(marks.length, 23);
        assert.equal(new Set(marks.map((mark) => mark.run)).size, 23);
        assert.equal(
          await page.locator("#comparison-chart [tabindex]").count(),
          23,
        );
        assert.equal(await page.locator("#comparison-chart circle").count(), 23);
        assert.equal(await page.locator("#comparison-chart rect").count(), 0);
        assert.equal(
          await page.locator("#comparison-chart line").count(),
          (await page.locator(".x-axis-tick").count()) + 5,
        );
        assert.equal(
          await page.locator(".x-axis-tick").first().getAttribute("data-value"),
          "0",
        );
        assert.equal(
          await page.locator(".y-axis-tick").first().getAttribute("data-value"),
          "0",
        );
        assert.equal(await page.locator(".run-label").count(), 23);
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
              cost: document.getElementById("cost-basis").value === "common"
                ? (window.BILLING_RESULTS.comparable_costs[run.id]?.api_equivalent_usd ?? run.usage.api_equivalent_usd)
                : run.usage.api_equivalent_usd,
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
        assert.deepEqual(labelIssues, [], `${width}px ${axis} ${basis}`);
        await page
          .locator(".chart-figure")
          .screenshot({ path: path.join(out, `${width}-${axis}-${basis}-labeled.png`) });
        for (const mark of marks) {
          assert.equal(
            mark.shape,
            "circle",
          );
          assert.match(mark.label, /#\d: \d+\/123 cases/);
        }
        const colors = [...new Set(marks.map((mark) => mark.model))].map(
          (model) =>
            new Set(
              marks
                .filter((mark) => mark.model === model)
                .map((mark) => mark.color),
            ),
        );
        colors.forEach((color) => assert.equal(color.size, 1));
        assert.equal(new Set(colors.map((color) => [...color][0])).size, 7);
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
      const deepseekMean = page.locator("#summary-body tr").filter({ hasText: "DeepSeek V4.1 Flash" });
      assert.match(await deepseekMean.locator("td").nth(5).innerText(), basis === "common" ? /^\$17\.52/ : /^\$6\.81/);
      }
      await page.locator(".run-detail summary").first().click();
      assert.equal(await page.locator(".run-detail[open] tbody tr").count(), 3);
      const opus = page.locator(".run-detail").filter({ hasText: "Claude Opus 5.5" });
      assert.match(await opus.locator("summary").innerText(), /all 2 runs/);
      await opus.locator("summary").click();
      assert.equal(await opus.locator("tbody tr").count(), 2);
      assert.match(await opus.locator("tbody tr").nth(1).innerText(), /105\/123.*20\/20.*3h 32m.*\$82\.21/s);
      const opusSummary = page.locator("#summary-body tr").filter({ hasText: "Claude Opus 5.5" });
      assert.match(await opusSummary.locator("td").nth(6).innerText(), /^21,610/);
      assert.match(await opusSummary.locator("td").nth(7).innerText(), /^7,756/);
      const deepseek = page.locator(".run-detail").filter({ hasText: "DeepSeek V4.1 Flash" });
      await deepseek.locator("summary").click();
      assert.equal(await deepseek.locator("tbody tr").count(), 3);
      assert.match(await deepseek.locator("tbody tr").nth(0).innerText(), /50\/123.*3\/20.*3h 45m.*\$19\.01.*20,478.*4,745/s);
      assert.match(await deepseek.locator("tbody tr").nth(1).innerText(), /12\/123.*2\/20.*4h 50m.*\$15\.73.*21,033.*4,743/s);
      assert.match(await deepseek.locator("tbody tr").nth(2).innerText(), /58\/123.*4 case errors.*18\/20.*3h 06m.*\$17\.82.*25,013.*5,553/s);
      await page.getByText("Scores at every release", { exact: true }).click();
      const deepseekReleases = page.locator("#release-body tr").filter({ hasText: "DeepSeek" });
      assert.match(await deepseekReleases.nth(0).innerText(), /21\/34.*31\/51.*39\/71.*43\/87.*50\/123/s);
      assert.match(await deepseekReleases.nth(2).innerText(), /21\/34.*33\/51.*2 case errors.*47\/71.*3 case errors.*47\/87.*4 case errors.*58\/123.*4 case errors/s);
      const point = page.locator("#comparison-chart [tabindex]").first();
      await point.focus();
      assert(await page.locator("#tooltip").isVisible());
      await point.press("Escape");
      assert(await page.locator("#tooltip").isHidden());
      await page.emulateMedia({ colorScheme: "dark" });
      await page.locator(".chart-figure").screenshot({path: path.join(out, `${width}-dark-chart.png`)});
      await page.screenshot({
        path: path.join(out, `${width}-dark.png`),
        fullPage: true,
      });
      assert.deepEqual(errors, []);
      await page.close();
    }
    console.log(
      "PASS: desktop/tablet/mobile, 23 labeled runs, paired Terra protocols, both cost bases, no overlapping labels or markers, seven model colors, zero-based chart axes and tooltips, run expansion, dark mode, no overflow or JS errors.",
    );
    fs.writeFileSync(path.join(out, "../site-check.json"), JSON.stringify({
      passed: true,
      url: process.env.REPORT_URL || `file://${root}/site/index.html`,
      widths: [1440, 768, 390, 320],
      axes: ["time", "code", "output", "cost"],
      sha256: Object.fromEntries(["index.html", "data.js", "report.js", "style.css"].map(
        (name) => [name, createHash("sha256").update(fs.readFileSync(path.join(root, "site", name))).digest("hex")],
      )),
    }, null, 2) + "\n");
  } finally {
    await browser.close();
  }
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
