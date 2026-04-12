import { Component, input } from '@angular/core';
import { MatTableModule } from '@angular/material/table';
import { Tournament } from '../../../models/tournament.model';

@Component({
  selector: 'app-pairwise-matrix',
  imports: [MatTableModule],
  templateUrl: './pairwise-matrix.component.html',
  styleUrl: './pairwise-matrix.component.scss',
})
export class PairwiseMatrixComponent {
  tournament = input.required<Tournament>();

  get entryNames(): string[] {
    return this.tournament().entries.map(
      (e) => (e.option_snapshot?.['name'] as string) ?? '?',
    );
  }

  get matrix(): number[][] {
    return (this.tournament().result?.metadata?.['pairwise_matrix'] as number[][]) ?? [];
  }

  get displayedColumns(): string[] {
    return ['name', ...this.entryNames.map((_, i) => `col${i}`)];
  }

  getCellClass(row: number, col: number): string {
    if (row === col) return 'diagonal';
    const val = this.matrix[row]?.[col] ?? 0;
    const opp = this.matrix[col]?.[row] ?? 0;
    if (val > opp) return 'win';
    if (val < opp) return 'loss';
    return 'tie';
  }
}
