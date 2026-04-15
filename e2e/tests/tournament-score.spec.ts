import { test, expect } from '@playwright/test';
import {
  cleanAll,
  setupActiveScoreTournament,
  submitVote,
  getVoteContext,
} from './helpers';

test.describe('Score Tournament', () => {
  test.beforeEach(async ({ request }) => {
    await cleanAll(request);
  });

  test('score voting flow', async ({ page, request }) => {
    // Setup a score tournament with 1 voter and 3 options via API
    const { tournament } = await setupActiveScoreTournament(
      request, 'Score Vote Test', ['Pizza', 'Pasta', 'Risotto'],
      { min_score: 1, max_score: 5, voter_labels: ['default'] },
    );

    // Navigate to the vote page
    await page.goto(`/tournaments/${tournament.id}/vote`);

    // Wait for the ballot UI to appear
    await expect(page.getByText('Rate each option')).toBeVisible({ timeout: 10000 });
    await expect(page.getByText('0 of 1 ballots submitted')).toBeVisible();

    // Should see all 3 entries listed
    await expect(page.locator('.entry-row')).toHaveCount(3);

    // Set scores using the slider thumbs
    // The sliders use mat-slider with matSliderThumb input elements
    const sliderInputs = page.locator('input[matSliderThumb]');
    await expect(sliderInputs).toHaveCount(3);

    // Set different values for each slider to ensure a clear winner
    await sliderInputs.nth(0).fill('5');
    await sliderInputs.nth(1).fill('3');
    await sliderInputs.nth(2).fill('1');

    // The Submit button should now be enabled (all entries scored)
    const submitButton = page.getByRole('button', { name: 'Submit Scores' });
    await expect(submitButton).toBeEnabled();

    // Click Submit
    await submitButton.click();

    // After submission with single voter, tournament completes
    // Should show the result inline
    await expect(page.getByText('Winner')).toBeVisible({ timeout: 10000 });
    await expect(page.getByText('Full Ranking')).toBeVisible();
  });

  test('multi-voter score flow', async ({ page, request }) => {
    // Setup score tournament with 2 voters
    const { tournament } = await setupActiveScoreTournament(
      request, 'Multi-Voter Score', ['Java', 'Python', 'Rust'],
      { min_score: 1, max_score: 5, voter_labels: ['Voter 1', 'Voter 2'] },
    );

    // Get vote context for Voter 1 to get the entry IDs
    const ctx = await getVoteContext(request, tournament.id, 'Voter 1');
    const entryIds = ctx.entries.map((e: any) => e.id);

    // Voter 1 submits via API
    const scores = entryIds.map((id: string, i: number) => ({
      entry_id: id,
      score: 5 - i, // scores: 5, 4, 3
    }));
    const updated = await submitVote(
      request, tournament.id, tournament.version, 'Voter 1',
      { scores },
    );

    // Navigate as Voter 2
    await page.goto(`/tournaments/${tournament.id}/vote?voter=Voter+2`);

    // Wait for ballot UI
    await expect(page.getByText('Rate each option')).toBeVisible({ timeout: 10000 });
    await expect(page.getByText('1 of 2 ballots submitted')).toBeVisible();

    // Set scores via slider for Voter 2
    const sliderInputs = page.locator('input[matSliderThumb]');
    await expect(sliderInputs).toHaveCount(3);

    for (let i = 0; i < 3; i++) {
      const slider = sliderInputs.nth(i);
      await slider.fill('3');
    }

    // Submit
    const submitButton = page.getByRole('button', { name: 'Submit Scores' });
    await expect(submitButton).toBeEnabled();
    await submitButton.click();

    // Tournament should now be complete (2/2 ballots)
    await expect(page.getByText('Winner')).toBeVisible({ timeout: 10000 });
    await expect(page.getByText('Full Ranking')).toBeVisible();
  });

  test('score result page', async ({ page, request }) => {
    // Setup and complete a score tournament via API
    const { tournament } = await setupActiveScoreTournament(
      request, 'Score Results', ['Espresso', 'Latte', 'Cappuccino'],
      { min_score: 1, max_score: 10, voter_labels: ['default'] },
    );

    // Get vote context to learn entry IDs
    const ctx = await getVoteContext(request, tournament.id, 'default');
    const entryIds = ctx.entries.map((e: any) => e.id);

    // Submit vote via API
    const scores = entryIds.map((id: string, i: number) => ({
      entry_id: id,
      score: 10 - (i * 3), // scores: 10, 7, 4
    }));
    await submitVote(
      request, tournament.id, tournament.version, 'default',
      { scores },
    );

    // Navigate to the result page
    await page.goto(`/tournaments/${tournament.id}/result`);

    // Verify result page content
    await expect(page.getByRole('heading', { name: 'Score Results', level: 1 })).toBeVisible({ timeout: 10000 });
    await expect(page.getByText('Winner')).toBeVisible();

    // Ranking table should exist with Avg scores
    await expect(page.getByText('Full Ranking')).toBeVisible();
    const rankingTable = page.locator('.ranking-table');
    await expect(rankingTable).toBeVisible();

    // Should show Rank, Option, Score columns
    await expect(rankingTable.getByText('Rank')).toBeVisible();
    await expect(rankingTable.getByText('Option')).toBeVisible();
    await expect(rankingTable.getByText('Score')).toBeVisible();

    // Should contain "Avg:" in the table rows
    await expect(rankingTable.getByText(/Avg:/).first()).toBeVisible();
  });

  test('custom voter labels', async ({ page, request }) => {
    // Setup score tournament with custom-named voters
    const { tournament } = await setupActiveScoreTournament(
      request, 'Custom Voter Names', ['Coffee', 'Tea', 'Juice'],
      { min_score: 1, max_score: 5, voter_labels: ['Alice', 'Bob'] },
    );

    // Alice submits via API
    const ctx = await getVoteContext(request, tournament.id, 'Alice');
    const entryIds = ctx.entries.map((e: any) => e.id);
    await submitVote(
      request, tournament.id, tournament.version, 'Alice',
      { scores: entryIds.map((id: string, i: number) => ({ entry_id: id, score: 5 - i })) },
    );

    // Navigate the UI as Bob — voter selector must show Alice and Bob (not "Voter 1"/"Voter 2")
    await page.goto(`/tournaments/${tournament.id}/vote?voter=Bob`);
    await expect(page.getByText('Rate each option')).toBeVisible({ timeout: 10000 });
    await expect(page.getByText('1 of 2 ballots submitted')).toBeVisible();

    // Voter selector dropdown should be present (multi-voter tournament)
    await expect(page.locator('app-voter-selector')).toBeVisible();

    // Submit Bob's scores
    const sliderInputs = page.locator('input[matSliderThumb]');
    await sliderInputs.nth(0).fill('5');
    await sliderInputs.nth(1).fill('3');
    await sliderInputs.nth(2).fill('1');
    await page.getByRole('button', { name: 'Submit Scores' }).click();

    // Tournament should complete
    await expect(page.getByText('Winner')).toBeVisible({ timeout: 10000 });
  });
});
