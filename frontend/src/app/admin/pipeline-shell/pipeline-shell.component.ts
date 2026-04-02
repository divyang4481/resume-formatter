import { Component } from '@angular/core';
import { RouterOutlet, RouterLink, RouterLinkActive } from '@angular/router';
import { MatToolbarModule } from '@angular/material/toolbar';

@Component({
  selector: 'app-pipeline-shell',
  standalone: true,
  imports: [RouterOutlet, RouterLink, RouterLinkActive, MatToolbarModule],
  template: `
    <div class="admin-layout">
      <mat-toolbar color="primary">
        <span>Hays Admin Pipeline</span>
      </mat-toolbar>
      <main class="admin-content">
        <router-outlet></router-outlet>
      </main>
    </div>
  `,
  styles: `
    .admin-layout {
      display: flex;
      flex-direction: column;
      height: 100vh;
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
