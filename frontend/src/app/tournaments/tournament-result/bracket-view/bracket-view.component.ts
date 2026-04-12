import { Component, input } from '@angular/core';
import { MatCardModule } from '@angular/material/card';
import { Tournament } from '../../../models/tournament.model';

interface Matchup {
  entry_a_id: string;
  entry_b_id: string | null;
  winner_id: string | null;
  is_bye: boolean;
}

interface Round {
  round_number: number;
  name: string;
  matchups: Matchup[];
}

@Component({
  selector: 'app-bracket-view',
  imports: [MatCardModule],
  templateUrl: './bracket-view.component.html',
  styleUrl: './bracket-view.component.scss',
})
export class BracketViewComponent {
  tournament = input.required<Tournament>();

  get rounds(): Round[] {
    return (this.tournament().state?.['rounds'] as Round[]) ?? [];
  }

  getEntryName(entryId: string | null): string {
    if (!entryId) return 'BYE';
    const entry = this.tournament().entries.find((e) => e.id === entryId);
    return (entry?.option_snapshot?.['name'] as string) ?? '?';
  }

  isWinner(matchup: Matchup, entryId: string | null): boolean {
    return !!entryId && matchup.winner_id === entryId;
  }
}
