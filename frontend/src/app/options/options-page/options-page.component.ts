import { Component, inject, OnInit, signal } from '@angular/core';
import {
  MAT_DIALOG_DATA,
  MatDialog,
  MatDialogModule,
  MatDialogRef,
} from '@angular/material/dialog';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { ApiService } from '../../services/api.service';
import { NotificationService } from '../../services/notification.service';
import { Option } from '../../models/option.model';
import { OptionCardComponent } from '../../shared/option-card/option-card.component';
import { OptionSearchComponent, SearchCriteria } from '../../shared/option-search/option-search.component';
import { OptionDialogComponent, OptionDialogResult } from '../option-dialog/option-dialog.component';

@Component({
  selector: 'app-options-page',
  imports: [
    MatDialogModule,
    MatButtonModule,
    MatIconModule,
    MatProgressSpinnerModule,
    OptionCardComponent,
    OptionSearchComponent,
  ],
  templateUrl: './options-page.component.html',
  styleUrl: './options-page.component.scss',
})
export class OptionsPageComponent implements OnInit {
  private api = inject(ApiService);
  private dialog = inject(MatDialog);
  private notify = inject(NotificationService);

  options = signal<Option[]>([]);
  loading = signal(true);
  currentSearch = signal<SearchCriteria>({ q: '', tagsAll: '', tagsAny: '' });

  ngOnInit(): void {
    this.loadOptions();
  }

  loadOptions(): void {
    this.loading.set(true);
    const { q, tagsAll, tagsAny } = this.currentSearch();
    this.api.listOptions(q, tagsAll, tagsAny).subscribe({
      next: (options) => {
        this.options.set(options);
        this.loading.set(false);
      },
      error: () => {
        this.notify.showError('Failed to load options.');
        this.loading.set(false);
      },
    });
  }

  onSearchChange(criteria: SearchCriteria): void {
    this.currentSearch.set(criteria);
    this.loadOptions();
  }

  openCreateDialog(): void {
    const dialogRef = this.dialog.open(OptionDialogComponent, {
      width: '500px',
      data: {},
    });

    dialogRef.afterClosed().subscribe((result: OptionDialogResult | undefined) => {
      if (!result) return;
      this.api.createOption(result).subscribe({
        next: () => {
          this.notify.showSuccess('Option created.');
          this.loadOptions();
        },
        error: () => this.notify.showError('Failed to create option.'),
      });
    });
  }

  openEditDialog(option: Option): void {
    const dialogRef = this.dialog.open(OptionDialogComponent, {
      width: '500px',
      data: { option },
    });

    dialogRef.afterClosed().subscribe((result: OptionDialogResult | undefined) => {
      if (!result) return;
      this.api.updateOption(option.id, result).subscribe({
        next: () => {
          this.notify.showSuccess('Option updated.');
          this.loadOptions();
        },
        error: () => this.notify.showError('Failed to update option.'),
      });
    });
  }

  confirmDelete(option: Option): void {
    const ref = this.dialog.open(DeleteConfirmDialogComponent, {
      width: '350px',
      data: { name: option.name },
    });

    ref.afterClosed().subscribe((confirmed: boolean) => {
      if (!confirmed) return;
      this.api.deleteOption(option.id).subscribe({
        next: () => {
          this.notify.showSuccess('Option deleted.');
          this.loadOptions();
        },
        error: () => this.notify.showError('Failed to delete option.'),
      });
    });
  }
}

@Component({
  selector: 'app-delete-confirm-dialog',
  imports: [MatDialogModule, MatButtonModule],
  template: `
    <h2 mat-dialog-title>Confirm Delete</h2>
    <mat-dialog-content>
      Are you sure you want to delete "{{ data.name }}"? This cannot be undone.
    </mat-dialog-content>
    <mat-dialog-actions align="end">
      <button mat-button (click)="dialogRef.close(false)">Cancel</button>
      <button mat-flat-button color="warn" (click)="dialogRef.close(true)">Delete</button>
    </mat-dialog-actions>
  `,
})
export class DeleteConfirmDialogComponent {
  dialogRef = inject(MatDialogRef<DeleteConfirmDialogComponent>);
  data: { name: string } = inject(MAT_DIALOG_DATA);
}
