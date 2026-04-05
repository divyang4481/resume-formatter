import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

@Injectable({
  providedIn: 'root'
})
export class AdminTemplateApiService {
  private apiUrl = 'http://localhost:8000/admin/templates';

  constructor(private http: HttpClient) {}

  createTemplate(formData: FormData): Observable<any> {
    return this.http.post(`${this.apiUrl}/upload`, formData);
  }

  updateTemplate(templateId: string, payload: any): Observable<any> {
    return this.http.patch(`${this.apiUrl}/${templateId}`, payload);
  }

  listTemplates(): Observable<any> {
    return this.http.get(this.apiUrl);
  }

  getTemplate(templateId: string): Observable<any> {
    return this.http.get(`${this.apiUrl}/${templateId}`);
  }

  publishTemplate(templateId: string): Observable<any> {
    return this.http.post(`${this.apiUrl}/${templateId}/publish`, {});
  }

  archiveTemplate(templateId: string): Observable<any> {
    return this.http.post(`${this.apiUrl}/${templateId}/archive`, {});
  }

  revertTemplateToDraft(templateId: string): Observable<any> {
    return this.http.post(`${this.apiUrl}/${templateId}/revert-to-draft`, {});
  }


  listTestRuns(templateId: string): Observable<any> {
    return this.http.get(`${this.apiUrl}/${templateId}/test-runs`);
  }

  saveTestReview(templateId: string, testRunId: string, payload: any): Observable<any> {
    return this.http.post(`${this.apiUrl}/${templateId}/test-runs/${testRunId}/review`, payload);
  }

  analyzeTemplate(templateId: string): Observable<any> {
    return this.http.post(`${this.apiUrl}/${templateId}/analyze`, {});
  }

  getAuditLogs(jobId: string): Observable<any> {
    // Audit logs are at the root admin level, not under templates
    const baseUrl = this.apiUrl.replace('/templates', '');
    return this.http.get<any>(`${baseUrl}/audit-logs/${jobId}`);
  }
}
