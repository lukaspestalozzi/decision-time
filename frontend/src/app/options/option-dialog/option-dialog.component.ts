import { Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import {
  MAT_DIALOG_DATA,
  MatDialogModule,
  MatDialogRef,
} from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatButtonModule } from '@angular/material/button';
import { MatChipsModule, MatChipInputEvent } from '@angular/material/chips';
import { MatIconModule } from '@angular/material/icon';
import { COMMA, ENTER } from '@angular/cdk/keycodes';
import { Option } from '../../models/option.model';

export interface OptionDialogData {
  option?: Option;
}

export interface OptionDialogResult {
  name: string;
  description: string;
  tags: string[];
}

@Component({
  selector: 'app-option-dialog',
  imports: [
    FormsModule,
    MatDialogModule,
    MatFormFieldModule,
    MatInputModule,
    MatButtonModule,
    MatChipsModule,
    MatIconModule,
  ],
  templateUrl: './option-dialog.component.html',
  styleUrl: './option-dialog.component.scss',
})
export class OptionDialogComponent {
  private dialogRef = inject(MatDialogRef<OptionDialogComponent>);
  private data: OptionDialogData = inject(MAT_DIALOG_DATA, { optional: true }) ?? {};

  readonly separatorKeyCodes = [ENTER, COMMA] as const;

  isEdit = signal(false);
  name = signal('');
  description = signal('');
  tags = signal<string[]>([]);

  constructor() {
    if (this.data.option) {
      this.isEdit.set(true);
      this.name.set(this.data.option.name);
      this.description.set(this.data.option.description ?? '');
      this.tags.set([...this.data.option.tags]);
    }
  }

  get title(): string {
    return this.isEdit() ? 'Edit Option' : 'Create Option';
  }

  get isValid(): boolean {
    return this.name().trim().length > 0 && this.name().trim().length <= 256;
  }

  addTag(event: MatChipInputEvent): void {
    const value = (event.value ?? '').trim();
    if (value && !this.tags().includes(value)) {
      this.tags.update((tags) => [...tags, value]);
    }
    event.chipInput.clear();
  }

  removeTag(tag: string): void {
    this.tags.update((tags) => tags.filter((t) => t !== tag));
  }

  onCancel(): void {
    this.dialogRef.close();
  }

  onSave(): void {
    if (!this.isValid) return;
    const result: OptionDialogResult = {
      name: this.name().trim(),
      description: this.description().trim(),
      tags: this.tags(),
    };
    this.dialogRef.close(result);
  }
}
