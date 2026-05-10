import { test, expect } from '@playwright/test';
import {
  cleanAll,
  completeCondorcetVoter,
  setupActiveCondorcetTournament,
} from './helpers';

test.describe('Options popularity (global Elo)', () => {
  test.beforeEach(async ({ request }) => {
    await cleanAll(request);
  });

  test('completing a Condorcet bumps option ratings; sort selector orders by popularity', async ({ page, request }) => {
    // Run a 3-option Condorcet where the default voter picks entry_a of every matchup,
    // so the first option (in itertools.combinations order) ends up the clear winner.
    const { tournament, options } = await setupActiveCondorcetTournament(
      request,
      'Popularity Test',
      ['Atlas', 'Beacon', 'Cinder'],
      { voter_labels: ['default'] },
    );
    await completeCondorcetVoter(request, tournament.id, 'default', tournament.version);

    // Reload the option records — Atlas should have moved above the default 1000;
    // Cinder should be below.
    const reloaded = await Promise.all(
      options.map((o: { id: string }) =>
        request.get(`/api/v1/options/${o.id}`).then((r) => r.json()),
      ),
    );
    const byName: Record<string, number> = {};
    for (const opt of reloaded) byName[opt.name] = opt.elo_rating;

    expect(byName['Atlas']).toBeGreaterThan(1000);
    expect(byName['Cinder']).toBeLessThan(1000);
    expect(byName['Atlas']).toBeGreaterThan(byName['Cinder']);

    // Now visit the options page and select the Popularity sort.
    await page.goto('/options');
    await expect(page.locator('app-option-card')).toHaveCount(3, { timeout: 10000 });

    // Default sort is "Recently Created"; switch to "Popularity".
    await page.locator('mat-form-field.sort-field mat-select').click();
    await page.getByRole('option', { name: 'Popularity' }).click();

    // Atlas should appear first now (highest rating).
    const cardTitles = page.locator('app-option-card mat-card-title');
    await expect(cardTitles.first()).toHaveText('Atlas');

    // Every card shows an Elo badge.
    const badges = page.locator('app-option-card .rating-badge');
    await expect(badges).toHaveCount(3);
    await expect(badges.first()).toContainText(/Elo \d+/);
  });

  test('newly created options start at Elo 1000', async ({ page, request }) => {
    await request.post('/api/v1/options', { data: { name: 'Fresh' } });
    await page.goto('/options');
    await expect(page.locator('app-option-card .rating-badge')).toHaveText(/Elo 1000/);
  });
});
