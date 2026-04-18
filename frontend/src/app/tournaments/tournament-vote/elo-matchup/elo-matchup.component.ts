import { Component, input, output } from '@angular/core';
import { DecimalPipe } from '@angular/common';
import { MatCardModule } from '@angular/material/card';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { Tournament } from '../../../models/tournament.model';
import { EloMatchupContext } from '../../../models/vote-context.model';

@Component({
  selector: 'app-elo-matchup',
  imports: [DecimalPipe, MatCardModule, MatProgressBarModule],
  templateUrl: './elo-matchup.component.html',
  styleUrl: './elo-matchup.component.scss',
})
export class EloMatchupComponent {
  context = input.required<EloMatchupContext>();
  tournament = input.required<Tournament>();
  vote = output<Record<string, unknown>>();

  getEntryName(entry: Record<string, unknown>): string {
    const id = entry['id'] as string;
    const e = this.tournament().entries.find((e) => e.id === id);
    return (e?.option_snapshot?.['name'] as string) ?? 'Unknown';
  }

  get progress(): number {
    const ctx = this.context();
    return (ctx.matchup_number / ctx.total_matchups) * 100;
  }

  select(entryId: string): void {
    this.vote.emit({ matchup_id: this.context().matchup_id, winner_entry_id: entryId });
  }
}
