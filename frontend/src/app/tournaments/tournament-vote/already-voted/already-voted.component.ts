import { Component } from '@angular/core';
import { MatCardModule } from '@angular/material/card';
import { MatIconModule } from '@angular/material/icon';

@Component({
  selector: 'app-already-voted',
  imports: [MatCardModule, MatIconModule],
  templateUrl: './already-voted.component.html',
  styleUrl: './already-voted.component.scss',
})
export class AlreadyVotedComponent {}
