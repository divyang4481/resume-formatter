import { Component, OnInit, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, Router } from '@angular/router';
import { MatTabsModule } from '@angular/material/tabs';
import { MatCardModule } from '@angular/material/card';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSlideToggleModule } from '@angular/material/slide-toggle';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatTableModule } from '@angular/material/table';
import { RouterModule } from '@angular/router';
import { MatChipsModule } from '@angular/material/chips';
import { MatExpansionModule } from '@angular/material/expansion';
import { MatDialogModule, MatDialog } from '@angular/material/dialog';
import { ReactiveFormsModule, FormBuilder, FormGroup } from '@angular/forms';

import { animate, state, style, transition, trigger } from '@angular/animations';
import { AdminTemplateApiService } from '../../../../services/admin-template-api.service';
import { AdminTemplateTestingService } from '../../../../services/admin-template-testing.service';
import { ViewChild, TemplateRef } from '@angular/core';

@Component({
  selector: 'app-template-detail',
  standalone: true,
  imports: [
    CommonModule,
    MatTabsModule,
    MatCardModule,
    MatButtonModule,
    MatIconModule,
    MatFormFieldModule,
    MatInputModule,
    MatSlideToggleModule,
    MatProgressSpinnerModule,
    MatTableModule,
    RouterModule,
    MatChipsModule,
    MatExpansionModule,
    ReactiveFormsModule,
    MatDialogModule
  ],
  templateUrl: './template-detail.component.html',
  styleUrls: ['./template-detail.component.scss'],
  animations: [

    trigger('detailExpand', [
      state('collapsed', style({height: '0px', minHeight: '0', display: 'none'})),
      state('expanded', style({height: '*'})),
      transition('expanded <=> collapsed', animate('225ms cubic-bezier(0.4, 0.0, 0.2, 1)')),
    ]),
  ]
})
export class TemplateDetailComponent implements OnInit, OnDestroy {
  templateId: string = '';
  template: any = null;
  publishEligibility: any = null;
  testRuns: any[] = [];
  displayedColumns: string[] = ['created_at', 'status', 'decision', 'warnings', 'actions'];
  expandedElement: any | null = null;

  pipelineStages = [
    { id: 'ingest', name: 'Ingestion', icon: 'cloud_upload' },
    { id: 'parse', name: 'Extraction', icon: 'document_scanner' },
    { id: 'classify', name: 'Classification', icon: 'category' },
    { id: 'normalize', name: 'Normalization', icon: 'schema' },
    { id: 'privacy', name: 'PII Privacy', icon: 'security' },
    { id: 'transform', name: 'AI Transformation', icon: 'auto_awesome' },
    { id: 'validate', name: 'Quality Check', icon: 'fact_check' },
    { id: 'render', name: 'Rendering', icon: 'picture_as_pdf' }
  ];


  metadataForm: FormGroup;
  requirementsForm: FormGroup;
  notesForm: FormGroup;
  testForm: FormGroup;


  selectedFile: File | null = null;
  currentJobId: string | null = null;
  jobStatus: any = null;
  jobOutputs: any = null;
  isRunningTest: boolean = false;

  private pollingTimeout: any;

  @ViewChild('auditLogsDialog') auditLogsDialogTemplate!: TemplateRef<any>;

  constructor(
    private route: ActivatedRoute,
    private router: Router,
    private fb: FormBuilder,
    private templateApi: AdminTemplateApiService,
    private testApi: AdminTemplateTestingService,
    private dialog: MatDialog
  ) {

    this.metadataForm = this.fb.group({
      name: [''],
      industry: [''],
      role_family: [''],
      language: ['en'],
      selection_weight: [50],
      is_default_for_industry: [false],
      purpose: ['']
    });

    this.requirementsForm = this.fb.group({
      expected_sections: [''],
      expected_fields: ['']
    });

    this.notesForm = this.fb.group({
      notes: [''],
      summary_guidance: [''],
      formatting_guidance: [''],
      validation_guidance: [''],
      pii_guidance: ['']
    });


    this.testForm = this.fb.group({
      industry_id: [''],
      job_description: [''],
      redact_pii: [false],
      generate_summary: [true]
    });
  }

  isAnalyzing: boolean = false;

  ngOnInit(): void {
    this.templateId = this.route.snapshot.paramMap.get('id') || '';
    if (this.templateId) {
      this.loadTemplate();
      this.refreshTestHistory();
    }
  }

  loadTemplate() {
    this.templateApi.getTemplate(this.templateId).subscribe(res => {
      this.template = res.template;
      this.publishEligibility = res.publish_eligibility;

      this.metadataForm.patchValue(this.template);
      this.requirementsForm.patchValue({
        expected_sections: this.template.expected_sections,
        expected_fields: this.template.expected_fields
      });
      this.notesForm.patchValue({
        notes: this.template.notes,
        summary_guidance: this.template.summary_guidance,
        formatting_guidance: this.template.formatting_guidance,
        validation_guidance: this.template.validation_guidance,
        pii_guidance: this.template.pii_guidance
      });
    });
  }

  analyzeTemplate() {
    this.isAnalyzing = true;
    this.templateApi.analyzeTemplate(this.templateId).subscribe({
      next: (res) => {
        this.isAnalyzing = false;
        if (res.suggestions) {
          // Pre-fill the forms with suggestions
          this.metadataForm.patchValue({
            purpose: res.suggestions.purpose
          });
          
          // Sync manifest suggestion into the current template view
          if (res.suggestions.field_extraction_manifest) {
             if (!this.template) this.template = {};
             this.template.field_extraction_manifest = res.suggestions.field_extraction_manifest;
          }

          this.requirementsForm.patchValue({
            expected_sections: res.suggestions.expected_sections,
            expected_fields: res.suggestions.expected_fields
          });
          
          this.notesForm.patchValue({
            summary_guidance: res.suggestions.summary_guidance,
            formatting_guidance: res.suggestions.formatting_guidance,
            validation_guidance: res.suggestions.validation_guidance,
            pii_guidance: res.suggestions.pii_guidance
          });
        }
      },
      error: () => {
        this.isAnalyzing = false;
      }
    });
  }

  saveRequirements() {
    this.templateApi.updateTemplate(this.templateId, this.requirementsForm.value).subscribe(() => {
      this.loadTemplate();
    });
  }


  refreshTestHistory() {
    this.templateApi.listTestRuns(this.templateId).subscribe(res => {
      this.testRuns = res.test_runs;
      this.checkAndPollActiveRuns();
    });
  }

  checkAndPollActiveRuns() {
    // If any test run doesn't have a decision and we aren't currently tracking it as currentJobId,
    // we should occasionally refresh the list. Since we don't have individual job statuses
    // without polling `getJob`, we'll just poll `listTestRuns` to see if results arrived.
    const hasPendingRuns = this.testRuns.some(run => !run.decision && !run.generated_summary);
    if (hasPendingRuns && !this.isRunningTest) {
      this.pollingTimeout = setTimeout(() => {
        this.refreshTestHistory();
      }, 5000);
    }
  }

  ngOnDestroy(): void {
    if (this.pollingTimeout) {
      clearTimeout(this.pollingTimeout);
    }
  }

  getStageStatus(stageId: string): string {
    if (!this.jobStatus) return 'pending';

    const status = this.jobStatus.status;
    const currentStage = this.jobStatus.stage;

    const stageIndex = this.pipelineStages.findIndex(s => s.id === stageId);
    const currentIndex = this.pipelineStages.findIndex(s => s.id === currentStage);

    if (status === 'failed' && currentStage === stageId) return 'failed';
    if (status === 'completed') return 'completed';

    if (stageIndex < currentIndex) return 'completed';
    if (stageIndex === currentIndex) return 'running';

    return 'pending';
  }

  getValidationWarningsCount(run: any): number {
    if (!run || !run.validation_result || !run.validation_result.warnings) return 0;
    return run.validation_result.warnings.length;
  }

  getValidationErrorsCount(run: any): number {
    if (!run || !run.validation_result || !run.validation_result.errors) return 0;
    return run.validation_result.errors.length;
  }

  saveMetadata() {
    this.templateApi.updateTemplate(this.templateId, this.metadataForm.value).subscribe(() => {
      this.loadTemplate();
    });
  }

  saveNotes() {
    this.templateApi.updateTemplate(this.templateId, this.notesForm.value).subscribe(() => {
      this.loadTemplate();
    });
  }

  onFileSelected(event: any) {
    this.selectedFile = event.target.files[0];
  }

  runTest() {
    if (!this.selectedFile) return;
    this.isRunningTest = true;
    this.jobStatus = { status: 'pending', stage: 'upload' };
    this.jobOutputs = null;

    const formData = new FormData();
    formData.append('file', this.selectedFile);
    formData.append('industry_id', this.testForm.value.industry_id);

    this.testApi.runTemplateTest(formData, this.templateId).subscribe({
      next: (res) => {
        this.currentJobId = res.job_id;
        this.pollJobStatus();
      },
      error: () => {
        this.isRunningTest = false;
      }
    });
  }

  pollJobStatus() {
    if (!this.currentJobId) return;

    this.testApi.getJob(this.currentJobId).subscribe({
      next: (res) => {
        this.jobStatus = res;
        if (res.status === 'completed') {
          this.isRunningTest = false;
          this.loadJobOutputs();
          this.refreshTestHistory(); // Refresh the history grid immediately
        } else if (res.status === 'failed') {
          this.isRunningTest = false;
          this.refreshTestHistory(); // Show the failure in history too
          // Handle failure
        } else {
          setTimeout(() => this.pollJobStatus(), 3000);
        }
      },
      error: () => {
        this.isRunningTest = false;
      }
    });
  }

  loadJobOutputs() {
    if (!this.currentJobId) return;
    this.testApi.getJobOutputs(this.currentJobId).subscribe(res => {
      this.jobOutputs = res;
    });
    this.testApi.getJobSummary(this.currentJobId).subscribe({
      next: (res) => {
        if(this.jobOutputs) {
          this.jobOutputs.summary = res.summary;
        } else {
          this.jobOutputs = { summary: res.summary };
        }
      },
      error: () => {
         if(this.jobOutputs) this.jobOutputs.summary = "Internal: Could not load generated summary string.";
      }
    });
  }

  reviewTestRun(testRunId: string, decision: string) {
    const payload = {
      decision: decision,
      review_notes: '',
      update_template_notes: false
    };
    this.templateApi.saveTestReview(this.templateId, testRunId, payload).subscribe(() => {
      this.refreshTestHistory();
      this.loadTemplate(); // reload template to update publish eligibility

      // Update currently displayed job output if we are looking at the current run
      if (this.currentJobId) {
        const matchingRun = this.testRuns.find(r => r.job_id === this.currentJobId);
        if (matchingRun && matchingRun.id === testRunId) {
            matchingRun.decision = decision;
        }
      }
    });
  }

  getCurrentTestRunId(): string | null {
    if (!this.currentJobId || !this.testRuns) return null;
    const run = this.testRuns.find(r => r.job_id === this.currentJobId);
    return run ? run.id : null;
  }

  getCurrentTestRunDecision(): string | null {
    if (!this.currentJobId || !this.testRuns) return null;
    const run = this.testRuns.find(r => r.job_id === this.currentJobId);
    return run ? run.decision : null;
  }

  publish() {
    this.templateApi.publishTemplate(this.templateId).subscribe(() => {
      this.loadTemplate();
    });
  }

  revertToDraft() {
    this.templateApi.revertTemplateToDraft(this.templateId).subscribe(() => {
      this.loadTemplate();
    });
  }

  archive() {
    this.templateApi.archiveTemplate(this.templateId).subscribe(() => {
      this.loadTemplate(); // Refresh locally instead of navigating away if we want to stay on the page
    });
  }

  openRunResults(dialogRef: any, run: any) {
    this.dialog.open(dialogRef, {
      width: '600px',
      data: { run }
    });
  }

  viewAuditLogs(jobId: string) {
    if (!jobId) return;
    this.templateApi.getAuditLogs(jobId).subscribe({
      next: (res) => {
        if (res.audit_logs && res.audit_logs.length > 0) {
          this.dialog.open(this.auditLogsDialogTemplate, {
            width: '800px',
            data: { logs: res.audit_logs }
          });
        } else {
          alert('No audit logs found for this run. Make sure ENABLE_AUDIT_LOGGING is true.');
        }
      },
      error: () => {
        alert('Failed to retrieve audit logs.');
      }
    });
  }
}


