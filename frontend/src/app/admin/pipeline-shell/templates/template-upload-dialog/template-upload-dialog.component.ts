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
    MatSnackBarModule
  ],
  template: `
    <h2 mat-dialog-title>Upload New Template</h2>
    <mat-dialog-content>
      <form [formGroup]="uploadForm" class="upload-form">

        <mat-form-field appearance="outline">
          <mat-label>Template Name</mat-label>
          <input matInput formControlName="name" placeholder="e.g. IT Services Standard">
          <mat-error *ngIf="uploadForm.get('name')?.hasError('required')">Name is required</mat-error>
        </mat-form-field>

        <div class="row">
          <mat-form-field appearance="outline">
            <mat-label>Industry / JD Category</mat-label>
            <input matInput formControlName="industry" placeholder="e.g. IT Services">
          </mat-form-field>

          <mat-form-field appearance="outline">
            <mat-label>Role Family</mat-label>
            <input matInput formControlName="role_family" placeholder="e.g. Software Engineering">
          </mat-form-field>
        </div>

        <div class="row">
          <mat-form-field appearance="outline">
            <mat-label>Region / Market</mat-label>
            <input matInput formControlName="region" placeholder="e.g. US, EMEA, APAC">
          </mat-form-field>

          <mat-form-field appearance="outline">
            <mat-label>Language</mat-label>
            <mat-select formControlName="language">
              <mat-option value="en">English (en)</mat-option>
              <mat-option value="fr">French (fr)</mat-option>
              <mat-option value="de">German (de)</mat-option>
              <mat-option value="es">Spanish (es)</mat-option>
            </mat-select>
          </mat-form-field>
        </div>

        <mat-form-field appearance="outline">
          <mat-label>Short Description / Notes</mat-label>
          <textarea matInput formControlName="description" rows="3"></textarea>
        </mat-form-field>

        <div class="file-upload-container">
          <button type="button" mat-stroked-button (click)="fileInput.click()">
            <mat-icon>attach_file</mat-icon> Select Template Document
          </button>
          <input hidden (change)="onFileSelected($event)" #fileInput type="file" accept=".pdf,.docx,.doc,.txt">
          <span class="file-name" *ngIf="selectedFile">{{ selectedFile.name }}</span>
          <mat-error *ngIf="uploadForm.get('file')?.hasError('required') && uploadForm.get('file')?.touched">
            File is required
          </mat-error>
        </div>

      </form>
    </mat-dialog-content>
    <mat-dialog-actions align="end">
      <button mat-button mat-dialog-close [disabled]="isUploading">Cancel</button>
      <button mat-raised-button color="primary" (click)="onSubmit()" [disabled]="uploadForm.invalid || !selectedFile || isUploading">
        {{ isUploading ? 'Uploading...' : 'Upload & Create Draft' }}
      </button>
    </mat-dialog-actions>
  `,
  styles: [`
    .upload-form {
      display: flex;
      flex-direction: column;
      gap: 16px;
      margin-top: 8px;
    }
    .row {
      display: flex;
      gap: 16px;
    }
    .row mat-form-field {
      flex: 1;
    }
    .file-upload-container {
      display: flex;
      align-items: center;
      gap: 16px;
      padding: 8px 0;
    }
    .file-name {
      font-size: 14px;
      color: #666;
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
      name: ['', Validators.required],
      industry: [''],
      role_family: [''],
      region: [''],
      language: ['en'],
      description: [''],
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
      asset_type: 'template', // default type
      name: formValue.name,
      industry: formValue.industry || null,
      role_family: formValue.role_family || null,
      region: formValue.region || null,
      language: formValue.language,
      description: formValue.description || null
    };

    this.adminService.uploadTemplate(this.selectedFile, metadata).subscribe({
      next: (res) => {
        this.snackBar.open('Template uploaded successfully', 'Close', { duration: 3000 });
        this.dialogRef.close(true); // Return true to signal success
      },
      error: (err) => {
        console.error('Upload failed', err);
        this.snackBar.open('Upload failed. Please try again.', 'Close', { duration: 5000 });
        this.isUploading = false;
      }
    });
  }
}
