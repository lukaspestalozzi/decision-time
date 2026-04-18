export interface BracketMatchupContext {
  type: 'bracket_matchup';
  matchup_id: string;
  entry_a: Record<string, unknown>;
  entry_b: Record<string, unknown>;
  round: number;
  round_name: string;
  match_number: number;
  matches_in_round: number;
}

export interface CondorcetMatchupContext {
  type: 'condorcet_matchup';
  matchup_id: string;
  entry_a: Record<string, unknown>;
  entry_b: Record<string, unknown>;
  matchup_number: number;
  total_matchups: number;
}

export interface EloMatchupContext {
  type: 'elo_matchup';
  matchup_id: string;
  entry_a: { id: string; rating: number } & Record<string, unknown>;
  entry_b: { id: string; rating: number } & Record<string, unknown>;
  matchup_number: number;
  total_matchups: number;
  round_number: number;
  rounds_per_pair: number;
}

export interface BallotContext {
  type: 'ballot';
  entries: Record<string, unknown>[];
  ballot_type: 'score' | 'multivote';
  ballots_submitted: number;
  ballots_required: number;
}

export interface SwissStandingEntry {
  rank: number;
  entry_id: string;
  points: number;
  wins: number;
  draws: number;
  losses: number;
}

export interface SwissMatchupContext {
  type: 'swiss_matchup';
  matchup_id: string;
  entry_a: Record<string, unknown>;
  entry_b: Record<string, unknown>;
  round: number;
  total_rounds: number;
  match_number: number;
  matches_in_round: number;
  allow_draws: boolean;
  standings: SwissStandingEntry[];
}

export interface AlreadyVotedContext {
  type: 'already_voted';
}

export interface CompletedContext {
  type: 'completed';
  result: Record<string, unknown>;
}

export type VoteContext =
  | BracketMatchupContext
  | CondorcetMatchupContext
  | EloMatchupContext
  | BallotContext
  | SwissMatchupContext
  | AlreadyVotedContext
  | CompletedContext;
