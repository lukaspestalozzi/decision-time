import { test, expect } from '@playwright/test';
import {
  cleanAll,
  setupActiveBracketTournament,
  completeBracketTournament,
} from './helpers';

test.describe('Clone + Edit flow', () => {
  test.beforeEach(async ({ request }) => {
    await cleanAll(request);
  });

  test('duplicate → edit → save persists the changes', async ({ page, request }) => {
    // Set up a completed bracket tournament via API.
    const { tournament } = await setupActiveBracketTournament(
      request, 'Source Draft', ['Red', 'Blue'],
    );
    await completeBracketTournament(request, tournament.id, tournament.version);

    // Duplicate via the overview page.
    await page.goto(`/tournaments/${tournament.id}`);
    await expect(page.getByRole('heading', { name: 'Source Draft', level: 1 })).toBeVisible({ timeout: 10000 });
    await page.getByRole('button', { name: 'Duplicate' }).click();

    // Now on the new draft's overview. Confirm the name is suffixed.
    await expect(page.getByRole('heading', { name: /Source Draft \(copy\)/, level: 1 })).toBeVisible({ timeout: 15000 });
    await expect(page.getByText('draft')).toBeVisible();

    // Click Edit → stepper opens with H1 "Edit Tournament" and prefilled fields.
    await page.getByRole('link', { name: 'Edit' }).click();
    await expect(page.getByRole('heading', { name: 'Edit Tournament', level: 1 })).toBeVisible({ timeout: 10000 });

    const nameInput = page.getByPlaceholder('e.g. Best Programming Language');
    await expect(nameInput).toHaveValue('Source Draft (copy)', { timeout: 10000 });

    // Bracket mode tile is selected.
    await expect(page.locator('.mode-card.mode-selected', { hasText: 'Bracket' })).toBeVisible();

    // Rename the duplicate, then advance through the stepper saving each step.
    await nameInput.fill('Source Draft — April');
    await page.getByRole('button', { name: 'Save' }).click();

    // Step 2: options are pre-checked (Red and Blue). Click Next to save.
    await expect(page.getByText('Selected (2)')).toBeVisible({ timeout: 10000 });
    await page.getByRole('button', { name: 'Next' }).click();

    // Step 3: bracket config prefilled. Click Next to save.
    await expect(page.getByText('Bracket Configuration')).toBeVisible({ timeout: 10000 });
    await page.getByRole('button', { name: 'Next' }).click();

    // Step 4 review shows the new name.
    await expect(page.getByText('Tournament Summary')).toBeVisible({ timeout: 10000 });
    await expect(page.getByText('Source Draft — April')).toBeVisible();

    // Verify the edits landed via API.
    const listRes = await request.get('/api/v1/tournaments?status=draft');
    const drafts = await listRes.json();
    const renamed = drafts.find((t: { name: string }) => t.name === 'Source Draft — April');
    expect(renamed).toBeDefined();
    expect(renamed.mode).toBe('bracket');
    expect(renamed.selected_option_ids.length).toBe(2);
  });

  test('mode change via confirm dialog resets config to new defaults', async ({ page, request }) => {
    // Start from a bracket tournament (config has shuffle_seed/third_place_match).
    const { tournament } = await setupActiveBracketTournament(
      request, 'Mode Switch Source', ['X', 'Y'],
    );
    await completeBracketTournament(request, tournament.id, tournament.version);

    // Duplicate + navigate into edit.
    await page.goto(`/tournaments/${tournament.id}`);
    await page.getByRole('button', { name: 'Duplicate' }).click();
    await expect(page.getByRole('heading', { name: /Mode Switch Source \(copy\)/, level: 1 })).toBeVisible({ timeout: 15000 });
    await page.getByRole('link', { name: 'Edit' }).click();

    await expect(page.getByRole('heading', { name: 'Edit Tournament', level: 1 })).toBeVisible({ timeout: 10000 });

    // Click the Score mode tile → confirm dialog appears.
    await page.locator('.mode-card', { hasText: 'Score' }).click();
    const confirmDialog = page.getByRole('dialog');
    await expect(confirmDialog).toBeVisible({ timeout: 5000 });
    await expect(confirmDialog.getByText('Change tournament mode?')).toBeVisible();
    await confirmDialog.getByRole('button', { name: 'Change mode' }).click();
    await expect(confirmDialog).not.toBeVisible();

    // Score tile is now selected.
    await expect(page.locator('.mode-card.mode-selected', { hasText: 'Score' })).toBeVisible();

    // Save step 1 — backend switches mode and resets config to score defaults.
    await page.getByRole('button', { name: 'Save' }).click();

    // Verify via API that mode is score and config matches score defaults.
    await expect(page.getByText('Selected (2)')).toBeVisible({ timeout: 10000 });
    const listRes = await request.get('/api/v1/tournaments?status=draft');
    const drafts = await listRes.json();
    const switched = drafts.find((t: { name: string }) => t.name.startsWith('Mode Switch Source'));
    expect(switched).toBeDefined();
    expect(switched.mode).toBe('score');
    // Score defaults.
    expect(switched.config.min_score).toBe(1);
    expect(switched.config.max_score).toBe(5);
    // Bracket-only fields are gone.
    expect(switched.config.shuffle_seed).toBeUndefined();
    expect(switched.config.third_place_match).toBeUndefined();
  });
});
