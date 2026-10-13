import { expect, test } from '@playwright/test';
test('demo dashboard, status filter, history, and theme', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByText('You’re exploring synthetic sample data. No AWS resources are connected.')).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Platform overview' })).toBeVisible();
  await page.getByRole('navigation').getByText('Processing jobs').click();
  await page.getByLabel('Filter jobs by status').selectOption('FAILED');
  await expect(page.getByRole('button', { name: /^Inventory snapshot/ })).toBeVisible();
  await expect(page.getByRole('button', { name: /^Quarterly revenue/ })).not.toBeVisible();
  await page.getByRole('button', { name: /^Inventory snapshot/ }).click();
  await expect(page.getByText('MISSING_COLUMNS')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Cancel job' })).toBeDisabled();
  await page.getByRole('button', { name: 'Use dark theme' }).click();
  await expect(page.locator('html')).toHaveClass('dark');
});
test('mobile navigation and synthetic job creation', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/');
  await page.getByRole('navigation').getByText('New job').click();
  await page.getByLabel('Job name').fill('Mobile report');
  await page.getByLabel('CSV file').setInputFiles({ name: 'data.csv', mimeType: 'text/csv', buffer: Buffer.from('name,amount\nAda,10\n') });
  await page.getByRole('button', { name: 'Create job & upload' }).click();
  await expect(page.getByRole('heading', { name: 'Mobile report' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Cancel job' })).toBeEnabled();
  await page.getByRole('button', { name: 'Cancel job' }).click();
  await expect(page.getByText('Job cancelled', { exact: true })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});
