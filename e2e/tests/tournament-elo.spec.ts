/** End-to-end tests for ELO tournament mode. */
import { test, expect } from '@playwright/test';
import {
  cleanAll,
  completeEloVoter,
  createOptions,
  createTournament,
  getResult,
  getVoteContext,
  setupActiveEloTournament,
  submitVote,
} from './helpers';

test.describe('Elo Tournament', () => {
  test.beforeEach(async ({ request }) => {
    await cleanAll(request);
  });

  test('A. Setup stepper: Elo mode appears and config form works', async ({ page, request }) => {
    await createOptions(request, ['Pizza', 'Sushi', 'Burger', 'Taco']);
    await page.goto('/tournaments/new');
    await expect(page.getByText('Name & Mode')).toBeVisible();
    await page.getByPlaceholder('e.g. Best Programming Language').fill('Elo Food Picker');

    // Elo tile visible alongside the others.
    await expect(page.locator('.mode-card', { hasText: 'Bracket' })).toBeVisible();
    await expect(page.locator('.mode-card', { hasText: 'Condorcet' })).toBeVisible();
    await expect(page.locator('.mode-card', { hasText: 'Swiss' })).toBeVisible();
    await expect(page.locator('.mode-card', { hasText: 'Elo' })).toBeVisible();

    await page.locator('.mode-card', { hasText: 'Elo' }).click();
    await expect(page.locator('.mode-card.mode-selected', { hasText: 'Elo' })).toBeVisible();
    await page.getByRole('button', { name: 'Next' }).click();

    // Step 2: options.
    await expect(page.locator('.option-item')).toHaveCount(4, { timeout: 10000 });
    await page.locator('.option-item', { hasText: 'Pizza' }).click();
    await page.locator('.option-item', { hasText: 'Sushi' }).click();
    await page.locator('.option-item', { hasText: 'Burger' }).click();
    await page.locator('.option-item', { hasText: 'Taco' }).click();
    await expect(page.getByText('Selected (4)')).toBeVisible();
    await page.getByRole('button', { name: 'Next' }).click();

    // Step 3: Elo config form fields are rendered.
    await expect(page.getByText('Elo Configuration')).toBeVisible({ timeout: 10000 });
    await expect(page.getByLabel('Rounds per Pair')).toBeVisible();
    await expect(page.getByLabel('K Factor')).toBeVisible();
    await expect(page.getByLabel('Initial Rating')).toBeVisible();
    await page.getByRole('button', { name: 'Next' }).click();

    // Step 4: review + summary includes Elo-specific rows.
    await expect(page.getByText('Tournament Summary')).toBeVisible({ timeout: 10000 });
    const summary = page.locator('.summary-card');
    await expect(summary.getByText('Rounds per Pair', { exact: true })).toBeVisible();
    await expect(summary.getByText('K Factor', { exact: true })).toBeVisible();
    await expect(summary.getByText('Initial Rating', { exact: true })).toBeVisible();
    await expect(summary.getByText('Elo', { exact: true })).toBeVisible();

    await page.getByRole('button', { name: 'Activate Tournament' }).click();
    await expect(page.getByRole('heading', { name: 'Elo Food Picker', level: 1 })).toBeVisible({
      timeout: 10000,
    });
    await expect(page.getByText('active')).toBeVisible();
  });

  test('B. Full 3-option Elo flow: click through matchups, live ratings visible, final ranking', async ({
    page,
    request,
  }) => {
    const { tournament } = await setupActiveEloTournament(
      request, 'Elo Vote Test', ['Alpha', 'Bravo', 'Charlie'], { rounds_per_pair: 2 },
    );
    // 3 entries * C(3,2)=3 pairs * 2 rounds = 6 matchups.
    expect(tournament.state.matchups).toHaveLength(6);

    await page.goto(`/tournaments/${tournament.id}/vote`);

    // Matchup UI renders with counter and live Elo badges.
    await expect(page.getByText(/Matchup 1 of 6/)).toBeVisible({ timeout: 10000 });
    await expect(page.getByText(/Round \d+ of 2/)).toBeVisible();
    const ratings = page.locator('app-elo-matchup .rating');
    await expect(ratings).toHaveCount(2);
    await expect(ratings.first()).toContainText(/Elo:\s*1[,.]?000/);

    // Vote 6 times, picking the left card each time.
    for (let i = 1; i <= 6; i++) {
      await expect(page.getByText(new RegExp(`Matchup ${i} of 6`))).toBeVisible({ timeout: 10000 });
      await page.locator('app-elo-matchup .entry-card').first().click();
    }

    // Completed: result page rendered.
    await expect(page.getByText('Winner')).toBeVisible({ timeout: 10000 });
    await expect(page.getByText('Full Ranking')).toBeVisible();

    // Backend result has mean_rating on each ranking row.
    const result = await getResult(request, tournament.id);
    expect(result.ranking).toHaveLength(3);
    expect(result.ranking[0]).toHaveProperty('mean_rating');
    expect(result.ranking[0].mean_rating).toBeGreaterThan(result.ranking[1].mean_rating);
  });

  test('C. Live ratings update after a vote', async ({ request }) => {
    const { tournament } = await setupActiveEloTournament(
      request, 'Elo Live Ratings', ['A', 'B'], { rounds_per_pair: 3 },
    );

    // First matchup: both entries at 1000.
    const ctx = await getVoteContext(request, tournament.id, 'default');
    expect(ctx.type).toBe('elo_matchup');
    expect(ctx.entry_a.rating).toBe(1000);
    expect(ctx.entry_b.rating).toBe(1000);
    expect(ctx.rounds_per_pair).toBe(3);
    expect(ctx.round_number).toBeGreaterThanOrEqual(1);
    expect(ctx.round_number).toBeLessThanOrEqual(3);

    // Vote A wins.
    const winnerId = ctx.entry_a.id;
    const updated = await submitVote(request, tournament.id, tournament.version, 'default', {
      matchup_id: ctx.matchup_id,
      winner_entry_id: winnerId,
    });

    // Next matchup: same pair, ratings have drifted; winner is above 1000.
    const ctx2 = await getVoteContext(request, updated.id, 'default');
    expect(ctx2.type).toBe('elo_matchup');
    const winnerRating = ctx2.entry_a.id === winnerId ? ctx2.entry_a.rating : ctx2.entry_b.rating;
    const loserRating = ctx2.entry_a.id === winnerId ? ctx2.entry_b.rating : ctx2.entry_a.rating;
    expect(winnerRating).toBeGreaterThan(1000);
    expect(loserRating).toBeLessThan(1000);
    expect(winnerRating + loserRating).toBeCloseTo(2000, 2);
  });

  test('D. Multi-voter Elo: per-voter ratings and mean aggregation', async ({ request }) => {
    const { tournament } = await setupActiveEloTournament(
      request, 'Elo Multi', ['Sun', 'Moon', 'Star'],
      { rounds_per_pair: 2, voter_labels: ['Alice', 'Bob'] },
    );

    await completeEloVoter(request, tournament.id, 'Alice', tournament.version);
    const afterAlice = await (await request.get(`/api/v1/tournaments/${tournament.id}`)).json();
    expect(afterAlice.status).toBe('active'); // Bob hasn't voted yet.

    await completeEloVoter(request, tournament.id, 'Bob', afterAlice.version);
    const result = await getResult(request, tournament.id);
    expect(result.ranking).toHaveLength(3);
    expect(result.ranking[0]).toHaveProperty('mean_rating');
    // Both voters always pick entry_a → rank 1 has highest rating, rank 3 has lowest.
    expect(result.ranking[0].mean_rating).toBeGreaterThan(result.ranking[2].mean_rating);
    expect(result.metadata.voter_ratings.Alice).toBeDefined();
    expect(result.metadata.voter_ratings.Bob).toBeDefined();
  });

  test('E. Config validation: rounds_per_pair=0 rejected at PUT', async ({ request }) => {
    const t = await createTournament(request, 'Elo Bad Config', 'elo');
    const res = await request.put(`/api/v1/tournaments/${t.id}`, {
      data: { version: t.version, config: { rounds_per_pair: 0 } },
    });
    expect(res.status()).toBe(422);
  });

  test('F. Activation rejected with < 2 options', async ({ request }) => {
    const [onlyOne] = await createOptions(request, ['Lonely']);
    let t = await createTournament(request, 'Elo one-opt', 'elo');
    t = await (await request.put(`/api/v1/tournaments/${t.id}`, {
      data: { version: t.version, selected_option_ids: [onlyOne.id] },
    })).json();
    const activateRes = await request.post(`/api/v1/tournaments/${t.id}/activate`, {
      data: { version: t.version },
    });
    expect(activateRes.status()).toBe(422);
  });

  test('G. Activation populates voter_shuffle_seeds for replay determinism', async ({ request }) => {
    const { tournament } = await setupActiveEloTournament(
      request, 'Elo Seeds', ['X', 'Y', 'Z'],
      { voter_labels: ['Alice', 'Bob'] },
    );
    const seeds = tournament.config.voter_shuffle_seeds;
    expect(seeds).toBeDefined();
    expect(Object.keys(seeds).sort()).toEqual(['Alice', 'Bob']);
    expect(typeof seeds.Alice).toBe('number');
  });

  test('H. Undo Elo vote reverts rating table', async ({ request }) => {
    const { tournament } = await setupActiveEloTournament(
      request, 'Elo Undo', ['A', 'B', 'C'], { rounds_per_pair: 1 },
    );

    const ctx = await getVoteContext(request, tournament.id, 'default');
    expect(ctx.type).toBe('elo_matchup');
    const updated = await submitVote(request, tournament.id, tournament.version, 'default', {
      matchup_id: ctx.matchup_id,
      winner_entry_id: ctx.entry_a.id,
    });

    // Ratings moved.
    const winnerId = ctx.entry_a.id;
    expect(updated.state.voter_ratings.default[winnerId]).toBeGreaterThan(1000);

    // Undo.
    const undoRes = await request.post(`/api/v1/tournaments/${tournament.id}/undo`, {
      data: { version: updated.version, voter_label: 'default' },
    });
    expect(undoRes.status()).toBe(200);
    const undone = (await undoRes.json()).tournament;

    // All ratings back to 1000.
    const ratings = undone.state.voter_ratings.default;
    for (const r of Object.values(ratings) as number[]) {
      expect(r).toBeCloseTo(1000, 6);
    }

    // Same matchup offered again.
    const ctx2 = await getVoteContext(request, tournament.id, 'default');
    expect(ctx2.type).toBe('elo_matchup');
    expect(ctx2.matchup_id).toBe(ctx.matchup_id);
  });

  test('I. Mode switch: can change a draft from Elo to Bracket (config resets)', async ({
    request,
  }) => {
    let t = await createTournament(request, 'Elo→Bracket switch', 'elo');
    expect(t.mode).toBe('elo');
    expect(t.config.rounds_per_pair).toBe(3);

    const upd = await request.put(`/api/v1/tournaments/${t.id}`, {
      data: { version: t.version, mode: 'bracket' },
    });
    t = await upd.json();
    expect(t.mode).toBe('bracket');
    expect(t.config.rounds_per_pair).toBeUndefined();
    expect(t.config.k_factor).toBeUndefined();
    expect(t.config.shuffle_seed).toBe(true);
  });
});
