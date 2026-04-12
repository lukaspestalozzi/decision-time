import { Component, inject, OnInit, signal } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { ApiService } from '../../services/api.service';
import { NotificationService } from '../../services/notification.service';
import { Tournament } from '../../models/tournament.model';
import { VoteContext } from '../../models/vote-context.model';
import { VoterSelectorComponent } from '../../shared/voter-selector/voter-selector.component';
import { BracketMatchupComponent } from './bracket-matchup/bracket-matchup.component';
import { CondorcetMatchupComponent } from './condorcet-matchup/condorcet-matchup.component';
import { ScoreBallotComponent } from './score-ballot/score-ballot.component';
import { MultivoteBallotComponent } from './multivote-ballot/multivote-ballot.component';
import { AlreadyVotedComponent } from './already-voted/already-voted.component';
import { TournamentResultComponent } from '../tournament-result/tournament-result.component';

@Component({
  selector: 'app-tournament-vote',
  imports: [
    MatProgressSpinnerModule,
    VoterSelectorComponent,
    BracketMatchupComponent,
    CondorcetMatchupComponent,
    ScoreBallotComponent,
    MultivoteBallotComponent,
    AlreadyVotedComponent,
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

  get tournamentId(): string {
    return this.route.snapshot.paramMap.get('id')!;
  }

  get isBracket(): boolean {
    return this.tournament()?.mode === 'bracket';
  }

  get voterCount(): number {
    const config = this.tournament()?.config;
    return (config?.['voter_count'] as number) ?? 1;
  }

  ngOnInit(): void {
    const voterParam = this.route.snapshot.queryParamMap.get('voter');
    if (voterParam) {
      this.currentVoter.set(voterParam);
    }
    this.loadTournament();
  }

  private loadTournament(): void {
    this.api.getTournament(this.tournamentId).subscribe({
      next: (t) => {
        this.tournament.set(t);
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
    this.loadVoteContext();
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
