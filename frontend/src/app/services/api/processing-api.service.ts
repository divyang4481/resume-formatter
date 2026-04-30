import { Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';

export interface Industry {
  id: string;
  name: string;
}

export interface Template {
  id: string;
  name: string;
  industry: string;
}

@Injectable({
  providedIn: 'root'
})
export class ProcessingApiService {
  private apiUrl = `${environment.apiUrl}/v1/processing`;

  constructor(private http: HttpClient) {}

  getApiUrl(): string {
    return this.apiUrl;
  }

  getIndustries(): Observable<{ industries: Industry[] }> {
    return this.http.get<{ industries: Industry[] }>(`${this.apiUrl}/lookups/industries`);
  }

  getTemplates(industry?: string): Observable<{ templates: Template[] }> {
    let params = new HttpParams();
    if (industry) {
      params = params.set('industry', industry);
    }
    return this.http.get<{ templates: Template[] }>(`${this.apiUrl}/lookups/templates`, { params });
  }

  submitDocument(
    file: File,
    industry?: string | null,
    templateId?: string | null
  ): Observable<{
    document_id: string,
    job_id: string,
    status: string,
    requires_confirmation: boolean,
    suggested_industry_id?: string,
    suggested_template_id?: string,
    provided_industry_id?: string,
    provided_template_id?: string,
    message: string,
    document_kind?: string,
    document_confidence?: number,
    document_reason?: string,
    suggested_template_ids?: string[],
    suggested_template_scores?: any[]
  }> {
    const formData = new FormData();
    formData.append('file', file);
    if (industry) formData.append('industry_id', industry);
    if (templateId) formData.append('template_id', templateId);

    return this.http.post<any>(`${this.apiUrl}/documents/submit`, formData);
  }

  confirmDocument(documentId: string, industry: string, templateId: string): Observable<any> {
    return this.http.post<any>(`${this.apiUrl}/documents/${documentId}/confirm`, {
      industry_id: industry,
      template_id: templateId
    });
  }

  getJobStatus(jobId: string): Observable<any> {
    return this.http.get<any>(`${this.apiUrl}/jobs/${jobId}`);
  }

  getJobSummary(jobId: string): Observable<{ summary: string }> {
    return this.http.get<{ summary: string }>(`${this.apiUrl}/jobs/${jobId}/summary`);
  }

  getJobOutput(jobId: string): Observable<{ url: string, message: string }> {
    return this.http.get<{ url: string, message: string }>(`${this.apiUrl}/jobs/${jobId}/output`);
  }

  submitJobFeedback(jobId: string, feedback: string): Observable<any> {
    return this.http.post<any>(`${this.apiUrl}/jobs/${jobId}/feedback`, { feedback });
  }
}
