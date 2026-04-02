import { Component } from '@angular/core';
import { RouterOutlet, RouterLink, RouterLinkActive } from '@angular/router';

@Component({
  selector: 'app-pipeline-shell',
  standalone: true,
  imports: [RouterOutlet, RouterLink, RouterLinkActive],
  template: `
    <div class="admin-layout">
      <nav class="admin-sidebar">
        <h2>Admin Pipeline</h2>
        <ul>
          <li><a routerLink="assets" routerLinkActive="active">Assets</a></li>
          <li><a routerLink="templates" routerLinkActive="active">Templates</a></li>
          <li><a routerLink="knowledge" routerLinkActive="active">Knowledge</a></li>
          <li><a routerLink="reviews" routerLinkActive="active">Reviews</a></li>
          <li><a routerLink="publish-registry" routerLinkActive="active">Publish / Registry</a></li>
        </ul>
      </nav>
      <main class="admin-content">
        <router-outlet></router-outlet>
      </main>
    </div>
  `,
  styles: `
    .admin-layout {
      display: flex;
      height: 100vh;
    }
    .admin-sidebar {
      width: 250px;
      background-color: #f4f5f7;
      border-right: 1px solid #ddd;
      padding: 20px;
    }
    .admin-sidebar ul {
      list-style-type: none;
      padding: 0;
    }
    .admin-sidebar li {
      margin-bottom: 10px;
    }
    .admin-sidebar a {
      text-decoration: none;
      color: #333;
      display: block;
      padding: 8px;
      border-radius: 4px;
    }
    .admin-sidebar a.active {
      background-color: #0056b3;
      color: white;
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
