# Copyright © 2021-2025 Technology Matters
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see https://www.gnu.org/licenses/.

from django.http import HttpResponse


def invalid_token_page():
    """Generate HTML page for invalid/expired export token."""
    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Invalid Export Link</title>

        <!-- Material Icons -->
        <link href="https://fonts.googleapis.com/icon?family=Material+Icons" rel="stylesheet">

        <style>
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
                max-width: 600px;
                margin: 50px auto;
                padding: 20px;
                background-color: #f5f5f5;
            }
            .container {
                background-color: white;
                border-radius: 8px;
                padding: 40px;
                text-align: center;
            }
            .logo {
                width: 120px;
                height: 120px;
                margin: 0 auto 20px;
                display: block;
            }
            .error-icon {
                font-size: 64px;
                color: #dc3545;
                margin: 20px 0;
                display: block;
            }
            h1 {
                color: #333;
                margin: 20px 0;
                font-size: 24px;
            }
            p {
                color: #666;
                line-height: 1.6;
                margin: 15px 0;
            }
            .info-box {
                background-color: #fff3cd;
                border-left: 4px solid #ffc107;
                padding: 15px;
                margin: 20px 0;
                text-align: left;
            }
            .info-box strong {
                color: #856404;
            }
            .material-icons {
                vertical-align: middle;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <img src="/static/export/landpks-round.png" alt="LandPKS Logo" class="logo">
            <span class="material-icons error-icon">link_off</span>
            <h1>Export Link No Longer Valid</h1>
            <p>This export link has been reset or expired and is no longer valid.</p>

            <div class="info-box">
                <strong>To get a new export link:</strong>
                <ol style="margin: 10px 0; padding-left: 20px;">
                    <li>Open the LandPKS mobile app</li>
                    <li>Navigate to your project or site</li>
                    <li>Generate a new export link</li>
                </ol>
            </div>

            <p style="font-size: 14px; color: #999; margin-top: 30px;">
                Export links can be reset at any time from the mobile app for security purposes.
            </p>
        </div>
    </body>
    </html>
    """
    return HttpResponse(html_content, content_type="text/html", status=404)


def export_page_html(name, resource_type, csv_url, json_url, request=None):
    """
    Generate HTML page for export with download links.

    Args:
        name: Display name for the export
        resource_type: Type of resource (project, site, user_all, user_owned)
        csv_url: URL for CSV download
        json_url: URL for JSON download
        request: Django request object (optional, for building absolute URLs)
    """
    resource_type_labels = {
        "project": "Project Sites",
        "site": "Single Site",
        "user_all": "All User's Sites (Projects + Unaffiliated)",
        "user_owned": "Owned Sites Only",
    }

    type_label = resource_type_labels.get(resource_type, "Sites")

    # Build absolute URLs for OpenGraph metadata
    if request:
        image_url = request.build_absolute_uri("/static/export/landpks-round.png")
        page_url = request.build_absolute_uri()
    else:
        image_url = "/static/export/landpks-round.png"
        page_url = ""

    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Export Download - {name}</title>

        <!-- Material Icons -->
        <link href="https://fonts.googleapis.com/icon?family=Material+Icons" rel="stylesheet">

        <!-- OpenGraph metadata for link previews -->
        <meta property="og:title" content="LandPKS Export: {name}" />
        <meta property="og:description" content="{type_label} - Download your LandPKS data export in CSV or JSON format" />
        <meta property="og:type" content="website" />
        <meta property="og:url" content="{page_url}" />
        <meta property="og:site_name" content="Terraso LandPKS" />
        <meta property="og:locale" content="en_US" />
        <meta property="og:image" content="{image_url}" />
        <meta property="og:image:width" content="1024" />
        <meta property="og:image:height" content="1024" />
        <meta property="og:image:alt" content="LandPKS Logo - Landscape and soil data platform" />

        <!-- Twitter Card metadata -->
        <meta name="twitter:card" content="summary_large_image" />
        <meta name="twitter:title" content="LandPKS Export: {name}" />
        <meta name="twitter:description" content="{type_label} - Download your LandPKS data export in CSV or JSON format" />
        <meta name="twitter:image" content="{image_url}" />
        <meta name="twitter:image:alt" content="LandPKS Logo - Landscape and soil data platform" />

        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
                max-width: 600px;
                margin: 50px auto;
                padding: 20px;
                background-color: #f5f5f5;
            }}
            .container {{
                background-color: white;
                border-radius: 8px;
                padding: 40px;
                text-align: center;
            }}
            .logo {{
                width: 120px;
                height: 120px;
                margin: 0 auto 20px;
            }}
            h1 {{
                color: #333;
                margin-top: 0;
                font-size: 24px;
            }}
            p {{
                color: #666;
                line-height: 1.6;
            }}
            .download-row {{
                display: flex;
                align-items: center;
                gap: 10px;
                margin: 10px 0;
            }}
            .download-link {{
                flex: 1;
                background-color: #028843;
                color: white;
                padding: 0 24px;
                text-decoration: none;
                border-radius: 4px;
                font-weight: 500;
                text-align: center;
                display: flex;
                align-items: center;
                justify-content: center;
                gap: 6px;
                height: 48px;
            }}
            .download-link:hover {{
                background-color: #026E38;
            }}
            .copy-button {{
                display: inline-flex;
                align-items: center;
                justify-content: center;
                gap: 6px;
                background-color: #6c757d;
                color: white;
                padding: 0 16px;
                border: none;
                border-radius: 4px;
                cursor: pointer;
                font-weight: 500;
                font-size: 14px;
                white-space: nowrap;
                width: 135px;
                height: 48px;
            }}
            .copy-button:hover {{
                background-color: #5a6268;
            }}
            .copy-button.copied {{
                background-color: #5a6268;
            }}
            .info {{
                background-color: #f8f9fa;
                padding: 15px;
                border-radius: 4px;
                margin-top: 20px;
                text-align: left;
            }}
            .info-label {{
                font-weight: 600;
                color: #333;
            }}
            .info-value {{
                color: #666;
            }}
            .download-section {{
                margin-top: 30px;
            }}
            .material-icons {{
                font-size: 18px;
                vertical-align: middle;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <img src="/static/export/landpks-round.png" alt="LandPKS Logo" class="logo">
            <h1>LandPKS Soil ID Data Export</h1>
            <p>Exports will always contain up-to-date data. Export links will be valid until reset in the mobile app.</p>

            <div class="info">
                <div style="margin-bottom: 10px;">
                    <span class="info-label">Export name:</span>
                    <span class="info-value">{name}</span>
                </div>
                <div>
                    <span class="info-label">Export type:</span>
                    <span class="info-value">{type_label}</span>
                </div>
            </div>

            <div class="download-section">
                <div class="download-row">
                    <a href="{csv_url}" class="download-link" download>
                        <span class="material-icons">file_download</span>
                        Download CSV
                    </a>
                    <button class="copy-button" onclick="copyLink('{csv_url}', this)">
                        <span class="material-icons">share</span>
                        <span class="copy-text">Copy Link</span>
                    </button>
                </div>
                <div class="download-row">
                    <a href="{json_url}" class="download-link" download>
                        <span class="material-icons">file_download</span>
                        Download JSON
                    </a>
                    <button class="copy-button" onclick="copyLink('{json_url}', this)">
                        <span class="material-icons">share</span>
                        <span class="copy-text">Copy Link</span>
                    </button>
                </div>
            </div>

        </div>

        <script>
            function copyLink(relativeUrl, button) {{
                // Build absolute URL from relative path
                const baseUrl = window.location.origin;
                const absoluteUrl = baseUrl + relativeUrl;

                // Try modern clipboard API first, fallback to older method
                if (navigator.clipboard && navigator.clipboard.writeText) {{
                    navigator.clipboard.writeText(absoluteUrl).then(() => {{
                        showCopiedFeedback(button);
                    }}).catch(err => {{
                        console.log('Clipboard API failed, using fallback:', err);
                        fallbackCopy(absoluteUrl, button);
                    }});
                }} else {{
                    fallbackCopy(absoluteUrl, button);
                }}
            }}

            function fallbackCopy(text, button) {{
                // Fallback method that works without HTTPS
                const textArea = document.createElement('textarea');
                textArea.value = text;
                textArea.style.position = 'fixed';
                textArea.style.left = '-999999px';
                textArea.style.top = '-999999px';
                document.body.appendChild(textArea);
                textArea.focus();
                textArea.select();

                try {{
                    const successful = document.execCommand('copy');
                    if (successful) {{
                        showCopiedFeedback(button);
                    }} else {{
                        alert('Failed to copy link');
                    }}
                }} catch (err) {{
                    console.error('Fallback copy failed:', err);
                    alert('Failed to copy link');
                }} finally {{
                    document.body.removeChild(textArea);
                }}
            }}

            function showCopiedFeedback(button) {{
                const textSpan = button.querySelector('.copy-text');
                button.classList.add('copied');
                textSpan.textContent = 'Copied!';
                setTimeout(() => {{
                    button.classList.remove('copied');
                    textSpan.textContent = 'Copy Link';
                }}, 2000);
            }}
        </script>
    </body>
    </html>
    """

    return HttpResponse(html_content, content_type="text/html")
