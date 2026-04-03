import { Component } from '@angular/core';
import { RouterOutlet, RouterLink, RouterLinkActive } from '@angular/router';
import { MatToolbarModule } from '@angular/material/toolbar';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatTabsModule } from '@angular/material/tabs';

@Component({
  selector: 'app-pipeline-shell',
  standalone: true,
  imports: [RouterOutlet, RouterLink, RouterLinkActive, MatToolbarModule, MatButtonModule, MatIconModule, MatTabsModule],
  template: `
    <div class="admin-layout">
      <mat-toolbar color="primary">
        <span>Hays Admin Pipeline</span>
        <nav mat-tab-nav-bar [tabPanel]="tabPanel">
          <a mat-tab-link routerLink="/resumeformatter/formview" routerLinkActive #rlaForm="routerLinkActive" [active]="rlaForm.isActive">
            <mat-icon>text_fields</mat-icon> Form View
          </a>
          <a mat-tab-link routerLink="/resumeformatter/agentview" routerLinkActive #rlaAgent="routerLinkActive" [active]="rlaAgent.isActive">
            <mat-icon>smart_toy</mat-icon> Agent View
          </a>
          <a mat-tab-link routerLink="/admin/mcp-docs" routerLinkActive #rlaMcp="routerLinkActive" [active]="rlaMcp.isActive">
            <mat-icon>hub</mat-icon> MCP Docs
          </a>
        </nav>
      </mat-toolbar>

      <main class="admin-content">
        <mat-tab-nav-panel #tabPanel>
          <router-outlet></router-outlet>
        </mat-tab-nav-panel>
      </main>
    </div>
  `,

  styles: `
    .admin-layout {
      display: flex;
      flex-direction: column;
      height: 100vh;
    }
    .admin-layout mat-toolbar span {
       margin-right: 2rem;
    }
    .admin-content {

      flex: 1;
      padding: 20px;
      overflow-y: auto;
    }
  `
})
export class PipelineShellComponent {

}
