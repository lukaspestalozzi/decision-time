import { ComponentRef } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideAnimationsAsync } from '@angular/platform-browser/animations/async';

import { VoterSelectorComponent } from './voter-selector.component';

describe('VoterSelectorComponent', () => {
  let component: VoterSelectorComponent;
  let componentRef: ComponentRef<VoterSelectorComponent>;
  let fixture: ComponentFixture<VoterSelectorComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [VoterSelectorComponent],
      providers: [provideAnimationsAsync()],
    }).compileComponents();

    fixture = TestBed.createComponent(VoterSelectorComponent);
    component = fixture.componentInstance;
    componentRef = fixture.componentRef;
  });

  it('renders one option per provided voter label', () => {
    componentRef.setInput('voterLabels', ['Alice', 'Bob', 'Charlie']);
    componentRef.setInput('currentVoter', 'Alice');
    fixture.detectChanges();

    // mat-select renders options into an overlay only when opened, so check
    // the component's exposed labels via its public API instead.
    expect(component.voterLabels()).toEqual(['Alice', 'Bob', 'Charlie']);
  });

  it('emits voterChange when onSelect is called', () => {
    componentRef.setInput('voterLabels', ['Alice', 'Bob']);
    componentRef.setInput('currentVoter', 'Alice');
    fixture.detectChanges();

    const emitted: string[] = [];
    component.voterChange.subscribe(value => emitted.push(value));
    component.onSelect('Bob');

    expect(emitted).toEqual(['Bob']);
  });
});
