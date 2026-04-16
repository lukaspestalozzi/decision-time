import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatCardModule } from '@angular/material/card';
import { MatChipsModule } from '@angular/material/chips';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { ApiService } from '../../services/api.service';
import { NotificationService } from '../../services/notification.service';
import { Option } from '../../models/option.model';
import { DecisionSpinnerComponent } from '../decision-spinner/decision-spinner.component';

type Phase = 'setup' | 'spinning' | 'result';

@Component({
  selector: 'app-random-page',
  imports: [
    RouterLink,
    MatFormFieldModule,
    MatInputModule,
    MatButtonModule,
    MatIconModule,
    MatCardModule,
    MatChipsModule,
    MatProgressSpinnerModule,
    DecisionSpinnerComponent,
  ],
  templateUrl: './random-page.component.html',
  styleUrl: './random-page.component.scss',
})
export class RandomPageComponent implements OnInit {
  private api = inject(ApiService);
  private notify = inject(NotificationService);

  allOptions = signal<Option[]>([]);
  allTags = signal<string[]>([]);
  loading = signal(true);
  selectedOptionIds = signal<Set<string>>(new Set());
  searchQuery = signal('');
  selectedTag = signal<string | null>(null);
  phase = signal<Phase>('setup');
  winner = signal<Option | null>(null);

  hasEnoughOptions = computed(() => this.allOptions().length >= 2);

  filteredOptions = computed(() => {
    const query = this.searchQuery().toLowerCase().trim();
    const tag = this.selectedTag();
    return this.allOptions().filter(opt => {
      const matchesQuery = !query
        || opt.name.toLowerCase().includes(query)
        || opt.tags.some(t => t.toLowerCase().includes(query));
      const matchesTag = !tag || opt.tags.includes(tag);
      return matchesQuery && matchesTag;
    });
  });

  selectedOptions = computed(() => {
    const ids = this.selectedOptionIds();
    return this.allOptions().filter(opt => ids.has(opt.id));
  });

  isValid = computed(() => this.selectedOptionIds().size >= 2);

  ngOnInit(): void {
    this.loadOptions();
  }

  private loadOptions(): void {
    this.loading.set(true);
    this.api.listOptions().subscribe({
      next: (options) => {
        this.allOptions.set(options);
        this.loading.set(false);
      },
      error: () => {
        this.loading.set(false);
        this.notify.showError('Failed to load options.');
      },
    });
    this.api.listTags().subscribe({
      next: (tags) => this.allTags.set(tags),
      error: () => { /* tags are optional, ignore errors */ },
    });
  }

  toggleOption(optionId: string): void {
    const current = new Set(this.selectedOptionIds());
    if (current.has(optionId)) {
      current.delete(optionId);
    } else {
      current.add(optionId);
    }
    this.selectedOptionIds.set(current);
  }

  isSelected(optionId: string): boolean {
    return this.selectedOptionIds().has(optionId);
  }

  removeOption(optionId: string): void {
    const current = new Set(this.selectedOptionIds());
    current.delete(optionId);
    this.selectedOptionIds.set(current);
  }

  selectAllFiltered(): void {
    const current = new Set(this.selectedOptionIds());
    for (const opt of this.filteredOptions()) {
      current.add(opt.id);
    }
    this.selectedOptionIds.set(current);
  }

  onSearchInput(event: Event): void {
    this.searchQuery.set((event.target as HTMLInputElement).value);
  }

  toggleTag(tag: string): void {
    this.selectedTag.set(this.selectedTag() === tag ? null : tag);
  }

  decide(): void {
    if (!this.isValid()) return;
    this.winner.set(null);
    this.phase.set('spinning');
  }

  onWinnerSelected(option: Option): void {
    this.winner.set(option);
    this.phase.set('result');
  }

  spinAgain(): void {
    this.winner.set(null);
    this.phase.set('spinning');
  }

  newRound(): void {
    this.winner.set(null);
    this.selectedOptionIds.set(new Set());
    this.phase.set('setup');
  }
}
