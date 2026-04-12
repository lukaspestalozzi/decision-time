import { Component, inject, OnInit, output, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatInputModule } from '@angular/material/input';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatChipsModule } from '@angular/material/chips';
import { MatAutocompleteModule } from '@angular/material/autocomplete';
import { MatIconModule } from '@angular/material/icon';
import { ApiService } from '../../services/api.service';

export interface SearchCriteria {
  q: string;
  tagsAll: string;
  tagsAny: string;
}

@Component({
  selector: 'app-option-search',
  imports: [
    FormsModule,
    MatInputModule,
    MatFormFieldModule,
    MatChipsModule,
    MatAutocompleteModule,
    MatIconModule,
  ],
  templateUrl: './option-search.component.html',
  styleUrl: './option-search.component.scss',
})
export class OptionSearchComponent implements OnInit {
  private api = inject(ApiService);

  searchChange = output<SearchCriteria>();

  query = signal('');
  availableTags = signal<string[]>([]);
  selectedTagsAll = signal<string[]>([]);
  selectedTagsAny = signal<string[]>([]);
  tagInput = signal('');
  tagMode = signal<'all' | 'any'>('any');

  filteredTags = signal<string[]>([]);

  ngOnInit(): void {
    this.api.listTags().subscribe({
      next: (tags) => this.availableTags.set(tags),
    });
  }

  onTagInputChange(value: string): void {
    this.tagInput.set(value);
    const lower = value.toLowerCase();
    const selected = [...this.selectedTagsAll(), ...this.selectedTagsAny()];
    this.filteredTags.set(
      this.availableTags().filter(
        (t) => t.toLowerCase().includes(lower) && !selected.includes(t),
      ),
    );
  }

  addTag(tag: string): void {
    if (this.tagMode() === 'all') {
      if (!this.selectedTagsAll().includes(tag)) {
        this.selectedTagsAll.update((tags) => [...tags, tag]);
      }
    } else {
      if (!this.selectedTagsAny().includes(tag)) {
        this.selectedTagsAny.update((tags) => [...tags, tag]);
      }
    }
    this.tagInput.set('');
    this.filteredTags.set([]);
    this.emitSearch();
  }

  removeTagAll(tag: string): void {
    this.selectedTagsAll.update((tags) => tags.filter((t) => t !== tag));
    this.emitSearch();
  }

  removeTagAny(tag: string): void {
    this.selectedTagsAny.update((tags) => tags.filter((t) => t !== tag));
    this.emitSearch();
  }

  toggleMode(): void {
    this.tagMode.update((m) => (m === 'all' ? 'any' : 'all'));
  }

  onQueryChange(value: string): void {
    this.query.set(value);
    this.emitSearch();
  }

  emitSearch(): void {
    this.searchChange.emit({
      q: this.query(),
      tagsAll: this.selectedTagsAll().join(','),
      tagsAny: this.selectedTagsAny().join(','),
    });
  }
}
