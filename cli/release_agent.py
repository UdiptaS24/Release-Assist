import os
import json
import typer
import httpx
from rich.console import Console
from rich.table import Table
from rich.markdown import Markdown
from dotenv import load_dotenv

load_dotenv()

app = typer.Typer(help="Release Assist MVP CLI", add_completion=False)
console = Console()

API_URL = os.getenv("RELEASE_API_URL")

@app.command()
def submit(
    app_name: str = typer.Option(..., "--app-name", help="Name of the application"),
    version: str = typer.Option(..., "--version", help="Semantic versioning (e.g., 1.0.0)"),
    release_type: str = typer.Option(..., "--release-type", help="Type of release (major, minor, patch, hotfix)"),
    contact_email: str = typer.Option(..., "--email", help="Contact email of the AppDev team"),
    repository_url: str = typer.Option(..., "--repo-url", help="GitHub repository URL"),
    rollback_plan: str = typer.Option(..., "--rollback-plan", help="Brief description of the rollback plan to revert this deployment if it fails")
):
    """Submit a new release request to the Release Assist MVP."""
    payload = {
        "app_name": app_name,
        "version": version,
        "release_type": release_type,
        "contact_email": contact_email,
        "repository_url": repository_url,
        "rollback_plan": rollback_plan
    }
    console.print(f"[yellow]Submitting release request for [bold]{app_name}[/bold] version [bold]{version}[/bold]...[/yellow]")
    try:
        timeout = httpx.Timeout(connect=10.0, read=600.0, write=600.0, pool=600.0
        )
        with console.status("[bold cyan]Cloning and analyzing the repository...[/bold cyan]", spinner="dots"):
            with httpx.Client(timeout=timeout) as client:
                response = client.post(API_URL, json=payload, timeout=timeout)
        if response.status_code == 201:
            data_summary = response.json()["summary"]
            risk_report = response.json()["data"]["validation_report"].get("risk_report", {})
            assessment = risk_report.get("assessment", {})
            console.print(f"[bold green]Release request submitted successfully![/bold green]")
            console.print(Markdown(data_summary))
            if assessment:
                rec = assessment.get("recommendation", "UNKNOWN")
                color_map = {"GO": "green", "GO_WITH_CAUTION": "yellow", "NO_GO": "red"}
                color = color_map.get(rec, "white")
                source = risk_report.get("source", "unknown")

                console.print(f"\n[bold {color}]Recommendation: {rec}[/bold {color}]\n"
                            f"[dim]source: {source}, confidence: {assessment.get('confidence', 'N/A')}[/dim]")
                console.print(Markdown(f"**Summary:** {assessment.get('summary', '')}"))

                if assessment.get("top_risks"):
                    console.print("\n[bold]Top Risks:[/bold]")
                    for i, r in enumerate(assessment["top_risks"], 1):
                        sev_color = {"CRITICAL": "red", "HIGH": "red", "MEDIUM": "yellow", "LOW": "blue"}.get(r["severity"], "white")
                        console.print(
                            f"  {i}. [bold {sev_color}][{r['severity']}][/bold {sev_color}] [bold]{r['title']}[/bold]\n"
                            f"     [dim]{r.get('description', '')}[/dim]\n"
                            f"     [green]→ {r['suggested_fix']}[/green]"
                        )
                if assessment.get("positive_signals"):
                    console.print("\n[bold green]Positive signals:[/bold green]")
                    for s in assessment["positive_signals"]:
                        console.print(f"  • {s}")              
        else:
            detail = response.json().get("detail", "Unknown error")
            console.print(f"[bold red]Error {response.status_code}:[/bold red] [red]{detail}[/red]")
            raise typer.Exit(code=1)
    except httpx.TimeoutException as e:
        console.print(f"[bold red]Request timed out while submitting the release request: {e}[/bold red]")
        raise typer.Exit(code=1)
    except httpx.HTTPError as e:
        console.print(f"[bold red]Failed to submit release request: {e}[/bold red]")
        raise typer.Exit(code=1)
    
@app.command(name="list")
def list_releases():
    """List all release requests."""
    console.print("[yellow]Fetching all release requests...[/yellow]")
    try:
        with httpx.Client() as client:
            response = client.get(API_URL)
        if response.status_code == 200:
            releases = response.json()
            if releases:
                table = Table(title="Release Requests")
                table.add_column("ID", style="cyan", no_wrap=True)
                table.add_column("App Name", style="magenta")
                table.add_column("Version", style="green")
                table.add_column("Release Type", style="yellow")
                table.add_column("Status", style="blue")
                table.add_column("Created At", style="dim")
                for release in releases:
                    table.add_row(
                        release["id"],
                        release["app_name"],
                        release["version"],
                        release["release_type"],
                        release["status"],
                        release["created_at"][:19]
                    )
                console.print(table)
            else:
                console.print("[bold yellow]No release requests found.[/bold yellow]")
        else:
            detail = response.json().get("detail", "Unknown error")
            console.print(f"[bold red]Error {response.status_code}:[/bold red] [red]{detail}[/red]")
            raise typer.Exit(code=1)
    except httpx.HTTPError as e:
        console.print(f"[bold red]Failed to fetch release requests: {e}[/bold red]")
        raise typer.Exit(code=1)
    
@app.command(name="view")
def view_release(release_id: str = typer.Argument(..., help="ID of the release request to view")):
    """View details of a specific release request by ID."""
    console.print(f"[yellow]Fetching details for release ID: [bold]{release_id}[/bold]...[/yellow]")
    try:
        with httpx.Client() as client:
            response = client.get(f"{API_URL}/{release_id}")
        if response.status_code == 200:
            data_summary = response.json()["summary"]
            quality_check_report = response.json()["data"]["validation_report"]["quality_check"]
            console.print(Markdown(data_summary))
            console.print(Markdown("# Quality Check Report"))
            console.print(json.dumps(quality_check_report, indent=2))
        else:
            detail = response.json().get("detail", "Unknown error")
            console.print(f"[bold red]Error {response.status_code}:[/bold red] [red]{detail}[/red]")
            raise typer.Exit(code=1)
    except httpx.HTTPError as e:
        console.print(f"[bold red]Failed to fetch release details: {e}[/bold red]")
        raise typer.Exit(code=1)
    
if __name__ == "__main__":
    app()