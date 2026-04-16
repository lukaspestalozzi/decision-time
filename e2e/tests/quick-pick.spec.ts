import { test, expect } from '@playwright/test';
import { cleanAll, createOptions } from './helpers';

test.describe('Quick Pick', () => {
  test.beforeEach(async ({ request }) => {
    await cleanAll(request);
  });

  test('shows empty state when fewer than 2 options exist', async ({ page }) => {
    await page.goto('/random');

    await expect(page.getByRole('heading', { name: 'Quick Pick', level: 1 })).toBeVisible();
    await expect(page.getByText('Not enough options')).toBeVisible({ timeout: 10000 });
    await expect(page.getByRole('link', { name: 'Go to Options' })).toBeVisible();
  });

  test('select options and get a random result', async ({ page, request }) => {
    await createOptions(request, ['Pizza', 'Pasta', 'Sushi']);

    await page.goto('/random');

    // Wait for options to load
    await expect(page.locator('.option-item')).toHaveCount(3, { timeout: 10000 });

    // "Decide for me!" should be disabled with no selection
    const decideBtn = page.getByRole('button', { name: 'Decide for me!' });
    await expect(decideBtn).toBeDisabled();

    // Select 2 options
    await page.locator('.option-item', { hasText: 'Pizza' }).click();
    await page.locator('.option-item', { hasText: 'Sushi' }).click();
    await expect(page.getByText('Selected (2)')).toBeVisible();

    // Button should now be enabled
    await expect(decideBtn).toBeEnabled();

    // Click decide — animation plays, then result appears
    await decideBtn.click();

    // Wait for the result phase (animation takes ~3-4s)
    await expect(page.getByText('The answer is...')).toBeVisible({ timeout: 10000 });

    // The winner should be one of the selected options
    const winnerName = await page.locator('.winner-name').textContent();
    expect(['Pizza', 'Sushi']).toContain(winnerName?.trim());

    // "Spin again" and "New round" buttons should be visible
    await expect(page.getByRole('button', { name: 'Spin again' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'New round' })).toBeVisible();
  });

  test('spin again keeps the same options', async ({ page, request }) => {
    await createOptions(request, ['Red', 'Blue']);

    await page.goto('/random');
    await expect(page.locator('.option-item')).toHaveCount(2, { timeout: 10000 });

    // Select both
    await page.locator('.option-item', { hasText: 'Red' }).click();
    await page.locator('.option-item', { hasText: 'Blue' }).click();

    // Decide
    await page.getByRole('button', { name: 'Decide for me!' }).click();
    await expect(page.getByText('The answer is...')).toBeVisible({ timeout: 10000 });

    // Spin again — should go straight to spinning, then result
    await page.getByRole('button', { name: 'Spin again' }).click();
    await expect(page.getByText('The answer is...')).toBeVisible({ timeout: 10000 });

    const winnerName = await page.locator('.winner-name').textContent();
    expect(['Red', 'Blue']).toContain(winnerName?.trim());
  });

  test('new round resets to setup', async ({ page, request }) => {
    await createOptions(request, ['Cat', 'Dog', 'Bird']);

    await page.goto('/random');
    await expect(page.locator('.option-item')).toHaveCount(3, { timeout: 10000 });

    // Select all and decide
    await page.locator('.option-item', { hasText: 'Cat' }).click();
    await page.locator('.option-item', { hasText: 'Dog' }).click();
    await page.getByRole('button', { name: 'Decide for me!' }).click();
    await expect(page.getByText('The answer is...')).toBeVisible({ timeout: 10000 });

    // New round — back to setup with no selection
    await page.getByRole('button', { name: 'New round' }).click();
    await expect(page.getByText('Choose your options')).toBeVisible();
    await expect(page.getByText('Selected (0)')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Decide for me!' })).toBeDisabled();
  });

  test('select all button selects all filtered options', async ({ page, request }) => {
    await createOptions(request, ['Alpha', 'Bravo', 'Charlie']);

    await page.goto('/random');
    await expect(page.locator('.option-item')).toHaveCount(3, { timeout: 10000 });

    // Click select all
    await page.getByRole('button', { name: /Select all/ }).click();
    await expect(page.getByText('Selected (3)')).toBeVisible();
  });
});
