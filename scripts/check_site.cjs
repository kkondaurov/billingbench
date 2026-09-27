const { chromium } = require("playwright");
const path = require("node:path");
const fs = require("node:fs");
const assert = require("node:assert/strict");

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
    for (const width of [1440, 768, 390]) {
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
          document.querySelectorAll("#comparison-chart circle").length >= 10,
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
      "PASS: desktop/tablet/mobile, local-file data, chart axes and tooltips, run expansion, dark mode, no overflow or JS errors.",
    );
  } finally {
    await browser.close();
  }
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
