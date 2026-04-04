import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { MatCardModule } from '@angular/material/card';
import { MatIconModule } from '@angular/material/icon';
import { MatButtonModule } from '@angular/material/button';

@Component({
  selector: 'app-mcp-doc',
  standalone: true,
  imports: [CommonModule, MatCardModule, MatIconModule, MatButtonModule],
  template: `
    <div class="mcp-doc-container">
      <header>
        <h1><mat-icon>terminal</mat-icon> Model Context Protocol (MCP) Execution</h1>
        <p class="subtitle">Interact with the document processing engine as a composable AI tool.</p>
      </header>

      <section class="overview">
        <mat-card>
          <mat-card-header>
            <mat-icon mat-card-avatar>info</mat-icon>
            <mat-card-title>Protocol Overview</mat-card-title>
            <mat-card-subtitle>A2A and Tool-Use Integration</mat-card-subtitle>
          </mat-card-header>
          <mat-card-content>
            <p>
              The platform exposes a standardized <strong>MCP surface</strong>, allowing external LLMs or autonomous agents
              to call our processing pipelines as specialized tools. This is the **Model Context Protocol** in action.
            </p>
          </mat-card-content>
        </mat-card>
      </section>

      <section class="manifest">
         <h2>Tool Manifest (Discovery)</h2>
         <p>External environments can discover our capabilities via: <code>GET /mcp/manifest</code></p>
         
         <div class="tool-list">
            <mat-card class="tool-card">
               <h3><mat-icon>description</mat-icon> extract_and_format</h3>
               <p>Main tool for processing a document. Accepts a <code>document_uri</code> and an optional <code>template_id</code>.</p>
               <pre>POST /mcp/execute/extract_and_format</pre>
            </mat-card>

            <mat-card class="tool-card">
               <h3><mat-icon>search</mat-icon> list_templates</h3>
               <p>Discovery tool to see all approved templates available to other agents.</p>
               <pre>GET /v1/processing/lookups/templates</pre>
            </mat-card>
         </div>
      </section>

      <footer class="docs-link">
         <button mat-flat-button color="accent" onclick="window.open('https://modelcontextprotocol.io', '_blank')">
            <mat-icon>open_in_new</mat-icon> Official MCP Documentation
         </button>
      </footer>
    </div>
  `,
  styles: `
    .mcp-doc-container {
      max-width: 1000px;
      margin: 0 auto;
      padding: 1.5rem;
      font-family: 'Inter', system-ui, sans-serif;
    }
    header {
       margin-bottom: 2rem;
       h1 {
          display: flex;
          align-items: center;
          gap: 0.75rem;
          margin: 0;
          font-weight: 800;
          color: #2c3e50;
       }
       .subtitle {
          color: #64748b;
          font-size: 1.1rem;
          margin-top: 0.5rem;
       }
    }
    .overview mat-card {
       background: #f8fafc;
       border-left: 4px solid #3f51b5;
    }
    .manifest {
       margin-top: 3rem;
       h2 { font-weight: 700; border-bottom: 2px solid #e2e8f0; padding-bottom: 0.5rem; }
    }
    .tool-list {
       display: grid;
       grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
       gap: 1.5rem;
       margin-top: 1.5rem;
    }
    .tool-card {
       box-shadow: none;
       border: 1px solid #e2e8f0;
       h3 { display: flex; align-items: center; gap: 0.5rem; margin-top: 0; }
       pre { background: #1e293b; color: #cbd5e1; padding: 0.75rem; border-radius: 6px; font-size: 0.9rem; overflow-x: auto; }
    }
    .docs-link {
       margin-top: 4rem;
       text-align: center;
       opacity: 0.8;
       &:hover { opacity: 1; }
    }
  `
})
export class McpDocComponent {}
