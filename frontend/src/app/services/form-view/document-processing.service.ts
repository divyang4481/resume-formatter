import { Injectable, signal } from '@angular/core';
import { RuntimeApiService, Industry, Template } from '../api/runtime-api.service';

export type ProcessingStatus = 'idle' | 'uploading' | 'waiting_for_confirmation' | 'processing' | 'completed' | 'error';

@Injectable({
  providedIn: 'root'
})
export class DocumentProcessingService {
  public industries = signal<Industry[]>([]);
  public templates = signal<Template[]>([]);
  public noTemplatesAvailable = signal<boolean>(false);

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
      next: (res) => {
        this.industries.set(res.industries);
        this.updateAvailabilityFlag();
      },
      error: (err) => console.error('Failed to load industries', err)
    });
  }
  
  private updateAvailabilityFlag() {
      const showMissing = this.industries().length === 0 && this.templates().length === 0;
      this.noTemplatesAvailable.set(showMissing);
  }

  loadTemplates(industryId?: string) {
    this.api.getTemplates(industryId).subscribe({
      next: (res) => {
        this.templates.set(res.templates);
        this.updateAvailabilityFlag();
      },
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
        this.currentDocumentId.set(res.document_id || res.job_id);
        this.currentJobId.set(res.job_id);

        if (res.requires_confirmation) {
          this.suggestedIndustryId.set(res.suggested_industry_id || null);
          this.suggestedTemplateId.set(res.suggested_template_id || null);
          this.status.set('waiting_for_confirmation');
        } else {
          this.status.set('processing');
          this.pollJobStatus(res.job_id);
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
    this.api.getJobStatus(jobId).subscribe({
      next: (res) => {
        if (res.status === 'completed') {
          this.status.set('completed');
          this.fetchResults(jobId);
        } else if (res.status === 'failed') {
          this.status.set('error');
        } else {
          // If still processing, wait 2 seconds and poll again
          setTimeout(() => this.pollJobStatus(jobId), 2000);
        }
      },
      error: (err) => {
        console.error('Failed to get job status', err);
        // We can either retry or fail. For now, we will mark as error to match old behavior.
        this.status.set('error');
      }
    });
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
