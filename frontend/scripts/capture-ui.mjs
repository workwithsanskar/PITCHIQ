// Capture real PITCHIQ routes at the supported viewport sizes and fail on
// browser errors, horizontal overflow, or missing page landmarks.
//
// Usage:
//   node scripts/capture-ui.mjs http://localhost:5173
//   node scripts/capture-ui.mjs http://localhost:5173 "/,/players,/compare"
//
// The default route list includes every route declared in App.tsx, with valid
// sample identifiers read from the supplied local dataset/database.
import { chromium } from 'playwright';
import fs from 'node:fs';
import path from 'node:path';
import process from 'node:process';

const DEFAULT_ROUTES = [
  '/',
  '/players',
  '/players/1',
  '/teams',
  '/compare',
  '/data-lab',
  '/database',
  '/database/player/cd17b4c2-75d2-56c5-8fe9-808aebb3b3f6',
  '/database/clubs',
  '/database/clubs/94913f7c-599d-5187-a431-57e5bf139377',
  '/database/competitions',
  '/database/competitions/5ffefbb2-9356-5e4a-aee8-3c7ae5c01fa4',
  '/database/seasons',
  '/database/seasons/2025-2026',
  '/database/compare',
  '/database/leaderboards',
  '/database/shooting',
  '/database/analytics/descriptive',
  '/database/analytics/correlation',
  '/database/analytics/distributions',
  '/database/data-lab',
  '/database/coverage',
];

const sizes = [
  [1440, 863, 'desktop'],
  [1280, 800, 'laptop'],
  [1024, 768, 'tablet-landscape'],
  [768, 1024, 'tablet'],
  [390, 844, 'mobile'],
];
const base = (process.argv[2] ?? 'http://localhost:5173').replace(/\/$/, '');
const routes = (process.argv[3] ?? DEFAULT_ROUTES.join(','))
  .split(',')
  .map((route) => route.trim())
  .filter(Boolean);
const outputDir = path.resolve('ui-validation');
fs.mkdirSync(outputDir, { recursive: true });

const chromeCandidates = [
  process.env.PITCHIQ_CHROME_PATH,
  '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
].filter(Boolean);
const executablePath = chromeCandidates.find((candidate) => fs.existsSync(candidate));
const browser = await chromium.launch({
  ...(executablePath ? { executablePath } : {}),
  args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'],
});
const problems = [];
const page = await browser.newPage({ viewport: { width: sizes[0][0], height: sizes[0][1] }, deviceScaleFactor: 1 });
let activeRoute = '';
let activeLabel = '';
page.on('console', (message) => {
  if (message.type() === 'error') problems.push(`${activeRoute} @${activeLabel}: console: ${message.text()}`);
});
page.on('pageerror', (error) => problems.push(`${activeRoute} @${activeLabel}: pageerror: ${error.message}`));
page.on('response', (response) => {
  if (response.status() >= 500) problems.push(`${activeRoute} @${activeLabel}: HTTP ${response.status()} ${response.url()}`);
});

for (const route of routes) {
  activeRoute = route;
  activeLabel = 'load';
  try {
    await page.goto(`${base}${route}`, { waitUntil: 'networkidle', timeout: 30000 });
    await page.evaluate(() => document.fonts.ready);
    if (route === '/') {
      let revealComplete = false;
      for (let attempt = 0; attempt < 80; attempt += 1) {
        const opacities = await page.locator('.hero-reveal').evaluateAll((elements) => elements.map((element) => Number(getComputedStyle(element).opacity)));
        if (opacities.length > 0 && opacities.every((opacity) => opacity >= 0.99)) { revealComplete = true; break; }
        await page.waitForTimeout(100);
      }
      if (!revealComplete) problems.push('overview: existing GSAP hero reveal did not reach its final visible state');
    } else await page.waitForTimeout(300);
    const slug = route.replace(/\W+/g, '_').replace(/^_+|_+$/g, '') || 'root';

    for (const [width, height, label] of sizes) {
      activeLabel = label;
      await page.setViewportSize({ width, height });
      await page.waitForTimeout(100);
      const info = await page.evaluate(() => ({
        overflow: document.documentElement.scrollWidth - window.innerWidth,
        h1: document.querySelectorAll('h1').length,
        mains: document.querySelectorAll('main').length,
        activeNavs: document.querySelectorAll('.pq-nav__item[aria-current="page"]').length,
        breadcrumb: document.querySelector('.pq-crumbs [aria-current="page"]')?.textContent?.trim() ?? '',
      }));
      if (info.overflow > 1) problems.push(`${route} @${label}: horizontal overflow ${info.overflow}px`);
      if (info.h1 !== 1) problems.push(`${route} @${label}: expected exactly one <h1>, found ${info.h1}`);
      if (info.mains !== 1) problems.push(`${route} @${label}: expected exactly one <main>, found ${info.mains}`);
      if (info.activeNavs !== 1) problems.push(`${route} @${label}: expected one active navigation item, found ${info.activeNavs}`);
      if (!info.breadcrumb) problems.push(`${route} @${label}: current breadcrumb is missing`);
      await page.screenshot({ path: path.join(outputDir, `${slug}-${label}.png`), fullPage: true });
    }
  } catch (error) {
    problems.push(`${route}: ${error instanceof Error ? error.message : String(error)}`);
  }
}
await page.close();

// Verify focus visibility on desktop and the mobile drawer's Escape/focus-return behavior.
const keyboardPage = await browser.newPage({ viewport: { width: 1440, height: 863 } });
try {
  await keyboardPage.goto(`${base}/`, { waitUntil: 'networkidle' });
  await keyboardPage.keyboard.press('Tab');
  const firstFocus = await keyboardPage.evaluate(() => {
    const active = document.activeElement;
    return {
      text: active?.textContent?.trim() ?? '',
      outline: active ? getComputedStyle(active).outlineStyle : 'none',
    };
  });
  if (firstFocus.outline === 'none') problems.push(`keyboard desktop: first tab target has no visible outline (${firstFocus.text})`);
  let reachedHeroAction = false;
  for (let step = 0; step < 20; step += 1) {
    await keyboardPage.keyboard.press('Tab');
    const isAction = await keyboardPage.evaluate(() => document.activeElement?.matches('.pq-hero__actions .pq-btn') ?? false);
    if (isAction) { reachedHeroAction = true; break; }
  }
  if (!reachedHeroAction) problems.push('keyboard desktop: Tab sequence did not reach a hero action after navigation');
} catch (error) {
  problems.push(`keyboard desktop: ${error instanceof Error ? error.message : String(error)}`);
} finally {
  await keyboardPage.close();
}

const mobilePage = await browser.newPage({ viewport: { width: 390, height: 844 } });
try {
  await mobilePage.goto(`${base}/`, { waitUntil: 'networkidle' });
  await mobilePage.keyboard.press('Tab');
  await mobilePage.keyboard.press('Tab');
  const menuFocused = await mobilePage.evaluate(() => document.activeElement === document.querySelector('.pq-menu-btn'));
  if (!menuFocused) problems.push('keyboard mobile: the navigation menu button is not reachable after the skip link');
  await mobilePage.keyboard.press('Enter');
  await mobilePage.waitForFunction(() => {
    const firstLink = document.querySelector('#pq-sidebar a');
    return document.querySelector('.pq-menu-btn')?.getAttribute('aria-expanded') === 'true'
      && document.activeElement === firstLink;
  });
  await mobilePage.keyboard.press('Escape');
  await mobilePage.waitForFunction(() => document.activeElement === document.querySelector('.pq-menu-btn'));
  const drawerState = await mobilePage.evaluate(() => ({
    expanded: document.querySelector('.pq-menu-btn')?.getAttribute('aria-expanded'),
    focusReturned: document.activeElement === document.querySelector('.pq-menu-btn'),
  }));
  if (drawerState.expanded !== 'false') problems.push('keyboard mobile: Escape did not close the navigation drawer');
  if (!drawerState.focusReturned) problems.push('keyboard mobile: focus did not return to the menu button');
} catch (error) {
  problems.push(`keyboard mobile: ${error instanceof Error ? error.message : String(error)}`);
} finally {
  await mobilePage.close();
}

const reducedMotionPage = await browser.newPage({ viewport: { width: 1440, height: 863 } });
try {
  await reducedMotionPage.emulateMedia({ reducedMotion: 'reduce' });
  await reducedMotionPage.goto(`${base}/`, { waitUntil: 'networkidle' });
  const animationName = await reducedMotionPage.locator('.pq-status .pq-dot').evaluate(element => getComputedStyle(element).animationName);
  if (animationName !== 'none') problems.push(`reduced motion: hero status animation is still ${animationName}`);
} catch (error) {
  problems.push(`reduced motion: ${error instanceof Error ? error.message : String(error)}`);
} finally {
  await reducedMotionPage.close();
}

await browser.close();
console.log(`Captured ${routes.length * sizes.length} route/viewport screenshots in ${outputDir}`);
console.log(problems.length ? `PROBLEMS:\n${problems.join('\n')}` : 'No overflow, heading, landmark, keyboard, or console problems.');
process.exitCode = problems.length ? 1 : 0;
