import { Component } from '@angular/core';
import { MatCardModule } from '@angular/material/card';
import { MatIconModule } from '@angular/material/icon';
import { MatDividerModule } from '@angular/material/divider';
import { MatListModule } from '@angular/material/list';

@Component({
  selector: 'app-mcp-docs',
  standalone: true,
  imports: [MatCardModule, MatIconModule, MatDividerModule, MatListModule],
  template: `
    <div class="mcp-docs-container">
      <mat-card class="docs-card">
        <mat-card-header>
          <mat-icon mat-card-avatar>hub</mat-icon>
          <mat-card-title>Model Context Protocol (MCP) Integration</mat-card-title>
          <mat-card-subtitle>Agent-to-Agent Connectivity</mat-card-subtitle>
        </mat-card-header>

        <mat-card-content>
          <p>
            The Agentic Document Platform natively supports the <strong>Model Context Protocol (MCP)</strong>.
            This allows external AI assistants, such as Claude and Microsoft Copilot, to seamlessly connect to our backend and utilize document processing capabilities as native tools.
          </p>

          <mat-divider></mat-divider>

          <h3>🔌 Connection Endpoints</h3>
          <mat-list>
            <mat-list-item>
              <mat-icon matListItemIcon>rss_feed</mat-icon>
              <div matListItemTitle>SSE Stream Endpoint</div>
              <div matListItemLine><code>http://localhost:8000/mcp/sse</code></div>
            </mat-list-item>
            <mat-list-item>
              <mat-icon matListItemIcon>extension</mat-icon>
              <div matListItemTitle>Copilot / AI Plugin Manifest</div>
              <div matListItemLine><code>http://localhost:8000/.well-known/ai-plugin.json</code></div>
            </mat-list-item>
          </mat-list>

          <mat-divider></mat-divider>

          <h3>🛠️ Available Tools</h3>
          <p>Once connected, agents have access to the following tools:</p>
          <mat-list>
            <mat-list-item>
              <mat-icon matListItemIcon>upload_file</mat-icon>
              <div matListItemTitle>submit_document</div>
              <div matListItemLine>Submits a base64 encoded document for processing.</div>
            </mat-list-item>
            <mat-list-item>
              <mat-icon matListItemIcon>check_circle</mat-icon>
              <div matListItemTitle>confirm_document</div>
              <div matListItemLine>Approves a template selection and resumes processing.</div>
            </mat-list-item>
            <mat-list-item>
              <mat-icon matListItemIcon>sync</mat-icon>
              <div matListItemTitle>get_document_status</div>
              <div matListItemLine>Checks the processing state of a job.</div>
            </mat-list-item>
            <mat-list-item>
              <mat-icon matListItemIcon>summarize</mat-icon>
              <div matListItemTitle>summarize_document</div>
              <div matListItemLine>Retrieves the AI-generated professional summary of a CV.</div>
            </mat-list-item>
          </mat-list>

          <mat-divider></mat-divider>

          <h3>🤖 How to test with Claude Desktop</h3>
          <p>Add the following to your <code>claude_desktop_config.json</code> (or connect via HTTP SSE if supported in your agent orchestrator):</p>
          <pre class="code-block">
{{ '{' }}
  "mcpServers": {{ '{' }}
    "document_platform": {{ '{' }}
      "command": "python",
      "args": ["-m", "mcp_client", "http://localhost:8000/mcp/sse"]
    {{ '}' }}
  {{ '}' }}
{{ '}' }}
          </pre>
        </mat-card-content>
      </mat-card>
    </div>
  `,
  styles: [`
    .mcp-docs-container {
      padding: 24px;
      max-width: 900px;
      margin: 0 auto;
    }
    .docs-card {
      padding: 16px;
    }
    mat-divider {
      margin: 24px 0;
    }
    h3 {
      margin-top: 16px;
      color: #3f51b5;
    }
    .code-block {
      background: #1e1e1e;
      color: #d4d4d4;
      padding: 16px;
      border-radius: 4px;
      overflow-x: auto;
      font-family: monospace;
    }
    mat-icon {
      color: #666;
    }
  `]
})
export class McpDocsComponent {}
