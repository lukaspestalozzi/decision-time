import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { ApiService } from '../../services/api.service';
import { NotificationService } from '../../services/notification.service';
import { Tournament, Vote } from '../../models/tournament.model';
import { VoteContext } from '../../models/vote-context.model';
import { VoterSelectorComponent } from '../../shared/voter-selector/voter-selector.component';
import { BracketMatchupComponent } from './bracket-matchup/bracket-matchup.component';
import { CondorcetMatchupComponent } from './condorcet-matchup/condorcet-matchup.component';
import { SwissMatchupComponent } from './swiss-matchup/swiss-matchup.component';
import { EloMatchupComponent } from './elo-matchup/elo-matchup.component';
import { ScoreBallotComponent } from './score-ballot/score-ballot.component';
import { MultivoteBallotComponent } from './multivote-ballot/multivote-ballot.component';
import { AlreadyVotedComponent } from './already-voted/already-voted.component';
import { BallotSummaryComponent } from './ballot-summary/ballot-summary.component';
import { TournamentResultComponent } from '../tournament-result/tournament-result.component';

@Component({
  selector: 'app-tournament-vote',
  imports: [
    MatProgressSpinnerModule,
    VoterSelectorComponent,
    BracketMatchupComponent,
    CondorcetMatchupComponent,
    SwissMatchupComponent,
    EloMatchupComponent,
    ScoreBallotComponent,
    MultivoteBallotComponent,
    AlreadyVotedComponent,
    BallotSummaryComponent,
    TournamentResultComponent,
  ],
  templateUrl: './tournament-vote.component.html',
  styleUrl: './tournament-vote.component.scss',
})
export class TournamentVoteComponent implements OnInit {
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  private api = inject(ApiService);
  private notify = inject(NotificationService);

  tournament = signal<Tournament | null>(null);
  voteContext = signal<VoteContext | null>(null);
  currentVoter = signal('default');
  loading = signal(false);
  /** Pre-captured scores/allocations preserved across the undo call for prefilling. */
  initialScores = signal<Record<string, number> | null>(null);
  initialAllocations = signal<Record<string, number> | null>(null);
  private explicitVoterParam = false;

  /** The current voter's active ballot, if any — used to render ballot-summary. */
  currentVoterVote = computed<Vote | null>(() => {
    const t = this.tournament();
    if (!t) return null;
    const mine = t.votes.filter((v) => v.voter_label === this.currentVoter() && v.status === 'active');
    if (mine.length === 0) return null;
    return mine.reduce((a, b) => (a.submitted_at > b.submitted_at ? a : b));
  });

  get tournamentId(): string {
    return this.route.snapshot.paramMap.get('id')!;
  }

  get isBracket(): boolean {
    return this.tournament()?.mode === 'bracket';
  }

  get voterLabels(): string[] {
    const config = this.tournament()?.config;
    const labels = config?.['voter_labels'];
    return Array.isArray(labels) && labels.length > 0 ? (labels as string[]) : ['default'];
  }

  ngOnInit(): void {
    const voterParam = this.route.snapshot.queryParamMap.get('voter');
    if (voterParam) {
      this.currentVoter.set(voterParam);
      this.explicitVoterParam = true;
    }
    this.loadTournament();
  }

  private loadTournament(): void {
    this.api.getTournament(this.tournamentId).subscribe({
      next: (t) => {
        this.tournament.set(t);
        // If no explicit voter param, default to the first configured voter label
        if (!this.explicitVoterParam) {
          this.currentVoter.set(this.voterLabels[0]);
        }
        this.loadVoteContext();
      },
      error: () => this.notify.showError('Tournament not found'),
    });
  }

  loadVoteContext(): void {
    this.loading.set(true);
    this.api.getVoteContext(this.tournamentId, this.currentVoter()).subscribe({
      next: (ctx) => {
        this.voteContext.set(ctx);
        this.loading.set(false);
      },
      error: () => {
        this.notify.showError('Failed to load vote context');
        this.loading.set(false);
      },
    });
  }

  onVoterChange(voter: string): void {
    this.currentVoter.set(voter);
    this.initialScores.set(null);
    this.initialAllocations.set(null);
    this.loadVoteContext();
  }

  /** Invoked when the voter clicks "Edit my ballot" on the summary screen.
   *
   * Captures the previous ballot's values from memory BEFORE calling undo (which
   * marks the Vote record SUPERSEDED server-side), so the re-opened ballot can
   * be pre-filled for a smooth UX.
   */
  onEditBallot(): void {
    const t = this.tournament();
    if (!t) return;
    const myVote = this.currentVoterVote();
    // Capture scores/allocations up-front
    if (myVote) {
      const scores = myVote.payload['scores'];
      if (Array.isArray(scores)) {
        this.initialScores.set(
          Object.fromEntries((scores as { entry_id: string; score: number }[]).map((s) => [s.entry_id, s.score])),
        );
      }
      const allocs = myVote.payload['allocations'];
      if (Array.isArray(allocs)) {
        this.initialAllocations.set(
          Object.fromEntries(
            (allocs as { entry_id: string; votes: number }[]).map((a) => [a.entry_id, a.votes]),
          ),
        );
      }
    }
    this.loading.set(true);
    this.api.undoVote(this.tournamentId, { version: t.version, voter_label: this.currentVoter() }).subscribe({
      next: (resp) => {
        this.tournament.set(resp.tournament);
        this.voteContext.set(resp.vote_context);
        this.loading.set(false);
      },
      error: (err) => {
        this.loading.set(false);
        this.initialScores.set(null);
        this.initialAllocations.set(null);
        const msg = err?.error?.error?.message ?? 'Failed to start edit';
        this.notify.showError(msg);
        this.loadTournament();
      },
    });
  }

  onVote(payload: Record<string, unknown>): void {
    const t = this.tournament();
    if (!t) return;
    this.loading.set(true);
    this.api
      .submitVote(this.tournamentId, {
        version: t.version,
        voter_label: this.currentVoter(),
        payload,
      })
      .subscribe({
        next: (updated) => {
          this.tournament.set(updated);
          this.initialScores.set(null);
          this.initialAllocations.set(null);
          this.loadVoteContext();
        },
        error: (err) => {
          this.loading.set(false);
          const msg = err?.error?.error?.message ?? 'Vote failed';
          this.notify.showError(msg);
          this.loadTournament();
        },
      });
  }
}
