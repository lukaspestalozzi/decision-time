import { Component, effect, input, output } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatCardModule } from '@angular/material/card';
import { MatButtonModule } from '@angular/material/button';
import { MatSliderModule } from '@angular/material/slider';
import { Tournament } from '../../../models/tournament.model';
import { BallotContext } from '../../../models/vote-context.model';

@Component({
  selector: 'app-score-ballot',
  imports: [FormsModule, MatCardModule, MatButtonModule, MatSliderModule],
  templateUrl: './score-ballot.component.html',
  styleUrl: './score-ballot.component.scss',
})
export class ScoreBallotComponent {
  context = input.required<BallotContext>();
  tournament = input.required<Tournament>();
  /** If provided, pre-fills the sliders and flips the submit button to "Update". */
  initialScores = input<Record<string, number> | null>(null);
  vote = output<Record<string, unknown>>();

  scores: Record<string, number> = {};

  constructor() {
    effect(() => {
      const initial = this.initialScores();
      if (initial) {
        this.scores = { ...initial };
      }
    });
  }

  get isEditing(): boolean {
    return this.initialScores() !== null;
  }

  get entries(): { id: string; name: string }[] {
    return this.context().entries.map((e) => {
      const id = e['id'] as string;
      const entry = this.tournament().entries.find((te) => te.id === id);
      return { id, name: (entry?.option_snapshot?.['name'] as string) ?? 'Unknown' };
    });
  }

  get minScore(): number {
    return (this.tournament().config?.['min_score'] as number) ?? 1;
  }

  get maxScore(): number {
    return (this.tournament().config?.['max_score'] as number) ?? 5;
  }

  get allScored(): boolean {
    return this.entries.every((e) => this.scores[e.id] !== undefined);
  }

  submit(): void {
    if (!this.allScored) return;
    this.vote.emit({
      scores: this.entries.map((e) => ({ entry_id: e.id, score: this.scores[e.id] })),
    });
  }
}
