import { Component, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatDialogModule, MatDialogRef } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatButtonModule } from '@angular/material/button';
import { MatChipsModule } from '@angular/material/chips';
import { MatIconModule } from '@angular/material/icon';
import { COMMA, ENTER } from '@angular/cdk/keycodes';
import { MatChipInputEvent } from '@angular/material/chips';

export interface BulkImportResult {
  names: string[];
  tags: string[];
}

@Component({
  selector: 'app-bulk-import-dialog',
  imports: [FormsModule, MatDialogModule, MatFormFieldModule, MatInputModule, MatButtonModule, MatChipsModule, MatIconModule],
  templateUrl: './bulk-import-dialog.component.html',
  styleUrl: './bulk-import-dialog.component.scss',
})
export class BulkImportDialogComponent {
  readonly separatorKeyCodes = [ENTER, COMMA] as const;
  rawText = signal('');
  tags = signal<string[]>([]);

  parsedNames = computed(() => {
    return this.rawText()
      .split('\n')
      .map((s) => s.trim())
      .filter((s) => s.length > 0);
  });

  private dialogRef = inject(MatDialogRef<BulkImportDialogComponent>);

  addTag(event: MatChipInputEvent): void {
    const value = (event.value || '').trim();
    if (value) {
      this.tags.update((t) => [...t, value]);
    }
    event.chipInput.clear();
  }

  removeTag(tag: string): void {
    this.tags.update((t) => t.filter((x) => x !== tag));
  }

  submit(): void {
    const names = this.parsedNames();
    if (names.length === 0) return;
    this.dialogRef.close({ names, tags: this.tags() } as BulkImportResult);
  }

  cancel(): void {
    this.dialogRef.close();
  }
}
