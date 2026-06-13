const { chromium } = require("playwright");
const fs = require("fs");
const path = require("path");

async function main() {
  const outputDir = path.resolve("data/charts");
  fs.mkdirSync(outputDir, { recursive: true });

  const browser = await chromium.launch({
    headless: true
  });

  const page = await browser.newPage({
    viewport: {
      width: 1280,
      height: 720
    },
    deviceScaleFactor: 1
  });

  const htmlPath = path.resolve("charts/tradingview_spx.html");
  const fileUrl = `file://${htmlPath}`;

  console.log(`Opening chart page: ${fileUrl}`);

  await page.goto(fileUrl, {
    waitUntil: "domcontentloaded",
    timeout: 60000
  });

  // TradingView widget loads inside an external iframe.
  // Give it time to render before taking the screenshot.
  await page.waitForTimeout(15000);

  const outputPath = path.join(outputDir, "tradingview_spx_5d.png");

  await page.locator("#chart-wrapper").screenshot({
    path: outputPath
  });

  await browser.close();

  console.log(`Saved TradingView chart screenshot: ${outputPath}`);
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});