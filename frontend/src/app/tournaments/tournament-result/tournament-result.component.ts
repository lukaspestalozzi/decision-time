import { Component, inject, input, OnInit, signal } from '@angular/core';
import { ActivatedRoute } from '@angular/router';
import { MatCardModule } from '@angular/material/card';
import { MatChipsModule } from '@angular/material/chips';
import { MatIconModule } from '@angular/material/icon';
import { MatTableModule } from '@angular/material/table';
import { Tournament } from '../../models/tournament.model';
import { ApiService } from '../../services/api.service';
import { BracketViewComponent } from './bracket-view/bracket-view.component';
import { PairwiseMatrixComponent } from './pairwise-matrix/pairwise-matrix.component';
import { SwissStandingsComponent } from './swiss-standings/swiss-standings.component';

@Component({
  selector: 'app-tournament-result',
  imports: [
    MatCardModule,
    MatChipsModule,
    MatIconModule,
    MatTableModule,
    BracketViewComponent,
    PairwiseMatrixComponent,
    SwissStandingsComponent,
  ],
  templateUrl: './tournament-result.component.html',
  styleUrl: './tournament-result.component.scss',
})
export class TournamentResultComponent implements OnInit {
  private route = inject(ActivatedRoute);
  private api = inject(ApiService);

  tournament = input<Tournament | undefined>();
  loadedTournament = signal<Tournament | null>(null);

  get t(): Tournament | null {
    return this.tournament() ?? this.loadedTournament();
  }

  ngOnInit(): void {
    if (!this.tournament()) {
      const id = this.route.snapshot.paramMap.get('id');
      if (id) {
        this.api.getTournament(id).subscribe((t) => this.loadedTournament.set(t));
      }
    }
  }

  getEntryName(entryId: string): string {
    const entry = this.t?.entries.find((e) => e.id === entryId);
    return (entry?.option_snapshot?.['name'] as string) ?? entryId;
  }

  get winnerNames(): string[] {
    if (!this.t?.result) return [];
    return this.t.result.winner_ids.map((id) => this.getEntryName(id));
  }

  get isTie(): boolean {
    return (this.t?.result?.winner_ids.length ?? 0) > 1;
  }

  get rankingRows(): { rank: number; name: string; detail: string }[] {
    if (!this.t?.result) return [];
    return this.t.result.ranking.map((r) => ({
      rank: r.rank,
      name: this.getEntryName(r.entry_id),
      detail: this.getRankDetail(r),
    }));
  }

  private getRankDetail(r: Record<string, unknown>): string {
    if ('mean_rating' in r) {
      const rating = Math.round(r['mean_rating'] as number);
      if ('wins' in r && 'losses' in r) {
        return `Rating: ${rating} (W: ${r['wins']}, L: ${r['losses']})`;
      }
      return `Rating: ${rating}`;
    }
    if ('average_score' in r) return `Avg: ${(r['average_score'] as number).toFixed(2)}`;
    if ('total_votes' in r) return `Votes: ${r['total_votes']}`;
    if ('wins' in r) return `Wins: ${r['wins']}`;
    return '';
  }

  displayedColumns = ['rank', 'name', 'detail'];
}
