import { Component, OnInit, ViewChild, ElementRef } from '@angular/core';
import { FormBuilder, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatButtonModule } from '@angular/material/button';
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
    CommonModule
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
      candidateName: ['', Validators.required],
      industry: ['', Validators.required],
      templateId: ['', Validators.required]
    });
  }

  ngOnInit(): void {
    this.docService.loadIndustries();
    this.docService.loadTemplates();

    this.form.get('industry')?.valueChanges.subscribe(industryId => {
      this.docService.loadTemplates(industryId);
    });
  }

  onFileSelected(event: any): void {
    const file = event.target.files[0];
    if (file) {
      this.selectedFile = file;
    }
  }

  triggerFileInput(): void {
    this.fileInput.nativeElement.click();
  }

  processCV(): void {
    if (this.form.valid && this.selectedFile) {
      const vals = this.form.value;
      this.docService.submitDocument(
        this.selectedFile,
        vals.industry,
        vals.templateId,
        vals.candidateName
      );
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
