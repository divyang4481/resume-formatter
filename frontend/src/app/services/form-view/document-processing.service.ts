import { Injectable, signal } from '@angular/core';
import { RuntimeApiService, Industry, Template } from '../api/runtime-api.service';

export type ProcessingStatus = 'idle' | 'uploading' | 'waiting_for_confirmation' | 'processing' | 'completed' | 'error';

@Injectable({
  providedIn: 'root'
})
export class DocumentProcessingService {
  public industries = signal<Industry[]>([]);
  public templates = signal<Template[]>([]);

  public status = signal<ProcessingStatus>('idle');
  public currentJobId = signal<string | null>(null);
  public currentDocumentId = signal<string | null>(null);

  public suggestedIndustryId = signal<string | null>(null);
  public suggestedTemplateId = signal<string | null>(null);

  public summary = signal<string | null>(null);
  public outputUrl = signal<string | null>(null);

  constructor(private api: RuntimeApiService) {}

  loadIndustries() {
    this.api.getIndustries().subscribe({
      next: (res) => this.industries.set(res.industries),
      error: (err) => console.error('Failed to load industries', err)
    });
  }

  loadTemplates(industryId?: string) {
    this.api.getTemplates(industryId).subscribe({
      next: (res) => this.templates.set(res.templates),
      error: (err) => console.error('Failed to load templates', err)
    });
  }

  submitDocument(file: File, industry?: string | null, templateId?: string | null) {
    this.status.set('uploading');
    this.summary.set(null);
    this.outputUrl.set(null);
    this.suggestedIndustryId.set(null);
    this.suggestedTemplateId.set(null);

    this.api.submitDocument(file, industry, templateId).subscribe({
      next: (res) => {
        this.currentDocumentId.set(res.documentId || res.jobId);
        this.currentJobId.set(res.jobId);

        if (res.requiresConfirmation) {
          this.suggestedIndustryId.set(res.suggestedIndustryId || null);
          this.suggestedTemplateId.set(res.suggestedTemplateId || null);
          this.status.set('waiting_for_confirmation');
        } else {
          this.status.set('processing');
          this.pollJobStatus(res.jobId);
        }
      },
      error: (err) => {
        console.error('Failed to submit document', err);
        this.status.set('error');
      }
    });
  }

  confirmDocument(industry: string, templateId: string) {
    const docId = this.currentDocumentId();
    const jobId = this.currentJobId();
    if (!docId || !jobId) return;

    this.status.set('processing');
    this.api.confirmDocument(docId, industry, templateId).subscribe({
      next: () => {
        this.pollJobStatus(jobId);
      },
      error: (err) => {
        console.error('Failed to confirm document', err);
        this.status.set('error');
      }
    });
  }

  private pollJobStatus(jobId: string) {
    const interval = setInterval(() => {
      this.api.getJobStatus(jobId).subscribe({
        next: (res) => {
          if (res.status === 'completed') {
            clearInterval(interval);
            this.status.set('completed');
            this.fetchResults(jobId);
          } else if (res.status === 'failed') {
            clearInterval(interval);
            this.status.set('error');
          }
        },
        error: (err) => {
          console.error('Failed to get job status', err);
          clearInterval(interval);
          this.status.set('error');
        }
      });
    }, 2000);
  }

  private fetchResults(jobId: string) {
    this.api.getJobSummary(jobId).subscribe({
      next: (res) => this.summary.set(res.summary),
      error: (err) => console.error('Failed to get summary', err)
    });

    this.api.getJobOutput(jobId).subscribe({
      next: (res) => this.outputUrl.set(res.url),
      error: (err) => console.error('Failed to get output', err)
    });
  }

  submitFeedback(feedback: string) {
    const jobId = this.currentJobId();
    if (jobId) {
      this.api.submitJobFeedback(jobId, feedback).subscribe({
        next: () => alert('Feedback submitted!'),
        error: (err) => console.error('Failed to submit feedback', err)
      });
    }
  }
}
