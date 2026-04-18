import { Component, computed, input, output } from '@angular/core';
import { MatCardModule } from '@angular/material/card';
import { MatButtonModule } from '@angular/material/button';
import { MatTableModule } from '@angular/material/table';
import { Tournament } from '../../../models/tournament.model';
import { SwissMatchupContext, SwissStandingEntry } from '../../../models/vote-context.model';

@Component({
  selector: 'app-swiss-matchup',
  imports: [MatCardModule, MatButtonModule, MatTableModule],
  templateUrl: './swiss-matchup.component.html',
  styleUrl: './swiss-matchup.component.scss',
})
export class SwissMatchupComponent {
  context = input.required<SwissMatchupContext>();
  tournament = input.required<Tournament>();
  vote = output<Record<string, unknown>>();

  standingsRows = computed<(SwissStandingEntry & { name: string })[]>(() =>
    this.context().standings.map((s) => ({ ...s, name: this.entryNameById(s.entry_id) })),
  );

  readonly displayedColumns = ['rank', 'name', 'points', 'record'];

  getEntryName(entry: Record<string, unknown>): string {
    return this.entryNameById(entry['id'] as string);
  }

  private entryNameById(id: string): string {
    const e = this.tournament().entries.find((e) => e.id === id);
    return (e?.option_snapshot?.['name'] as string) ?? 'Unknown';
  }

  pick(result: 'a_wins' | 'b_wins' | 'draw'): void {
    this.vote.emit({ matchup_id: this.context().matchup_id, result });
  }
}
