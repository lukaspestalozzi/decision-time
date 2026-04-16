import { ComponentRef } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { NoopAnimationsModule } from '@angular/platform-browser/animations';
import { BallotSummaryComponent } from './ballot-summary.component';
import { Tournament } from '../../../models/tournament.model';

function makeTournament(overrides: Partial<Tournament> = {}): Tournament {
  return {
    id: 't1',
    name: 'T',
    description: '',
    mode: 'score',
    status: 'active',
    config: { voter_labels: ['Alice', 'Bob'] },
    version: 1,
    selected_option_ids: [],
    entries: [
      { id: 'e1', option_id: 'o1', seed: null, option_snapshot: { name: 'Option A' } },
      { id: 'e2', option_id: 'o2', seed: null, option_snapshot: { name: 'Option B' } },
    ],
    state: {},
    votes: [],
    result: null,
    created_at: '',
    updated_at: '',
    completed_at: null,
    cool_off_ends_at: null,
    ...overrides,
  };
}

describe('BallotSummaryComponent', () => {
  let fixture: ComponentFixture<BallotSummaryComponent>;
  let ref: ComponentRef<BallotSummaryComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [BallotSummaryComponent, NoopAnimationsModule],
    }).compileComponents();

    fixture = TestBed.createComponent(BallotSummaryComponent);
    ref = fixture.componentRef;
  });

  it('renders score rows for the voter\'s active vote', () => {
    const t = makeTournament({
      votes: [
        {
          id: 'v1',
          voter_label: 'Alice',
          round: null,
          submitted_at: '2026-04-15T10:00:00Z',
          payload: {
            scores: [
              { entry_id: 'e1', score: 5 },
              { entry_id: 'e2', score: 2 },
            ],
          },
          status: 'active',
          superseded_at: null,
        },
      ],
    });
    ref.setInput('tournament', t);
    ref.setInput('voterLabel', 'Alice');
    fixture.detectChanges();

    const rows = fixture.nativeElement.querySelectorAll('.row');
    expect(rows.length).toBe(2);
    expect(rows[0].textContent).toContain('Option A');
    expect(rows[0].textContent).toContain('5');
    expect(rows[1].textContent).toContain('Option B');
    expect(rows[1].textContent).toContain('2');
  });

  it('renders multivote rows for allocation payloads', () => {
    const t = makeTournament({
      mode: 'multivote',
      votes: [
        {
          id: 'v1',
          voter_label: 'Alice',
          round: null,
          submitted_at: '2026-04-15T10:00:00Z',
          payload: {
            allocations: [
              { entry_id: 'e1', votes: 3 },
              { entry_id: 'e2', votes: 1 },
            ],
          },
          status: 'active',
          superseded_at: null,
        },
      ],
    });
    ref.setInput('tournament', t);
    ref.setInput('voterLabel', 'Alice');
    fixture.detectChanges();

    const rows = fixture.nativeElement.querySelectorAll('.row');
    expect(rows.length).toBe(2);
    expect(rows[0].textContent).toContain('3 votes');
    expect(rows[1].textContent).toContain('1 vote');
  });

  it('shows ballot progress when no cool-off is active', () => {
    const t = makeTournament({
      votes: [
        {
          id: 'v1',
          voter_label: 'Alice',
          round: null,
          submitted_at: '2026-04-15T10:00:00Z',
          payload: { scores: [{ entry_id: 'e1', score: 5 }, { entry_id: 'e2', score: 2 }] },
          status: 'active',
          superseded_at: null,
        },
      ],
    });
    ref.setInput('tournament', t);
    ref.setInput('voterLabel', 'Alice');
    fixture.detectChanges();

    const progress = fixture.nativeElement.querySelector('.progress').textContent;
    expect(progress).toContain('1 of 2 voters have submitted');
  });

  it('shows cool-off countdown when cool_off_ends_at is in the future', () => {
    const futureIso = new Date(Date.now() + 27_000).toISOString();
    const t = makeTournament({
      cool_off_ends_at: futureIso,
      votes: [
        {
          id: 'v1',
          voter_label: 'Alice',
          round: null,
          submitted_at: '2026-04-15T10:00:00Z',
          payload: { scores: [{ entry_id: 'e1', score: 5 }, { entry_id: 'e2', score: 2 }] },
          status: 'active',
          superseded_at: null,
        },
      ],
    });
    ref.setInput('tournament', t);
    ref.setInput('voterLabel', 'Alice');
    fixture.detectChanges();

    const progress = fixture.nativeElement.querySelector('.progress').textContent;
    expect(progress).toMatch(/finalize in \d+s/i);
  });

  it('emits editClicked when the button is pressed', () => {
    const t = makeTournament({
      votes: [
        {
          id: 'v1',
          voter_label: 'Alice',
          round: null,
          submitted_at: '2026-04-15T10:00:00Z',
          payload: { scores: [{ entry_id: 'e1', score: 5 }, { entry_id: 'e2', score: 2 }] },
          status: 'active',
          superseded_at: null,
        },
      ],
    });
    ref.setInput('tournament', t);
    ref.setInput('voterLabel', 'Alice');
    fixture.detectChanges();

    let emitted = false;
    fixture.componentInstance.editClicked.subscribe(() => { emitted = true; });

    const button: HTMLButtonElement = fixture.nativeElement.querySelector('button');
    expect(button).toBeTruthy();
    button.click();
    expect(emitted).toBe(true);
  });

  it('hides edit button when allow_undo is false', () => {
    const t = makeTournament({
      config: { voter_labels: ['Alice'], allow_undo: false },
      votes: [
        {
          id: 'v1',
          voter_label: 'Alice',
          round: null,
          submitted_at: '2026-04-15T10:00:00Z',
          payload: { scores: [{ entry_id: 'e1', score: 5 }, { entry_id: 'e2', score: 2 }] },
          status: 'active',
          superseded_at: null,
        },
      ],
    });
    ref.setInput('tournament', t);
    ref.setInput('voterLabel', 'Alice');
    fixture.detectChanges();

    const button = fixture.nativeElement.querySelector('button');
    expect(button).toBeNull();
  });
});
