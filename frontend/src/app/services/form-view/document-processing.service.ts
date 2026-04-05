import { Injectable, signal } from '@angular/core';
import { ProcessingApiService, Industry, Template } from '../api/processing-api.service';

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
  public suggestedTemplateIds = signal<string[] | null>(null);
  public documentKind = signal<string | null>(null);
  public documentReason = signal<string | null>(null);
  public errorMessage = signal<string | null>(null);

  public summary = signal<string | null>(null);
  public outputUrl = signal<string | null>(null);
  public currentStage = signal<string | null>(null);
  public validationPassed = signal<boolean | null>(null);
  public validationReport = signal<string | null>(null);



  constructor(private api: ProcessingApiService) {}

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
        this.status.set('processing');
        this.pollJobStatus(res.job_id);
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

  public pollJobStatus(jobId: string) {

    this.api.getJobStatus(jobId).subscribe({
      next: (res) => {
        if (res.status === 'completed') {
          this.status.set('completed');
          this.fetchResults(jobId);
        } else if (res.status === 'failed') {
          this.status.set('error');
          this.errorMessage.set(res.error_message || 'Processing failed');
        } else if (res.status === 'waiting_for_confirmation') {
          this.suggestedTemplateId.set(res.suggested_template_ids?.[0] || null);
          this.suggestedTemplateIds.set(res.suggested_template_ids || null);
          this.documentKind.set(res.document_kind || null);
          this.documentReason.set(res.document_reason || null);
          this.status.set('waiting_for_confirmation');
        } else {
          // If still processing, wait 2 seconds and poll again
          this.currentStage.set(res.stage || null);
          
          // Capture intermediate validation if it exists
          if (res.validation_passed !== undefined) {
             this.validationPassed.set(res.validation_passed);
          }
          if (res.validation_report) {
             this.validationReport.set(res.validation_report);
          }

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
