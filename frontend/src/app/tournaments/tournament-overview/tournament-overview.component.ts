import { Component, DestroyRef, inject, OnInit, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { MatCardModule } from '@angular/material/card';
import { MatButtonModule } from '@angular/material/button';
import { MatChipsModule } from '@angular/material/chips';
import { MatIconModule } from '@angular/material/icon';
import { MatDividerModule } from '@angular/material/divider';
import { Tournament } from '../../models/tournament.model';
import { ApiService } from '../../services/api.service';
import { NotificationService } from '../../services/notification.service';

@Component({
  selector: 'app-tournament-overview',
  imports: [MatCardModule, MatButtonModule, MatChipsModule, MatIconModule, MatDividerModule, RouterLink],
  templateUrl: './tournament-overview.component.html',
  styleUrl: './tournament-overview.component.scss',
})
export class TournamentOverviewComponent implements OnInit {
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  private api = inject(ApiService);
  private notify = inject(NotificationService);
  private destroyRef = inject(DestroyRef);

  tournament = signal<Tournament | null>(null);

  ngOnInit(): void {
    this.route.paramMap.pipe(takeUntilDestroyed(this.destroyRef)).subscribe(params => {
      const id = params.get('id')!;
      this.loadTournament(id);
    });
  }

  private loadTournament(id: string): void {
    this.api.getTournament(id).subscribe({
      next: (t) => this.tournament.set(t),
      error: () => this.notify.showError('Tournament not found'),
    });
  }

  onCancel(): void {
    const t = this.tournament();
    if (!t) return;
    this.api.cancelTournament(t.id, t.version).subscribe({
      next: (updated) => {
        this.tournament.set(updated);
        this.notify.showSuccess('Tournament cancelled');
      },
      error: () => this.notify.showError('Failed to cancel tournament'),
    });
  }

  onClone(): void {
    const t = this.tournament();
    if (!t) return;
    this.api.cloneTournament(t.id).subscribe({
      next: (clone) => {
        this.notify.showSuccess('Tournament cloned');
        this.router.navigate(['/tournaments', clone.id]);
      },
      error: () => this.notify.showError('Failed to clone tournament'),
    });
  }

  onDelete(): void {
    const t = this.tournament();
    if (!t) return;
    this.api.deleteTournament(t.id).subscribe({
      next: () => {
        this.notify.showSuccess('Tournament deleted');
        this.router.navigate(['/']);
      },
      error: () => this.notify.showError('Failed to delete tournament'),
    });
  }

  getEntryName(entryId: string): string {
    const t = this.tournament();
    if (!t) return entryId;
    const entry = t.entries.find((e) => e.id === entryId);
    return (entry?.option_snapshot?.['name'] as string) ?? entryId;
  }
}
