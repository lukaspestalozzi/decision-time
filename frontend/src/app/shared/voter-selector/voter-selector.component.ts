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
  voterLabels = input.required<string[]>();
  currentVoter = input<string>('');
  voterChange = output<string>();

  onSelect(voter: string): void {
    this.voterChange.emit(voter);
  }
}
