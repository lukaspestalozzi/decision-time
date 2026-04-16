import { Component, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatDialogModule, MatDialogRef } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatButtonModule } from '@angular/material/button';
import { MatChipsModule } from '@angular/material/chips';
import { MatIconModule } from '@angular/material/icon';
import { MatAutocompleteModule, MatAutocompleteSelectedEvent } from '@angular/material/autocomplete';
import { COMMA, ENTER } from '@angular/cdk/keycodes';
import { MatChipInputEvent } from '@angular/material/chips';
import { ApiService } from '../../services/api.service';

export interface BulkImportResult {
  names: string[];
  tags: string[];
}

@Component({
  selector: 'app-bulk-import-dialog',
  imports: [FormsModule, MatDialogModule, MatFormFieldModule, MatInputModule, MatButtonModule, MatChipsModule, MatIconModule, MatAutocompleteModule],
  templateUrl: './bulk-import-dialog.component.html',
  styleUrl: './bulk-import-dialog.component.scss',
})
export class BulkImportDialogComponent {
  readonly separatorKeyCodes = [ENTER, COMMA] as const;
  rawText = signal('');
  tags = signal<string[]>([]);
  allTags = signal<string[]>([]);
  tagInput = signal('');

  parsedNames = computed(() => {
    return this.rawText()
      .split('\n')
      .map((s) => s.trim())
      .filter((s) => s.length > 0);
  });

  filteredTags = computed(() => {
    const input = this.tagInput().toLowerCase();
    const current = this.tags();
    return this.allTags().filter(t => !current.includes(t) && t.toLowerCase().includes(input));
  });

  private dialogRef = inject(MatDialogRef<BulkImportDialogComponent>);
  private api = inject(ApiService);

  constructor() {
    this.api.listTags().subscribe({
      next: (tags) => this.allTags.set(tags),
      error: () => { /* tags are optional, ignore errors */ },
    });
  }

  addTag(event: MatChipInputEvent): void {
    const value = (event.value || '').trim();
    if (value && !this.tags().includes(value)) {
      this.tags.update((t) => [...t, value]);
    }
    event.chipInput.clear();
    this.tagInput.set('');
  }

  selectTag(event: MatAutocompleteSelectedEvent): void {
    const value = event.option.viewValue;
    if (value && !this.tags().includes(value)) {
      this.tags.update((t) => [...t, value]);
    }
    this.tagInput.set('');
  }

  removeTag(tag: string): void {
    this.tags.update((t) => t.filter((x) => x !== tag));
  }

  submit(): void {
    // Commit any tag the user typed but didn't confirm with Enter/comma — otherwise
    // clicking Import would silently drop it.
    this.commitPendingTag();
    const names = this.parsedNames();
    if (names.length === 0) return;
    this.dialogRef.close({ names, tags: this.tags() } as BulkImportResult);
  }

  private commitPendingTag(): void {
    const value = this.tagInput().trim();
    if (value && !this.tags().includes(value)) {
      this.tags.update((t) => [...t, value]);
    }
    this.tagInput.set('');
  }

  cancel(): void {
    this.dialogRef.close();
  }
}
