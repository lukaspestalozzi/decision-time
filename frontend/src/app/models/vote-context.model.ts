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

export interface BallotContext {
  type: 'ballot';
  entries: Record<string, unknown>[];
  ballot_type: 'score' | 'multivote';
  ballots_submitted: number;
  ballots_required: number;
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
  | BallotContext
  | AlreadyVotedContext
  | CompletedContext;
