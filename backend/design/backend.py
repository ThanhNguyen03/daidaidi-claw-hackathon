# Design Backend Interface
# =======================
# Swappable interface for design/wireframe generation.
# Supports: HTML low-fi fallback, Figma export, FigJam via MCP.

from abc import ABC, abstractmethod
from typing import Optional
import os


class DesignBackend(ABC):
    """Abstract base class for design backends."""

    @abstractmethod
    async def generate_wireframe(
        self,
        requirements: dict,
        output_format: str = "html"
    ) -> dict:
        """
        Generate a wireframe from requirements.

        Args:
            requirements: Dict with design requirements
            output_format: Output format (html, figjam, png, svg)

        Returns:
            dict with status, preview/data, and metadata
        """
        pass

    @abstractmethod
    async def export_design(
        self,
        design_id: str,
        format: str = "png"
    ) -> dict:
        """
        Export a design to a specific format.

        Args:
            design_id: ID of the design to export
            format: Export format (png, svg, pdf)

        Returns:
            dict with status and file data/path
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if this backend is available (configured)."""
        pass

    @property
    @abstractmethod
    def backend_name(self) -> str:
        """Return the name of this backend."""
        pass


class HTMLLowFiBackend(DesignBackend):
    """HTML low-fi wireframe fallback - no external dependencies."""

    def __init__(self):
        self._available = True

    async def generate_wireframe(
        self,
        requirements: dict,
        output_format: str = "html"
    ) -> dict:
        """Generate a simple HTML wireframe."""

        # Extract key elements from requirements
        page_type = requirements.get("page_type", "landing")
        sections = requirements.get("sections", ["header", "content", "footer"])
        brand_name = requirements.get("brand_name", "Brand")
        primary_color = requirements.get("primary_color", "#3b82f6")

        # Generate HTML wireframe
        html = self._generate_html_wireframe(
            page_type=page_type,
            sections=sections,
            brand_name=brand_name,
            primary_color=primary_color
        )

        return {
            "status": "success",
            "format": "html",
            "content": html,
            "preview": self._generate_text_preview(requirements),
            "wireframe_type": "low-fi",
            "backend": self.backend_name
        }

    async def export_design(
        self,
        design_id: str,
        format: str = "png"
    ) -> dict:
        """Export not supported for HTML backend."""
        return {
            "status": "error",
            "error": "Export not supported for HTML low-fi backend"
        }

    def is_available(self) -> bool:
        return self._available

    @property
    def backend_name(self) -> str:
        return "html_lowfi"

    def _generate_html_wireframe(
        self,
        page_type: str,
        sections: list,
        brand_name: str,
        primary_color: str
    ) -> str:
        """Generate a simple HTML wireframe."""

        section_html = ""
        for section in sections:
            section_html += f"""
    <div class="section section-{section}">
        <div class="placeholder">{section.upper()}</div>
    </div>
"""

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{brand_name} - {page_type.title()} Wireframe</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: system-ui, sans-serif; line-height: 1.6; }}
        .container {{ max-width: 1200px; margin: 0 auto; padding: 20px; }}
        .header {{ background: {primary_color}; color: white; padding: 20px; text-align: center; }}
        .section {{ padding: 40px 20px; border-bottom: 1px dashed #ccc; }}
        .placeholder {{ background: #f3f4f6; border: 2px dashed #9ca3af; padding: 60px; text-align: center; color: #6b7280; font-size: 18px; }}
        .footer {{ background: #1f2937; color: white; padding: 20px; text-align: center; }}
        .wireframe-label {{ position: fixed; bottom: 10px; right: 10px; background: #ef4444; color: white; padding: 5px 10px; font-size: 12px; border-radius: 4px; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>{brand_name}</h1>
        <p>{page_type.title()} Page</p>
    </div>
    <div class="container">
{section_html}
    </div>
    <div class="footer">
        <p>&copy; 2024 {brand_name}</p>
    </div>
    <div class="wireframe-label">LOW-FI WIREFRAME</div>
</body>
</html>"""

        return html

    def _generate_text_preview(self, requirements: dict) -> str:
        """Generate text preview of the wireframe."""
        sections = requirements.get("sections", [])
        return f"""
=== WIREFRAME PREVIEW ===

Page Type: {requirements.get('page_type', 'landing').title()}
Brand: {requirements.get('brand_name', 'Brand')}
Sections: {', '.join(sections) if sections else 'Default'}

This is a simple HTML wireframe that can be viewed in any browser.
"""


class FigmaExportBackend(DesignBackend):
    """Figma export backend using PAT/REST API (read-only)."""

    def __init__(self, access_token: Optional[str] = None, file_key: Optional[str] = None):
        """
        Initialize Figma export backend.

        Args:
            access_token: Figma access token (PAT)
            file_key: Figma file key to export from
        """
        self.access_token = access_token or os.getenv("FIGMA_ACCESS_TOKEN")
        self.file_key = file_key or os.getenv("FIGMA_FILE_KEY")
        self.base_url = "https://api.figma.com/v1"

    async def generate_wireframe(
        self,
        requirements: dict,
        output_format: str = "figma"
    ) -> dict:
        """Generate wireframe by exporting from Figma template."""

        if not self.is_available():
            return {
                "status": "error",
                "error": "Figma backend not available. Set FIGMA_ACCESS_TOKEN and FIGMA_FILE_KEY"
            }

        # For now, return a placeholder that explains the Figma flow
        # Real implementation would use the Figma MCP or REST API
        return {
            "status": "success",
            "format": "figma",
            "message": "Figma export initiated",
            "file_key": self.file_key,
            "requirements": requirements,
            "preview": f"Would export frame from Figma file {self.file_key}",
            "backend": self.backend_name,
            "note": "Use FigJam MCP for generative wireframes"
        }

    async def export_design(
        self,
        design_id: str,
        format: str = "png"
    ) -> dict:
        """Export design from Figma using REST API."""

        if not self.is_available():
            return {
                "status": "error",
                "error": "Figma backend not available"
            }

        try:
            import requests

            # Get file info
            headers = {"X-Figma-Token": self.access_token}
            response = requests.get(
                f"{self.base_url}/files/{self.file_key}",
                headers=headers
            )

            if response.status_code != 200:
                return {
                    "status": "error",
                    "error": f"Figma API error: {response.status_code}"
                }

            # Get image export URL
            response = requests.get(
                f"{self.base_url}/images/{self.file_key}",
                params={"ids": design_id, "format": format},
                headers=headers
            )

            if response.status_code == 200:
                data = response.json()
                return {
                    "status": "success",
                    "images": data.get("images", {}),
                    "format": format
                }

            return {
                "status": "error",
                "error": f"Export failed: {response.status_code}"
            }

        except ImportError:
            return {
                "status": "error",
                "error": "requests library required for Figma export"
            }

    def is_available(self) -> bool:
        return bool(self.access_token and self.file_key)

    @property
    def backend_name(self) -> str:
        return "figma_export"


class FigJamMCPBackend(DesignBackend):
    """FigJam wireframe generation via MCP (generative)."""

    def __init__(self, mcp_config: Optional[dict] = None):
        """
        Initialize FigJam MCP backend.

        Args:
            mcp_config: Optional MCP configuration dict. If provided with valid
                       settings, backend is available. Otherwise checks env vars.
        """
        self.mcp_config = mcp_config or {}
        # Check if MCP is actually configured - must have explicit config
        # to be available (no auto-fallback to stub)
        self._available = self._check_mcp_configured()

    def _check_mcp_configured(self) -> bool:
        """Check if FigJam MCP is configured."""
        # Must have explicit MCP config in constructor or env vars
        if self.mcp_config and self.mcp_config.get("server_url"):
            return True
        # Also check for common MCP env vars
        if os.getenv("FIGJAM_MCP_SERVER"):
            return True
        return False

    async def generate_wireframe(
        self,
        requirements: dict,
        output_format: str = "figjam"
    ) -> dict:
        """Generate FigJam wireframe via MCP."""

        # Extract design elements
        elements = requirements.get("elements", [])
        layout = requirements.get("layout", "vertical")

        # For now, return instructions for MCP-based generation
        # Real implementation would call the Figma MCP use_figma tool
        return {
            "status": "success",
            "format": "figjam",
            "message": "FigJam wireframe generation via MCP",
            "requirements": requirements,
            "elements": elements,
            "layout": layout,
            "preview": f"Would create FigJam board with {len(elements)} elements",
            "backend": self.backend_name,
            "mcp_required": True
        }

    async def export_design(
        self,
        design_id: str,
        format: str = "png"
    ) -> dict:
        """Export from FigJam."""
        return {
            "status": "error",
            "error": "Export via FigJam MCP not yet implemented"
        }

    def is_available(self) -> bool:
        return self._available

    @property
    def backend_name(self) -> str:
        return "figjam_mcp"


def create_design_backend(backend_type: Optional[str] = None) -> DesignBackend:
    """
    Create a design backend based on configuration.

    Args:
        backend_type: Override backend type. If None, auto-detect:
            - "figma_export" if FIGMA_ACCESS_TOKEN is set
            - "figjam_mcp" if FigJam MCP is configured
            - "html_lowfi" as fallback

    Returns:
        DesignBackend implementation
    """
    if backend_type == "html_lowfi":
        return HTMLLowFiBackend()
    elif backend_type == "figma_export":
        return FigmaExportBackend()
    elif backend_type == "figjam_mcp":
        return FigJamMCPBackend()
    elif backend_type is None:
        # Auto-detect best available backend
        if os.getenv("FIGMA_ACCESS_TOKEN"):
            return FigmaExportBackend()
        # Could check for MCP config here
        return HTMLLowFiBackend()
    else:
        # Default fallback
        return HTMLLowFiBackend()


def get_available_backends() -> list[DesignBackend]:
    """Get list of all available design backends."""
    backends = [
        HTMLLowFiBackend(),
        FigmaExportBackend(),
        FigJamMCPBackend()
    ]
    return [b for b in backends if b.is_available()]


def get_default_backend() -> DesignBackend:
    """Get the default design backend (best available)."""
    available = get_available_backends()
    if available:
        # Prefer Figma > FigJam > HTML
        for backend in [FigmaExportBackend, FigJamMCPBackend, HTMLLowFiBackend]:
            for b in available:
                if isinstance(b, backend):
                    return b
    return HTMLLowFiBackend()