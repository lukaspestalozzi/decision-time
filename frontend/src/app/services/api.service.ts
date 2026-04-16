import { HttpClient, HttpParams } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { Observable } from 'rxjs';
import { Option } from '../models/option.model';
import { Result, Tournament, TournamentMode } from '../models/tournament.model';
import { VoteContext } from '../models/vote-context.model';
import { environment } from '../../environments/environment';

@Injectable({ providedIn: 'root' })
export class ApiService {
  private http = inject(HttpClient);
  private base = environment.apiUrl;

  // --- Options ---

  listOptions(q?: string, tagsAll?: string, tagsAny?: string): Observable<Option[]> {
    let params = new HttpParams();
    if (q) params = params.set('q', q);
    if (tagsAll) params = params.set('tags_all', tagsAll);
    if (tagsAny) params = params.set('tags_any', tagsAny);
    return this.http.get<Option[]>(`${this.base}/options`, { params });
  }

  getOption(id: string): Observable<Option> {
    return this.http.get<Option>(`${this.base}/options/${id}`);
  }

  createOption(body: { name: string; description?: string; tags?: string[] }): Observable<Option> {
    return this.http.post<Option>(`${this.base}/options`, body);
  }

  updateOption(id: string, body: { name?: string; description?: string; tags?: string[] }): Observable<Option> {
    return this.http.put<Option>(`${this.base}/options/${id}`, body);
  }

  deleteOption(id: string): Observable<void> {
    return this.http.delete<void>(`${this.base}/options/${id}`);
  }

  bulkCreateOptions(body: { names: string[]; tags?: string[] }): Observable<Option[]> {
    return this.http.post<Option[]>(`${this.base}/options/bulk`, body);
  }

  bulkUpdateTags(body: { option_ids: string[]; add_tags?: string[]; remove_tags?: string[] }): Observable<Option[]> {
    return this.http.patch<Option[]>(`${this.base}/options/bulk`, body);
  }

  // --- Tags ---

  listTags(): Observable<string[]> {
    return this.http.get<string[]>(`${this.base}/tags`);
  }

  // --- Tournaments ---

  listTournaments(status?: string): Observable<Tournament[]> {
    let params = new HttpParams();
    if (status) params = params.set('status', status);
    return this.http.get<Tournament[]>(`${this.base}/tournaments`, { params });
  }

  getTournament(id: string): Observable<Tournament> {
    return this.http.get<Tournament>(`${this.base}/tournaments/${id}`);
  }

  createTournament(body: { name: string; mode: string; description?: string }): Observable<Tournament> {
    return this.http.post<Tournament>(`${this.base}/tournaments`, body);
  }

  updateTournament(id: string, body: {
    version: number;
    name?: string;
    description?: string;
    mode?: TournamentMode;
    selected_option_ids?: string[];
    config?: Record<string, unknown>;
  }): Observable<Tournament> {
    return this.http.put<Tournament>(`${this.base}/tournaments/${id}`, body);
  }

  deleteTournament(id: string): Observable<void> {
    return this.http.delete<void>(`${this.base}/tournaments/${id}`);
  }

  activateTournament(id: string, version: number): Observable<Tournament> {
    return this.http.post<Tournament>(`${this.base}/tournaments/${id}/activate`, { version });
  }

  cancelTournament(id: string, version: number): Observable<Tournament> {
    return this.http.post<Tournament>(`${this.base}/tournaments/${id}/cancel`, { version });
  }

  cloneTournament(id: string): Observable<Tournament> {
    return this.http.post<Tournament>(`${this.base}/tournaments/${id}/clone`, {});
  }

  getVoteContext(id: string, voter: string): Observable<VoteContext> {
    const params = new HttpParams().set('voter', voter);
    return this.http.get<VoteContext>(`${this.base}/tournaments/${id}/vote-context`, { params });
  }

  submitVote(id: string, body: {
    version: number;
    voter_label: string;
    payload: Record<string, unknown>;
  }): Observable<Tournament> {
    return this.http.post<Tournament>(`${this.base}/tournaments/${id}/vote`, body);
  }

  undoVote(id: string, body: {
    version: number;
    voter_label: string;
  }): Observable<{ tournament: Tournament; vote_context: VoteContext }> {
    return this.http.post<{ tournament: Tournament; vote_context: VoteContext }>(
      `${this.base}/tournaments/${id}/undo`,
      body,
    );
  }

  getResult(id: string): Observable<Result> {
    return this.http.get<Result>(`${this.base}/tournaments/${id}/result`);
  }

  getState(id: string): Observable<Record<string, unknown>> {
    return this.http.get<Record<string, unknown>>(`${this.base}/tournaments/${id}/state`);
  }
}
