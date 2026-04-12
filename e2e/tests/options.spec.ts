import { test, expect } from '@playwright/test';
import { cleanAll, createOption, createOptions } from './helpers';

test.describe('Options Management', () => {
  test.beforeEach(async ({ request }) => {
    await cleanAll(request);
  });

  test('navigate to options page', async ({ page }) => {
    await page.goto('/options');

    await expect(page.getByRole('heading', { name: 'Options', level: 1 })).toBeVisible();
    await expect(page.getByRole('button', { name: /Add Option/i })).toBeVisible();
    await expect(page.getByRole('button', { name: /Bulk Import/i })).toBeVisible();
  });

  test('create option via UI', async ({ page }) => {
    await page.goto('/options');
    await expect(page.getByRole('heading', { name: 'Options', level: 1 })).toBeVisible();

    // Click Add Option button
    await page.getByRole('button', { name: /Add Option/i }).click();

    // Wait for dialog to appear
    const dialog = page.locator('mat-dialog-container');
    await expect(dialog).toBeVisible();
    await expect(dialog.getByText('Create Option')).toBeVisible();

    // Fill in the name
    await dialog.locator('input[matInput]').first().fill('Test Option Alpha');

    // Fill in the description
    await dialog.locator('textarea[matInput]').fill('A test description');

    // Add a tag by typing in the chip input and pressing Enter
    const tagInput = dialog.getByPlaceholder('Add tag...');
    await tagInput.fill('test-tag');
    await tagInput.press('Enter');

    // Verify the tag chip appeared
    await expect(dialog.locator('mat-chip-row')).toContainText('test-tag');

    // Click Create button
    await dialog.getByRole('button', { name: 'Create' }).click();

    // Wait for dialog to close
    await expect(dialog).toBeHidden();

    // Verify the option card appears on the page
    await expect(page.locator('mat-card-title', { hasText: 'Test Option Alpha' })).toBeVisible();
  });

  test('edit option', async ({ page, request }) => {
    // Create option via API
    await createOption(request, 'Original Name');

    await page.goto('/options');

    // Wait for the option card to appear
    await expect(page.locator('mat-card-title', { hasText: 'Original Name' })).toBeVisible();

    // Click the edit button on the option card
    await page.getByRole('button', { name: 'Edit option' }).click();

    // Wait for dialog
    const dialog = page.locator('mat-dialog-container');
    await expect(dialog).toBeVisible();
    await expect(dialog.getByText('Edit Option')).toBeVisible();

    // Clear and change the name
    const nameInput = dialog.locator('input[matInput]').first();
    await nameInput.clear();
    await nameInput.fill('Updated Name');

    // Click Update button
    await dialog.getByRole('button', { name: 'Update' }).click();

    // Wait for dialog to close
    await expect(dialog).toBeHidden();

    // Verify the updated name appears
    await expect(page.locator('mat-card-title', { hasText: 'Updated Name' })).toBeVisible();
    // Verify old name is gone
    await expect(page.locator('mat-card-title', { hasText: 'Original Name' })).toBeHidden();
  });

  test('delete option', async ({ page, request }) => {
    // Create option via API
    await createOption(request, 'Doomed Option');

    await page.goto('/options');

    // Wait for option to appear
    await expect(page.locator('mat-card-title', { hasText: 'Doomed Option' })).toBeVisible();

    // Click the delete button
    await page.getByRole('button', { name: 'Delete option' }).click();

    // Confirm deletion in the dialog
    const dialog = page.locator('mat-dialog-container');
    await expect(dialog).toBeVisible();
    await expect(dialog).toContainText('Confirm Delete');
    await expect(dialog).toContainText('Doomed Option');

    await dialog.getByRole('button', { name: 'Delete' }).click();

    // Wait for dialog to close
    await expect(dialog).toBeHidden();

    // Verify the option is gone
    await expect(page.locator('mat-card-title', { hasText: 'Doomed Option' })).toBeHidden();
    // The empty state should appear since there are no more options
    await expect(page.getByText('No options found')).toBeVisible();
  });

  test('search options by name', async ({ page, request }) => {
    // Create 3 options via API
    await createOption(request, 'Apple Pie');
    await createOption(request, 'Banana Split');
    await createOption(request, 'Cherry Cobbler');

    await page.goto('/options');

    // Wait for all 3 to appear
    await expect(page.locator('mat-card-title', { hasText: 'Apple Pie' })).toBeVisible();
    await expect(page.locator('mat-card-title', { hasText: 'Banana Split' })).toBeVisible();
    await expect(page.locator('mat-card-title', { hasText: 'Cherry Cobbler' })).toBeVisible();

    // Type in the search input
    const searchInput = page.getByPlaceholder('Search by name or description');
    await searchInput.fill('Banana');

    // Wait for filtered results - only Banana Split should be visible
    await expect(page.locator('mat-card-title', { hasText: 'Banana Split' })).toBeVisible();
    await expect(page.locator('mat-card-title', { hasText: 'Apple Pie' })).toBeHidden();
    await expect(page.locator('mat-card-title', { hasText: 'Cherry Cobbler' })).toBeHidden();

    // Clear search and verify all are back
    await searchInput.clear();
    await expect(page.locator('mat-card-title', { hasText: 'Apple Pie' })).toBeVisible();
    await expect(page.locator('mat-card-title', { hasText: 'Banana Split' })).toBeVisible();
    await expect(page.locator('mat-card-title', { hasText: 'Cherry Cobbler' })).toBeVisible();
  });

  test('bulk import options', async ({ page }) => {
    await page.goto('/options');
    await expect(page.getByRole('heading', { name: 'Options', level: 1 })).toBeVisible();

    // Click Bulk Import button
    await page.getByRole('button', { name: /Bulk Import/i }).click();

    // Wait for dialog to appear
    const dialog = page.locator('mat-dialog-container');
    await expect(dialog).toBeVisible();
    await expect(dialog.getByText('Bulk Import Options')).toBeVisible();

    // Paste option names into the textarea (one per line)
    const textarea = dialog.locator('textarea[matInput]');
    await textarea.fill('Luna\nMira\nNova');

    // Verify the count text
    await expect(dialog.getByText('3 options will be imported')).toBeVisible();

    // Click Import button
    await dialog.getByRole('button', { name: /Import 3 Options/i }).click();

    // Wait for dialog to close
    await expect(dialog).toBeHidden();

    // Verify all 3 option cards appear
    await expect(page.locator('mat-card-title', { hasText: 'Luna' })).toBeVisible();
    await expect(page.locator('mat-card-title', { hasText: 'Mira' })).toBeVisible();
    await expect(page.locator('mat-card-title', { hasText: 'Nova' })).toBeVisible();
  });
});
