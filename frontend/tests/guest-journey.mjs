import assert from "node:assert/strict";
import { chromium } from "playwright-core";

const base = process.env.TEST_APP_URL || "http://127.0.0.1:3000";
const browser = await chromium.launch({ channel: process.env.TEST_BROWSER_CHANNEL || undefined });
try {
  for (const width of [360, 390, 1280]) {
    const page = await browser.newPage({ viewport: { width, height: 844 } });
    const errors = [];
    page.on("pageerror", error => errors.push(error.message));
    await page.goto(base + "/schemes");
    await page.getByText("75 records", { exact: true }).waitFor();
    await page.goto(base + "/profile");
    await page.getByLabel("State or Union Territory", { exact: true }).fill("Punjab");
    await page.getByRole("button", { name: "Continue" }).click();
    await page.getByLabel("Date of birth", { exact: true }).fill("1960-01-01");
    await page.getByRole("button", { name: "Continue" }).click();
    await page.getByLabel("Total annual household income (INR)").fill("50000");
    for (let step = 0; step < 5; step++) {
      await page.getByRole("button", { name: "Continue" }).click();
    }
    await page.getByRole("button", { name: /See my matches/ }).click();
    await page.getByText("75 schemes assessed", { exact: true }).waitFor();
    await page.reload();
    await page.getByText("75 schemes assessed", { exact: true }).waitFor();
    await page.goto(base + "/schemes");
    await page.getByRole("heading", {name: /Pradhan Mantri Ujjwala/i}).first().waitFor();
    await page.goto(base + "/schemes/HR-MSYBC");
    await page.getByRole("heading", { name: "Scheme document checklist" }).waitFor();
    await page.getByText("Route readiness", { exact: false }).first().waitFor();
    const source = await page.getByRole("link", { name: /Open official source/ }).getAttribute("href");
    assert.match(source, /^https:\/\//);
    await page.goto(base + "/profile");
    assert.equal(await page.getByLabel("State or Union Territory", { exact: true }).inputValue(), "Punjab");
    await page.getByRole("link", { name: "Go to chatbot" }).click();
    await page.getByRole("heading", { name: "Scheme assistant" }).waitFor();
    assert.deepEqual(errors, []);
    console.log(width + "px guest journey passed");
    await page.close();
  }
} finally {
  await browser.close();
}
