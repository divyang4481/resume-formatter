import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { MatTableModule } from '@angular/material/table';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatChipsModule } from '@angular/material/chips';
import { MatCardModule } from '@angular/material/card';
import { AdminService, TemplateAsset } from '../../../services/admin.service';
import { MatDialog, MatDialogModule } from '@angular/material/dialog';
import { TemplateUploadDialogComponent } from './template-upload-dialog/template-upload-dialog.component';

@Component({
  selector: 'app-templates',
  standalone: true,
  imports: [
    CommonModule,
    MatTableModule,
    MatButtonModule,
    MatIconModule,
    MatChipsModule,
    MatCardModule,
    MatDialogModule
  ],
  template: `
    <div class="templates-container">
      <div class="header">
        <h1>Global Dashboard & Listing</h1>
        <button mat-raised-button color="primary" (click)="openUploadDialog()">
          <mat-icon>add</mat-icon> New Template Pipeline
        </button>
      </div>

      <div class="kpi-cards">
        <mat-card class="kpi-card">
          <mat-card-header>
            <mat-card-title>Total Active</mat-card-title>
          </mat-card-header>
          <mat-card-content>
            <h2 class="kpi-value">{{ totalActive }}</h2>
          </mat-card-content>
        </mat-card>

        <mat-card class="kpi-card">
          <mat-card-header>
            <mat-card-title>Drafts Pending</mat-card-title>
          </mat-card-header>
          <mat-card-content>
            <h2 class="kpi-value">{{ draftsPending }}</h2>
          </mat-card-content>
        </mat-card>

        <mat-card class="kpi-card">
          <mat-card-header>
            <mat-card-title>Recent Failures</mat-card-title>
          </mat-card-header>
          <mat-card-content>
            <h2 class="kpi-value">0</h2>
          </mat-card-content>
        </mat-card>
      </div>

      <div class="table-container mat-elevation-z8">
        <table mat-table [dataSource]="templates">

          <ng-container matColumnDef="id">
            <th mat-header-cell *matHeaderCellDef> ID </th>
            <td mat-cell *matCellDef="let element"> {{element.id | slice:0:8}}... </td>
          </ng-container>

          <ng-container matColumnDef="name">
            <th mat-header-cell *matHeaderCellDef> Name </th>
            <td mat-cell *matCellDef="let element"> {{element.name}} </td>
          </ng-container>

          <ng-container matColumnDef="industry">
            <th mat-header-cell *matHeaderCellDef> Industry </th>
            <td mat-cell *matCellDef="let element"> {{element.industry || 'N/A'}} </td>
          </ng-container>

          <ng-container matColumnDef="role_family">
            <th mat-header-cell *matHeaderCellDef> Role Family </th>
            <td mat-cell *matCellDef="let element"> {{element.role_family || 'N/A'}} </td>
          </ng-container>

          <ng-container matColumnDef="region">
            <th mat-header-cell *matHeaderCellDef> Region </th>
            <td mat-cell *matCellDef="let element"> {{element.region || 'N/A'}} </td>
          </ng-container>

          <ng-container matColumnDef="version">
            <th mat-header-cell *matHeaderCellDef> Version </th>
            <td mat-cell *matCellDef="let element"> {{element.version}} </td>
          </ng-container>

          <ng-container matColumnDef="status">
            <th mat-header-cell *matHeaderCellDef> Status </th>
            <td mat-cell *matCellDef="let element">
              <mat-chip-set>
                <mat-chip [ngClass]="getStatusClass(element.status)">
                  {{element.status | uppercase}}
                </mat-chip>
              </mat-chip-set>
            </td>
          </ng-container>

          <tr mat-header-row *matHeaderRowDef="displayedColumns"></tr>
          <tr mat-row *matRowDef="let row; columns: displayedColumns;"></tr>
        </table>

        <div *ngIf="templates.length === 0" class="empty-state">
          No templates found. Create a new one to get started.
        </div>
      </div>
    </div>
  `,
  styles: [`
    .templates-container {
      padding: 24px;
    }
    .header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 24px;
    }
    h1 {
      margin: 0;
      font-size: 24px;
      color: #333;
    }
    .kpi-cards {
      display: flex;
      gap: 16px;
      margin-bottom: 24px;
    }
    .kpi-card {
      flex: 1;
    }
    .kpi-value {
      font-size: 36px;
      margin: 10px 0 0 0;
      color: #0056b3;
    }
    .table-container {
      background: white;
      border-radius: 8px;
      overflow: hidden;
    }
    table {
      width: 100%;
    }
    .empty-state {
      padding: 32px;
      text-align: center;
      color: #666;
    }

    ::ng-deep .status-draft {
      background-color: #e0e0e0 !important;
      color: #333 !important;
    }
    ::ng-deep .status-validated {
      background-color: #bbdefb !important;
      color: #0d47a1 !important;
    }
    ::ng-deep .status-pending {
      background-color: #fff9c4 !important;
      color: #f57f17 !important;
    }
    ::ng-deep .status-approved, ::ng-deep .status-active {
      background-color: #c8e6c9 !important;
      color: #1b5e20 !important;
    }
    ::ng-deep .status-published {
      background-color: #e1bee7 !important;
      color: #4a148c !important;
    }
  `]
})
export class TemplatesComponent implements OnInit {
  templates: TemplateAsset[] = [];
  displayedColumns: string[] = ['id', 'name', 'industry', 'role_family', 'region', 'version', 'status'];

  totalActive = 0;
  draftsPending = 0;

  constructor(private adminService: AdminService, private dialog: MatDialog) {}

  ngOnInit() {
    this.loadTemplates();
  }

  loadTemplates() {
    this.adminService.getTemplates().subscribe({
      next: (res) => {
        this.templates = res.templates;
        this.calculateKPIs();
      },
      error: (err) => {
        console.error('Failed to load templates', err);
      }
    });
  }

  calculateKPIs() {
    this.totalActive = this.templates.filter(t => t.status.toLowerCase() === 'active' || t.status.toLowerCase() === 'published').length;
    this.draftsPending = this.templates.filter(t => t.status.toLowerCase() === 'draft' || t.status.toLowerCase() === 'pending').length;
  }

  getStatusClass(status: string): string {
    const s = status ? status.toLowerCase() : '';
    if (s === 'draft') return 'status-draft';
    if (s === 'validated') return 'status-validated';
    if (s.includes('pending')) return 'status-pending';
    if (s === 'approved' || s === 'active') return 'status-approved';
    if (s === 'published') return 'status-published';
    return 'status-draft';
  }

  openUploadDialog() {
    const dialogRef = this.dialog.open(TemplateUploadDialogComponent, {
      width: '600px',
      disableClose: true
    });

    dialogRef.afterClosed().subscribe(result => {
      if (result) {
        this.loadTemplates();
      }
    });
  }
}
