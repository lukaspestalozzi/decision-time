import { test, expect } from '@playwright/test';
import {
  cleanAll,
  createOptions,
  setupActiveBracketTournament,
  completeBracketTournament,
} from './helpers';

test.describe('Bracket Tournament', () => {
  test.beforeEach(async ({ request }) => {
    await cleanAll(request);
  });

  test('create bracket tournament via stepper', async ({ page, request }) => {
    // Pre-create options via API so the stepper has options to select
    await createOptions(request, ['Option A', 'Option B', 'Option C']);

    await page.goto('/tournaments/new');

    // --- Step 1: Name & Mode ---
    await expect(page.getByText('Name & Mode')).toBeVisible();

    // Fill tournament name
    const nameInput = page.getByPlaceholder('e.g. Best Programming Language');
    await nameInput.fill('My Bracket Test');

    // Select Bracket mode by clicking the Bracket card
    await page.locator('.mode-card', { hasText: 'Bracket' }).click();

    // Click Next (creates tournament draft, advances to step 2)
    await page.getByRole('button', { name: 'Next' }).click();

    // --- Step 2: Select Options ---
    // Wait for options to load from API
    await expect(page.locator('.option-item')).toHaveCount(3, { timeout: 10000 });
    await page.locator('.option-item', { hasText: 'Option A' }).click();
    await page.locator('.option-item', { hasText: 'Option B' }).click();
    await expect(page.getByText('Selected (2)')).toBeVisible();

    // Click Next (saves options, advances to step 3)
    await page.getByRole('button', { name: 'Next' }).click();

    // --- Step 3: Configure ---
    await expect(page.getByText('Bracket Configuration')).toBeVisible({ timeout: 10000 });

    // Default config is fine, click Next (saves config, advances to step 4)
    await page.getByRole('button', { name: 'Next' }).click();

    // --- Step 4: Review & Activate ---
    await expect(page.getByText('Tournament Summary')).toBeVisible({ timeout: 10000 });
    await expect(page.getByText('My Bracket Test')).toBeVisible();
    await expect(page.getByLabel('Review & Activate').getByText('Bracket', { exact: true })).toBeVisible();

    // Click Activate Tournament
    await page.getByRole('button', { name: 'Activate Tournament' }).click();

    // Should navigate to the tournament overview page
    await expect(page.getByRole('heading', { name: 'My Bracket Test', level: 1 })).toBeVisible({ timeout: 10000 });
    await expect(page.getByText('active')).toBeVisible();
  });

  test('vote through bracket tournament', async ({ page, request }) => {
    // Setup a bracket tournament with 2 options via API
    const { tournament } = await setupActiveBracketTournament(
      request, 'Bracket Vote Test', ['Alpha', 'Beta'],
    );

    // Navigate to the vote page
    await page.goto(`/tournaments/${tournament.id}/vote`);

    // Should see bracket matchup UI
    await expect(page.getByText('VS')).toBeVisible({ timeout: 10000 });

    // The two entries should be visible (names from option_snapshot)
    // Click on one of the entry cards to select it
    const entryCards = page.locator('.entry-card');
    await expect(entryCards).toHaveCount(2);

    // Click the first entry card
    await entryCards.first().click();

    // Verify it gets the selected class
    await expect(entryCards.first()).toHaveClass(/selected/);

    // Click Confirm Choice
    await page.getByRole('button', { name: 'Confirm Choice' }).click();

    // With only 2 options, the tournament should complete after 1 vote.
    // The vote page should show the completed result inline.
    // Wait for the result to appear (the TournamentResultComponent is shown inline)
    await expect(page.getByText('Winner')).toBeVisible({ timeout: 10000 });
    await expect(page.getByText('Full Ranking')).toBeVisible();
  });

  test('view bracket result', async ({ page, request }) => {
    // Setup and complete a bracket tournament via API
    const { tournament } = await setupActiveBracketTournament(
      request, 'Bracket Result Test', ['Red', 'Blue'],
    );
    await completeBracketTournament(request, tournament.id, tournament.version);

    // Navigate to the result page
    await page.goto(`/tournaments/${tournament.id}/result`);

    // Verify the result page content
    await expect(page.getByRole('heading', { name: 'Bracket Result Test', level: 1 })).toBeVisible({ timeout: 10000 });
    await expect(page.getByText('Winner')).toBeVisible();

    // The winner name should be displayed (Red, since completeBracketTournament always picks entry_a)
    await expect(page.locator('.winner-name')).toBeVisible();

    // Full ranking table should be visible
    await expect(page.getByText('Full Ranking')).toBeVisible();
    await expect(page.locator('.ranking-table')).toBeVisible();

    // Bracket view should be present
    await expect(page.getByRole('heading', { name: 'Bracket', exact: true })).toBeVisible();
  });

  test('clone tournament', async ({ page, request }) => {
    // Setup and complete a bracket tournament via API
    const { tournament } = await setupActiveBracketTournament(
      request, 'Clone Source', ['Cat', 'Dog'],
    );
    await completeBracketTournament(request, tournament.id, tournament.version);

    // Navigate to the overview page
    await page.goto(`/tournaments/${tournament.id}`);

    await expect(page.getByRole('heading', { name: 'Clone Source', level: 1 })).toBeVisible({ timeout: 10000 });
    await expect(page.getByText('completed')).toBeVisible();

    // Click the Clone button
    await page.getByRole('button', { name: 'Clone' }).click();

    // Should navigate to the new tournament overview
    // The new tournament should be in draft status
    await expect(page.getByText('draft')).toBeVisible({ timeout: 15000 });
    // It should have the same name
    await expect(page.getByRole('heading', { name: 'Clone Source', level: 1 })).toBeVisible();
    // The URL should have changed to a new ID
    await expect(page).not.toHaveURL(`/tournaments/${tournament.id}`);
  });

  test('cancel active tournament', async ({ page, request }) => {
    // Setup an active bracket tournament via API
    const { tournament } = await setupActiveBracketTournament(
      request, 'Cancel Me', ['Fox', 'Bear'],
    );

    // Navigate to the overview page
    await page.goto(`/tournaments/${tournament.id}`);

    await expect(page.getByRole('heading', { name: 'Cancel Me', level: 1 })).toBeVisible({ timeout: 10000 });
    await expect(page.getByText('active')).toBeVisible();

    // Click Cancel button
    await page.getByRole('button', { name: 'Cancel' }).click();

    // Verify the status changed to cancelled (exact match to avoid matching snackbar text)
    await expect(page.getByText('cancelled', { exact: true })).toBeVisible({ timeout: 10000 });
  });
});
