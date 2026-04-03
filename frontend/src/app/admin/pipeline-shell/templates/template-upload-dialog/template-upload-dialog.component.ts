import { Component, Inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormBuilder, FormGroup, Validators, ReactiveFormsModule } from '@angular/forms';
import { MatDialogRef, MAT_DIALOG_DATA, MatDialogModule } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { AdminService } from '../../../../services/admin.service';

@Component({
  selector: 'app-template-upload-dialog',
  standalone: true,
  imports: [
    CommonModule,
    ReactiveFormsModule,
    MatDialogModule,
    MatFormFieldModule,
    MatInputModule,
    MatSelectModule,
    MatButtonModule,
    MatIconModule,
    MatSnackBarModule,
    MatProgressSpinnerModule
  ],
  template: `
    <h2 mat-dialog-title>Upload Template Document</h2>
    <mat-dialog-content>
      <form [formGroup]="uploadForm" class="upload-form">
        <p class="instruction-text">Upload a .docx template. Our AI will automatically suggest the name, purpose, and guidance policies based on the document content.</p>

        <div class="row">
          <mat-form-field appearance="outline">
            <mat-label>Industry / Vertical</mat-label>
            <input matInput formControlName="industry" placeholder="e.g. Technology, Healthcare">
            <mat-hint>Helps with classification</mat-hint>
          </mat-form-field>

          <mat-form-field appearance="outline">
            <mat-label>Template Language</mat-label>
            <mat-select formControlName="language">
              <mat-option value="en">English (default)</mat-option>
              <mat-option value="fr">French</mat-option>
              <mat-option value="de">German</mat-option>
              <mat-option value="es">Spanish</mat-option>
            </mat-select>
          </mat-form-field>
        </div>

        <div class="file-upload-zone" [class.has-file]="selectedFile" (click)="fileInput.click()">
          <mat-icon class="upload-icon">{{ selectedFile ? 'check_circle' : 'cloud_upload' }}</mat-icon>
          <div class="upload-text">
            <span *ngIf="!selectedFile">Click to select .docx template</span>
            <span *ngIf="selectedFile" class="file-name">{{ selectedFile.name }}</span>
          </div>
          <input hidden (change)="onFileSelected($event)" #fileInput type="file" accept=".docx">
        </div>
        <mat-error *ngIf="uploadForm.get('file')?.hasError('required') && uploadForm.get('file')?.touched" style="margin-top: 8px; text-align: center;">
          Template file is required
        </mat-error>

      </form>
    </mat-dialog-content>
    <mat-dialog-actions align="end">
      <button mat-button mat-dialog-close [disabled]="isUploading">Cancel</button>
      <button mat-flat-button color="primary" (click)="onSubmit()" [disabled]="uploadForm.invalid || !selectedFile || isUploading">
        <mat-spinner diameter="20" *ngIf="isUploading" style="margin-right: 8px; display: inline-block;"></mat-spinner>
        {{ isUploading ? 'Analyzing & Uploading...' : 'Start AI Analysis' }}
      </button>
    </mat-dialog-actions>
  `,
  styles: [`
    .upload-form {
      display: flex;
      flex-direction: column;
      gap: 20px;
      padding: 10px 0;
    }
    .instruction-text {
      font-size: 0.9rem;
      color: #64748b;
      margin-bottom: 8px;
      line-height: 1.4;
    }
    .row {
      display: flex;
      gap: 16px;
    }
    .row mat-form-field {
      flex: 1;
    }
    .file-upload-zone {
      border: 2px dashed #cbd5e1;
      border-radius: 12px;
      padding: 32px;
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 12px;
      cursor: pointer;
      transition: all 0.2s ease;
      background: #f8fafc;
      
      &:hover {
        border-color: #6366f1;
        background: #f1f5f9;
        .upload-icon { color: #6366f1; }
      }

      &.has-file {
        border-color: #10b981;
        background: #f0fdf4;
        .upload-icon { color: #10b981; }
      }
    }
    .upload-icon {
      font-size: 48px;
      width: 48px;
      height: 48px;
      color: #94a3b8;
    }
    .upload-text {
      font-weight: 500;
      color: #334155;
    }
    .file-name {
      color: #0f172a;
      font-weight: 600;
      text-align: center;
      word-break: break-all;
    }
    mat-spinner {
        vertical-align: middle;
    }
  `]
})
export class TemplateUploadDialogComponent {
  uploadForm: FormGroup;
  selectedFile: File | null = null;
  isUploading = false;

  constructor(
    private fb: FormBuilder,
    private adminService: AdminService,
    private dialogRef: MatDialogRef<TemplateUploadDialogComponent>,
    private snackBar: MatSnackBar
  ) {
    this.uploadForm = this.fb.group({
      industry: ['', Validators.required],
      language: ['en', Validators.required],
      file: [null, Validators.required]
    });
  }

  onFileSelected(event: any) {
    const file = event.target.files[0];
    if (file) {
      this.selectedFile = file;
      this.uploadForm.patchValue({ file: file });
      this.uploadForm.get('file')?.markAsTouched();
    }
  }

  onSubmit() {
    if (this.uploadForm.invalid || !this.selectedFile) {
      return;
    }

    this.isUploading = true;

    const formValue = this.uploadForm.value;
    const metadata = {
      asset_type: 'template_docx',
      name: '', // Will be suggested by AI
      industry: formValue.industry,
      language: formValue.language
    };

    this.adminService.uploadTemplate(this.selectedFile, metadata).subscribe({
      next: (res) => {
        this.snackBar.open('Template analyzed successfully', 'Close', { duration: 3000 });
        this.dialogRef.close(res.asset_id);
      },
      error: (err) => {
        console.error('Upload failed', err);
        this.snackBar.open('Analysis failed. Please try again.', 'Close', { duration: 5000 });
        this.isUploading = false;
      }
    });
  }
}
