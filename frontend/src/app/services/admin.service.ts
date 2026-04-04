import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

export interface FieldExtractionManifestItem {
  fieldname: string;
  meaning: string;
  source_hints: string;
}

export interface TemplateAsset {
  id: string;
  asset_type: string;
  version: string;
  status: string;
  name: string;
  description?: string;
  industry?: string;
  role_family?: string;
  region?: string;
  language: string;
  tags: string[];

  // Guidance & Extraction Data
  notes?: string;
  purpose?: string;
  expected_sections?: string;
  expected_fields?: string;
  field_extraction_manifest?: FieldExtractionManifestItem[];
  summary_guidance?: string;
  formatting_guidance?: string;
  validation_guidance?: string;
  pii_guidance?: string;

  original_file_ref: string;
  checksum: string;
  extraction_artifact_ref?: string;
  render_config_ref?: string;
  created_by: string;
  created_at: string;
  updated_at: string;
  extension_metadata: any;
}

export interface TemplateListResponse {
  templates: TemplateAsset[];
}

@Injectable({
  providedIn: 'root'
})
export class AdminService {
  private apiUrl = 'http://localhost:8000/admin';

  constructor(private http: HttpClient) { }

  getTemplates(): Observable<TemplateListResponse> {
    return this.http.get<TemplateListResponse>(`${this.apiUrl}/templates`);
  }

  uploadTemplate(file: File, metadata: any): Observable<any> {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('metadata', JSON.stringify(metadata));

    return this.http.post(`${this.apiUrl}/templates/upload`, formData);
  }
}
