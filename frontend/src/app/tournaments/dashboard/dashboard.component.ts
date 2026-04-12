import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { MatCardModule } from '@angular/material/card';
import { MatButtonModule } from '@angular/material/button';
import { MatChipsModule } from '@angular/material/chips';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { ApiService } from '../../services/api.service';
import { Tournament } from '../../models/tournament.model';
import { forkJoin } from 'rxjs';

@Component({
  selector: 'app-dashboard',
  imports: [
    RouterLink,
    MatCardModule,
    MatButtonModule,
    MatChipsModule,
    MatIconModule,
    MatProgressSpinnerModule,
  ],
  templateUrl: './dashboard.component.html',
  styleUrl: './dashboard.component.scss',
})
export class DashboardComponent implements OnInit {
  private api = inject(ApiService);

  activeTournaments = signal<Tournament[]>([]);
  completedTournaments = signal<Tournament[]>([]);
  loading = signal(true);
  error = signal<string | null>(null);

  isEmpty = computed(
    () => this.activeTournaments().length === 0 && this.completedTournaments().length === 0,
  );

  ngOnInit(): void {
    this.loadTournaments();
  }

  loadTournaments(): void {
    this.loading.set(true);
    this.error.set(null);

    forkJoin({
      active: this.api.listTournaments('active,draft'),
      completed: this.api.listTournaments('completed'),
    }).subscribe({
      next: ({ active, completed }) => {
        this.activeTournaments.set(active);
        this.completedTournaments.set(completed);
        this.loading.set(false);
      },
      error: (err) => {
        this.error.set('Failed to load tournaments. Please try again.');
        this.loading.set(false);
        console.error('Dashboard load error:', err);
      },
    });
  }

  modeLabel(mode: string): string {
    const labels: Record<string, string> = {
      bracket: 'Bracket',
      score: 'Score',
      multivote: 'Multivote',
      condorcet: 'Condorcet',
    };
    return labels[mode] ?? mode;
  }

  modeIcon(mode: string): string {
    const icons: Record<string, string> = {
      bracket: 'account_tree',
      score: 'star',
      multivote: 'how_to_vote',
      condorcet: 'swap_vert',
    };
    return icons[mode] ?? 'emoji_events';
  }
}
