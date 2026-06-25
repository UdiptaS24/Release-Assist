import os
import json
import typer
import httpx
from rich.console import Console
from rich.table import Table
from rich.markdown import Markdown
from dotenv import load_dotenv
from datetime import timedelta
from dateutil import parser as date_parser

load_dotenv()

app = typer.Typer(help="Release Assist MVP CLI", add_completion=False)
console = Console()

API_URL = os.getenv("RELEASE_API_URL")

# Submit a new release request to the Release Assist MVP.
@app.command()
def submit(
    app_name: str = typer.Option(..., "--app-name", help="Name of the application"),
    version: str = typer.Option(..., "--version", help="Semantic versioning (e.g., 1.0.0)"),
    release_type: str = typer.Option(..., "--release-type", help="Type of release (major, minor, patch, hotfix)"),
    contact_email: str = typer.Option(..., "--email", help="Contact email of the AppDev team"),
    repository_url: str = typer.Option(..., "--repo-url", help="GitHub repository URL"),
    rollback_plan: str = typer.Option(..., "--rollback-plan", help="Brief description of the rollback plan to revert this deployment if it fails")
):
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
    
# List all release requests
@app.command(name="list")
def list_releases():
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
    
# View details of a specific release request by ID
@app.command(name="view")
def view_release(release_id: str = typer.Argument(..., help="ID of the release request to view")):
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

# Schedule a deployment window for an approved release
@app.command(name="schedule")
def schedule_release(
    release_id: str = typer.Argument(..., help="ID of the release request to schedule"),
    requested_start: str = typer.Option(..., "--start", help="Requested deployment start time (e.g. '2026-06-29 11:00' or '29 June 2026 11 AM)"),
    requested_end: str = typer.Option(..., "--end", help="Requested deployment end time (e.g. '2026-06-29 11:00' or '29 June 2026 11 AM)"),
    notify_contacts: list[str] = typer.Option(..., "--notify", help="Email addresses to notify (can be passes multiple times)")
):
    console.print(f"[yellow]Scheduling release [bold]{release_id}[/bold]...[/yellow]")
    try:
        start_dt = date_parser.parse(requested_start, dayfirst=False)
    except Exception:
        console.print(f"[bold red]Could not parse start date: '{requested_start}'[/bold red]")
        raise typer.Exit(code=1)

    try:
        end_dt = date_parser.parse(requested_end, dayfirst=False)
    except Exception:
        console.print(f"[bold red]Could not parse end date: '{requested_end}'[/bold red]")
        raise typer.Exit(code=1)
    
    
    payload = {
        "requested_start": start_dt.isoformat(),
        "requested_end": end_dt.isoformat(),
        "notify_contacts": notify_contacts or [],
    }

    try:
        timeout = httpx.Timeout(connect=10.0, read=600.0, write=600.0, pool=600.0)
        with httpx.Client(timeout=timeout) as client:
            response = client.post(f"{API_URL}/{release_id}/schedule", json=payload)
    except httpx.HTTPError as e:
        console.print(f"[bold red]Failed to schedule deployment: {e}[/bold red]")
        raise typer.Exit(code=1)
    
    if response.status_code != 200:
        detail = response.json().get("detail", "Unknown error")
        console.print(f"[bold red]Error {response.status_code}:[/bold red] [red]{detail}[/red]")
        raise typer.Exit(code=1)

    body = response.json()
    schedule = body.get("schedule", {})
    _render_schedule_result(schedule)



def _render_schedule_result(schedule: dict):
    status = schedule.get("status", "UNKNOWN")
    color_map = {
        "SCHEDULED": "green",
        "SUGGESTED_ALTERNATE": "yellow",
        "BLOCKED": "red",
    }
    color = color_map.get(status, "white")
        
    console.print(f"\n[bold {color}]Schedule status: {status}[/bold {color}]")
    console.print(f"[bold]Reason:[/bold] {schedule.get('reason', '')}")

    requested_start = schedule.get("requested_start")
    requested_end = schedule.get("requested_end")
    scheduled_start = schedule.get("scheduled_start")
    scheduled_end = schedule.get("scheduled_end")

    table = Table(title="Deployment Window", show_lines=False)
    table.add_column("Field", style="cyan", no_wrap=True)
    table.add_column("Value", style="magenta")

    table.add_row("Requested Start", requested_start or "-")
    table.add_row("Requested End", requested_end or "-")
    table.add_row("Scheduled Start", scheduled_start or "-")
    table.add_row("Scheduled End", scheduled_end or "-")

    console.print(table)

    conflicts = schedule.get("conflicts", [])
    if conflicts:
        console.print("\n[bold red]Conflicts detected:[/bold red]")
        for conflict in conflicts:
            name = conflict.get("name", conflict.get("type", "Unknown"))
            reason = conflict.get("reason", "")
            console.print(f"  - [bold]{name}[/bold]: {reason}")

    contacts = schedule.get("notified_contacts", [])
    if contacts:
        console.print("\n[bold cyan]Notified contacts:[/bold cyan]")
        for c in contacts:
            console.print(f"  - {c}")

if __name__ == "__main__":
    app()