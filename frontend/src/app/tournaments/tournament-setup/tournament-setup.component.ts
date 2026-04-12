import { Component, computed, inject, signal, ViewChild } from '@angular/core';
import { Router } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { STEPPER_GLOBAL_OPTIONS } from '@angular/cdk/stepper';
import { MatStepper, MatStepperModule } from '@angular/material/stepper';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatButtonModule } from '@angular/material/button';
import { MatSlideToggleModule } from '@angular/material/slide-toggle';
import { MatChipsModule } from '@angular/material/chips';
import { MatIconModule } from '@angular/material/icon';
import { MatCardModule } from '@angular/material/card';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { ApiService } from '../../services/api.service';
import { NotificationService } from '../../services/notification.service';
import { Tournament, TournamentMode } from '../../models/tournament.model';
import { Option } from '../../models/option.model';

interface ModeInfo {
  value: TournamentMode;
  label: string;
  icon: string;
  description: string;
}

@Component({
  selector: 'app-tournament-setup',
  imports: [
    FormsModule,
    MatStepperModule,
    MatFormFieldModule,
    MatInputModule,
    MatButtonModule,
    MatSlideToggleModule,
    MatChipsModule,
    MatIconModule,
    MatCardModule,
    MatProgressSpinnerModule,
  ],
  templateUrl: './tournament-setup.component.html',
  styleUrl: './tournament-setup.component.scss',
  providers: [
    { provide: STEPPER_GLOBAL_OPTIONS, useValue: { showError: true } },
  ],
})
export class TournamentSetupComponent {
  private api = inject(ApiService);
  private router = inject(Router);
  private notify = inject(NotificationService);

  @ViewChild('stepper') stepper!: MatStepper;

  // --- Step 1: Name + Mode ---
  name = signal('');
  description = signal('');
  mode = signal<TournamentMode | null>(null);
  step1Valid = computed(() => this.name().trim().length > 0 && this.mode() !== null);
  creatingTournament = signal(false);

  // Created tournament (after step 1 completes)
  tournament = signal<Tournament | null>(null);

  // --- Step 2: Select Options ---
  availableOptions = signal<Option[]>([]);
  allTags = signal<string[]>([]);
  selectedOptionIds = signal<Set<string>>(new Set());
  searchQuery = signal('');
  selectedTag = signal<string | null>(null);
  loadingOptions = signal(false);
  savingOptions = signal(false);
  step2Completed = signal(false);

  step2Valid = computed(() => this.selectedOptionIds().size >= 2);

  filteredOptions = computed(() => {
    const query = this.searchQuery().toLowerCase().trim();
    const tag = this.selectedTag();
    return this.availableOptions().filter(opt => {
      const matchesQuery = !query
        || opt.name.toLowerCase().includes(query)
        || opt.tags.some(t => t.toLowerCase().includes(query));
      const matchesTag = !tag || opt.tags.includes(tag);
      return matchesQuery && matchesTag;
    });
  });

  selectedOptions = computed(() => {
    const ids = this.selectedOptionIds();
    return this.availableOptions().filter(opt => ids.has(opt.id));
  });

  // --- Step 3: Configure ---
  savingConfig = signal(false);
  step3Completed = signal(false);

  // Bracket config
  shuffleSeed = signal(true);
  thirdPlaceMatch = signal(false);

  // Score config
  minScore = signal(1);
  maxScore = signal(5);
  scoreVoterCount = signal(1);

  // Multivote config
  totalVotes = signal<number | null>(null);
  maxPerOption = signal<number | null>(null);
  multivoteVoterCount = signal(1);

  // Condorcet config
  condorcetVoterCount = signal(1);

  // --- Step 4: Activate ---
  activating = signal(false);

  // --- Mode definitions ---
  readonly modes: ModeInfo[] = [
    {
      value: 'bracket',
      label: 'Bracket',
      icon: 'account_tree',
      description: 'Single elimination bracket. Head-to-head matchups until one winner remains.',
    },
    {
      value: 'score',
      label: 'Score',
      icon: 'star',
      description: 'Rate each option on a scale. Highest average score wins.',
    },
    {
      value: 'multivote',
      label: 'Multivote',
      icon: 'how_to_vote',
      description: 'Distribute a budget of votes across options. Most votes wins.',
    },
    {
      value: 'condorcet',
      label: 'Condorcet',
      icon: 'swap_vert',
      description: 'Every option compared head-to-head. Schulze method finds the strongest winner.',
    },
  ];

  // --- Helpers ---

  modeLabel(mode: TournamentMode): string {
    return this.modes.find(m => m.value === mode)?.label ?? mode;
  }

  // --- Summary for Step 4 ---
  configSummary = computed(() => {
    const t = this.tournament();
    if (!t) return [];

    const entries: { label: string; value: string }[] = [
      { label: 'Name', value: t.name },
      { label: 'Mode', value: this.modeLabel(t.mode) },
      { label: 'Options', value: `${this.selectedOptionIds().size} selected` },
    ];

    if (t.description) {
      entries.splice(1, 0, { label: 'Description', value: t.description });
    }

    switch (t.mode) {
      case 'bracket':
        entries.push(
          { label: 'Shuffle Seed', value: this.shuffleSeed() ? 'Yes' : 'No' },
          { label: 'Third Place Match', value: this.thirdPlaceMatch() ? 'Yes' : 'No' },
        );
        break;
      case 'score':
        entries.push(
          { label: 'Score Range', value: `${this.minScore()} - ${this.maxScore()}` },
          { label: 'Voter Count', value: `${this.scoreVoterCount()}` },
        );
        break;
      case 'multivote':
        entries.push(
          { label: 'Total Votes', value: this.totalVotes() !== null ? `${this.totalVotes()}` : 'Auto' },
          { label: 'Max Per Option', value: this.maxPerOption() !== null ? `${this.maxPerOption()}` : 'Unlimited' },
          { label: 'Voter Count', value: `${this.multivoteVoterCount()}` },
        );
        break;
      case 'condorcet':
        entries.push(
          { label: 'Voter Count', value: `${this.condorcetVoterCount()}` },
        );
        break;
    }

    return entries;
  });

  // --- Step 1 Actions ---

  createTournament(): void {
    if (!this.step1Valid() || this.creatingTournament()) return;
    this.creatingTournament.set(true);

    const body: { name: string; mode: string; description?: string } = {
      name: this.name().trim(),
      mode: this.mode()!,
    };
    const desc = this.description().trim();
    if (desc) body.description = desc;

    this.api.createTournament(body).subscribe({
      next: (tournament) => {
        this.tournament.set(tournament);
        this.creatingTournament.set(false);
        this.notify.showSuccess('Tournament draft created.');
        this.loadOptions();
        // Advance stepper after the step's [completed] binding becomes true
        setTimeout(() => this.stepper.next());
      },
      error: (err) => {
        this.creatingTournament.set(false);
        this.notify.showError('Failed to create tournament.');
        console.error('Create tournament error:', err);
      },
    });
  }

  // --- Step 2 Actions ---

  private loadOptions(): void {
    this.loadingOptions.set(true);
    this.api.listOptions().subscribe({
      next: (options) => {
        this.availableOptions.set(options);
        this.loadingOptions.set(false);
      },
      error: (err) => {
        this.loadingOptions.set(false);
        this.notify.showError('Failed to load options.');
        console.error('Load options error:', err);
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

  onSearchInput(event: Event): void {
    this.searchQuery.set((event.target as HTMLInputElement).value);
  }

  toggleTag(tag: string): void {
    this.selectedTag.set(this.selectedTag() === tag ? null : tag);
  }

  saveSelectedOptions(): void {
    const t = this.tournament();
    if (!t || !this.step2Valid() || this.savingOptions()) return;
    this.savingOptions.set(true);

    this.api.updateTournament(t.id, {
      version: t.version,
      selected_option_ids: [...this.selectedOptionIds()],
    }).subscribe({
      next: (updated) => {
        this.tournament.set(updated);
        this.savingOptions.set(false);
        this.step2Completed.set(true);
        this.notify.showSuccess('Options saved.');
        setTimeout(() => this.stepper.next());
      },
      error: (err) => {
        this.savingOptions.set(false);
        this.notify.showError('Failed to save options.');
        console.error('Save options error:', err);
      },
    });
  }

  // --- Step 3 Actions ---

  private buildConfig(): Record<string, unknown> {
    const t = this.tournament();
    if (!t) return {};

    switch (t.mode) {
      case 'bracket':
        return {
          shuffle_seed: this.shuffleSeed(),
          third_place_match: this.thirdPlaceMatch(),
        };
      case 'score':
        return {
          min_score: this.minScore(),
          max_score: this.maxScore(),
          voter_count: this.scoreVoterCount(),
        };
      case 'multivote':
        return {
          total_votes: this.totalVotes(),
          max_per_option: this.maxPerOption(),
          voter_count: this.multivoteVoterCount(),
        };
      case 'condorcet':
        return {
          voter_count: this.condorcetVoterCount(),
        };
      default:
        return {};
    }
  }

  saveConfig(): void {
    const t = this.tournament();
    if (!t || this.savingConfig()) return;
    this.savingConfig.set(true);

    this.api.updateTournament(t.id, {
      version: t.version,
      config: this.buildConfig(),
    }).subscribe({
      next: (updated) => {
        this.tournament.set(updated);
        this.savingConfig.set(false);
        this.step3Completed.set(true);
        this.notify.showSuccess('Configuration saved.');
        setTimeout(() => this.stepper.next());
      },
      error: (err) => {
        this.savingConfig.set(false);
        this.notify.showError('Failed to save configuration.');
        console.error('Save config error:', err);
      },
    });
  }

  // --- Step 4 Actions ---

  activateTournament(): void {
    const t = this.tournament();
    if (!t || this.activating()) return;
    this.activating.set(true);

    this.api.activateTournament(t.id, t.version).subscribe({
      next: () => {
        this.activating.set(false);
        this.notify.showSuccess('Tournament activated!');
        this.router.navigate(['/tournaments', t.id]);
      },
      error: (err) => {
        this.activating.set(false);
        this.notify.showError('Failed to activate tournament.');
        console.error('Activate error:', err);
      },
    });
  }
}
