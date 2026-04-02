import { Injectable } from '@angular/core';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { Observable } from 'rxjs';

@Injectable({
  providedIn: 'root'
})
export class AdminTemplateTestingService {
  private runtimeUrl = 'http://localhost:8000/v1/runtime';

  constructor(private http: HttpClient) {}

  runTemplateTest(formData: FormData, templateId: string): Observable<any> {
    const headers = new HttpHeaders({
      'X-Execution-Mode': 'admin_template_test',
      'X-Actor-Role': 'admin'
    });

    // Ensure templateId is in the form data
    if (!formData.has('template_id')) {
        formData.append('template_id', templateId);
    }

    return this.http.post(`${this.runtimeUrl}/documents/submit`, formData, { headers });
  }

  getJob(jobId: string): Observable<any> {
    const headers = new HttpHeaders({
      'X-Actor-Role': 'admin'
    });
    return this.http.get(`${this.runtimeUrl}/jobs/${jobId}`, { headers });
  }

  getJobOutputs(jobId: string): Observable<any> {
    const headers = new HttpHeaders({
      'X-Actor-Role': 'admin'
    });
    return this.http.get(`${this.runtimeUrl}/jobs/${jobId}/output`, { headers });
  }

  getJobSummary(jobId: string): Observable<any> {
    const headers = new HttpHeaders({
      'X-Actor-Role': 'admin'
    });
    return this.http.get(`${this.runtimeUrl}/jobs/${jobId}/summary`, { headers });
  }
}
