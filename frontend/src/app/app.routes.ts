import { Routes } from '@angular/router';
import { DashboardComponent } from './tournaments/dashboard/dashboard.component';
import { OptionsPageComponent } from './options/options-page/options-page.component';
import { TournamentSetupComponent } from './tournaments/tournament-setup/tournament-setup.component';
import { TournamentOverviewComponent } from './tournaments/tournament-overview/tournament-overview.component';
import { TournamentVoteComponent } from './tournaments/tournament-vote/tournament-vote.component';
import { TournamentResultComponent } from './tournaments/tournament-result/tournament-result.component';
import { RandomPageComponent } from './random/random-page/random-page.component';

export const routes: Routes = [
  { path: '', component: DashboardComponent },
  { path: 'options', component: OptionsPageComponent },
  { path: 'tournaments/new', component: TournamentSetupComponent },
  { path: 'tournaments/:id/edit', component: TournamentSetupComponent },
  { path: 'tournaments/:id', component: TournamentOverviewComponent },
  { path: 'tournaments/:id/vote', component: TournamentVoteComponent },
  { path: 'tournaments/:id/result', component: TournamentResultComponent },
  { path: 'random', component: RandomPageComponent },
];
