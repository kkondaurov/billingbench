/* Replays observed UI navigation only. Economic acceptance stays in Python. */
const fs = require('node:fs');
const { chromium } = require('playwright');

async function main() {
  const job = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
  const plan = JSON.parse(fs.readFileSync(process.argv[3], 'utf8'));
  const browser = await chromium.launch({headless: true, args: ['--no-sandbox']});
  const page = await browser.newPage({viewport: {width: 1360, height: 900}});
  try {
  await page.route('**/api/**', route => route.continue({headers: {
    ...route.request().headers(), 'x-business-time': job.business_time
  }}));
  const actions = [];
  page.on('request', request => {
    if (request.url().includes('/api/') && request.method() !== 'GET') {
      actions.push({method: request.method(), url: request.url(), body: request.postData()});
    }
  });
  const base = process.env.OPERATOR_BASE_URL || job.base_url;
  await page.goto(base + '/_session');
  await page.locator('input[name="token"]').fill(job.token);
  await page.locator('button[type="submit"]').click();
  for (let index = 0; index < plan.length; index++) {
    const step = plan[index];
    if (step.action === 'goto') {
      await page.goto(new URL(step.path, base).href);
    } else if (step.action === 'screenshot') {
      await page.screenshot({path: step.path, fullPage: true});
    } else {
      let target;
      if (step.role) target = page.getByRole(step.role, {name: step.name, exact: step.exact !== false});
      else if (step.label) target = page.getByLabel(step.label, {exact: true});
      else if (step.testId) target = page.getByTestId(step.testId);
      else if (step.selector) target = page.locator(step.selector);
      else throw new Error(`Missing observed locator at step ${index}`);
      if (step.action === 'click') await target.click();
      else if (step.action === 'fill') await target.fill(String(step.value));
      else if (step.action === 'select') await target.selectOption(step.value);
      else if (step.action === 'check') await target.setChecked(step.value);
      else if (step.action === 'visible') await target.waitFor({state: 'visible'});
      else if (step.action === 'hidden') await target.waitFor({state: 'hidden'});
      else throw new Error(`Unsupported UI action ${step.action}`);
    }
  }
  await page.screenshot({path: '/tmp/operator-final.png', fullPage: true});
  fs.writeFileSync('/tmp/operator-browser.json', JSON.stringify({actions, url: page.url(), text: await page.locator('body').innerText()}, null, 2));
  } finally {
    await browser.close();
  }
}

main().catch(error => {console.error(error); process.exitCode = 1;});
