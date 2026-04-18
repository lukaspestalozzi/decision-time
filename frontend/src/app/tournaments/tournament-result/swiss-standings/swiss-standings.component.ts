import { Component, computed, input } from '@angular/core';
import { MatTableModule } from '@angular/material/table';
import { MatIconModule } from '@angular/material/icon';
import { Tournament } from '../../../models/tournament.model';

interface SwissStandingRow {
  rank: number;
  name: string;
  points: number;
  record: string;
  buchholz: number;
  isWinner: boolean;
}

@Component({
  selector: 'app-swiss-standings',
  imports: [MatTableModule, MatIconModule],
  templateUrl: './swiss-standings.component.html',
  styleUrl: './swiss-standings.component.scss',
})
export class SwissStandingsComponent {
  tournament = input.required<Tournament>();

  rows = computed<SwissStandingRow[]>(() => {
    const t = this.tournament();
    const result = t.result;
    if (!result) return [];
    const winners = new Set(result.winner_ids);
    return result.ranking.map((r) => ({
      rank: r['rank'] as number,
      name: this.nameOf(r['entry_id'] as string),
      points: (r['points'] as number) ?? 0,
      record: `${r['wins'] ?? 0}-${r['draws'] ?? 0}-${r['losses'] ?? 0}`,
      buchholz: (r['buchholz'] as number) ?? 0,
      isWinner: winners.has(r['entry_id'] as string),
    }));
  });

  readonly displayedColumns = ['rank', 'name', 'points', 'record', 'buchholz'];

  private nameOf(entryId: string): string {
    const e = this.tournament().entries.find((e) => e.id === entryId);
    return (e?.option_snapshot?.['name'] as string) ?? entryId;
  }
}
