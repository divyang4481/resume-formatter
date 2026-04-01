import { Component, OnInit } from '@angular/core';
import { MatCardModule } from '@angular/material/card';
import { ApiService } from '../services/api.service';
import { CommonModule } from '@angular/common';

@Component({
  selector: 'app-admin',
  standalone: true,
  imports: [MatCardModule, CommonModule],
  templateUrl: './admin.component.html',
  styleUrl: './admin.component.scss'
})
export class AdminComponent implements OnInit {
  healthStatus: any;

  constructor(private apiService: ApiService) {}

  ngOnInit() {
    this.apiService.getHealth().subscribe({
      next: (data) => {
        this.healthStatus = data;
      },
      error: (err) => {
        console.error('Error connecting to backend API', err);
        this.healthStatus = { status: 'Error', message: 'Could not reach backend' };
      }
    });
  }
}
