import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

@Injectable({
  providedIn: 'root'
})
export class ApiService {
  private apiUrl = 'http://localhost:8000'; // Default FastAPI backend URL

  constructor(private http: HttpClient) { }

  getHealth(): Observable<any> {
    return this.http.get(`${this.apiUrl}/health`);
  }

  getRoot(): Observable<any> {
    return this.http.get(`${this.apiUrl}/`);
  }
}
