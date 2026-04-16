import { ComponentFixture, TestBed } from '@angular/core/testing';
import { ActivatedRoute, provideRouter } from '@angular/router';
import { provideAnimationsAsync } from '@angular/platform-browser/animations/async';
import { of } from 'rxjs';

import { TournamentSetupComponent } from './tournament-setup.component';
import { ApiService } from '../../services/api.service';
import { Tournament, TournamentMode } from '../../models/tournament.model';
import { Option } from '../../models/option.model';

function makeTournament(overrides: Partial<Tournament> & { id: string; mode: TournamentMode }): Tournament {
  return {
    id: overrides.id,
    name: overrides.name ?? 'Draft Tournament',
    description: overrides.description ?? '',
    mode: overrides.mode,
    status: overrides.status ?? 'draft',
    config: overrides.config ?? {},
    version: overrides.version ?? 1,
    selected_option_ids: overrides.selected_option_ids ?? [],
    entries: [],
    state: {},
    votes: [],
    result: null,
    created_at: '2026-04-16T00:00:00Z',
    updated_at: '2026-04-16T00:00:00Z',
    completed_at: null,
  };
}

function makeOption(id: string, name: string): Option {
  return {
    id,
    name,
    description: '',
    tags: [],
    created_at: '2026-04-16T00:00:00Z',
    updated_at: '2026-04-16T00:00:00Z',
  };
}

function makeRoute(params: Record<string, string>): Pick<ActivatedRoute, 'snapshot'> {
  return {
    snapshot: {
      paramMap: {
        has: (key: string) => key in params,
        get: (key: string) => params[key] ?? null,
      },
    },
  } as Pick<ActivatedRoute, 'snapshot'>;
}

describe('TournamentSetupComponent', () => {
  describe('create mode (no :id in route)', () => {
    let fixture: ComponentFixture<TournamentSetupComponent>;
    let component: TournamentSetupComponent;

    beforeEach(async () => {
      const apiSpy: Partial<ApiService> = {
        listOptions: jest.fn().mockReturnValue(of([])),
        listTags: jest.fn().mockReturnValue(of([])),
      };
      await TestBed.configureTestingModule({
        imports: [TournamentSetupComponent],
        providers: [
          provideRouter([]),
          provideAnimationsAsync(),
          { provide: ApiService, useValue: apiSpy },
          { provide: ActivatedRoute, useValue: makeRoute({}) },
        ],
      }).compileComponents();

      fixture = TestBed.createComponent(TournamentSetupComponent);
      component = fixture.componentInstance;
      fixture.detectChanges();
    });

    it('does not mark itself in edit mode', () => {
      expect(component.isEditMode()).toBe(false);
      expect(component.editId()).toBeNull();
    });

    it('shows the create-mode page title', () => {
      expect(component.pageTitle()).toBe('New Tournament');
      expect(component.step1ButtonLabel()).toBe('Next');
    });

    it('leaves step signals at defaults', () => {
      expect(component.name()).toBe('');
      expect(component.mode()).toBeNull();
      expect(component.tournament()).toBeNull();
    });
  });

  describe('edit mode (:id in route)', () => {
    let fixture: ComponentFixture<TournamentSetupComponent>;
    let component: TournamentSetupComponent;
    let listOptionsSpy: jest.Mock;
    let getTournamentSpy: jest.Mock;

    const loadedTournament = makeTournament({
      id: 'abc-123',
      name: 'Loaded Draft',
      description: 'Pre-existing description',
      mode: 'score',
      version: 4,
      selected_option_ids: ['opt-1', 'opt-2'],
      config: {
        allow_undo: false,
        voter_labels: ['Alice', 'Bob'],
        min_score: 0,
        max_score: 10,
      },
    });

    beforeEach(async () => {
      getTournamentSpy = jest.fn().mockReturnValue(of(loadedTournament));
      listOptionsSpy = jest.fn().mockReturnValue(of([makeOption('opt-1', 'Cat'), makeOption('opt-2', 'Dog')]));
      const apiSpy: Partial<ApiService> = {
        getTournament: getTournamentSpy,
        listOptions: listOptionsSpy,
        listTags: jest.fn().mockReturnValue(of([])),
      };
      await TestBed.configureTestingModule({
        imports: [TournamentSetupComponent],
        providers: [
          provideRouter([]),
          provideAnimationsAsync(),
          { provide: ApiService, useValue: apiSpy },
          { provide: ActivatedRoute, useValue: makeRoute({ id: 'abc-123' }) },
        ],
      }).compileComponents();

      fixture = TestBed.createComponent(TournamentSetupComponent);
      component = fixture.componentInstance;
      fixture.detectChanges();
    });

    it('detects edit mode from the route param', () => {
      expect(component.isEditMode()).toBe(true);
      expect(component.editId()).toBe('abc-123');
      expect(component.pageTitle()).toBe('Edit Tournament');
      expect(component.step1ButtonLabel()).toBe('Save');
    });

    it('calls getTournament with the route id', () => {
      expect(getTournamentSpy).toHaveBeenCalledWith('abc-123');
    });

    it('triggers loadOptions on init (must not wait for create)', () => {
      expect(listOptionsSpy).toHaveBeenCalled();
    });

    it('prefills every step 1 signal from the loaded tournament', () => {
      expect(component.name()).toBe('Loaded Draft');
      expect(component.description()).toBe('Pre-existing description');
      expect(component.mode()).toBe('score');
      expect(component.tournament()).toEqual(loadedTournament);
    });

    it('prefills selected options as a Set', () => {
      expect(component.selectedOptionIds().size).toBe(2);
      expect(component.selectedOptionIds().has('opt-1')).toBe(true);
      expect(component.selectedOptionIds().has('opt-2')).toBe(true);
    });

    it('prefills mode-specific config signals', () => {
      expect(component.minScore()).toBe(0);
      expect(component.maxScore()).toBe(10);
      expect(component.scoreVoterLabels()).toEqual(['Alice', 'Bob']);
    });

    it('round-trips allow_undo through buildConfig', () => {
      expect(component.allowUndo()).toBe(false);
      const config = (component as unknown as { buildConfig: () => Record<string, unknown> }).buildConfig();
      expect(config['allow_undo']).toBe(false);
    });
  });
});
