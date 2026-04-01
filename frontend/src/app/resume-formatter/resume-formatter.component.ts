import { Component } from '@angular/core';
import { RouterOutlet, RouterModule } from '@angular/router';
import { MatToolbarModule } from '@angular/material/toolbar';
import { MatTabsModule } from '@angular/material/tabs';

@Component({
  selector: 'app-resume-formatter',
  standalone: true,
  imports: [RouterOutlet, RouterModule, MatToolbarModule, MatTabsModule],
  templateUrl: './resume-formatter.component.html',
  styleUrl: './resume-formatter.component.scss'
})
export class ResumeFormatterComponent {

}
