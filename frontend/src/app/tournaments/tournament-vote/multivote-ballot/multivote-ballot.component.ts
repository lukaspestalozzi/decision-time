import { Component, effect, input, output } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatCardModule } from '@angular/material/card';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { Tournament } from '../../../models/tournament.model';
import { BallotContext } from '../../../models/vote-context.model';

@Component({
  selector: 'app-multivote-ballot',
  imports: [FormsModule, MatCardModule, MatButtonModule, MatIconModule],
  templateUrl: './multivote-ballot.component.html',
  styleUrl: './multivote-ballot.component.scss',
})
export class MultivoteBallotComponent {
  context = input.required<BallotContext>();
  tournament = input.required<Tournament>();
  /** If provided, pre-fills the counters and flips the submit button to "Update". */
  initialAllocations = input<Record<string, number> | null>(null);
  vote = output<Record<string, unknown>>();

  allocations: Record<string, number> = {};

  constructor() {
    effect(() => {
      const initial = this.initialAllocations();
      if (initial) {
        this.allocations = { ...initial };
      }
    });
  }

  get isEditing(): boolean {
    return this.initialAllocations() !== null;
  }

  get entries(): { id: string; name: string }[] {
    return this.context().entries.map((e) => {
      const id = e['id'] as string;
      const entry = this.tournament().entries.find((te) => te.id === id);
      return { id, name: (entry?.option_snapshot?.['name'] as string) ?? 'Unknown' };
    });
  }

  get totalVotes(): number {
    return (this.tournament().state?.['total_votes'] as number) ?? 0;
  }

  get usedVotes(): number {
    return Object.values(this.allocations).reduce((sum, v) => sum + (v || 0), 0);
  }

  get remainingVotes(): number {
    return this.totalVotes - this.usedVotes;
  }

  get isValid(): boolean {
    return this.usedVotes === this.totalVotes;
  }

  increment(entryId: string): void {
    if (this.remainingVotes <= 0) return;
    this.allocations[entryId] = (this.allocations[entryId] || 0) + 1;
  }

  decrement(entryId: string): void {
    if ((this.allocations[entryId] || 0) <= 0) return;
    this.allocations[entryId] = (this.allocations[entryId] || 0) - 1;
  }

  submit(): void {
    if (!this.isValid) return;
    const allocs = Object.entries(this.allocations)
      .filter(([, v]) => v > 0)
      .map(([entry_id, votes]) => ({ entry_id, votes }));
    this.vote.emit({ allocations: allocs });
  }
}
