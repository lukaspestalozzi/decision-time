import { ComponentFixture, TestBed } from '@angular/core/testing';
import { MatDialogRef } from '@angular/material/dialog';
import { provideAnimationsAsync } from '@angular/platform-browser/animations/async';
import { of } from 'rxjs';

import { BulkImportDialogComponent, BulkImportResult } from './bulk-import-dialog.component';
import { ApiService } from '../../services/api.service';

describe('BulkImportDialogComponent', () => {
  let fixture: ComponentFixture<BulkImportDialogComponent>;
  let component: BulkImportDialogComponent;
  let dialogRefSpy: { close: jest.Mock };

  beforeEach(async () => {
    dialogRefSpy = { close: jest.fn() };
    await TestBed.configureTestingModule({
      imports: [BulkImportDialogComponent],
      providers: [
        provideAnimationsAsync(),
        { provide: MatDialogRef, useValue: dialogRefSpy },
        { provide: ApiService, useValue: { listTags: () => of([]) } },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(BulkImportDialogComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('commits a typed-but-unconfirmed tag when the user clicks Import', () => {
    component.rawText.set('Luna\nMira');
    // Simulates a user who typed "pets" in the tag input but never pressed Enter/comma.
    component.tagInput.set('pets');
    expect(component.tags()).toEqual([]);

    component.submit();

    expect(dialogRefSpy.close).toHaveBeenCalledTimes(1);
    const closed = dialogRefSpy.close.mock.calls[0][0] as BulkImportResult;
    expect(closed.names).toEqual(['Luna', 'Mira']);
    expect(closed.tags).toEqual(['pets']);
  });

  it('does not duplicate a tag already in the list', () => {
    component.rawText.set('Luna');
    component.tags.set(['pets']);
    component.tagInput.set('pets');

    component.submit();

    const closed = dialogRefSpy.close.mock.calls[0][0] as BulkImportResult;
    expect(closed.tags).toEqual(['pets']);
  });

  it('passes through confirmed chips untouched when the input is empty', () => {
    component.rawText.set('Luna');
    component.tags.set(['a', 'b']);
    component.tagInput.set('');

    component.submit();

    const closed = dialogRefSpy.close.mock.calls[0][0] as BulkImportResult;
    expect(closed.tags).toEqual(['a', 'b']);
  });

  it('does nothing if the textarea is empty', () => {
    component.rawText.set('   \n   ');
    component.tagInput.set('pets');

    component.submit();

    expect(dialogRefSpy.close).not.toHaveBeenCalled();
  });
});
