import { Component, computed, input, output } from '@angular/core';
import { MatCardModule } from '@angular/material/card';
import { MatChipsModule } from '@angular/material/chips';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { Option } from '../../models/option.model';

@Component({
  selector: 'app-option-card',
  imports: [MatCardModule, MatChipsModule, MatButtonModule, MatIconModule],
  templateUrl: './option-card.component.html',
  styleUrl: './option-card.component.scss',
})
export class OptionCardComponent {
  option = input.required<Option>();

  edit = output<Option>();
  delete = output<Option>();

  truncatedDescription = computed(() => {
    const desc = this.option().description;
    if (!desc) return '';
    return desc.length > 120 ? desc.substring(0, 120) + '...' : desc;
  });

  onEdit(): void {
    this.edit.emit(this.option());
  }

  onDelete(): void {
    this.delete.emit(this.option());
  }
}
