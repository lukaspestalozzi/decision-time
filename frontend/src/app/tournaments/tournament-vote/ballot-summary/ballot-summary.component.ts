import { Component, computed, input, output, signal, OnDestroy } from '@angular/core';
import { MatCardModule } from '@angular/material/card';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { Tournament, Vote } from '../../../models/tournament.model';

/**
 * Displayed to a voter after they submit a ballot (Score/Multivote modes).
 *
 * Shows a read-only summary of their submitted scores/allocations, an overall
 * submission progress count, an optional cool-off countdown when the tournament
 * is about to finalize, and an "Edit my ballot" action.
 */
@Component({
  selector: 'app-ballot-summary',
  imports: [MatCardModule, MatButtonModule, MatIconModule],
  templateUrl: './ballot-summary.component.html',
  styleUrl: './ballot-summary.component.scss',
})
export class BallotSummaryComponent implements OnDestroy {
  tournament = input.required<Tournament>();
  voterLabel = input.required<string>();
  editClicked = output<void>();

  private tickHandle: ReturnType<typeof setInterval> | null = null;
  private nowMs = signal(Date.now());

  constructor() {
    // Update the countdown every second when a cool-off is pending.
    this.tickHandle = setInterval(() => this.nowMs.set(Date.now()), 1000);
  }

  ngOnDestroy(): void {
    if (this.tickHandle) clearInterval(this.tickHandle);
  }

  /** Find this voter's most recent active vote. */
  myVote = computed<Vote | null>(() => {
    const votes = this.tournament().votes.filter(
      (v) => v.voter_label === this.voterLabel() && v.status === 'active',
    );
    if (votes.length === 0) return null;
    return votes.reduce((a, b) => (a.submitted_at > b.submitted_at ? a : b));
  });

  /** Display lines e.g. "Option A: 5" */
  summaryRows = computed<{ name: string; value: string }[]>(() => {
    const vote = this.myVote();
    if (!vote) return [];
    const entries = this.tournament().entries;
    const entryName = (id: string): string => {
      const entry = entries.find((e) => e.id === id);
      return (entry?.option_snapshot?.['name'] as string) ?? id;
    };
    const payload = vote.payload;
    if (Array.isArray(payload['scores'])) {
      return (payload['scores'] as { entry_id: string; score: number }[]).map((s) => ({
        name: entryName(s.entry_id),
        value: String(s.score),
      }));
    }
    if (Array.isArray(payload['allocations'])) {
      return (payload['allocations'] as { entry_id: string; votes: number }[]).map((a) => ({
        name: entryName(a.entry_id),
        value: `${a.votes} vote${a.votes === 1 ? '' : 's'}`,
      }));
    }
    return [];
  });

  /** Count of active ballots from all voters. */
  ballotsSubmitted = computed<number>(() => {
    const labels = new Set(
      this.tournament()
        .votes.filter((v) => v.status === 'active')
        .map((v) => v.voter_label),
    );
    return labels.size;
  });

  ballotsRequired = computed<number>(() => {
    const labels = this.tournament().config['voter_labels'];
    return Array.isArray(labels) ? labels.length : 1;
  });

  /** Seconds remaining until cool-off expires, or null when no cool-off is active. */
  secondsUntilFinalize = computed<number | null>(() => {
    const endsAt = this.tournament().cool_off_ends_at;
    if (!endsAt) return null;
    const remaining = Math.ceil((new Date(endsAt).getTime() - this.nowMs()) / 1000);
    return remaining > 0 ? remaining : 0;
  });

  /** True if the tournament owner allows voters to edit. */
  canEdit = computed<boolean>(() => {
    return this.tournament().config['allow_undo'] !== false;
  });

  onEditClick(): void {
    this.editClicked.emit();
  }
}
