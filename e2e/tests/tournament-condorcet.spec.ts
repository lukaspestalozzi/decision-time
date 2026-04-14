import { test, expect } from '@playwright/test';
import {
  cleanAll,
  setupActiveCondorcetTournament,
  completeCondorcetVoter,
  getVoteContext,
} from './helpers';

test.describe('Condorcet Tournament', () => {
  test.beforeEach(async ({ request }) => {
    await cleanAll(request);
  });

  test('condorcet voting flow', async ({ page, request }) => {
    // Setup a condorcet tournament with 3 options (3 pairwise matchups)
    const { tournament } = await setupActiveCondorcetTournament(
      request, 'Condorcet Vote Test', ['Elm', 'Oak', 'Pine'],
      { voter_count: 1 },
    );

    // Navigate to the vote page with explicit voter label
    await page.goto(`/tournaments/${tournament.id}/vote?voter=Voter+1`);

    // Wait for the condorcet matchup UI to appear
    await expect(page.getByText('Pairwise Comparison')).toBeVisible({ timeout: 15000 });

    // With 3 options, there are 3*(3-1)/2 = 3 matchups
    // Verify progress text is present
    await expect(page.getByText(/Matchup \d+ of 3/)).toBeVisible();

    // Verify progress bar exists
    await expect(page.locator('mat-progress-bar')).toBeVisible();

    // Vote through all 3 matchups
    for (let i = 0; i < 3; i++) {
      // VS text should be present
      await expect(page.getByText('VS')).toBeVisible();

      // Click the first entry card
      const entryCards = page.locator('.entry-card');
      await expect(entryCards).toHaveCount(2);
      await entryCards.first().click();

      // Verify selection
      await expect(entryCards.first()).toHaveClass(/selected/);

      // Click Confirm Choice
      await page.getByRole('button', { name: 'Confirm Choice' }).click();

      if (i < 2) {
        // Wait for next matchup to load (matchup number should change)
        await expect(page.getByText(`Matchup ${i + 2} of 3`)).toBeVisible({ timeout: 10000 });
      }
    }

    // After all 3 matchups, tournament completes (single voter)
    // Should show results inline
    await expect(page.getByText('Winner')).toBeVisible({ timeout: 10000 });
    await expect(page.getByText('Full Ranking')).toBeVisible();
  });

  test('condorcet result with pairwise matrix', async ({ page, request }) => {
    // Setup and complete a condorcet tournament via API
    const { tournament } = await setupActiveCondorcetTournament(
      request, 'Condorcet Matrix', ['A', 'B', 'C'],
      { voter_count: 1 },
    );

    // Complete via API (all matchups for Voter 1)
    await completeCondorcetVoter(
      request, tournament.id, 'Voter 1', tournament.version,
    );

    // Navigate to the result page
    await page.goto(`/tournaments/${tournament.id}/result`);

    // Verify result page content
    await expect(page.getByRole('heading', { name: 'Condorcet Matrix', level: 1 })).toBeVisible({ timeout: 10000 });
    await expect(page.getByText('Winner')).toBeVisible();
    await expect(page.getByText('Full Ranking')).toBeVisible();

    // Ranking table should show wins
    const rankingTable = page.locator('.ranking-table');
    await expect(rankingTable).toBeVisible();
    await expect(rankingTable.getByText(/Wins:/).first()).toBeVisible();

    // Pairwise matrix should be present
    await expect(page.getByText('Pairwise Results')).toBeVisible();
    const matrix = page.locator('.matrix');
    await expect(matrix).toBeVisible();

    // The matrix should have cells with numbers (pairwise counts)
    // Header row should have entry names
    const headerCells = matrix.locator('thead th');
    // 3 entries + 1 empty corner cell = 4 header cells
    await expect(headerCells).toHaveCount(4);

    // Body rows should exist (3 rows for 3 entries)
    const bodyRows = matrix.locator('tbody tr');
    await expect(bodyRows).toHaveCount(3);
  });

  test('condorcet multi-voter', async ({ page, request }) => {
    // Setup a condorcet tournament with voter_count=2
    const { tournament } = await setupActiveCondorcetTournament(
      request, 'Condorcet Multi', ['Sun', 'Moon', 'Star'],
      { voter_count: 2 },
    );

    // Voter 1 completes all matchups via API
    const afterVoter1 = await completeCondorcetVoter(
      request, tournament.id, 'Voter 1', tournament.version,
    );

    // Navigate as Voter 2 using query param
    await page.goto(`/tournaments/${tournament.id}/vote?voter=Voter+2`);

    // Wait for condorcet matchup UI
    await expect(page.getByText('Pairwise Comparison')).toBeVisible({ timeout: 15000 });

    // Voter selector should be visible for multi-voter modes
    await expect(page.locator('app-voter-selector')).toBeVisible();

    // Vote through all 3 matchups as Voter 2
    for (let i = 0; i < 3; i++) {
      await expect(page.getByText('VS')).toBeVisible();

      const entryCards = page.locator('.entry-card');
      await expect(entryCards).toHaveCount(2);
      await entryCards.first().click();
      await expect(entryCards.first()).toHaveClass(/selected/);

      await page.getByRole('button', { name: 'Confirm Choice' }).click();

      if (i < 2) {
        await expect(page.getByText(`Matchup ${i + 2} of 3`)).toBeVisible({ timeout: 10000 });
      }
    }

    // Both voters done, tournament should complete
    await expect(page.getByText('Winner')).toBeVisible({ timeout: 10000 });
    await expect(page.getByText('Full Ranking')).toBeVisible();
  });
});
