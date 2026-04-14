import { test, expect } from '@playwright/test';
import {
  cleanAll,
  setupActiveMultivoteTournament,
  submitVote,
  getVoteContext,
} from './helpers';

test.describe('Multivote Tournament', () => {
  test.beforeEach(async ({ request }) => {
    await cleanAll(request);
  });

  test('multivote voting flow', async ({ page, request }) => {
    // Setup a multivote tournament with 3 options and 1 voter
    // total_votes defaults to null (auto = options * 2 = 6)
    const { tournament } = await setupActiveMultivoteTournament(
      request, 'Multivote Flow', ['Ruby', 'Emerald', 'Sapphire'],
      { voter_count: 1 },
    );

    // Navigate to the vote page
    await page.goto(`/tournaments/${tournament.id}/vote`);

    // Wait for the multivote ballot UI
    await expect(page.getByText('Distribute your votes')).toBeVisible({ timeout: 10000 });
    await expect(page.getByText('0 of 1 ballots submitted')).toBeVisible();

    // Should see the budget display (total_votes = 3*2 = 6)
    await expect(page.getByText(/0 \/ 6 votes used/)).toBeVisible();
    await expect(page.getByText('6 remaining')).toBeVisible();

    // Should see all 3 entry rows
    const entryRows = page.locator('.entry-row');
    await expect(entryRows).toHaveCount(3);

    // Distribute votes by clicking increment buttons
    // Give 3 to the first, 2 to the second, 1 to the third
    const addButtons = page.locator('.entry-row button', { hasText: 'add' });

    // Click add button for first entry 3 times
    for (let i = 0; i < 3; i++) {
      await addButtons.nth(0).click();
    }

    // Click add button for second entry 2 times
    for (let i = 0; i < 2; i++) {
      await addButtons.nth(1).click();
    }

    // Click add button for third entry 1 time
    await addButtons.nth(2).click();

    // Verify budget display shows 6/6 votes used
    await expect(page.getByText(/6 \/ 6 votes used/)).toBeVisible();

    // Submit button should be enabled now
    const submitButton = page.getByRole('button', { name: 'Submit Votes' });
    await expect(submitButton).toBeEnabled();

    // Click Submit
    await submitButton.click();

    // With voter_count=1, tournament should complete
    await expect(page.getByText('Winner')).toBeVisible({ timeout: 10000 });
    await expect(page.getByText('Full Ranking')).toBeVisible();
  });

  test('multivote result', async ({ page, request }) => {
    // Setup and complete a multivote tournament via API
    const { tournament } = await setupActiveMultivoteTournament(
      request, 'Multivote Result', ['Gold', 'Silver', 'Bronze'],
      { voter_count: 1 },
    );

    // Get vote context to learn entry IDs and total_votes
    const ctx = await getVoteContext(request, tournament.id, 'Voter 1');
    const entryIds = ctx.entries.map((e: any) => e.id);

    // The auto total_votes = 3 * 2 = 6
    // Submit vote: give all votes to the first entry
    await submitVote(
      request, tournament.id, tournament.version, 'Voter 1',
      {
        allocations: [
          { entry_id: entryIds[0], votes: 4 },
          { entry_id: entryIds[1], votes: 1 },
          { entry_id: entryIds[2], votes: 1 },
        ],
      },
    );

    // Navigate to result page
    await page.goto(`/tournaments/${tournament.id}/result`);

    // Verify result page
    await expect(page.getByRole('heading', { name: 'Multivote Result', level: 1 })).toBeVisible({ timeout: 10000 });
    await expect(page.getByText('Winner')).toBeVisible();
    await expect(page.getByText('Full Ranking')).toBeVisible();

    // Ranking table should show vote counts
    const rankingTable = page.locator('.ranking-table');
    await expect(rankingTable).toBeVisible();
    await expect(rankingTable.getByText(/Votes:/).first()).toBeVisible();
  });

  test('multivote budget validation', async ({ page, request }) => {
    // Setup a multivote tournament
    const { tournament } = await setupActiveMultivoteTournament(
      request, 'Budget Validation', ['X', 'Y', 'Z'],
      { voter_count: 1 },
    );

    await page.goto(`/tournaments/${tournament.id}/vote`);

    // Wait for ballot UI
    await expect(page.getByText('Distribute your votes')).toBeVisible({ timeout: 10000 });

    // Submit button should be disabled initially (no votes distributed)
    const submitButton = page.getByRole('button', { name: 'Submit Votes' });
    await expect(submitButton).toBeDisabled();

    // Add only 1 vote (not all 6)
    const addButtons = page.locator('.entry-row button', { hasText: 'add' });
    await addButtons.nth(0).click();

    // Budget display should show partial usage
    await expect(page.getByText(/1 \/ 6 votes used/)).toBeVisible();

    // Submit should still be disabled (haven't used all votes)
    await expect(submitButton).toBeDisabled();

    // The remaining count should show
    await expect(page.getByText('5 remaining')).toBeVisible();

    // Now use up all remaining votes
    for (let i = 0; i < 5; i++) {
      await addButtons.nth(0).click();
    }

    // Budget should show 6/6
    await expect(page.getByText(/6 \/ 6 votes used/)).toBeVisible();

    // Submit should now be enabled
    await expect(submitButton).toBeEnabled();

    // Test decrement: remove 1 vote
    const removeButtons = page.locator('.entry-row button', { hasText: 'remove' });
    await removeButtons.nth(0).click();

    // Budget back to 5/6
    await expect(page.getByText(/5 \/ 6 votes used/)).toBeVisible();

    // Submit should be disabled again
    await expect(submitButton).toBeDisabled();
  });
});
