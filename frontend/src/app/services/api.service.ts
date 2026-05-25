import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../environments/environment';

@Injectable({
  providedIn: 'root'
})
export class ApiService {
  private apiUrl = environment.baseApiUrl;

  constructor(private http: HttpClient) { }

  checkHealth(): Observable<any> {
    return this.http.get(`${this.apiUrl}/api/health`);
  }

  getRoot(): Observable<any> {
    return this.http.get(`${this.apiUrl}/api`);
  }
}
