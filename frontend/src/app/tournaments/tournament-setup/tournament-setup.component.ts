import { afterNextRender, Component, computed, DestroyRef, inject, Injector, OnInit, signal, ViewChild } from '@angular/core';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormsModule } from '@angular/forms';
import { ENTER, COMMA } from '@angular/cdk/keycodes';
import { STEPPER_GLOBAL_OPTIONS } from '@angular/cdk/stepper';
import { MatChipInputEvent } from '@angular/material/chips';
import { MatStepper, MatStepperModule } from '@angular/material/stepper';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatButtonModule } from '@angular/material/button';
import { MatSlideToggleModule } from '@angular/material/slide-toggle';
import { MatChipsModule } from '@angular/material/chips';
import { MatIconModule } from '@angular/material/icon';
import { MatCardModule } from '@angular/material/card';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatDialog, MatDialogModule } from '@angular/material/dialog';
import { ApiService } from '../../services/api.service';
import { NotificationService } from '../../services/notification.service';
import { Tournament, TournamentMode } from '../../models/tournament.model';
import { Option } from '../../models/option.model';
import { ConfirmDialogComponent, ConfirmDialogData } from '../../shared/confirm-dialog/confirm-dialog.component';

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
    MatDialogModule,
    RouterLink,
  ],
  templateUrl: './tournament-setup.component.html',
  styleUrl: './tournament-setup.component.scss',
  providers: [
    { provide: STEPPER_GLOBAL_OPTIONS, useValue: { showError: true } },
  ],
})
export class TournamentSetupComponent implements OnInit {
  private api = inject(ApiService);
  private router = inject(Router);
  private route = inject(ActivatedRoute);
  private notify = inject(NotificationService);
  private injector = inject(Injector);
  private destroyRef = inject(DestroyRef);
  private dialog = inject(MatDialog);

  @ViewChild('stepper') stepper!: MatStepper;

  // --- Edit mode state ---
  isEditMode = signal(false);
  editId = signal<string | null>(null);
  editLoading = signal(false);

  // --- Step 1: Name + Mode ---
  name = signal('');
  description = signal('');
  mode = signal<TournamentMode | null>(null);
  step1Valid = computed(() => this.name().trim().length > 0 && this.mode() !== null);
  creatingTournament = signal(false);

  // Snapshot of step-1 fields at load/save time — used to skip no-op PUTs.
  private step1Snapshot = signal<{ name: string; description: string; mode: TournamentMode | null } | null>(null);

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
  step2Completed = computed(() => (this.tournament()?.selected_option_ids?.length ?? 0) >= 2);

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
  step3Completed = computed(() => Object.keys(this.tournament()?.config ?? {}).length > 0);

  // Hidden round-trip of allow_undo — the setup UI doesn't expose it yet, but
  // partial updates that rebuild config from signals must not silently flip it.
  allowUndo = signal(true);

  // Bracket config
  shuffleSeed = signal(true);
  thirdPlaceMatch = signal(false);

  // Score config
  minScore = signal(1);
  maxScore = signal(5);
  scoreVoterLabels = signal<string[]>(['Voter 1']);

  // Multivote config
  totalVotes = signal<number | null>(null);
  maxPerOption = signal<number | null>(null);
  multivoteVoterLabels = signal<string[]>(['Voter 1']);

  // Condorcet config
  condorcetVoterLabels = signal<string[]>(['Voter 1']);

  // Voter chip input separators
  readonly voterSeparatorKeyCodes = [ENTER, COMMA] as const;

  addVoterLabel(target: 'score' | 'multivote' | 'condorcet', event: MatChipInputEvent): void {
    const value = (event.value ?? '').trim();
    event.chipInput.clear();
    if (!value) return;
    const signal = this._voterSignal(target);
    if (signal().includes(value)) return;
    signal.update((labels) => [...labels, value]);
  }

  removeVoterLabel(target: 'score' | 'multivote' | 'condorcet', label: string): void {
    const signal = this._voterSignal(target);
    signal.update((labels) => labels.filter((l) => l !== label));
  }

  private _voterSignal(target: 'score' | 'multivote' | 'condorcet') {
    switch (target) {
      case 'score': return this.scoreVoterLabels;
      case 'multivote': return this.multivoteVoterLabels;
      case 'condorcet': return this.condorcetVoterLabels;
    }
  }

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

  ngOnInit(): void {
    const id = this.route.snapshot.paramMap.get('id');
    if (id) {
      this.isEditMode.set(true);
      this.editId.set(id);
      this.loadForEdit(id);
    }
  }

  private loadForEdit(id: string): void {
    this.editLoading.set(true);
    this.api.getTournament(id).pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: (t) => {
        this.prefillFromTournament(t);
        this.loadOptions();
        this.editLoading.set(false);
      },
      error: () => {
        this.editLoading.set(false);
        this.notify.showError('Failed to load tournament for editing.');
        this.router.navigate(['/']);
      },
    });
  }

  /** Populate every stepper signal from a loaded tournament. */
  private prefillFromTournament(t: Tournament): void {
    this.tournament.set(t);
    this.name.set(t.name);
    this.description.set(t.description);
    this.mode.set(t.mode);
    this.selectedOptionIds.set(new Set(t.selected_option_ids));
    this.step1Snapshot.set({ name: t.name, description: t.description, mode: t.mode });
    this.applyConfigToSignals(t.mode, t.config);
  }

  /** Copy mode-specific config into the matching signals. */
  private applyConfigToSignals(mode: TournamentMode, config: Record<string, unknown>): void {
    this.allowUndo.set((config['allow_undo'] as boolean | undefined) ?? true);
    const voterLabels = (config['voter_labels'] as string[] | undefined) ?? ['Voter 1'];

    switch (mode) {
      case 'bracket':
        this.shuffleSeed.set((config['shuffle_seed'] as boolean | undefined) ?? true);
        this.thirdPlaceMatch.set((config['third_place_match'] as boolean | undefined) ?? false);
        break;
      case 'score':
        this.minScore.set((config['min_score'] as number | undefined) ?? 1);
        this.maxScore.set((config['max_score'] as number | undefined) ?? 5);
        this.scoreVoterLabels.set([...voterLabels]);
        break;
      case 'multivote':
        this.totalVotes.set((config['total_votes'] as number | null | undefined) ?? null);
        this.maxPerOption.set((config['max_per_option'] as number | null | undefined) ?? null);
        this.multivoteVoterLabels.set([...voterLabels]);
        break;
      case 'condorcet':
        this.condorcetVoterLabels.set([...voterLabels]);
        break;
    }
  }

  /** Reset mode-specific config signals to defaults for the given mode. */
  private resetConfigSignalsForMode(mode: TournamentMode): void {
    this.allowUndo.set(true);
    switch (mode) {
      case 'bracket':
        this.shuffleSeed.set(true);
        this.thirdPlaceMatch.set(false);
        break;
      case 'score':
        this.minScore.set(1);
        this.maxScore.set(5);
        this.scoreVoterLabels.set(['Voter 1']);
        break;
      case 'multivote':
        this.totalVotes.set(null);
        this.maxPerOption.set(null);
        this.multivoteVoterLabels.set(['Voter 1']);
        break;
      case 'condorcet':
        this.condorcetVoterLabels.set(['Voter 1']);
        break;
    }
  }

  // --- Stepper ---

  /** Advance stepper after the next render so [completed] bindings are applied. */
  private advanceStepper(): void {
    afterNextRender(() => this.stepper.next(), { injector: this.injector });
  }

  // --- Helpers ---

  modeLabel(mode: TournamentMode): string {
    return this.modes.find(m => m.value === mode)?.label ?? mode;
  }

  pageTitle = computed(() => (this.isEditMode() ? 'Edit Tournament' : 'New Tournament'));

  step1ButtonLabel = computed(() => (this.isEditMode() ? 'Save' : 'Next'));

  // --- Mode selection (with confirm in edit mode) ---

  onModeSelect(newMode: TournamentMode): void {
    if (this.mode() === newMode) return;
    if (!this.isEditMode()) {
      this.mode.set(newMode);
      return;
    }
    const currentModeLabel = this.mode() ? this.modeLabel(this.mode()!) : '';
    const data: ConfirmDialogData = {
      title: 'Change tournament mode?',
      message: `Changing from ${currentModeLabel} to ${this.modeLabel(newMode)} will reset this tournament's configuration to defaults. Continue?`,
      confirmLabel: 'Change mode',
      cancelLabel: 'Cancel',
    };
    this.dialog
      .open(ConfirmDialogComponent, { data })
      .afterClosed()
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe((confirmed) => {
        if (confirmed) {
          this.mode.set(newMode);
          this.resetConfigSignalsForMode(newMode);
        }
      });
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
          { label: 'Voters', value: this.scoreVoterLabels().join(', ') },
        );
        break;
      case 'multivote':
        entries.push(
          { label: 'Total Votes', value: this.totalVotes() !== null ? `${this.totalVotes()}` : 'Auto' },
          { label: 'Max Per Option', value: this.maxPerOption() !== null ? `${this.maxPerOption()}` : 'Unlimited' },
          { label: 'Voters', value: this.multivoteVoterLabels().join(', ') },
        );
        break;
      case 'condorcet':
        entries.push(
          { label: 'Voters', value: this.condorcetVoterLabels().join(', ') },
        );
        break;
    }

    return entries;
  });

  // --- Step 1 Actions ---

  createTournament(): void {
    if (!this.step1Valid() || this.creatingTournament()) return;

    if (this.isEditMode()) {
      this.saveStep1Edits();
      return;
    }

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
        this.advanceStepper();
      },
      error: (err) => {
        this.creatingTournament.set(false);
        this.notify.showError('Failed to create tournament.');
        console.error('Create tournament error:', err);
      },
    });
  }

  private saveStep1Edits(): void {
    const t = this.tournament();
    if (!t) return;

    const nextName = this.name().trim();
    const nextDesc = this.description().trim();
    const nextMode = this.mode();
    const snap = this.step1Snapshot();

    const unchanged = snap
      && snap.name === nextName
      && snap.description === nextDesc
      && snap.mode === nextMode;
    if (unchanged) {
      this.advanceStepper();
      return;
    }

    this.creatingTournament.set(true);
    const body: {
      version: number;
      name?: string;
      description?: string;
      mode?: TournamentMode;
    } = { version: t.version };
    if (!snap || snap.name !== nextName) body.name = nextName;
    if (!snap || snap.description !== nextDesc) body.description = nextDesc;
    if (nextMode && (!snap || snap.mode !== nextMode)) body.mode = nextMode;

    this.api.updateTournament(t.id, body).subscribe({
      next: (updated) => {
        this.tournament.set(updated);
        // If mode changed, re-apply config from server defaults (server authoritative).
        if (snap && snap.mode !== updated.mode) {
          this.applyConfigToSignals(updated.mode, updated.config);
        }
        this.step1Snapshot.set({ name: updated.name, description: updated.description, mode: updated.mode });
        this.creatingTournament.set(false);
        this.notify.showSuccess('Changes saved.');
        this.advanceStepper();
      },
      error: (err) => {
        this.creatingTournament.set(false);
        this.notify.showError('Failed to save changes.');
        console.error('Update tournament error:', err);
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

  selectAllFiltered(): void {
    const current = new Set(this.selectedOptionIds());
    for (const opt of this.filteredOptions()) {
      current.add(opt.id);
    }
    this.selectedOptionIds.set(current);
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
        this.notify.showSuccess('Options saved.');
        this.advanceStepper();
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

    const base = { allow_undo: this.allowUndo() };
    switch (t.mode) {
      case 'bracket':
        return {
          ...base,
          shuffle_seed: this.shuffleSeed(),
          third_place_match: this.thirdPlaceMatch(),
        };
      case 'score':
        return {
          ...base,
          min_score: this.minScore(),
          max_score: this.maxScore(),
          voter_labels: this.scoreVoterLabels(),
        };
      case 'multivote':
        return {
          ...base,
          total_votes: this.totalVotes(),
          max_per_option: this.maxPerOption(),
          voter_labels: this.multivoteVoterLabels(),
        };
      case 'condorcet':
        return {
          ...base,
          voter_labels: this.condorcetVoterLabels(),
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
        this.notify.showSuccess('Configuration saved.');
        this.advanceStepper();
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
