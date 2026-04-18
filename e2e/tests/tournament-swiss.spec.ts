/** End-to-end tests for Swiss tournament mode. */
import { test, expect } from '@playwright/test';
import { cleanAll, createOptions, createTournament } from './helpers';

test.describe('Swiss Tournament', () => {
  test.beforeEach(async ({ request }) => {
    await cleanAll(request);
  });

  test('A. Setup stepper: Swiss mode appears and config form works', async ({ page, request }) => {
    await createOptions(request, ['Pizza', 'Sushi', 'Burger', 'Taco']);
    await page.goto('/tournaments/new');
    await expect(page.getByText('Name & Mode')).toBeVisible();
    await page.getByPlaceholder('e.g. Best Programming Language').fill('Swiss Food Picker');

    // All five mode tiles should be visible, including Swiss.
    await expect(page.locator('.mode-card', { hasText: 'Bracket' })).toBeVisible();
    await expect(page.locator('.mode-card', { hasText: 'Score' })).toBeVisible();
    await expect(page.locator('.mode-card', { hasText: 'Multivote' })).toBeVisible();
    await expect(page.locator('.mode-card', { hasText: 'Condorcet' })).toBeVisible();
    await expect(page.locator('.mode-card', { hasText: 'Swiss' })).toBeVisible();

    await page.locator('.mode-card', { hasText: 'Swiss' }).click();
    await expect(page.locator('.mode-card.mode-selected', { hasText: 'Swiss' })).toBeVisible();
    await page.getByRole('button', { name: 'Next' }).click();

    // Step 2: options.
    await expect(page.locator('.option-item')).toHaveCount(4, { timeout: 10000 });
    await page.locator('.option-item', { hasText: 'Pizza' }).click();
    await page.locator('.option-item', { hasText: 'Sushi' }).click();
    await page.locator('.option-item', { hasText: 'Burger' }).click();
    await page.locator('.option-item', { hasText: 'Taco' }).click();
    await expect(page.getByText('Selected (4)')).toBeVisible();
    await page.getByRole('button', { name: 'Next' }).click();

    // Step 3: Swiss config.
    await expect(page.getByText('Swiss Configuration')).toBeVisible({ timeout: 10000 });
    await expect(page.getByLabel('Allow draws')).toBeVisible();
    await expect(page.getByLabel('Shuffle round-1 pairings')).toBeVisible();
    await expect(page.getByLabel('Total Rounds')).toBeVisible();
    await page.getByRole('button', { name: 'Next' }).click();

    // Step 4: review + summary should include Swiss-specific rows.
    await expect(page.getByText('Tournament Summary')).toBeVisible({ timeout: 10000 });
    const summary = page.locator('.summary-card');
    await expect(summary.getByText('Rounds', { exact: true })).toBeVisible();
    await expect(summary.getByText('Allow Draws', { exact: true })).toBeVisible();
    await expect(summary.getByText('Mode', { exact: true })).toBeVisible();
    await expect(summary.getByText('Swiss', { exact: true })).toBeVisible();

    await page.getByRole('button', { name: 'Activate Tournament' }).click();
    await expect(page.getByRole('heading', { name: 'Swiss Food Picker', level: 1 })).toBeVisible({
      timeout: 10000,
    });
    await expect(page.getByText('active')).toBeVisible();
  });

  test('B. 4-option Swiss flow: instant-submit vote + live standings + final results', async ({
    page,
    request,
  }) => {
    const opts = await createOptions(request, ['Alpha', 'Bravo', 'Charlie', 'Delta']);
    let t = await createTournament(request, 'Swiss 4-opt', 'swiss');
    t = await (await request.put(`/api/v1/tournaments/${t.id}`, {
      data: { version: t.version, selected_option_ids: opts.map((o: any) => o.id) },
    })).json();
    t = await (await request.put(`/api/v1/tournaments/${t.id}`, {
      data: { version: t.version, config: { shuffle_seed: false, voter_labels: ['default'] } },
    })).json();
    const act = await request.post(`/api/v1/tournaments/${t.id}/activate`, {
      data: { version: t.version },
    });
    t = await act.json();

    await page.goto(`/tournaments/${t.id}/vote`);

    // Should see round heading + match counter + live standings table.
    await expect(page.getByText(/Round 1 of 2/)).toBeVisible({ timeout: 10000 });
    await expect(page.getByText(/Match 1 of 2/)).toBeVisible();
    await expect(page.getByText('Current Standings')).toBeVisible();

    // Standings should list all 4 entries with 0 points each.
    const standingsRows = page.locator('app-swiss-matchup table tr');
    await expect(standingsRows).toHaveCount(5); // 1 header + 4 data rows.

    // Click the first (left) matchup card → instant submit, advance to next match.
    const matchupCards = page.locator('app-swiss-matchup .entry-card');
    await expect(matchupCards).toHaveCount(2);
    await matchupCards.first().click();

    // Next match in round 1.
    await expect(page.getByText(/Round 1 of 2/)).toBeVisible({ timeout: 5000 });
    await expect(page.getByText(/Match 2 of 2/)).toBeVisible();
    await page.locator('app-swiss-matchup .entry-card').first().click();

    // Round 2 starts.
    await expect(page.getByText(/Round 2 of 2/)).toBeVisible({ timeout: 5000 });

    // Resolve round 2.
    await page.locator('app-swiss-matchup .entry-card').first().click();
    await expect(page.getByText(/Round 2 of 2/)).toBeVisible({ timeout: 5000 });
    await page.locator('app-swiss-matchup .entry-card').first().click();

    // Tournament complete — swiss standings table rendered.
    await expect(page.getByText('Winner')).toBeVisible({ timeout: 10000 });
    await expect(page.getByText('Full Ranking')).toBeVisible();
    // Swiss-specific columns.
    await expect(page.getByRole('columnheader', { name: 'Points' })).toBeVisible();
    await expect(page.getByRole('columnheader', { name: 'W-D-L' })).toBeVisible();
    await expect(page.getByRole('columnheader', { name: 'Buchholz' })).toBeVisible();
  });

  test('C. Draws: button present when allow_draws=true, awards 0.5 pts each', async ({
    page,
    request,
  }) => {
    const opts = await createOptions(request, ['Red', 'Blue', 'Green', 'Yellow']);
    let t = await createTournament(request, 'Swiss Draws', 'swiss');
    t = await (await request.put(`/api/v1/tournaments/${t.id}`, {
      data: { version: t.version, selected_option_ids: opts.map((o: any) => o.id) },
    })).json();
    t = await (await request.put(`/api/v1/tournaments/${t.id}`, {
      data: {
        version: t.version,
        config: { shuffle_seed: false, allow_draws: true, voter_labels: ['default'] },
      },
    })).json();
    t = await (await request.post(`/api/v1/tournaments/${t.id}/activate`, {
      data: { version: t.version },
    })).json();

    await page.goto(`/tournaments/${t.id}/vote`);
    await expect(page.getByRole('button', { name: 'Draw' })).toBeVisible({ timeout: 10000 });
    await page.getByRole('button', { name: 'Draw' }).click();

    // Next match — still should have Draw button.
    await expect(page.getByRole('button', { name: 'Draw' })).toBeVisible({ timeout: 5000 });

    // Confirm standings show two entries at 0.5 points.
    const rows = page.locator('app-swiss-matchup table tbody tr');
    await expect(rows).toHaveCount(4);
    const points = await rows.locator('td').nth(2).allInnerTexts();
    // Not precise — just sanity check we have some fractional score present.
    const halves = (await rows.allInnerTexts()).filter((t) => t.includes('0.5'));
    expect(halves.length).toBeGreaterThanOrEqual(2);
  });

  test('D. No-draws mode: Draw button not rendered; backend rejects draw payload', async ({
    page,
    request,
  }) => {
    const opts = await createOptions(request, ['One', 'Two']);
    let t = await createTournament(request, 'Swiss NoDraws', 'swiss');
    t = await (await request.put(`/api/v1/tournaments/${t.id}`, {
      data: { version: t.version, selected_option_ids: opts.map((o: any) => o.id) },
    })).json();
    t = await (await request.put(`/api/v1/tournaments/${t.id}`, {
      data: {
        version: t.version,
        config: { shuffle_seed: false, allow_draws: false, voter_labels: ['default'] },
      },
    })).json();
    t = await (await request.post(`/api/v1/tournaments/${t.id}/activate`, {
      data: { version: t.version },
    })).json();

    await page.goto(`/tournaments/${t.id}/vote`);
    await expect(page.getByText(/Round 1 of 1/)).toBeVisible({ timeout: 10000 });
    await expect(page.locator('app-swiss-matchup').getByText('VS')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Draw' })).toHaveCount(0);

    // Try submitting a draw via API — should 422.
    const ctx = await (await request.get(`/api/v1/tournaments/${t.id}/vote-context`, {
      params: { voter: 'default' },
    })).json();
    const rejected = await request.post(`/api/v1/tournaments/${t.id}/vote`, {
      data: {
        version: t.version,
        voter_label: 'default',
        payload: { matchup_id: ctx.matchup_id, result: 'draw' },
      },
    });
    expect(rejected.status()).toBe(422);
  });

  test('E. Odd option count (5 entries) produces a bye; full flow completes', async ({
    page,
    request,
  }) => {
    const opts = await createOptions(request, ['A', 'B', 'C', 'D', 'E']);
    let t = await createTournament(request, 'Swiss Odd', 'swiss');
    t = await (await request.put(`/api/v1/tournaments/${t.id}`, {
      data: { version: t.version, selected_option_ids: opts.map((o: any) => o.id) },
    })).json();
    t = await (await request.put(`/api/v1/tournaments/${t.id}`, {
      data: { version: t.version, config: { shuffle_seed: false, voter_labels: ['default'] } },
    })).json();
    t = await (await request.post(`/api/v1/tournaments/${t.id}/activate`, {
      data: { version: t.version },
    })).json();

    // Verify state snapshot has exactly 1 bye in round 1.
    const state = t.state;
    const round1ByeCount = state.rounds[0].matchups.filter((m: any) => m.is_bye).length;
    expect(round1ByeCount).toBe(1);
    expect(state.total_rounds).toBe(3);

    // Walk through the UI to completion. Swiss with 5 entries over 3 rounds:
    // 2 real matches per round × 3 rounds = 6 clicks (1 bye per round).
    await page.goto(`/tournaments/${t.id}/vote`);
    for (let i = 0; i < 10; i++) {
      // Ask the server what to do next rather than racing the DOM.
      const ctx = await (await request.get(`/api/v1/tournaments/${t.id}/vote-context`, {
        params: { voter: 'default' },
      })).json();
      if (ctx.type === 'completed') break;
      const card = page.locator('app-swiss-matchup .entry-card').first();
      await expect(card).toBeVisible({ timeout: 10000 });
      const before = ctx.matchup_id;
      await card.click();
      // Wait for the server to advance (new matchup_id or completion).
      await page.waitForFunction(
        async ([id, prev]) => {
          const r = await fetch(`/api/v1/tournaments/${id}/vote-context?voter=default`);
          const c = await r.json();
          return c.type !== 'swiss_matchup' || c.matchup_id !== prev;
        },
        [t.id, before],
        { timeout: 5000 },
      );
    }
    await expect(page.getByText('Winner')).toBeVisible({ timeout: 10000 });
    await expect(page.getByText('Full Ranking')).toBeVisible();

    // Completed tournament ranking covers all 5 entries with Swiss-specific columns.
    const result = await (await request.get(`/api/v1/tournaments/${t.id}/result`)).json();
    expect(result.ranking).toHaveLength(5);
    expect(result.ranking[0]).toHaveProperty('points');
    expect(result.ranking[0]).toHaveProperty('buchholz');
    expect(result.ranking[0]).toHaveProperty('byes');
    // Exactly one entry received a bye per round × 3 rounds; byes distributed.
    const totalByes = result.ranking.reduce((s: number, r: any) => s + (r.byes || 0), 0);
    expect(totalByes).toBe(3);
  });

  test('F. Mode switch: can change a draft from Swiss to Bracket (config resets)', async ({
    request,
  }) => {
    let t = await createTournament(request, 'Mode switch', 'swiss');
    expect(t.mode).toBe('swiss');
    expect(t.config.allow_draws).toBe(true);

    const upd = await request.put(`/api/v1/tournaments/${t.id}`, {
      data: { version: t.version, mode: 'bracket' },
    });
    t = await upd.json();
    expect(t.mode).toBe('bracket');
    expect(t.config.allow_draws).toBeUndefined();
    expect(t.config.shuffle_seed).toBe(true);
  });

  test('G. 2-option Swiss: single round, winner picked in one click', async ({ page, request }) => {
    const opts = await createOptions(request, ['Left', 'Right']);
    let t = await createTournament(request, 'Swiss 2opt', 'swiss');
    t = await (await request.put(`/api/v1/tournaments/${t.id}`, {
      data: { version: t.version, selected_option_ids: opts.map((o: any) => o.id) },
    })).json();
    t = await (await request.put(`/api/v1/tournaments/${t.id}`, {
      data: { version: t.version, config: { shuffle_seed: false, voter_labels: ['default'] } },
    })).json();
    t = await (await request.post(`/api/v1/tournaments/${t.id}/activate`, {
      data: { version: t.version },
    })).json();
    expect(t.state.total_rounds).toBe(1);

    await page.goto(`/tournaments/${t.id}/vote`);
    await expect(page.getByText(/Round 1 of 1/)).toBeVisible({ timeout: 10000 });
    await page.locator('app-swiss-matchup .entry-card').first().click();
    await expect(page.getByText('Winner')).toBeVisible({ timeout: 10000 });
  });

  test('H. Explicit total_rounds: 3 options, 4 rounds forces >log2(N) play', async ({ request }) => {
    const opts = await createOptions(request, ['A', 'B', 'C']);
    let t = await createTournament(request, 'Swiss extra rounds', 'swiss');
    t = await (await request.put(`/api/v1/tournaments/${t.id}`, {
      data: { version: t.version, selected_option_ids: opts.map((o: any) => o.id) },
    })).json();
    t = await (await request.put(`/api/v1/tournaments/${t.id}`, {
      data: {
        version: t.version,
        config: { shuffle_seed: false, total_rounds: 4, voter_labels: ['default'] },
      },
    })).json();
    t = await (await request.post(`/api/v1/tournaments/${t.id}/activate`, {
      data: { version: t.version },
    })).json();
    expect(t.state.total_rounds).toBe(4);

    // Drive the whole thing via API.
    let version = t.version;
    for (let i = 0; i < 20; i++) {
      const ctx = await (await request.get(`/api/v1/tournaments/${t.id}/vote-context`, {
        params: { voter: 'default' },
      })).json();
      if (ctx.type === 'completed') break;
      const vr = await request.post(`/api/v1/tournaments/${t.id}/vote`, {
        data: {
          version,
          voter_label: 'default',
          payload: { matchup_id: ctx.matchup_id, result: 'a_wins' },
        },
      });
      expect(vr.status()).toBe(200);
      version = (await vr.json()).version;
    }
    const result = await (await request.get(`/api/v1/tournaments/${t.id}/result`)).json();
    expect(result.metadata.total_rounds).toBe(4);
    // Every entry should appear in ranking.
    expect(result.ranking).toHaveLength(3);
  });

  test('I. Activation rejected with < 2 options', async ({ request }) => {
    const opts = await createOptions(request, ['Only']);
    let t = await createTournament(request, 'Swiss single', 'swiss');
    t = await (await request.put(`/api/v1/tournaments/${t.id}`, {
      data: { version: t.version, selected_option_ids: opts.map((o: any) => o.id) },
    })).json();
    const act = await request.post(`/api/v1/tournaments/${t.id}/activate`, {
      data: { version: t.version },
    });
    expect(act.status()).toBe(422);
    const body = await act.json();
    expect(body.error.code).toBe('VALIDATION_ERROR');
  });

  test('J. All-draws small tournament produces multi-way tie at rank 1', async ({ request }) => {
    const opts = await createOptions(request, ['W', 'X', 'Y', 'Z']);
    let t = await createTournament(request, 'Swiss all draws', 'swiss');
    t = await (await request.put(`/api/v1/tournaments/${t.id}`, {
      data: { version: t.version, selected_option_ids: opts.map((o: any) => o.id) },
    })).json();
    t = await (await request.put(`/api/v1/tournaments/${t.id}`, {
      data: {
        version: t.version,
        config: { shuffle_seed: false, allow_draws: true, voter_labels: ['default'] },
      },
    })).json();
    t = await (await request.post(`/api/v1/tournaments/${t.id}/activate`, {
      data: { version: t.version },
    })).json();

    let version = t.version;
    for (let i = 0; i < 20; i++) {
      const ctx = await (await request.get(`/api/v1/tournaments/${t.id}/vote-context`, {
        params: { voter: 'default' },
      })).json();
      if (ctx.type === 'completed') break;
      const vr = await request.post(`/api/v1/tournaments/${t.id}/vote`, {
        data: {
          version,
          voter_label: 'default',
          payload: { matchup_id: ctx.matchup_id, result: 'draw' },
        },
      });
      expect(vr.status()).toBe(200);
      version = (await vr.json()).version;
    }
    const result = await (await request.get(`/api/v1/tournaments/${t.id}/result`)).json();
    // Everyone drew every game → all rank 1.
    expect(result.ranking.every((r: any) => r.rank === 1)).toBe(true);
    expect(result.winner_ids).toHaveLength(4);
  });

  test('K. Undo: vote → undo → state reverts and same matchup is offered again', async ({
    request,
  }) => {
    const opts = await createOptions(request, ['P', 'Q', 'R', 'S']);
    let t = await createTournament(request, 'Swiss undo', 'swiss');
    t = await (await request.put(`/api/v1/tournaments/${t.id}`, {
      data: { version: t.version, selected_option_ids: opts.map((o: any) => o.id) },
    })).json();
    t = await (await request.put(`/api/v1/tournaments/${t.id}`, {
      data: {
        version: t.version,
        config: { shuffle_seed: false, voter_labels: ['default'], allow_undo: true },
      },
    })).json();
    t = await (await request.post(`/api/v1/tournaments/${t.id}/activate`, {
      data: { version: t.version },
    })).json();

    const initialCtx = await (await request.get(`/api/v1/tournaments/${t.id}/vote-context`, {
      params: { voter: 'default' },
    })).json();
    expect(initialCtx.type).toBe('swiss_matchup');

    // Submit a vote.
    const voted = await (await request.post(`/api/v1/tournaments/${t.id}/vote`, {
      data: {
        version: t.version,
        voter_label: 'default',
        payload: { matchup_id: initialCtx.matchup_id, result: 'a_wins' },
      },
    })).json();

    // Undo.
    const undone = await (await request.post(`/api/v1/tournaments/${t.id}/undo`, {
      data: { version: voted.version, voter_label: 'default' },
    })).json();

    // After undo, the server should offer the same matchup again.
    const afterCtx = await (await request.get(`/api/v1/tournaments/${undone.tournament.id}/vote-context`, {
      params: { voter: 'default' },
    })).json();
    expect(afterCtx.matchup_id).toBe(initialCtx.matchup_id);
    // Standings should be zeroed.
    expect(afterCtx.standings.every((s: any) => s.points === 0)).toBe(true);
  });

  test('L. Large tournament (8 entries): multi-round with expected byes & Buchholz', async ({
    request,
  }) => {
    const names = Array.from({ length: 8 }, (_, i) => `Opt${i + 1}`);
    const opts = await createOptions(request, names);
    let t = await createTournament(request, 'Swiss 8', 'swiss');
    t = await (await request.put(`/api/v1/tournaments/${t.id}`, {
      data: { version: t.version, selected_option_ids: opts.map((o: any) => o.id) },
    })).json();
    t = await (await request.put(`/api/v1/tournaments/${t.id}`, {
      data: { version: t.version, config: { shuffle_seed: false, voter_labels: ['default'] } },
    })).json();
    t = await (await request.post(`/api/v1/tournaments/${t.id}/activate`, {
      data: { version: t.version },
    })).json();
    expect(t.state.total_rounds).toBe(3); // ceil(log2(8)) = 3

    // Drive with alternating results to exercise tiebreakers.
    let version = t.version;
    let vote_i = 0;
    for (let i = 0; i < 30; i++) {
      const ctx = await (await request.get(`/api/v1/tournaments/${t.id}/vote-context`, {
        params: { voter: 'default' },
      })).json();
      if (ctx.type === 'completed') break;
      const result = vote_i++ % 3 === 0 ? 'b_wins' : 'a_wins';
      const vr = await request.post(`/api/v1/tournaments/${t.id}/vote`, {
        data: {
          version,
          voter_label: 'default',
          payload: { matchup_id: ctx.matchup_id, result },
        },
      });
      expect(vr.status()).toBe(200);
      version = (await vr.json()).version;
    }
    const result = await (await request.get(`/api/v1/tournaments/${t.id}/result`)).json();
    expect(result.ranking).toHaveLength(8);
    // Points are consistent: max possible = 3 wins = 3.0.
    expect(result.ranking[0].points).toBeLessThanOrEqual(3);
    // Ranking should be monotonically non-increasing by points.
    for (let i = 1; i < result.ranking.length; i++) {
      expect(result.ranking[i].points).toBeLessThanOrEqual(result.ranking[i - 1].points);
    }
    // Buchholz is attached to every row.
    expect(result.ranking.every((r: any) => typeof r.buchholz === 'number')).toBe(true);
  });
});
