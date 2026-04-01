import { Routes } from '@angular/router';
import { AdminComponent } from './admin/admin.component';
import { ResumeFormatterComponent } from './resume-formatter/resume-formatter.component';
import { AgentViewComponent } from './resume-formatter/agent-view/agent-view.component';
import { FormViewComponent } from './resume-formatter/form-view/form-view.component';

export const routes: Routes = [
  { path: '', redirectTo: '/resumeformatter', pathMatch: 'full' },
  { path: 'admin', component: AdminComponent },
  {
    path: 'resumeformatter',
    component: ResumeFormatterComponent,
    children: [
      { path: '', redirectTo: 'agentview', pathMatch: 'full' },
      { path: 'agentview', component: AgentViewComponent },
      { path: 'formview', component: FormViewComponent }
    ]
  }
];
