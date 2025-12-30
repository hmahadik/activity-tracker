"""Report Export Module for Activity Tracker.

This module provides export functionality for activity reports to various
formats including Markdown, HTML, PDF, and JSON.

Supported formats:
- Markdown: Plain text with formatting
- HTML: Standalone HTML with embedded images
- PDF: Generated from HTML (requires weasyprint)
- JSON: Machine-readable data export

Example:
    >>> from tracker.report_export import ReportExporter
    >>> exporter = ReportExporter()
    >>> path = exporter.export(report, format='html')
    >>> print(f"Report saved to: {path}")
"""

from pathlib import Path
from datetime import datetime
import json
import base64
import logging
from typing import TYPE_CHECKING, Dict, Any, Optional

if TYPE_CHECKING:
    from .reports import Report

logger = logging.getLogger(__name__)


def is_pdf_available() -> bool:
    """Check if PDF export is available (weasyprint installed).

    Returns:
        True if weasyprint is available, False otherwise.
    """
    try:
        import weasyprint  # noqa: F401
        return True
    except ImportError:
        return False


class ReportExporter:
    """Export reports to various formats.

    Handles conversion of Report objects to different file formats
    with appropriate styling and embedded content.

    Attributes:
        output_dir: Directory where exported files are saved.
    """

    def __init__(self, output_dir: Path = None):
        """Initialize ReportExporter.

        Args:
            output_dir: Directory for exported files. Defaults to
                ~/activity-tracker-data/reports.
        """
        self.output_dir = output_dir or Path.home() / 'activity-tracker-data' / 'reports'
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def export(self, report: "Report", format: str = 'markdown') -> Path:
        """Export report to specified format.

        Args:
            report: Report object to export.
            format: Output format - 'markdown', 'html', 'pdf', or 'json'.

        Returns:
            Path to the exported file.

        Raises:
            ValueError: If format is not supported.
        """
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        safe_title = report.title.replace(' ', '_').replace(':', '')[:50]

        if format == 'markdown':
            return self._export_markdown(report, f"{safe_title}_{timestamp}.md")
        elif format == 'html':
            return self._export_html(report, f"{safe_title}_{timestamp}.html")
        elif format == 'pdf':
            return self._export_pdf(report, f"{safe_title}_{timestamp}.pdf")
        elif format == 'json':
            return self._export_json(report, f"{safe_title}_{timestamp}.json")
        else:
            raise ValueError(f"Unknown format: {format}")

    def export_from_dict(
        self,
        report_data: Dict[str, Any],
        format: str = 'markdown',
        save_to_history: bool = True
    ) -> Path:
        """Export report from dict data (as returned by API).

        This method allows exporting without regenerating the report - it uses
        the already-generated report data directly.

        Args:
            report_data: Report dict with keys: title, time_range, generated_at,
                executive_summary, sections, analytics, key_screenshots.
            format: Output format - 'markdown', 'html', 'pdf', or 'json'.
            save_to_history: Whether to save export to DB history.

        Returns:
            Path to the exported file.

        Raises:
            ValueError: If format is not supported or PDF requested but unavailable.
        """
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        safe_title = report_data.get('title', 'Report').replace(' ', '_').replace(':', '')[:50]

        if format == 'pdf' and not is_pdf_available():
            raise ValueError("PDF export requires weasyprint. Install with: pip install weasyprint")

        if format == 'markdown':
            path = self._export_markdown_from_dict(report_data, f"{safe_title}_{timestamp}.md")
        elif format == 'html':
            path = self._export_html_from_dict(report_data, f"{safe_title}_{timestamp}.html")
        elif format == 'pdf':
            path = self._export_pdf_from_dict(report_data, f"{safe_title}_{timestamp}.pdf")
        elif format == 'json':
            path = self._export_json_from_dict(report_data, f"{safe_title}_{timestamp}.json")
        else:
            raise ValueError(f"Unknown format: {format}")

        # Save to history
        if save_to_history:
            self._save_to_history(report_data, format, path)

        return path

    def _save_to_history(self, report_data: Dict[str, Any], format: str, path: Path) -> None:
        """Save export metadata to database history."""
        try:
            from .storage import ActivityStorage
            storage = ActivityStorage()

            # Get file size
            file_size = path.stat().st_size if path.exists() else None

            # Infer report_type from title or default to "summary"
            title = report_data.get('title', 'Report')
            if 'Standup' in title:
                report_type = 'standup'
            elif 'Detailed' in title:
                report_type = 'detailed'
            else:
                report_type = 'summary'

            storage.save_exported_report(
                title=title,
                time_range=report_data.get('time_range', ''),
                report_type=report_type,
                format=format,
                filename=path.name,
                filepath=str(path),
                file_size=file_size,
            )
            logger.debug(f"Saved export to history: {path.name}")
        except Exception as e:
            logger.warning(f"Failed to save export to history: {e}")

    def _export_markdown(self, report: "Report", filename: str) -> Path:
        """Export to Markdown with image references.

        Args:
            report: Report to export.
            filename: Output filename.

        Returns:
            Path to exported file.
        """
        lines = [
            f"# {report.title}",
            "",
            f"*Generated: {report.generated_at.strftime('%B %d, %Y at %I:%M %p')}*",
            "",
            "---",
            "",
            "## Executive Summary",
            "",
            report.executive_summary,
            "",
        ]

        # Analytics section
        lines.extend([
            "## Activity Overview",
            "",
            f"- **Total Active Time:** {report.analytics.total_active_minutes // 60}h {report.analytics.total_active_minutes % 60}m",
            f"- **Sessions:** {report.analytics.total_sessions}",
            f"- **Busiest Period:** {report.analytics.busiest_period}",
            "",
            "### Top Applications",
            "",
        ])

        for app in report.analytics.top_apps[:5]:
            lines.append(f"- {app['name']}: {app['minutes']}m ({app['percentage']}%)")

        lines.append("")

        # Sections
        for section in report.sections:
            lines.extend([
                f"## {section.title}",
                "",
                section.content,
                "",
            ])

        # Key screenshots
        if report.key_screenshots:
            lines.extend([
                "## Key Screenshots",
                "",
            ])
            for i, ss in enumerate(report.key_screenshots):
                ts = ss.get('timestamp')
                if isinstance(ts, int):
                    ts_str = datetime.fromtimestamp(ts).strftime('%I:%M %p')
                elif isinstance(ts, datetime):
                    ts_str = ts.strftime('%I:%M %p')
                else:
                    ts_str = str(ts)

                window_title = ss.get('window_title', 'Unknown')[:50]
                lines.append(f"### {ts_str} - {window_title}")
                lines.append("")
                lines.append(f"![Screenshot {i+1}]({ss.get('filepath', '')})")
                lines.append("")

        content = '\n'.join(lines)
        path = self.output_dir / filename
        path.write_text(content)
        logger.info(f"Exported markdown report to {path}")
        return path

    def _export_html(self, report: "Report", filename: str) -> Path:
        """Export to standalone HTML with embedded images.

        Args:
            report: Report to export.
            filename: Output filename.

        Returns:
            Path to exported file.
        """
        # Convert screenshots to base64 for embedding
        screenshot_embeds = []
        data_dir = Path.home() / 'activity-tracker-data'

        for ss in report.key_screenshots:
            try:
                filepath = ss.get('filepath', '')
                if filepath:
                    full_path = data_dir / 'screenshots' / filepath
                    if full_path.exists():
                        with open(full_path, 'rb') as f:
                            data = base64.b64encode(f.read()).decode()

                        ts = ss.get('timestamp')
                        if isinstance(ts, int):
                            ts_str = datetime.fromtimestamp(ts).strftime('%I:%M %p')
                        elif isinstance(ts, datetime):
                            ts_str = ts.strftime('%I:%M %p')
                        else:
                            ts_str = str(ts)

                        screenshot_embeds.append({
                            'data': data,
                            'time': ts_str,
                            'title': ss.get('window_title', 'Unknown')[:50]
                        })
            except Exception as e:
                logger.debug(f"Failed to embed screenshot: {e}")

        # Generate sections HTML with markdown conversion
        sections_html = ''
        for s in report.sections:
            content_html = self._convert_markdown_to_html(s.content)
            sections_html += f'<div class="section"><h2>{s.title}</h2><div class="section-content">{content_html}</div></div>'

        # Generate screenshots HTML with lightbox onclick
        screenshots_html = ''.join(
            f'''
            <div class="screenshot" onclick="openLightbox('data:image/webp;base64,{s["data"]}')">
                <img src="data:image/webp;base64,{s["data"]}" alt="Screenshot">
                <div class="screenshot-caption">{s["time"]} - {s["title"]}</div>
            </div>
            '''
            for s in screenshot_embeds
        )

        # Generate top apps HTML
        top_apps_html = ''.join(
            f'<li><span>{a["name"]}</span><span>{a["minutes"]}m ({a["percentage"]}%)</span></li>'
            for a in report.analytics.top_apps[:5]
        )

        # Generate hourly activity chart
        hourly_data = report.analytics.activity_by_hour
        max_hourly = max(hourly_data) if hourly_data else 1
        hourly_bars_html = ''
        for hour, mins in enumerate(hourly_data):
            height = (mins / max_hourly * 100) if max_hourly > 0 else 0
            hourly_bars_html += f'''
            <div class="hour-bar-col">
                <div class="hour-bar" style="height: {height}%" title="{mins}m"></div>
                <span class="hour-label">{hour}</span>
            </div>
            '''

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{report.title}</title>
    <style>
        :root {{
            --bg: #1a1a2e;
            --surface: #16213e;
            --text: #eee;
            --muted: #888;
            --accent: #4f8cff;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: var(--bg);
            color: var(--text);
            line-height: 1.6;
            max-width: 900px;
            margin: 0 auto;
            padding: 2rem;
        }}
        h1 {{ color: var(--accent); border-bottom: 2px solid var(--accent); padding-bottom: 0.5rem; }}
        h2 {{ color: var(--text); margin-top: 2rem; }}
        .meta {{ color: var(--muted); font-size: 0.9rem; }}
        .summary {{ background: var(--surface); padding: 1.5rem; border-radius: 8px; margin: 1rem 0; white-space: pre-line; }}
        .analytics {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; }}
        .stat {{ background: var(--surface); padding: 1rem; border-radius: 8px; text-align: center; }}
        .stat-value {{ font-size: 2rem; font-weight: bold; color: var(--accent); }}
        .stat-label {{ color: var(--muted); font-size: 0.9rem; }}
        .app-list {{ list-style: none; padding: 0; }}
        .app-list li {{ display: flex; justify-content: space-between; padding: 0.5rem 0; border-bottom: 1px solid var(--surface); }}
        .screenshot {{ margin: 1rem 0; cursor: pointer; }}
        .screenshot img {{ max-width: 100%; border-radius: 8px; border: 1px solid var(--surface); transition: transform 0.2s; }}
        .screenshot img:hover {{ transform: scale(1.02); }}
        .screenshot-caption {{ color: var(--muted); font-size: 0.9rem; margin-top: 0.5rem; }}
        .section {{ background: var(--surface); padding: 1.5rem; border-radius: 8px; margin: 1rem 0; }}
        .section-content {{ line-height: 1.7; }}
        .section-content p {{ margin-bottom: 0.5rem; }}
        .section-content ul {{ margin-left: 1.5rem; margin-bottom: 0.75rem; }}
        .section-content li {{ margin-bottom: 0.25rem; }}
        /* Hourly chart */
        .hourly-chart {{ background: var(--surface); padding: 1.5rem; border-radius: 8px; margin: 1rem 0; }}
        .hourly-chart h3 {{ margin-top: 0; margin-bottom: 1rem; }}
        .hour-bars {{ display: flex; align-items: flex-end; height: 100px; gap: 2px; }}
        .hour-bar-col {{ flex: 1; display: flex; flex-direction: column; align-items: center; }}
        .hour-bar {{ width: 100%; background: linear-gradient(180deg, var(--accent), #6ea8fe); border-radius: 2px 2px 0 0; min-height: 2px; }}
        .hour-label {{ font-size: 0.65rem; color: var(--muted); margin-top: 4px; }}
        /* Lightbox modal */
        .lightbox {{ display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.9); z-index: 1000; justify-content: center; align-items: center; }}
        .lightbox.active {{ display: flex; }}
        .lightbox img {{ max-width: 95%; max-height: 95%; object-fit: contain; border-radius: 8px; }}
        .lightbox-close {{ position: absolute; top: 20px; right: 30px; color: white; font-size: 40px; cursor: pointer; }}
    </style>
</head>
<body>
    <h1>{report.title}</h1>
    <p class="meta">Generated: {report.generated_at.strftime('%B %d, %Y at %I:%M %p')}</p>

    <div class="summary">
        <h2>Executive Summary</h2>
        <p>{report.executive_summary}</p>
    </div>

    <h2>Activity Overview</h2>
    <div class="analytics">
        <div class="stat">
            <div class="stat-value">{report.analytics.total_active_minutes // 60}h {report.analytics.total_active_minutes % 60}m</div>
            <div class="stat-label">Active Time</div>
        </div>
        <div class="stat">
            <div class="stat-value">{report.analytics.total_sessions}</div>
            <div class="stat-label">Sessions</div>
        </div>
        <div class="stat">
            <div class="stat-value">{len(report.analytics.top_apps)}</div>
            <div class="stat-label">Applications Used</div>
        </div>
    </div>

    <h3>Top Applications</h3>
    <ul class="app-list">
        {top_apps_html}
    </ul>

    <div class="hourly-chart">
        <h3>Activity by Hour</h3>
        <div class="hour-bars">
            {hourly_bars_html}
        </div>
    </div>

    {sections_html}

    <h2>Key Screenshots</h2>
    {screenshots_html}

    <!-- Lightbox modal for screenshots -->
    <div class="lightbox" id="lightbox" onclick="closeLightbox()">
        <span class="lightbox-close">&times;</span>
        <img id="lightbox-img" src="" alt="Screenshot">
    </div>

    <script>
        function openLightbox(src) {{
            document.getElementById('lightbox-img').src = src;
            document.getElementById('lightbox').classList.add('active');
        }}
        function closeLightbox() {{
            document.getElementById('lightbox').classList.remove('active');
        }}
        document.addEventListener('keydown', function(e) {{
            if (e.key === 'Escape') closeLightbox();
        }});
    </script>
</body>
</html>"""

        path = self.output_dir / filename
        path.write_text(html)
        logger.info(f"Exported HTML report to {path}")
        return path

    def _export_pdf(self, report: "Report", filename: str) -> Path:
        """Export to PDF using weasyprint.

        Falls back to HTML if weasyprint is not available.

        Args:
            report: Report to export.
            filename: Output filename.

        Returns:
            Path to exported file.
        """
        # First generate HTML
        html_filename = filename.replace('.pdf', '_temp.html')
        html_path = self._export_html(report, html_filename)
        pdf_path = self.output_dir / filename

        try:
            from weasyprint import HTML
            HTML(str(html_path)).write_pdf(str(pdf_path))
            html_path.unlink()  # Clean up temp HTML
            logger.info(f"Exported PDF report to {pdf_path}")
            return pdf_path
        except ImportError:
            logger.warning("weasyprint not available, keeping HTML file")
            # Rename HTML to final name
            final_html_path = pdf_path.with_suffix('.html')
            html_path.rename(final_html_path)
            return final_html_path

    def _export_json(self, report: "Report", filename: str) -> Path:
        """Export raw report data as JSON.

        Args:
            report: Report to export.
            filename: Output filename.

        Returns:
            Path to exported file.
        """
        # Convert screenshots to serializable format
        key_screenshots = []
        for ss in report.key_screenshots:
            ts = ss.get('timestamp')
            if isinstance(ts, int):
                ts_str = datetime.fromtimestamp(ts).isoformat()
            elif isinstance(ts, datetime):
                ts_str = ts.isoformat()
            else:
                ts_str = str(ts)

            key_screenshots.append({
                'id': ss.get('id'),
                'filepath': ss.get('filepath'),
                'timestamp': ts_str,
                'window_title': ss.get('window_title', ''),
                'app_name': ss.get('app_name', '')
            })

        data = {
            'title': report.title,
            'time_range': report.time_range,
            'generated_at': report.generated_at.isoformat(),
            'executive_summary': report.executive_summary,
            'sections': [
                {'title': s.title, 'content': s.content}
                for s in report.sections
            ],
            'analytics': {
                'total_active_minutes': report.analytics.total_active_minutes,
                'total_sessions': report.analytics.total_sessions,
                'top_apps': report.analytics.top_apps,
                'top_windows': report.analytics.top_windows,
                'activity_by_hour': report.analytics.activity_by_hour,
                'activity_by_day': report.analytics.activity_by_day,
                'busiest_period': report.analytics.busiest_period,
            },
            'key_screenshots': key_screenshots
        }

        path = self.output_dir / filename
        path.write_text(json.dumps(data, indent=2))
        logger.info(f"Exported JSON report to {path}")
        return path

    # ==================== Dict-based export methods ====================
    # These work with report data as returned by the API (dict format)

    def _export_markdown_from_dict(self, data: Dict[str, Any], filename: str) -> Path:
        """Export to Markdown from dict data."""
        analytics = data.get('analytics', {})
        total_mins = analytics.get('total_active_minutes', 0)

        lines = [
            f"# {data.get('title', 'Activity Report')}",
            "",
            f"*Generated: {data.get('generated_at', '')}*",
            "",
            "---",
            "",
            "## Executive Summary",
            "",
            data.get('executive_summary', ''),
            "",
            "## Activity Overview",
            "",
            f"- **Total Active Time:** {total_mins // 60}h {total_mins % 60}m",
            f"- **Sessions:** {analytics.get('total_sessions', 0)}",
            f"- **Busiest Period:** {analytics.get('busiest_period', 'N/A')}",
            "",
            "### Top Applications",
            "",
        ]

        for app in analytics.get('top_apps', [])[:5]:
            lines.append(f"- {app.get('name', 'Unknown')}: {app.get('minutes', 0)}m ({app.get('percentage', 0)}%)")

        lines.append("")

        # Sections
        for section in data.get('sections', []):
            lines.extend([
                f"## {section.get('title', '')}",
                "",
                section.get('content', ''),
                "",
            ])

        # Key screenshots - use URL for viewing
        screenshots = data.get('key_screenshots', [])
        if screenshots:
            lines.extend(["## Key Screenshots", ""])
            for i, ss in enumerate(screenshots):
                ts = ss.get('timestamp', '')
                if 'T' in str(ts):
                    try:
                        ts = datetime.fromisoformat(ts.replace('Z', '+00:00')).strftime('%I:%M %p')
                    except Exception:
                        pass
                window_title = ss.get('window_title', 'Unknown')[:50]
                lines.append(f"### {ts} - {window_title}")
                lines.append("")
                # Use URL since we don't have filepath in API response
                lines.append(f"![Screenshot {i+1}]({ss.get('url', '')})")
                lines.append("")

        content = '\n'.join(lines)
        path = self.output_dir / filename
        path.write_text(content)
        logger.info(f"Exported markdown report to {path}")
        return path

    def _convert_markdown_to_html(self, text: str) -> str:
        """Convert basic markdown to HTML.

        Handles:
        - **bold** -> <strong>bold</strong>
        - *italic* -> <em>italic</em>
        - Bullet points (- item or * item)
        - Newlines to paragraphs
        """
        import re

        if not text:
            return ''

        # Convert **bold**
        text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)

        # Convert *italic* (but not if part of a list marker)
        text = re.sub(r'(?<!\*)\*([^*\n]+?)\*(?!\*)', r'<em>\1</em>', text)

        # Convert bullet lists
        lines = text.split('\n')
        in_list = False
        result_lines = []

        for line in lines:
            stripped = line.strip()
            # Check if it's a bullet point
            if stripped.startswith('- ') or stripped.startswith('* '):
                if not in_list:
                    result_lines.append('<ul>')
                    in_list = True
                item_content = stripped[2:].strip()
                result_lines.append(f'<li>{item_content}</li>')
            else:
                if in_list:
                    result_lines.append('</ul>')
                    in_list = False
                if stripped:
                    result_lines.append(f'<p>{line}</p>')
                else:
                    result_lines.append('')

        if in_list:
            result_lines.append('</ul>')

        return '\n'.join(result_lines)

    def _export_html_from_dict(self, data: Dict[str, Any], filename: str) -> Path:
        """Export to standalone HTML from dict data with professional styling."""
        analytics = data.get('analytics', {})
        total_mins = analytics.get('total_active_minutes', 0)

        # For HTML export, we need to fetch screenshots and embed them
        screenshot_embeds = []
        data_dir = Path.home() / 'activity-tracker-data'

        for ss in data.get('key_screenshots', []):
            try:
                ss_id = ss.get('id')
                if ss_id:
                    from .storage import ActivityStorage
                    storage = ActivityStorage()
                    ss_data = storage.get_screenshot(ss_id)
                    if ss_data and ss_data.get('filepath'):
                        full_path = data_dir / 'screenshots' / ss_data['filepath']
                        if full_path.exists():
                            with open(full_path, 'rb') as f:
                                img_data = base64.b64encode(f.read()).decode()
                            screenshot_embeds.append({
                                'data': img_data,
                                'time': ss.get('timestamp', ''),
                                'title': ss.get('window_title', 'Unknown')[:60]
                            })
            except Exception as e:
                logger.debug(f"Failed to embed screenshot: {e}")

        # Convert executive summary markdown to HTML
        exec_summary_html = self._convert_markdown_to_html(data.get('executive_summary', ''))

        # Generate sections HTML with markdown conversion
        sections_html = ''
        for s in data.get('sections', []):
            content_html = self._convert_markdown_to_html(s.get('content', ''))
            sections_html += f'''
            <div class="section">
                <h3>{s.get("title", "")}</h3>
                <div class="section-content">{content_html}</div>
            </div>
            '''

        # Generate screenshots gallery with clickable lightbox
        screenshots_html = ''
        if screenshot_embeds:
            screenshots_html = '<div class="screenshot-gallery">'
            for s in screenshot_embeds:
                screenshots_html += f'''
                <div class="screenshot-item" onclick="openLightbox('data:image/webp;base64,{s["data"]}')">
                    <img src="data:image/webp;base64,{s["data"]}" alt="Screenshot" loading="lazy">
                    <div class="screenshot-caption">
                        <span class="time">{s["time"]}</span>
                        <span class="title">{s["title"]}</span>
                    </div>
                </div>
                '''
            screenshots_html += '</div>'

        # Generate app usage bars
        top_apps = analytics.get('top_apps', [])[:7]
        max_pct = max((a.get('percentage', 0) for a in top_apps), default=100) or 100
        app_bars_html = ''
        for app in top_apps:
            pct = app.get('percentage', 0)
            bar_width = (pct / max_pct) * 100
            app_bars_html += f'''
            <div class="app-bar-row">
                <span class="app-name">{app.get("name", "Unknown")}</span>
                <div class="app-bar-container">
                    <div class="app-bar" style="width: {bar_width}%"></div>
                </div>
                <span class="app-stats">{app.get("minutes", 0)}m ({pct}%)</span>
            </div>
            '''

        # Generate hourly activity chart (simple bar chart)
        hourly_data = analytics.get('activity_by_hour', [0] * 24)
        max_hourly = max(hourly_data) if hourly_data else 1
        hourly_bars_html = ''
        for hour, mins in enumerate(hourly_data):
            height = (mins / max_hourly * 100) if max_hourly > 0 else 0
            label = f'{hour}:00'
            hourly_bars_html += f'''
            <div class="hour-bar-col">
                <div class="hour-bar" style="height: {height}%" title="{mins}m"></div>
                <span class="hour-label">{hour}</span>
            </div>
            '''

        # Format generated time
        generated_at = data.get('generated_at', '')
        if generated_at:
            try:
                if 'T' in generated_at:
                    dt = datetime.fromisoformat(generated_at.replace('Z', '+00:00'))
                    generated_at = dt.strftime('%B %d, %Y at %I:%M %p')
            except Exception:
                pass

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{data.get('title', 'Activity Report')}</title>
    <style>
        /* Professional light theme */
        :root {{
            --bg: #ffffff;
            --surface: #f8f9fa;
            --surface-alt: #e9ecef;
            --text: #212529;
            --text-muted: #6c757d;
            --accent: #0d6efd;
            --accent-light: #e7f1ff;
            --border: #dee2e6;
            --success: #198754;
        }}

        * {{ box-sizing: border-box; margin: 0; padding: 0; }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background: var(--bg);
            color: var(--text);
            line-height: 1.6;
            font-size: 14px;
        }}

        .container {{
            max-width: 1000px;
            margin: 0 auto;
            padding: 2rem;
        }}

        /* Header */
        .header {{
            border-bottom: 3px solid var(--accent);
            padding-bottom: 1.5rem;
            margin-bottom: 2rem;
        }}

        .header h1 {{
            font-size: 1.75rem;
            font-weight: 600;
            color: var(--text);
            margin-bottom: 0.5rem;
        }}

        .header .meta {{
            color: var(--text-muted);
            font-size: 0.875rem;
        }}

        /* Stats cards */
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 1rem;
            margin-bottom: 2rem;
        }}

        .stat-card {{
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 1.25rem;
            text-align: center;
        }}

        .stat-value {{
            font-size: 2rem;
            font-weight: 700;
            color: var(--accent);
            line-height: 1.2;
        }}

        .stat-label {{
            color: var(--text-muted);
            font-size: 0.8rem;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-top: 0.25rem;
        }}

        /* Executive Summary */
        .summary-section {{
            background: var(--accent-light);
            border-left: 4px solid var(--accent);
            padding: 1.5rem;
            margin-bottom: 2rem;
            border-radius: 0 8px 8px 0;
        }}

        .summary-section h2 {{
            font-size: 1.1rem;
            font-weight: 600;
            color: var(--accent);
            margin-bottom: 1rem;
        }}

        .summary-section p {{
            margin-bottom: 0.75rem;
        }}

        .summary-section ul {{
            margin-left: 1.5rem;
            margin-bottom: 0.75rem;
        }}

        .summary-section li {{
            margin-bottom: 0.25rem;
        }}

        /* App usage */
        .app-usage {{
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 1.5rem;
            margin-bottom: 2rem;
        }}

        .app-usage h2 {{
            font-size: 1rem;
            font-weight: 600;
            margin-bottom: 1rem;
        }}

        .app-bar-row {{
            display: flex;
            align-items: center;
            margin-bottom: 0.75rem;
        }}

        .app-name {{
            width: 120px;
            font-size: 0.85rem;
            font-weight: 500;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }}

        .app-bar-container {{
            flex: 1;
            height: 20px;
            background: var(--surface-alt);
            border-radius: 4px;
            margin: 0 1rem;
            overflow: hidden;
        }}

        .app-bar {{
            height: 100%;
            background: linear-gradient(90deg, var(--accent), #6ea8fe);
            border-radius: 4px;
            transition: width 0.3s ease;
        }}

        .app-stats {{
            width: 90px;
            text-align: right;
            font-size: 0.8rem;
            color: var(--text-muted);
        }}

        /* Hourly activity chart */
        .hourly-chart {{
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 1.5rem;
            margin-bottom: 2rem;
        }}

        .hourly-chart h2 {{
            font-size: 1rem;
            font-weight: 600;
            margin-bottom: 1rem;
        }}

        .hour-bars {{
            display: flex;
            align-items: flex-end;
            height: 100px;
            gap: 2px;
        }}

        .hour-bar-col {{
            flex: 1;
            display: flex;
            flex-direction: column;
            align-items: center;
        }}

        .hour-bar {{
            width: 100%;
            background: linear-gradient(180deg, var(--accent), #6ea8fe);
            border-radius: 2px 2px 0 0;
            min-height: 2px;
        }}

        .hour-label {{
            font-size: 0.65rem;
            color: var(--text-muted);
            margin-top: 4px;
        }}

        /* Daily sections */
        .daily-breakdown {{
            margin-bottom: 2rem;
        }}

        .daily-breakdown > h2 {{
            font-size: 1.1rem;
            font-weight: 600;
            margin-bottom: 1rem;
            padding-bottom: 0.5rem;
            border-bottom: 2px solid var(--border);
        }}

        .section {{
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 1.25rem;
            margin-bottom: 1rem;
        }}

        .section h3 {{
            font-size: 0.95rem;
            font-weight: 600;
            color: var(--accent);
            margin-bottom: 0.75rem;
        }}

        .section-content {{
            font-size: 0.9rem;
            color: var(--text);
        }}

        .section-content p {{
            margin-bottom: 0.5rem;
        }}

        .section-content ul {{
            margin-left: 1.25rem;
            margin-bottom: 0.5rem;
        }}

        .section-content li {{
            margin-bottom: 0.25rem;
        }}

        /* Screenshots gallery */
        .screenshots {{
            margin-bottom: 2rem;
        }}

        .screenshots > h2 {{
            font-size: 1.1rem;
            font-weight: 600;
            margin-bottom: 1rem;
        }}

        .screenshot-gallery {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
            gap: 1rem;
        }}

        .screenshot-item {{
            border: 1px solid var(--border);
            border-radius: 8px;
            overflow: hidden;
            background: var(--surface);
            cursor: pointer;
            transition: transform 0.2s, box-shadow 0.2s;
        }}

        .screenshot-item:hover {{
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0,0,0,0.1);
        }}

        .screenshot-item img {{
            width: 100%;
            height: 180px;
            object-fit: cover;
            display: block;
        }}

        /* Lightbox modal */
        .lightbox {{
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.9);
            z-index: 1000;
            justify-content: center;
            align-items: center;
        }}
        .lightbox.active {{
            display: flex;
        }}
        .lightbox img {{
            max-width: 95%;
            max-height: 95%;
            object-fit: contain;
            border-radius: 8px;
        }}
        .lightbox-close {{
            position: absolute;
            top: 20px;
            right: 30px;
            color: white;
            font-size: 40px;
            cursor: pointer;
        }}

        .screenshot-caption {{
            padding: 0.75rem;
            font-size: 0.8rem;
        }}

        .screenshot-caption .time {{
            display: block;
            color: var(--text-muted);
            font-size: 0.75rem;
        }}

        .screenshot-caption .title {{
            display: block;
            font-weight: 500;
            margin-top: 0.25rem;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }}

        /* Footer */
        .footer {{
            margin-top: 3rem;
            padding-top: 1.5rem;
            border-top: 1px solid var(--border);
            text-align: center;
            color: var(--text-muted);
            font-size: 0.8rem;
        }}

        /* Print styles */
        @media print {{
            body {{ font-size: 11px; }}
            .container {{ max-width: 100%; padding: 0; }}
            .stat-card, .section, .app-usage, .hourly-chart {{
                break-inside: avoid;
                page-break-inside: avoid;
            }}
            .screenshot-gallery {{
                grid-template-columns: repeat(3, 1fr);
            }}
            .screenshot-item img {{
                height: 120px;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>{data.get('title', 'Activity Report')}</h1>
            <p class="meta">Generated: {generated_at}</p>
        </div>

        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-value">{total_mins // 60}h {total_mins % 60}m</div>
                <div class="stat-label">Active Time</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{analytics.get('total_sessions', 0)}</div>
                <div class="stat-label">Sessions</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{len(top_apps)}</div>
                <div class="stat-label">Applications</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{len(data.get('sections', []))}</div>
                <div class="stat-label">Days Tracked</div>
            </div>
        </div>

        <div class="summary-section">
            <h2>Executive Summary</h2>
            {exec_summary_html}
        </div>

        <div class="app-usage">
            <h2>Application Usage</h2>
            {app_bars_html}
        </div>

        <div class="hourly-chart">
            <h2>Activity by Hour</h2>
            <div class="hour-bars">
                {hourly_bars_html}
            </div>
        </div>

        <div class="daily-breakdown">
            <h2>Daily Breakdown</h2>
            {sections_html}
        </div>

        <div class="screenshots">
            <h2>Key Screenshots</h2>
            {screenshots_html if screenshot_embeds else '<p style="color: var(--text-muted);">No screenshots available.</p>'}
        </div>

        <div class="footer">
            <p>Activity Report • Generated by Activity Tracker</p>
        </div>
    </div>

    <!-- Lightbox modal for screenshots -->
    <div class="lightbox" id="lightbox" onclick="closeLightbox()">
        <span class="lightbox-close">&times;</span>
        <img id="lightbox-img" src="" alt="Screenshot">
    </div>

    <script>
        function openLightbox(src) {{
            document.getElementById('lightbox-img').src = src;
            document.getElementById('lightbox').classList.add('active');
        }}
        function closeLightbox() {{
            document.getElementById('lightbox').classList.remove('active');
        }}
        document.addEventListener('keydown', function(e) {{
            if (e.key === 'Escape') closeLightbox();
        }});
    </script>
</body>
</html>"""

        path = self.output_dir / filename
        path.write_text(html)
        logger.info(f"Exported HTML report to {path}")
        return path

    def _export_pdf_from_dict(self, data: Dict[str, Any], filename: str) -> Path:
        """Export to PDF from dict data using weasyprint."""
        # First generate HTML
        html_filename = filename.replace('.pdf', '_temp.html')
        html_path = self._export_html_from_dict(data, html_filename)
        pdf_path = self.output_dir / filename

        from weasyprint import HTML
        HTML(str(html_path)).write_pdf(str(pdf_path))
        html_path.unlink()  # Clean up temp HTML
        logger.info(f"Exported PDF report to {pdf_path}")
        return pdf_path

    def _export_json_from_dict(self, data: Dict[str, Any], filename: str) -> Path:
        """Export report data as JSON (already in dict format)."""
        path = self.output_dir / filename
        path.write_text(json.dumps(data, indent=2))
        logger.info(f"Exported JSON report to {path}")
        return path
