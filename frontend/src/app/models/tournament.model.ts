export type TournamentMode = 'bracket' | 'score' | 'multivote' | 'condorcet' | 'swiss' | 'elo';
export type TournamentStatus = 'draft' | 'active' | 'completed' | 'cancelled';

export interface TournamentEntry {
  id: string;
  option_id: string;
  seed: number | null;
  option_snapshot: Record<string, unknown>;
}

export type VoteStatus = 'active' | 'superseded';

export interface Vote {
  id: string;
  voter_label: string;
  round: number | null;
  submitted_at: string;
  payload: Record<string, unknown>;
  status: VoteStatus;
  superseded_at: string | null;
}

export interface RankingEntry {
  rank: number;
  entry_id: string;
  [key: string]: unknown;
}

export interface Result {
  winner_ids: string[];
  ranking: RankingEntry[];
  metadata: Record<string, unknown>;
  computed_at: string;
}

export interface Tournament {
  id: string;
  name: string;
  description: string;
  mode: TournamentMode;
  status: TournamentStatus;
  config: Record<string, unknown>;
  version: number;
  selected_option_ids: string[];
  entries: TournamentEntry[];
  state: Record<string, unknown>;
  votes: Vote[];
  result: Result | null;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
}
