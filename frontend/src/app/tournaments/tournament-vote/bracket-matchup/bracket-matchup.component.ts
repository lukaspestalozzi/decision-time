import { Component, input, output } from '@angular/core';
import { MatCardModule } from '@angular/material/card';
import { Tournament } from '../../../models/tournament.model';
import { BracketMatchupContext } from '../../../models/vote-context.model';

@Component({
  selector: 'app-bracket-matchup',
  imports: [MatCardModule],
  templateUrl: './bracket-matchup.component.html',
  styleUrl: './bracket-matchup.component.scss',
})
export class BracketMatchupComponent {
  context = input.required<BracketMatchupContext>();
  tournament = input.required<Tournament>();
  vote = output<Record<string, unknown>>();

  getEntryName(entry: Record<string, unknown>): string {
    const id = entry['id'] as string;
    const e = this.tournament().entries.find((e) => e.id === id);
    return (e?.option_snapshot?.['name'] as string) ?? 'Unknown';
  }

  select(entryId: string): void {
    this.vote.emit({ matchup_id: this.context().matchup_id, winner_entry_id: entryId });
  }
}
