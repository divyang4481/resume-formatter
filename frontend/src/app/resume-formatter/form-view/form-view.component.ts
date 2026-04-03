import { Component, OnInit, ViewChild, ElementRef, effect, untracked } from '@angular/core';
import { FormBuilder, FormGroup, ReactiveFormsModule } from '@angular/forms';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatButtonModule } from '@angular/material/button';
import { RouterModule } from '@angular/router';
import { MatIconModule } from '@angular/material/icon';
import { MatSelectModule } from '@angular/material/select';
import { MatCardModule } from '@angular/material/card';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { CommonModule } from '@angular/common';
import { DocumentProcessingService } from '../../services/form-view/document-processing.service';

@Component({
  selector: 'app-form-view',
  standalone: true,
  imports: [
    ReactiveFormsModule,
    MatFormFieldModule,
    MatInputModule,
    MatButtonModule,
    MatIconModule,
    MatSelectModule,
    MatCardModule,
    MatProgressSpinnerModule,
    CommonModule,
    RouterModule
  ],
  templateUrl: './form-view.component.html',
  styleUrl: './form-view.component.scss'
})
export class FormViewComponent implements OnInit {
  form: FormGroup;
  selectedFile: File | null = null;
  feedbackText: string = '';

  @ViewChild('fileInput') fileInput!: ElementRef;

  constructor(
    private fb: FormBuilder,
    public docService: DocumentProcessingService
  ) {
    this.form = this.fb.group({
      industry: [{ value: '', disabled: true }],
      templateId: [{ value: '', disabled: true }]
    });

    effect(() => {
      if (this.docService.status() !== 'waiting_for_confirmation') return;

      const industry = this.docService.suggestedIndustryId();
      const templateId = this.docService.suggestedTemplateId();

      if (
        this.form.get('industry')?.value === industry &&
        this.form.get('templateId')?.value === templateId
      ) {
        return;
      }

      untracked(() => {
        this.form.patchValue(
          { industry, templateId },
          { emitEvent: false }
        );
      });
    });
  }

  ngOnInit(): void {
    this.docService.loadIndustries();
    this.docService.loadTemplates();

    this.form.get('industry')?.valueChanges.subscribe(industryId => {
      if (industryId) {
        this.docService.loadTemplates(industryId);
      }
    });
  }

  onFileSelected(event: any): void {
    const file = event.target.files[0];
    if (file) {
      this.selectedFile = file;
      this.form.get('industry')?.enable();
      this.form.get('templateId')?.enable();
    }
  }

  triggerFileInput(): void {
    this.fileInput.nativeElement.click();
  }

  processCV(): void {
    if (this.selectedFile) {
      const vals = this.form.getRawValue(); // gets values even if disabled/enabled

      if (this.docService.status() === 'waiting_for_confirmation') {
        // User confirming the suggested or modified values
        if (vals.industry && vals.templateId) {
          this.docService.confirmDocument(vals.industry, vals.templateId);
        }
      } else {
        // Initial submission
        this.docService.submitDocument(
          this.selectedFile,
          vals.industry || null,
          vals.templateId || null
        );
      }
    }
  }

  resetForm(): void {
    this.form.reset();
    this.selectedFile = null;
    this.docService.status.set('idle');
    this.docService.summary.set(null);
    this.docService.outputUrl.set(null);
  }

  submitFeedback(): void {
    if (this.feedbackText.trim()) {
      this.docService.submitFeedback(this.feedbackText);
      this.feedbackText = '';
    }
  }

  updateFeedback(event: any): void {
    this.feedbackText = event.target.value;
  }
}
