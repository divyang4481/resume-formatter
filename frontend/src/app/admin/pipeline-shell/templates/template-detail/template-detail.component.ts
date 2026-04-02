import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, Router } from '@angular/router';
import { MatTabsModule } from '@angular/material/tabs';
import { MatCardModule } from '@angular/material/card';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSlideToggleModule } from '@angular/material/slide-toggle';
import { ReactiveFormsModule, FormBuilder, FormGroup } from '@angular/forms';
import { AdminTemplateApiService } from '../../../../services/admin-template-api.service';
import { AdminTemplateTestingService } from '../../../../services/admin-template-testing.service';

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
    ReactiveFormsModule
  ],
  templateUrl: './template-detail.component.html',
  styleUrls: ['./template-detail.component.scss']
})
export class TemplateDetailComponent implements OnInit {
  templateId: string = '';
  template: any = null;
  publishEligibility: any = null;
  testRuns: any[] = [];

  metadataForm: FormGroup;
  notesForm: FormGroup;
  testForm: FormGroup;

  selectedFile: File | null = null;
  currentJobId: string | null = null;
  jobStatus: any = null;
  jobOutputs: any = null;

  constructor(
    private route: ActivatedRoute,
    private router: Router,
    private fb: FormBuilder,
    private templateApi: AdminTemplateApiService,
    private testApi: AdminTemplateTestingService
  ) {
    this.metadataForm = this.fb.group({
      name: [''],
      industry: [''],
      role_family: [''],
      language: ['en'],
      selection_weight: [50],
      is_default_for_industry: [false]
    });

    this.notesForm = this.fb.group({
      notes: ['']
    });

    this.testForm = this.fb.group({
      industry_id: [''],
      job_description: [''],
      redact_pii: [false],
      generate_summary: [true]
    });
  }

  ngOnInit(): void {
    this.templateId = this.route.snapshot.paramMap.get('id') || '';
    if (this.templateId) {
      this.loadTemplate();
      this.loadTestRuns();
    }
  }

  loadTemplate() {
    this.templateApi.getTemplate(this.templateId).subscribe(res => {
      this.template = res.template;
      this.publishEligibility = res.publish_eligibility;

      this.metadataForm.patchValue(this.template);
      this.notesForm.patchValue({ notes: this.template.notes });
    });
  }

  loadTestRuns() {
    this.templateApi.listTestRuns(this.templateId).subscribe(res => {
      this.testRuns = res.test_runs;
    });
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

    const formData = new FormData();
    formData.append('file', this.selectedFile);
    formData.append('industry_id', this.testForm.value.industry_id);

    this.testApi.runTemplateTest(formData, this.templateId).subscribe(res => {
      this.currentJobId = res.job_id;
      this.pollJobStatus();
    });
  }

  pollJobStatus() {
    if (!this.currentJobId) return;

    this.testApi.getJob(this.currentJobId).subscribe(res => {
      this.jobStatus = res;
      if (res.status === 'completed') {
        this.loadJobOutputs();
      } else if (res.status === 'failed') {
        // Handle failure
      } else {
        setTimeout(() => this.pollJobStatus(), 3000);
      }
    });
  }

  loadJobOutputs() {
    if (!this.currentJobId) return;
    this.testApi.getJobOutputs(this.currentJobId).subscribe(res => {
      this.jobOutputs = res;
    });
    this.testApi.getJobSummary(this.currentJobId).subscribe(res => {
      if(this.jobOutputs) {
        this.jobOutputs.summary = res.summary;
      } else {
        this.jobOutputs = { summary: res.summary };
      }
    });
  }

  publish() {
    this.templateApi.publishTemplate(this.templateId).subscribe(() => {
      this.loadTemplate();
    });
  }

  archive() {
    this.templateApi.archiveTemplate(this.templateId).subscribe(() => {
      this.router.navigate(['/admin/templates']);
    });
  }
}
