import { APIRequestContext } from '@playwright/test';

const API = '/api/v1';

/**
 * Create a single option via API, return its JSON.
 */
export async function createOption(
  request: APIRequestContext,
  name: string,
  tags?: string[],
): Promise<any> {
  const body: Record<string, unknown> = { name };
  if (tags) body.tags = tags;
  const res = await request.post(`${API}/options`, { data: body });
  if (!res.ok()) {
    throw new Error(`createOption failed (${res.status()}): ${await res.text()}`);
  }
  return res.json();
}

/**
 * Create multiple options via API, return array of created option JSON objects.
 */
export async function createOptions(
  request: APIRequestContext,
  names: string[],
): Promise<any[]> {
  const results: any[] = [];
  for (const name of names) {
    results.push(await createOption(request, name));
  }
  return results;
}

/**
 * Create a tournament via API, return its JSON.
 */
export async function createTournament(
  request: APIRequestContext,
  name: string,
  mode: string,
): Promise<any> {
  const res = await request.post(`${API}/tournaments`, {
    data: { name, mode },
  });
  if (!res.ok()) {
    throw new Error(`createTournament failed (${res.status()}): ${await res.text()}`);
  }
  return res.json();
}

/**
 * Set options on a tournament (partial update).
 */
export async function setTournamentOptions(
  request: APIRequestContext,
  id: string,
  version: number,
  optionIds: string[],
): Promise<any> {
  const res = await request.put(`${API}/tournaments/${id}`, {
    data: { version, selected_option_ids: optionIds },
  });
  if (!res.ok()) {
    throw new Error(`setTournamentOptions failed (${res.status()}): ${await res.text()}`);
  }
  return res.json();
}

/**
 * Update tournament config.
 */
export async function setTournamentConfig(
  request: APIRequestContext,
  id: string,
  version: number,
  config: Record<string, unknown>,
): Promise<any> {
  const res = await request.put(`${API}/tournaments/${id}`, {
    data: { version, config },
  });
  if (!res.ok()) {
    throw new Error(`setTournamentConfig failed (${res.status()}): ${await res.text()}`);
  }
  return res.json();
}

/**
 * Activate a tournament.
 */
export async function activateTournament(
  request: APIRequestContext,
  id: string,
  version: number,
): Promise<any> {
  const res = await request.post(`${API}/tournaments/${id}/activate`, {
    data: { version },
  });
  if (!res.ok()) {
    throw new Error(`activateTournament failed (${res.status()}): ${await res.text()}`);
  }
  return res.json();
}

/**
 * Get the vote context for a tournament (optionally for a specific voter).
 */
export async function getVoteContext(
  request: APIRequestContext,
  id: string,
  voter?: string,
): Promise<any> {
  const params: Record<string, string> = {};
  if (voter) params.voter = voter;
  const res = await request.get(`${API}/tournaments/${id}/vote-context`, { params });
  if (!res.ok()) {
    throw new Error(`getVoteContext failed (${res.status()}): ${await res.text()}`);
  }
  return res.json();
}

/**
 * Submit a vote for a tournament.
 */
export async function submitVote(
  request: APIRequestContext,
  id: string,
  version: number,
  voterLabel: string,
  payload: any,
): Promise<any> {
  const res = await request.post(`${API}/tournaments/${id}/vote`, {
    data: { version, voter_label: voterLabel, payload },
  });
  if (!res.ok()) {
    throw new Error(`submitVote failed (${res.status()}): ${await res.text()}`);
  }
  return res.json();
}

/**
 * Get the tournament result.
 */
export async function getResult(
  request: APIRequestContext,
  id: string,
): Promise<any> {
  const res = await request.get(`${API}/tournaments/${id}/result`);
  if (!res.ok()) {
    throw new Error(`getResult failed (${res.status()}): ${await res.text()}`);
  }
  return res.json();
}

/**
 * Delete all options (cleanup helper).
 */
export async function deleteAllOptions(request: APIRequestContext): Promise<void> {
  const res = await request.get(`${API}/options`);
  const options = await res.json();
  for (const opt of options) {
    await request.delete(`${API}/options/${opt.id}`);
  }
}

/**
 * Delete all tournaments (cleanup helper).
 */
export async function deleteAllTournaments(request: APIRequestContext): Promise<void> {
  const res = await request.get(`${API}/tournaments`);
  const tournaments = await res.json();
  for (const t of tournaments) {
    await request.delete(`${API}/tournaments/${t.id}`);
  }
}

/**
 * Full cleanup: delete all tournaments and options.
 */
export async function cleanAll(request: APIRequestContext): Promise<void> {
  await deleteAllTournaments(request);
  await deleteAllOptions(request);
}

/**
 * Create a fully activated bracket tournament with the given option names.
 * Returns { tournament, options }.
 */
export async function setupActiveBracketTournament(
  request: APIRequestContext,
  tournamentName: string,
  optionNames: string[],
): Promise<{ tournament: any; options: any[] }> {
  const options = await createOptions(request, optionNames);
  let tournament = await createTournament(request, tournamentName, 'bracket');
  tournament = await setTournamentOptions(
    request, tournament.id, tournament.version,
    options.map((o: any) => o.id),
  );
  tournament = await setTournamentConfig(
    request, tournament.id, tournament.version,
    { shuffle_seed: false, third_place_match: false },
  );
  tournament = await activateTournament(request, tournament.id, tournament.version);
  return { tournament, options };
}

/**
 * Create a fully activated score tournament.
 * Returns { tournament, options }.
 */
export async function setupActiveScoreTournament(
  request: APIRequestContext,
  tournamentName: string,
  optionNames: string[],
  config: { min_score?: number; max_score?: number; voter_labels?: string[] } = {},
): Promise<{ tournament: any; options: any[] }> {
  const options = await createOptions(request, optionNames);
  let tournament = await createTournament(request, tournamentName, 'score');
  tournament = await setTournamentOptions(
    request, tournament.id, tournament.version,
    options.map((o: any) => o.id),
  );
  tournament = await setTournamentConfig(
    request, tournament.id, tournament.version,
    { min_score: 1, max_score: 5, voter_labels: ['default'], ...config },
  );
  tournament = await activateTournament(request, tournament.id, tournament.version);
  return { tournament, options };
}

/**
 * Create a fully activated multivote tournament.
 * Returns { tournament, options }.
 */
export async function setupActiveMultivoteTournament(
  request: APIRequestContext,
  tournamentName: string,
  optionNames: string[],
  config: { total_votes?: number | null; max_per_option?: number | null; voter_labels?: string[] } = {},
): Promise<{ tournament: any; options: any[] }> {
  const options = await createOptions(request, optionNames);
  let tournament = await createTournament(request, tournamentName, 'multivote');
  tournament = await setTournamentOptions(
    request, tournament.id, tournament.version,
    options.map((o: any) => o.id),
  );
  tournament = await setTournamentConfig(
    request, tournament.id, tournament.version,
    { total_votes: null, max_per_option: null, voter_labels: ['default'], ...config },
  );
  tournament = await activateTournament(request, tournament.id, tournament.version);
  return { tournament, options };
}

/**
 * Create a fully activated condorcet tournament.
 * Returns { tournament, options }.
 */
export async function setupActiveCondorcetTournament(
  request: APIRequestContext,
  tournamentName: string,
  optionNames: string[],
  config: { voter_labels?: string[] } = {},
): Promise<{ tournament: any; options: any[] }> {
  const options = await createOptions(request, optionNames);
  let tournament = await createTournament(request, tournamentName, 'condorcet');
  tournament = await setTournamentOptions(
    request, tournament.id, tournament.version,
    options.map((o: any) => o.id),
  );
  tournament = await setTournamentConfig(
    request, tournament.id, tournament.version,
    { voter_labels: ['default'], ...config },
  );
  tournament = await activateTournament(request, tournament.id, tournament.version);
  return { tournament, options };
}

/**
 * Complete a bracket tournament by voting through all matchups via API.
 * Always picks entry_a as the winner.
 */
export async function completeBracketTournament(
  request: APIRequestContext,
  tournamentId: string,
  startVersion: number,
): Promise<any> {
  let version = startVersion;
  for (;;) {
    const ctx = await getVoteContext(request, tournamentId, 'default');
    if (ctx.type === 'completed') {
      // Fetch the final tournament state
      const res = await request.get(`${API}/tournaments/${tournamentId}`);
      return res.json();
    }
    if (ctx.type !== 'bracket_matchup') {
      throw new Error(`Unexpected context type: ${ctx.type}`);
    }
    const updated = await submitVote(request, tournamentId, version, 'default', {
      matchup_id: ctx.matchup_id,
      winner_entry_id: ctx.entry_a.id,
    });
    version = updated.version;
  }
}

/**
 * Complete a condorcet tournament for a given voter by voting all their matchups via API.
 * Always picks entry_a as the winner.
 */
export async function completeCondorcetVoter(
  request: APIRequestContext,
  tournamentId: string,
  voterLabel: string,
  startVersion: number,
): Promise<any> {
  let version = startVersion;
  for (;;) {
    const ctx = await getVoteContext(request, tournamentId, voterLabel);
    if (ctx.type === 'completed' || ctx.type === 'already_voted') {
      const res = await request.get(`${API}/tournaments/${tournamentId}`);
      return res.json();
    }
    if (ctx.type !== 'condorcet_matchup') {
      throw new Error(`Unexpected context type for condorcet: ${ctx.type}`);
    }
    const updated = await submitVote(request, tournamentId, version, voterLabel, {
      matchup_id: ctx.matchup_id,
      winner_entry_id: ctx.entry_a.id,
    });
    version = updated.version;
  }
}
