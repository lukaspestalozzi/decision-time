import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { provideAnimationsAsync } from '@angular/platform-browser/animations/async';
import { of } from 'rxjs';
import { By } from '@angular/platform-browser';

import { DashboardComponent } from './dashboard.component';
import { ApiService } from '../../services/api.service';
import { Tournament, TournamentStatus, TournamentMode } from '../../models/tournament.model';

function makeTournament(
  overrides: Partial<Tournament> & { id: string; status: TournamentStatus; mode?: TournamentMode },
): Tournament {
  return {
    id: overrides.id,
    name: overrides.name ?? `Tournament ${overrides.id}`,
    description: overrides.description ?? '',
    mode: overrides.mode ?? 'bracket',
    status: overrides.status,
    config: {},
    version: 1,
    selected_option_ids: overrides.selected_option_ids ?? [],
    entries: overrides.entries ?? [],
    state: {},
    votes: [],
    result: null,
    created_at: '2026-04-16T00:00:00Z',
    updated_at: '2026-04-16T00:00:00Z',
    completed_at: null,
  };
}

describe('DashboardComponent', () => {
  let fixture: ComponentFixture<DashboardComponent>;
  let apiSpy: jest.Mocked<Pick<ApiService, 'listTournaments'>>;

  const activeTournament = makeTournament({ id: 'active-1', status: 'active', name: 'Active One' });
  const draftTournament = makeTournament({ id: 'draft-1', status: 'draft', name: 'Draft One' });
  const completedTournament = makeTournament({ id: 'completed-1', status: 'completed', name: 'Completed One' });
  const cancelledTournament = makeTournament({ id: 'cancelled-1', status: 'cancelled', name: 'Cancelled One' });

  beforeEach(async () => {
    apiSpy = {
      listTournaments: jest.fn((status?: string) => {
        if (status === 'active,draft') return of([activeTournament, draftTournament]);
        if (status === 'completed') return of([completedTournament]);
        if (status === 'cancelled') return of([cancelledTournament]);
        return of([]);
      }),
    };

    await TestBed.configureTestingModule({
      imports: [DashboardComponent],
      providers: [
        provideRouter([]),
        provideAnimationsAsync(),
        { provide: ApiService, useValue: apiSpy },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(DashboardComponent);
    fixture.detectChanges();
  });

  it('fetches active/draft, completed, and cancelled tournaments', () => {
    expect(apiSpy.listTournaments).toHaveBeenCalledWith('active,draft');
    expect(apiSpy.listTournaments).toHaveBeenCalledWith('completed');
    expect(apiSpy.listTournaments).toHaveBeenCalledWith('cancelled');
  });

  it('wraps the card header/content in an anchor that links to the overview', () => {
    const cardLinks = fixture.debugElement.queryAll(By.css('a.card-link'));
    const hrefs = cardLinks.map((el) => el.nativeElement.getAttribute('href'));

    expect(hrefs).toEqual(
      expect.arrayContaining([
        '/tournaments/active-1',
        '/tournaments/draft-1',
        '/tournaments/completed-1',
        '/tournaments/cancelled-1',
      ]),
    );
  });

  it('sets an accessible label on each card link', () => {
    const cardLinks = fixture.debugElement.queryAll(By.css('a.card-link'));
    const labels = cardLinks.map((el) => el.nativeElement.getAttribute('aria-label'));

    expect(labels).toEqual(
      expect.arrayContaining([
        'View Active One',
        'View Draft One',
        'View Completed One',
        'View Cancelled One',
      ]),
    );
  });

  it('renders a Vote button only for active tournaments, pointing to the vote route', () => {
    const voteLinks = fixture.debugElement
      .queryAll(By.css('mat-card-actions a'))
      .filter((el) => el.nativeElement.getAttribute('href')?.endsWith('/vote'));

    expect(voteLinks.length).toBe(1);
    expect(voteLinks[0].nativeElement.getAttribute('href')).toBe('/tournaments/active-1/vote');
  });

  it('renders a View Result button for completed tournaments, pointing to the result route', () => {
    const resultLinks = fixture.debugElement
      .queryAll(By.css('mat-card-actions a'))
      .filter((el) => el.nativeElement.getAttribute('href')?.endsWith('/result'));

    expect(resultLinks.length).toBe(1);
    expect(resultLinks[0].nativeElement.getAttribute('href')).toBe('/tournaments/completed-1/result');
  });

  it('does not render any inline action buttons for cancelled tournaments', () => {
    const cancelledCard = fixture.debugElement
      .queryAll(By.css('mat-card.cancelled-card'))
      .find((el) => el.nativeElement.textContent.includes('Cancelled One'));

    expect(cancelledCard).toBeDefined();
    const actions = cancelledCard!.queryAll(By.css('mat-card-actions'));
    expect(actions.length).toBe(0);
  });

  it('keeps inline action links outside the card anchor so they navigate independently', () => {
    const cardLinks = fixture.debugElement.queryAll(By.css('a.card-link'));
    for (const link of cardLinks) {
      const nestedActions = link.queryAll(By.css('mat-card-actions'));
      expect(nestedActions.length).toBe(0);
    }
  });
});
