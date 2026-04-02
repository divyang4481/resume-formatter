import { Routes } from '@angular/router';
import { AdminComponent } from './admin/admin.component';
import { PipelineShellComponent } from './admin/pipeline-shell/pipeline-shell.component';
import { AssetsComponent } from './admin/pipeline-shell/assets/assets.component';
import { TemplatesComponent } from './admin/pipeline-shell/templates/templates.component';
import { TemplateDetailComponent } from './admin/pipeline-shell/templates/template-detail/template-detail.component';
import { KnowledgeComponent } from './admin/pipeline-shell/knowledge/knowledge.component';
import { ReviewsComponent } from './admin/pipeline-shell/reviews/reviews.component';
import { PublishRegistryComponent } from './admin/pipeline-shell/publish-registry/publish-registry.component';
import { ResumeFormatterComponent } from './resume-formatter/resume-formatter.component';
import { AgentViewComponent } from './resume-formatter/agent-view/agent-view.component';
import { FormViewComponent } from './resume-formatter/form-view/form-view.component';

export const routes: Routes = [
  { path: '', redirectTo: '/resumeformatter', pathMatch: 'full' },
  {
    path: 'admin',
    component: PipelineShellComponent,
    children: [
      { path: '', redirectTo: 'templates', pathMatch: 'full' },
      { path: 'templates', component: TemplatesComponent },
      { path: 'templates/:id', component: TemplateDetailComponent }
    ]
  },
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
