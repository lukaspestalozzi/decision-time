import { Component, input, output } from '@angular/core';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatSelectModule } from '@angular/material/select';

@Component({
  selector: 'app-voter-selector',
  imports: [MatFormFieldModule, MatSelectModule],
  templateUrl: './voter-selector.component.html',
  styleUrl: './voter-selector.component.scss',
})
export class VoterSelectorComponent {
  voterCount = input.required<number>();
  currentVoter = input<string>('Voter 1');
  voterChange = output<string>();

  get voters(): string[] {
    return Array.from({ length: this.voterCount() }, (_, i) => `Voter ${i + 1}`);
  }

  onSelect(voter: string): void {
    this.voterChange.emit(voter);
  }
}
