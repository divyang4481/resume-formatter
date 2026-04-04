import { Component, OnInit, ViewChild, ElementRef, AfterViewInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute } from '@angular/router';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatCardModule } from '@angular/material/card';
import { HttpClient } from '@angular/common/http';
import * as docx from 'docx-preview';

@Component({
  selector: 'app-document-viewer',
  standalone: true,
  imports: [CommonModule, MatProgressSpinnerModule, MatCardModule],
  template: `
    <div class="viewer-container">
      <div *ngIf="loading" class="loading-state">
        <mat-spinner diameter="40"></mat-spinner>
        <p>Loading document...</p>
      </div>
      <div *ngIf="error" class="error-state">
        <mat-card>
          <mat-card-content class="error-content">
            <h3>Error loading document</h3>
            <p>{{ error }}</p>
          </mat-card-content>
        </mat-card>
      </div>
      <div #documentContainer class="document-container" [class.hidden]="loading || error"></div>
    </div>
  `,
  styles: [`
    .viewer-container {
      width: 100%;
      min-height: 100vh;
      background-color: #f5f5f5;
      display: flex;
      justify-content: center;
      padding: 24px;
      box-sizing: border-box;
    }
    .loading-state, .error-state {
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      height: 60vh;
    }
    .loading-state p {
      margin-top: 16px;
      color: #666;
    }
    .error-content {
      color: #f44336;
      text-align: center;
    }
    .document-container {
      width: 100%;
      max-width: 1000px;
      background: white;
      box-shadow: 0 4px 6px rgba(0,0,0,0.1);
      padding: 32px;
      min-height: 80vh;
    }
    .hidden {
      display: none;
    }
  `]
})
export class DocumentViewerComponent implements OnInit, AfterViewInit {
  @ViewChild('documentContainer') documentContainer!: ElementRef;
  jobId: string | null = null;
  loading = true;
  error: string | null = null;

  constructor(
    private route: ActivatedRoute,
    private http: HttpClient
  ) {}

  ngOnInit(): void {
    this.jobId = this.route.snapshot.paramMap.get('id');
  }

  ngAfterViewInit(): void {
    if (this.jobId) {
      this.loadDocument();
    } else {
      this.error = "No document ID provided.";
      this.loading = false;
    }
  }

  private loadDocument() {
    this.loading = true;
    this.error = null;

    const url = `/v1/processing/documents/${this.jobId}/download`;

    this.http.get(url, { responseType: 'blob' }).subscribe({
      next: async (blob) => {
        try {
          await docx.renderAsync(blob, this.documentContainer.nativeElement);
          this.loading = false;
        } catch (err) {
          console.error("Failed to render docx:", err);
          this.error = "Failed to render document format. It may be corrupted or in an unsupported format.";
          this.loading = false;
        }
      },
      error: (err) => {
        console.error("Failed to fetch document:", err);
        this.error = "Failed to download document from server.";
        this.loading = false;
      }
    });
  }
}
