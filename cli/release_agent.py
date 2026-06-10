import typer
import httpx
from rich.console import Console
from rich.table import Table

app = typer.Typer(help="Release Assist MVP CLI", add_completion=False)
console = Console()

API_URL = "http://127.0.0.1:8000/releases"

@app.command()
def submit(
    app_name: str = typer.Option(..., "--app-name", help="Name of the application"),
    version: str = typer.Option(..., "--version", help="Semantic versioning (e.g., 1.0.0)"),
    release_type: str = typer.Option(..., "--release-type", help="Type of release (major, minor, patch, hotfix)"),
    contact_email: str = typer.Option(..., "--email", help="Contact email of the AppDev team"),
    repository_url: str = typer.Option(..., "--repo-url", help="GitHub repository URL")
):
    """Submit a new release request to the Release Assist MVP."""
    payload = {
        "app_name": app_name,
        "version": version,
        "release_type": release_type,
        "contact_email": contact_email,
        "repository_url": repository_url
    }
    console.print(f"[yellow]Submitting release request for [bold]{app_name}[/bold] version [bold]{version}[/bold]...[/yellow]")
    try:
        with httpx.Client() as client:
            response = client.post(API_URL, json=payload)
        if response.status_code == 201:
            data = response.json()["data"]
            console.print(f"[bold green]Release request submitted successfully![/bold green]")
            console.print(data)
        else:
            detail = response.json().get("detail", "Unknown error")
            console.print(f"[bold red]Error {response.status_code}: {detail}[/bold red]")
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
            console.print(f"[bold red]Error {response.status_code}: {detail}[/bold red]")
            raise typer.Exit(code=1)
    except httpx.HTTPError as e:
        console.print(f"[bold red]Failed to fetch release requests: {e}[/bold red]")
        raise typer.Exit(code=1)
    
if __name__ == "__main__":
    app()