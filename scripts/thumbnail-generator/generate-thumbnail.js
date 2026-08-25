const { chromium } = require('playwright');
const { expect } = require('@playwright/test');
const sharp = require('sharp');
const fs = require('fs');
const path = require('path');

(async () => {
  const browser = await chromium.launch();
  const context = await browser.newContext({
    viewport: {
      width: 1280, // Set the desired window width here
      height: 720, // Set the desired window height here
    },
  });
  const page = await context.newPage();

  await context.addCookies([
    {
      name: 'atoken',
      value: 'TOKEN',
      domain: '.staging.terraso.net',
      path: '/',
    },
  ]);

  await page.goto('https://app.staging.terraso.net/tools/story-maps/f2xs943/ecuador-2'); // Replace with the URL of the website you want to capture
  await expect(
    page
      .getByRole('region', { name: 'Chapters' })
  ).toBeVisible();
  await page.waitForTimeout(3000);
  const screenshotBuffer = await page.screenshot();

  await browser.close();

  const outputPath = path.join('output', 'thumbnail.png');

  // sharp(screenshotBuffer)
  //   .resize(200, 150) // Set the thumbnail dimensions here
  //   .toFile(outputPath, (err, info) => {
  //     if (err) {
  //       console.error('Error generating thumbnail:', err);
  //     } else {
  //       console.log('Thumbnail generated successfully:', info);
  //     }
  //   });

    fs.writeFile(outputPath, screenshotBuffer, (err) => {
      if (err) {
        console.error('Error saving screenshot:', err);
      } else {
        console.log(`Screenshot saved successfully to ${outputPath}`);
      }
    });
})();
